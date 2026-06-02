from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from agent.models import AssetCard, AssetIndex, DeliveryPreparation, DeliveryStageItem, KnowledgeLevel
from agent.settings import AppPaths
from agent.utils import ensure_directory, slugify


class LocalFileAdapter:
    TRACKED_EXTENSIONS = {".psd", ".psb", ".png", ".jpg", ".jpeg", ".webp", ".gif"}

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def ensure_runtime_directories(self) -> None:
        for path in (
            self.paths.memory / "projects",
            self.paths.memory / "style_bases",
            self.paths.memory / "reviews",
            self.paths.memory / "sessions",
            self.paths.memory / "audits",
            self.paths.memory / "session-transition",
            self.paths.memory / "style_references",
            self.paths.workspace,
            self.paths.root / "workspace" / "deliveries",
            self.paths.templates,
        ):
            ensure_directory(path)

    def prepare_run_directory(self, project_key: str, work_item_id: str, title: str) -> Path:
        project_slug = slugify(project_key, fallback="project")
        item_slug = slugify(title, fallback=work_item_id)
        run_dir = self.paths.workspace / project_slug / f"{work_item_id}-{item_slug}"
        ensure_directory(run_dir)
        return run_dir

    def scan_assets(self, project_key: str, asset_root: Path) -> AssetIndex:
        root = asset_root.resolve()
        cards: list[AssetCard] = []
        warnings: list[str] = []
        seen_names: dict[str, list[str]] = {}

        if not root.exists():
            raise FileNotFoundError(f"Asset root does not exist: {root}")

        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self.TRACKED_EXTENSIONS:
                continue
            relative_path = str(path.relative_to(root))
            role_guess = self._guess_role(path)
            tags = self._guess_tags(path)
            notes: list[str] = []
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and "final" not in path.stem.lower():
                notes.append("可能不是最终导出图，请确认是否需要进入正式交付包")
            seen_names.setdefault(path.name.lower(), []).append(relative_path)
            cards.append(
                AssetCard(
                    project_key=project_key,
                    source_root=str(root),
                    relative_path=relative_path,
                    file_name=path.name,
                    extension=path.suffix.lower(),
                    role_guess=role_guess,
                    tags=tags,
                    size_bytes=path.stat().st_size,
                    modified_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                    level=KnowledgeLevel.K4,
                    notes=notes,
                )
            )

        duplicate_names = [name for name, items in seen_names.items() if len(items) > 1]
        if duplicate_names:
            warnings.append(f"发现重复文件名，交付前建议统一命名：{', '.join(sorted(duplicate_names))}")
        if cards and not any(card.extension in {".psd", ".psb"} for card in cards):
            warnings.append("当前目录未发现 PSD/PSB 源文件，若需要源文件交付请补充检查")
        if not cards:
            warnings.append("未扫描到可跟踪资产文件")

        return AssetIndex(
            project_key=project_key,
            source_root=str(root),
            scanned_at=datetime.now().isoformat(timespec="seconds"),
            asset_cards=cards,
            warnings=warnings,
        )

    def prepare_delivery_package(
        self,
        project_key: str,
        work_item_id: str,
        source_root: Path,
        include_extensions: set[str] | None = None,
    ) -> DeliveryPreparation:
        asset_index = self.scan_assets(project_key, source_root)
        extensions = {ext.lower() for ext in include_extensions} if include_extensions else self.TRACKED_EXTENSIONS
        safe_project = slugify(project_key, fallback="project")
        safe_item = slugify(work_item_id, fallback="item")
        stage_root = ensure_directory(
            self.paths.root / "workspace" / "deliveries" / safe_project / f"{safe_item}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

        staged_files: list[DeliveryStageItem] = []
        warnings = list(asset_index.warnings)
        for card in asset_index.asset_cards:
            if card.extension not in extensions:
                continue
            source_path = Path(card.source_root) / card.relative_path
            target_path = self._unique_target_path(stage_root / card.relative_path)
            ensure_directory(target_path.parent)
            shutil.copy2(source_path, target_path)
            staged_files.append(
                DeliveryStageItem(
                    source_relative_path=card.relative_path,
                    staged_relative_path=str(target_path.relative_to(stage_root)),
                    role_guess=card.role_guess,
                    size_bytes=card.size_bytes,
                    notes=list(card.notes),
                )
            )

        if not staged_files:
            warnings.append("未复制任何文件到交付 staging 目录，请检查扩展名过滤条件")
        if any(item.role_guess == "unknown" for item in staged_files):
            warnings.append("存在未识别用途的文件，建议交付前人工复核")

        checklist = [
            "确认 staged 目录中的文件是本次要交付的版本，而不是过程稿",
            "确认是否需要同时交付 PSD/PSB 源文件与 PNG/JPG 导出图",
            "确认命名、尺寸、语言版本和平台后缀无误后再正式发送",
            "该 staging 目录仅用于预交付检查，系统未覆盖任何正式文件",
        ]

        return DeliveryPreparation(
            project_key=project_key,
            work_item_id=work_item_id,
            source_root=str(source_root.resolve()),
            staged_root=str(stage_root),
            created_at=datetime.now().isoformat(timespec="seconds"),
            files=staged_files,
            warnings=warnings,
            confirmation_checklist=checklist,
        )

    @staticmethod
    def _unique_target_path(target_path: Path) -> Path:
        if not target_path.exists():
            return target_path
        candidate = target_path
        counter = 1
        while candidate.exists():
            candidate = target_path.with_name(f"{target_path.stem}-{counter}{target_path.suffix}")
            counter += 1
        return candidate

    @staticmethod
    def _guess_role(path: Path) -> str:
        lower = path.stem.lower()
        if any(token in lower for token in ("psd", "master", "source")):
            return "source"
        if any(token in lower for token in ("banner", "kv", "poster", "main", "hero")):
            return "key-visual"
        if any(token in lower for token in ("button", "btn", "cta")):
            return "cta"
        if any(token in lower for token in ("icon", "badge", "corner")):
            return "ui-element"
        if any(token in lower for token in ("bg", "background")):
            return "background"
        if any(token in lower for token in ("logo", "title")):
            return "branding"
        return "unknown"

    @staticmethod
    def _guess_tags(path: Path) -> list[str]:
        lower = path.as_posix().lower()
        tags: list[str] = []
        for token in ("final", "draft", "export", "ios", "android", "en", "cn"):
            if token in lower:
                tags.append(token)
        if path.suffix.lower() in {".psd", ".psb"}:
            tags.append("source-file")
        else:
            tags.append("render")
        return tags

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import PsdHandoffPackage, PsdHandoffStageItem
from agent.utils import ensure_directory, slugify


class PsdHandoffPackager:
    def build(
        self,
        plan_payload: dict[str, Any],
        source_plan: str,
        staged_root: Path,
    ) -> PsdHandoffPackage:
        ensure_directory(staged_root)
        items: list[PsdHandoffStageItem] = []
        warnings = list(plan_payload.get("warnings", []))
        for asset in plan_payload.get("assets", []):
            item, item_warnings = self._stage_asset(asset, staged_root)
            items.append(item)
            warnings.extend(item_warnings)

        if not items:
            warnings.append("PSD 交接计划中没有候选资产，staging 包只会包含说明文档。")
        if not any(item.status == "staged" for item in items):
            warnings.append("没有复制任何本地文件；如使用远程 URL，请先人工下载或确认后续工具可访问。")

        return PsdHandoffPackage(
            project_key=str(plan_payload.get("project_key") or "unknown-project"),
            work_item_id=str(plan_payload.get("work_item_id") or "unknown-work-item"),
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_plan=source_plan,
            staged_root=str(staged_root),
            items=items,
            warnings=list(dict.fromkeys(warnings)),
            confirmation_checklist=self._confirmation_checklist(plan_payload),
        )

    @staticmethod
    def render_markdown(package: PsdHandoffPackage) -> str:
        lines = [
            f"# PSD 交接 staging 包 - {package.work_item_id}",
            "",
            f"- 项目：`{package.project_key}`",
            f"- 创建时间：`{package.created_at}`",
            f"- 来源计划：`{package.source_plan}`",
            f"- staging 目录：`{package.staged_root}`",
            "",
            "## 文件与引用",
        ]
        if not package.items:
            lines.append("- 无")
        for item in package.items:
            lines.extend(
                [
                    f"### {item.asset_id}",
                    f"- 方案：`{item.variant_id or 'unknown'}`",
                    f"- 状态：`{item.status}`",
                    f"- 角色：`{item.role}`",
                    f"- 来源：`{item.source_uri}`",
                    f"- staging：`{item.staged_relative_path or '未复制'}`",
                    *(f"- 备注：{note}" for note in item.notes),
                    "",
                ]
            )
        lines.extend(["## 警告", *(f"- {item}" for item in package.warnings or ["无"])])
        lines.extend(["", "## 确认清单", *(f"- [ ] {item}" for item in package.confirmation_checklist)])
        return "\n".join(lines)

    @staticmethod
    def render_approval_ticket(package: PsdHandoffPackage) -> str:
        return "\n".join(
            [
                f"# PSD 交接确认单 - {package.work_item_id}",
                "",
                f"- 项目：`{package.project_key}`",
                f"- staging 目录：`{package.staged_root}`",
                f"- 文件/引用数：`{len(package.items)}`",
                "",
                "## 安全说明",
                "- 当前仅整理 PSD 精修/切图工作包，未覆盖任何正式文件。",
                "- 远程 URL 只登记为引用，不自动下载。",
                "- 对外发送、正式交付或覆盖正式资产前必须再次确认。",
                "",
                "## 需确认项目",
                *(f"- [ ] {item}" for item in package.confirmation_checklist),
                "",
                "## 结果",
                "- [ ] 允许进入 PSD 精修/切图",
                "- [ ] 退回修改候选图或交接计划",
            ]
        )

    def _stage_asset(self, asset: dict[str, Any], staged_root: Path) -> tuple[PsdHandoffStageItem, list[str]]:
        uri = str(asset.get("uri") or "")
        asset_id = str(asset.get("asset_id") or Path(uri).stem or "asset")
        variant_id = str(asset.get("variant_id") or "")
        role = str(asset.get("role") or "psd-reference")
        notes = [str(item) for item in asset.get("slicing_notes", [])]
        warnings: list[str] = []

        if uri.lower().startswith(("http://", "https://")):
            return (
                PsdHandoffStageItem(
                    asset_id=asset_id,
                    variant_id=variant_id,
                    source_uri=uri,
                    staged_relative_path=None,
                    status="external-reference",
                    role=role,
                    notes=notes,
                ),
                warnings,
            )

        source = Path(uri)
        if not source.exists() or not source.is_file():
            warnings.append(f"本地候选资产不存在，未复制：{uri}")
            return (
                PsdHandoffStageItem(
                    asset_id=asset_id,
                    variant_id=variant_id,
                    source_uri=uri,
                    staged_relative_path=None,
                    status="missing-local-file",
                    role=role,
                    notes=notes,
                ),
                warnings,
            )

        target_dir = ensure_directory(staged_root / "references" / slugify(variant_id or "unknown", fallback="variant"))
        target = self._unique_target_path(target_dir / f"{slugify(asset_id, fallback='asset')}{source.suffix.lower()}")
        shutil.copy2(source, target)
        return (
            PsdHandoffStageItem(
                asset_id=asset_id,
                variant_id=variant_id,
                source_uri=uri,
                staged_relative_path=str(target.relative_to(staged_root)),
                status="staged",
                role=role,
                notes=notes,
            ),
            warnings,
        )

    @staticmethod
    def _confirmation_checklist(plan_payload: dict[str, Any]) -> list[str]:
        checklist = [
            "确认 staging 中的候选图是本次要进入 PSD 精修/切图的版本。",
            "确认图层地图、PSD 重建步骤和切图检查清单已阅读。",
            "确认远程引用是否需要人工下载成本地文件。",
            "确认不会覆盖已有正式文件，正式交付前再次人工确认。",
        ]
        checklist.extend(str(item) for item in plan_payload.get("approval_checklist", [])[:4])
        return list(dict.fromkeys(checklist))

    @staticmethod
    def _unique_target_path(target_path: Path) -> Path:
        if not target_path.exists():
            return target_path
        counter = 1
        candidate = target_path
        while candidate.exists():
            candidate = target_path.with_name(f"{target_path.stem}-{counter}{target_path.suffix}")
            counter += 1
        return candidate

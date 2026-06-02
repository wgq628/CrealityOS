from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import GeneratedAssetResult, ImageGenerationResultIndex
from agent.utils import load_json, stringify


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


class ImageGenerationResultRegistrar:
    def load_assets(self, results_file: str, queue_payload: dict | None = None) -> list[GeneratedAssetResult]:
        path = Path(results_file)
        if path.suffix.lower() == ".json":
            payload = load_json(path, {})
            raw_items = payload.get("assets", payload.get("results", [])) if isinstance(payload, dict) else payload
            if not isinstance(raw_items, list):
                raise ValueError("Generation results JSON must contain a list or an assets/results list.")
            return [self._asset_from_mapping(item, queue_payload) for item in raw_items]
        return self._assets_from_text(path.read_text(encoding="utf-8"), queue_payload)

    def build_index(
        self,
        project_key: str,
        work_item_id: str,
        source_queue: str | None,
        assets: list[GeneratedAssetResult],
    ) -> ImageGenerationResultIndex:
        missing = [asset.uri for asset in assets if not asset.exists and asset.kind == "local"]
        delivery_candidates = [
            asset.uri
            for asset in assets
            if asset.exists and asset.kind in {"local", "url"} and any(token in " ".join(asset.notes).lower() for token in ("candidate", "候选", "final", "selected"))
        ]
        if not delivery_candidates:
            delivery_candidates = [asset.uri for asset in assets if asset.exists and asset.kind in {"local", "url"}]
        return ImageGenerationResultIndex(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_queue=source_queue,
            assets=assets,
            missing_assets=missing,
            delivery_candidates=delivery_candidates,
            next_actions=self._next_actions(assets, missing),
        )

    @staticmethod
    def render_gallery(index: ImageGenerationResultIndex) -> str:
        lines = [
            f"# 生成图索引 - {index.work_item_id}",
            "",
            f"- 项目：`{index.project_key}`",
            f"- 创建时间：`{index.created_at}`",
            f"- 来源队列：`{index.source_queue or '未绑定'}`",
            f"- 资产数：`{len(index.assets)}`",
            "",
            "## 资产",
        ]
        if not index.assets:
            lines.append("- 暂无登记资产")
        for asset in index.assets:
            lines.extend(
                [
                    f"### {asset.asset_id}",
                    f"- Job：`{asset.job_id}`",
                    f"- 方案：`{asset.variant_id}`",
                    f"- 类型：`{asset.kind}`",
                    f"- 存在：{'是' if asset.exists else '否'}",
                    f"- 地址：`{asset.uri}`",
                    f"- 尺寸：{asset.width or '未知'} x {asset.height or '未知'}",
                    *(f"- 备注：{note}" for note in asset.notes),
                    "",
                ]
            )
            if asset.exists and asset.kind in {"local", "url"}:
                lines.extend([f"![{asset.asset_id}]({asset.uri})", ""])
        lines.extend(["## 缺失资产", *(f"- `{item}`" for item in index.missing_assets or ["无"])])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in index.next_actions)])
        return "\n".join(lines)

    @staticmethod
    def render_delivery_candidates(index: ImageGenerationResultIndex) -> str:
        lines = [
            f"# 交付候选图清单 - {index.work_item_id}",
            "",
            "## 候选资产",
        ]
        if not index.delivery_candidates:
            lines.append("- 暂无候选资产")
        else:
            lines.extend(f"- [ ] `{item}`" for item in index.delivery_candidates)
        lines.extend(
            [
                "",
                "## 进入 PSD/切图前确认",
                "- [ ] 已完成候选图评审并运行 `ingest-candidate-review` 回写记忆",
                "- [ ] 已确认尺寸、平台、语言版本和命名规则",
                "- [ ] 已确认是否需要 PSD 重建、局部精修或直接切图",
                "- [ ] 正式交付前不会覆盖已有文件",
            ]
        )
        return "\n".join(lines)

    def _asset_from_mapping(self, item: dict[str, Any], queue_payload: dict | None) -> GeneratedAssetResult:
        uri = str(item.get("uri") or item.get("path") or item.get("url") or "").strip()
        if not uri:
            raise ValueError("Every generated asset needs uri/path/url.")
        job_id = str(item.get("job_id") or self._job_id_from_variant(item.get("variant_id"), queue_payload) or "").strip()
        variant_id = str(item.get("variant_id") or self._variant_from_job(job_id) or "").strip().upper()
        asset_id = str(item.get("asset_id") or item.get("id") or self._default_asset_id(job_id, variant_id, uri)).strip()
        kind = self._kind(uri)
        exists = self._exists(uri, kind)
        return GeneratedAssetResult(
            asset_id=asset_id,
            job_id=job_id,
            variant_id=variant_id,
            uri=uri,
            kind=kind,
            exists=exists,
            width=self._optional_int(item.get("width")),
            height=self._optional_int(item.get("height")),
            notes=self._list_field(item.get("notes") or item.get("tags") or item.get("comment")),
        )

    def _assets_from_text(self, content: str, queue_payload: dict | None) -> list[GeneratedAssetResult]:
        assets: list[GeneratedAssetResult] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) == 1:
                parts = ["", parts[0]]
            variant_id = parts[0].upper() if parts[0] else ""
            uri = parts[1] if len(parts) > 1 else ""
            if not uri:
                continue
            job_id = self._job_id_from_variant(variant_id, queue_payload) or ""
            notes = self._list_field(parts[2] if len(parts) > 2 else "")
            assets.append(
                GeneratedAssetResult(
                    asset_id=self._default_asset_id(job_id, variant_id, uri),
                    job_id=job_id,
                    variant_id=variant_id or self._variant_from_job(job_id),
                    uri=uri,
                    kind=self._kind(uri),
                    exists=self._exists(uri, self._kind(uri)),
                    notes=notes,
                )
            )
        if not assets:
            raise ValueError("No generated assets found. Use JSON or lines like: V01 | C:\\path\\draft.png | candidate")
        return assets

    @staticmethod
    def _kind(uri: str) -> str:
        lower = uri.lower()
        if lower.startswith(("http://", "https://")):
            return "url"
        if Path(uri).suffix.lower() in IMAGE_EXTENSIONS:
            return "local"
        return "other"

    @staticmethod
    def _exists(uri: str, kind: str) -> bool:
        if kind == "url":
            return True
        if kind == "local":
            return Path(uri).exists()
        return False

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None and value != "" else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _list_field(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [stringify(item).strip() for item in value if stringify(item).strip()]
        text = stringify(value).strip()
        if not text:
            return []
        for sep in ("\n", "；", ";", ","):
            if sep in text:
                return [item.strip() for item in text.split(sep) if item.strip()]
        return [text]

    @staticmethod
    def _job_id_from_variant(variant_id: Any, queue_payload: dict | None) -> str | None:
        if not variant_id:
            return None
        wanted = str(variant_id).upper()
        for job in (queue_payload or {}).get("jobs", []):
            if str(job.get("variant_id", "")).upper() == wanted:
                return str(job.get("job_id") or "")
        return None

    @staticmethod
    def _variant_from_job(job_id: str) -> str:
        for token in job_id.split("-"):
            if token.upper().startswith("V") and token[1:].isdigit():
                return token.upper()
        return ""

    @staticmethod
    def _default_asset_id(job_id: str, variant_id: str, uri: str) -> str:
        stem = Path(uri).stem if not uri.startswith(("http://", "https://")) else uri.rstrip("/").split("/")[-1].split(".")[0]
        parts = [item for item in (variant_id, stem or "asset") if item]
        if not parts and job_id:
            parts.append(job_id)
        return "_".join(parts)

    @staticmethod
    def _next_actions(assets: list[GeneratedAssetResult], missing: list[str]) -> list[str]:
        actions = [
            "打开 generated_gallery.md 对照生成图，挑选进入候选评审的版本。",
            "把候选图评分和修改意见写入 candidate_review.json，然后运行 ingest-candidate-review。",
            "确认进入精修的资产后，再进入 PSD/切图或交付 staging。",
        ]
        if missing:
            actions.insert(0, "先补齐缺失的本地图片路径，避免评审索引引用失效。")
        if not assets:
            actions = ["先登记至少一张生成结果图片或 URL。"]
        return actions

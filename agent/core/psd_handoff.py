from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.models import CreativePack, PsdHandoffAsset, PsdHandoffPlan


class PsdHandoffPlanner:
    DEFAULT_LAYER_GROUPS = [
        "00_refs",
        "01_background",
        "02_subject",
        "03_effects",
        "04_copy",
        "05_cta",
        "06_ui_slices",
        "99_exports",
    ]

    def build(
        self,
        project_key: str,
        work_item_id: str,
        results_payload: dict[str, Any] | None,
        creative_pack: CreativePack | None,
        selected_assets: list[str] | None = None,
        source_results: str | None = None,
        source_creative_pack: str | None = None,
    ) -> PsdHandoffPlan:
        selected = {item for item in selected_assets or []}
        assets = self._assets(results_payload, selected)
        warnings: list[str] = []
        if not assets:
            warnings.append("没有可进入 PSD 交接的候选图，请先登记生成结果或检查筛选条件。")
        if not creative_pack:
            warnings.append("未找到创作包，PSD 图层建议只能使用默认结构。")

        layer_groups = self._layer_groups(creative_pack)
        return PsdHandoffPlan(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_results=source_results,
            source_creative_pack=source_creative_pack,
            assets=assets,
            layer_groups=layer_groups,
            reconstruction_steps=self._reconstruction_steps(creative_pack, assets),
            slicing_tasks=self._slicing_tasks(creative_pack, assets),
            naming_rules=self._naming_rules(creative_pack),
            warnings=warnings,
            approval_checklist=self._approval_checklist(creative_pack),
        )

    @staticmethod
    def render_markdown(plan: PsdHandoffPlan) -> str:
        lines = [
            f"# PSD 交接计划 - {plan.work_item_id}",
            "",
            f"- 项目：`{plan.project_key}`",
            f"- 创建时间：`{plan.created_at}`",
            f"- 生成结果：`{plan.source_results or '未绑定'}`",
            f"- 创作包：`{plan.source_creative_pack or '未绑定'}`",
            "",
            "## 警告",
            *(f"- {item}" for item in plan.warnings or ["无"]),
            "",
            "## 候选资产",
        ]
        if not plan.assets:
            lines.append("- 暂无候选资产")
        for asset in plan.assets:
            lines.extend(
                [
                    f"### {asset.asset_id}",
                    f"- 方案：`{asset.variant_id or 'unknown'}`",
                    f"- 角色：`{asset.role}`",
                    f"- 来源：`{asset.uri}`",
                    "- 推荐图层：" + " / ".join(asset.recommended_layers),
                    "- 切图提示：" + "；".join(asset.slicing_notes),
                    "",
                ]
            )
        lines.extend(["## 推荐图层组", *(f"- `{item}`" for item in plan.layer_groups)])
        lines.extend(["", "## PSD 重建步骤", *(f"- [ ] {item}" for item in plan.reconstruction_steps)])
        lines.extend(["", "## 切图任务", *(f"- [ ] {item}" for item in plan.slicing_tasks)])
        lines.extend(["", "## 命名规则", *(f"- {item}" for item in plan.naming_rules)])
        lines.extend(["", "## 确认清单", *(f"- [ ] {item}" for item in plan.approval_checklist)])
        return "\n".join(lines)

    @staticmethod
    def render_layer_map(plan: PsdHandoffPlan) -> str:
        lines = [
            f"# 图层地图 - {plan.work_item_id}",
            "",
            "## 建议 PSD 结构",
        ]
        for group in plan.layer_groups:
            lines.append(f"- `{group}`")
            if group == "00_refs":
                lines.extend(f"  - `{asset.asset_id}` reference from {asset.variant_id}" for asset in plan.assets)
            elif group == "06_ui_slices":
                lines.append("  - buttons")
                lines.append("  - badges")
                lines.append("  - icons")
                lines.append("  - cards")
            elif group == "99_exports":
                lines.append("  - flattened_preview")
                lines.append("  - platform_exports")
        lines.extend(["", "## 资产到图层建议"])
        for asset in plan.assets:
            lines.append(f"- `{asset.asset_id}` -> " + " / ".join(asset.recommended_layers))
        return "\n".join(lines)

    @staticmethod
    def render_slice_checklist(plan: PsdHandoffPlan) -> str:
        lines = [
            f"# 切图检查清单 - {plan.work_item_id}",
            "",
            "## 切图任务",
            *(f"- [ ] {item}" for item in plan.slicing_tasks),
            "",
            "## 资产逐项检查",
        ]
        for asset in plan.assets:
            lines.extend(
                [
                    f"### {asset.asset_id}",
                    "- [ ] 确认源图清晰度足够进入 PSD 重建或精修",
                    "- [ ] 确认主体、背景、文案、按钮是否能拆层",
                    *(f"- [ ] {note}" for note in asset.slicing_notes),
                    "",
                ]
            )
        lines.extend(["## 正式交付前", *(f"- [ ] {item}" for item in plan.approval_checklist)])
        return "\n".join(lines)

    def _assets(self, results_payload: dict[str, Any] | None, selected: set[str]) -> list[PsdHandoffAsset]:
        raw_assets = (results_payload or {}).get("assets", [])
        delivery_candidates = set((results_payload or {}).get("delivery_candidates", []))
        assets: list[PsdHandoffAsset] = []
        for item in raw_assets:
            asset_id = str(item.get("asset_id") or "")
            uri = str(item.get("uri") or "")
            variant_id = str(item.get("variant_id") or "")
            if selected and asset_id not in selected and uri not in selected and variant_id not in selected:
                continue
            if not selected and delivery_candidates and uri not in delivery_candidates:
                continue
            notes = item.get("notes", [])
            assets.append(
                PsdHandoffAsset(
                    asset_id=asset_id or uri,
                    variant_id=variant_id,
                    uri=uri,
                    role=self._role(notes),
                    recommended_layers=self._recommended_layers(notes),
                    slicing_notes=self._slicing_notes_for_asset(notes),
                )
            )
        return assets

    @classmethod
    def _layer_groups(cls, creative_pack: CreativePack | None) -> list[str]:
        groups = list(cls.DEFAULT_LAYER_GROUPS)
        if creative_pack and creative_pack.delivery_manifest.slicing_notes:
            groups.append("slice_notes")
        return list(dict.fromkeys(groups))

    @staticmethod
    def _reconstruction_steps(creative_pack: CreativePack | None, assets: list[PsdHandoffAsset]) -> list[str]:
        steps = [
            "把选中的生成图放入 `00_refs`，锁定原始参考层，保留来源文件名。",
            "重建或拆分背景、主体、效果、文案、CTA 和 UI 切图组，不直接在单张扁平图上交付。",
            "按项目风格规则检查色彩、材质、字体、角色表现和信息层级。",
            "输出 flattened preview 供人工确认后，再进入正式切图。",
        ]
        if creative_pack:
            steps.extend(creative_pack.psd_guidance[:4])
            if creative_pack.uncertainties:
                steps.insert(0, "先确认创作包未闭合问题，避免把探索图误当最终稿。")
        if not assets:
            steps.insert(0, "先选择至少一张候选图作为 PSD 重建参考。")
        return list(dict.fromkeys(steps))

    @staticmethod
    def _slicing_tasks(creative_pack: CreativePack | None, assets: list[PsdHandoffAsset]) -> list[str]:
        tasks = [
            "确认是否需要 1x/2x 或 Android/iOS 双端规格。",
            "单独导出按钮、底板、图标、角标、logo 等可复用元素。",
            "导出前检查透明边距、命名后缀、语言版本和平台尺寸。",
        ]
        for asset in assets:
            tasks.append(f"基于 {asset.asset_id} 检查可拆分元素：" + "；".join(asset.slicing_notes))
        if creative_pack:
            tasks.extend(creative_pack.delivery_manifest.slicing_notes)
        return list(dict.fromkeys(tasks))

    @staticmethod
    def _naming_rules(creative_pack: CreativePack | None) -> list[str]:
        if creative_pack:
            return creative_pack.delivery_manifest.naming_rules
        return ["{project_key}_{work_item_id}_{asset_role}_{size}_v001"]

    @staticmethod
    def _approval_checklist(creative_pack: CreativePack | None) -> list[str]:
        checklist = [
            "设计师确认候选图可以进入 PSD 重建或切图。",
            "确认 PSD 图层命名、尺寸、语言版本和导出格式。",
            "确认所有正式导出都进入 staging，不覆盖已有正式资产。",
            "对外发送或交付前必须再次人工确认。",
        ]
        if creative_pack and creative_pack.uncertainties:
            checklist.insert(0, "创作包不确定项已闭合或已明确接受风险。")
        return checklist

    @staticmethod
    def _role(notes: Any) -> str:
        text = " ".join(notes if isinstance(notes, list) else [str(notes)]).lower()
        if "切图" in text or "slice" in text:
            return "slice-reference"
        if "final" in text or "selected" in text or "candidate" in text or "候选" in text:
            return "psd-reference"
        return "visual-reference"

    @staticmethod
    def _recommended_layers(notes: Any) -> list[str]:
        text = " ".join(notes if isinstance(notes, list) else [str(notes)]).lower()
        layers = ["00_refs", "01_background", "02_subject", "03_effects"]
        if "按钮" in text or "cta" in text:
            layers.append("05_cta")
        if "切图" in text or "slice" in text:
            layers.append("06_ui_slices")
        return layers

    @staticmethod
    def _slicing_notes_for_asset(notes: Any) -> list[str]:
        values = notes if isinstance(notes, list) else [str(notes)] if notes else []
        result = [str(item) for item in values if str(item).strip()]
        result.extend(["确认主体边缘是否需要手工修边", "确认是否需要从扁平图中重建按钮/底板/角标"])
        return list(dict.fromkeys(result))

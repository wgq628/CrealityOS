from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.models import DesignBrief, RequirementChangeItem, RequirementChangeReport


class RequirementChangeAnalyzer:
    FIELD_LABELS = {
        "title": "标题",
        "objective": "设计目标",
        "target_audience": "目标受众",
        "platform": "平台/版位",
        "sizes": "尺寸",
        "deliverables": "交付物",
        "deadline": "截止时间",
        "same_category": "同品类底座",
        "source_links": "关联文档",
        "missing_information": "缺失信息",
        "raw_signals": "风格信号",
    }

    MAJOR_FIELDS = {"objective", "target_audience", "platform", "sizes", "deliverables", "same_category"}
    WARNING_FIELDS = {"deadline", "source_links", "missing_information", "raw_signals", "title"}

    def build(
        self,
        project_key: str,
        work_item_id: str,
        old_brief: DesignBrief,
        new_brief: DesignBrief,
        source_mode: str,
        source_artifacts: dict[str, str | None],
    ) -> RequirementChangeReport:
        change_items: list[RequirementChangeItem] = []
        unchanged_fields: list[str] = []
        for field in self.FIELD_LABELS:
            old_value = getattr(old_brief, field)
            new_value = getattr(new_brief, field)
            if self._normalized(old_value) == self._normalized(new_value):
                unchanged_fields.append(field)
                continue
            severity = self._severity(field, old_value, new_value)
            change_items.append(
                RequirementChangeItem(
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                    severity=severity,
                    impact=self._impact(field, severity),
                )
            )
        blockers = [
            f"{self.FIELD_LABELS[item.field]} 已变化：需要重新生成创作包与后续产物。"
            for item in change_items
            if item.severity == "blocker"
        ]
        warnings = [
            f"{self.FIELD_LABELS[item.field]} 已变化：建议复核相关报告。"
            for item in change_items
            if item.severity == "warning"
        ]
        impacted_artifacts = self._impacted_artifacts(change_items)
        status = "no_change" if not change_items else "requires_rebuild" if blockers else "needs_review"
        return RequirementChangeReport(
            project_key=project_key,
            work_item_id=work_item_id,
            title=new_brief.title,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            source_mode=source_mode,
            change_items=change_items,
            unchanged_fields=unchanged_fields,
            impacted_artifacts=impacted_artifacts,
            blockers=blockers,
            warnings=warnings,
            next_actions=self._next_actions(status, impacted_artifacts, project_key, work_item_id),
            source_artifacts=source_artifacts,
        )

    def render_markdown(self, report: RequirementChangeReport) -> str:
        lines = [
            f"# 需求变更影响分析 - {report.title}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 工作项：`{report.work_item_id}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 来源模式：`{report.source_mode}`",
            f"- 状态：`{report.status}`",
            "",
            "## 变更项",
        ]
        if not report.change_items:
            lines.append("- 无字段变化")
        for item in report.change_items:
            label = self.FIELD_LABELS.get(item.field, item.field)
            lines.extend(
                [
                    f"### {label}",
                    f"- 严重级别：`{item.severity}`",
                    f"- 旧值：`{self._value_text(item.old_value)}`",
                    f"- 新值：`{self._value_text(item.new_value)}`",
                    f"- 影响：{item.impact}",
                    "",
                ]
            )
        lines.extend(["## 未变化字段", *(f"- {self.FIELD_LABELS.get(field, field)}" for field in report.unchanged_fields or ["无"])])
        lines.extend(["", "## 受影响产物", *(f"- `{item}`" for item in report.impacted_artifacts or ["无"])])
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in report.blockers or ["无"])])
        lines.extend(["", "## 风险提醒", *(f"- {item}" for item in report.warnings or ["无"])])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in report.next_actions)])
        lines.extend(["", "## 来源产物", *(f"- {key}: `{value or '缺失'}`" for key, value in report.source_artifacts.items())])
        lines.extend(
            [
                "",
                "## 安全说明",
                "- 本报告只比较需求字段并写入本地文件，不自动覆盖旧创作包。",
                "- 需求变化导致的重生成、出图、PSD 修改、Meegle 回写仍需设计师确认。",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _normalized(value: Any) -> Any:
        if isinstance(value, list):
            return [str(item).strip() for item in value]
        if isinstance(value, str):
            return value.strip()
        return value

    @classmethod
    def _severity(cls, field: str, old_value: Any, new_value: Any) -> str:
        if field in cls.MAJOR_FIELDS:
            return "blocker"
        if field == "deadline" and str(old_value).strip() != str(new_value).strip():
            return "warning"
        if field == "missing_information":
            old_missing = set(old_value or [])
            new_missing = set(new_value or [])
            return "warning" if new_missing - old_missing else "info"
        if field in cls.WARNING_FIELDS:
            return "warning"
        return "info"

    @staticmethod
    def _impact(field: str, severity: str) -> str:
        impacts = {
            "objective": "创作目标变化会影响创作包、提示词、构图和评审标准。",
            "target_audience": "受众变化会影响风格判断、文案语气和素材重点。",
            "platform": "平台/版位变化会影响尺寸、构图安全区、CTA 和交付规格。",
            "sizes": "尺寸变化会影响构图、PSD 图层布局、切图和导出清单。",
            "deliverables": "交付物变化会影响 PSD/切图计划、staging 和交付清单。",
            "same_category": "同品类底座变化会影响可迁移风格与项目覆盖层判断。",
            "deadline": "截止时间变化会影响优先级和可投入的精修深度。",
            "source_links": "关联文档变化可能带来新的约束或参考，需要重新读取。",
            "missing_information": "缺失信息变化会影响是否能继续推进或需要澄清。",
            "raw_signals": "风格信号变化可能影响风格卡和提示词。",
            "title": "标题变化通常不阻塞，但会影响产物命名和回写摘要。",
        }
        return impacts.get(field, "该字段变化需要设计师复核。") if severity != "info" else "变化较小，记录供追踪。"

    @staticmethod
    def _impacted_artifacts(change_items: list[RequirementChangeItem]) -> list[str]:
        fields = {item.field for item in change_items}
        artifacts: list[str] = []
        if fields:
            artifacts.extend(["design_brief", "requirement_clarification_report"])
        if fields & {"objective", "target_audience", "platform", "sizes", "deliverables", "same_category", "raw_signals"}:
            artifacts.extend(["style_card", "creative_pack", "style_transfer_report", "style_alignment_report", "design_decision_record"])
        if fields & {"objective", "target_audience", "platform", "sizes", "raw_signals"}:
            artifacts.extend(["image_generation_batch", "image_generation_jobs", "image_execution_package"])
        if fields & {"sizes", "deliverables", "platform"}:
            artifacts.extend(["psd_handoff_plan", "psd_slice_spec_report", "delivery_manifest", "delivery_readiness_report"])
        if fields & {"deadline", "title", "source_links", "missing_information"}:
            artifacts.extend(["designer_review_packet", "meegle_writeback_draft", "design_workflow_plan"])
        return list(dict.fromkeys(artifacts))

    @staticmethod
    def _next_actions(status: str, impacted_artifacts: list[str], project_key: str, work_item_id: str) -> list[str]:
        if status == "no_change":
            return ["未检测到需求字段变化，可以继续沿用当前创作包和工作流计划。"]
        actions = [
            "先由设计师确认需求变更是否成立，避免误把字段解析差异当作真实变更。",
            f"确认后重新运行：python -m agent.cli build-creative-pack --project-key {project_key} --work-item-id {work_item_id}",
            f"随后刷新工作流：python -m agent.cli create-design-workflow-plan --project-key {project_key} --work-item-id {work_item_id}",
        ]
        if "psd_handoff_plan" in impacted_artifacts:
            actions.append("如果已进入 PSD/切图阶段，先暂停正式交付，重新核对 PSD 交接计划和切图规格。")
        return actions

    @staticmethod
    def _value_text(value: Any) -> str:
        if isinstance(value, list):
            return "、".join(str(item) for item in value) or "空"
        return str(value)

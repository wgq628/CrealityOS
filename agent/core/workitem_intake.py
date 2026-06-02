from __future__ import annotations

from datetime import datetime

from agent.core.field_calibration import FieldCalibrator
from agent.core.requirement_interpreter import RequirementInterpreter
from agent.models import FieldMapping, WorkItemContext, WorkItemIntakeDiagnosticsReport, WorkItemIntakeFinding
from agent.utils import flatten_pairs


class WorkItemIntakeDiagnostician:
    def __init__(self) -> None:
        self.calibrator = FieldCalibrator()
        self.interpreter = RequirementInterpreter()

    def build(
        self,
        context: WorkItemContext,
        source_mode: str,
        source_artifacts: dict[str, str | None],
        existing_mapping: FieldMapping | None = None,
    ) -> WorkItemIntakeDiagnosticsReport:
        project_key = context.project_key or "unknown-project"
        calibration = self.calibrator.build_report(project_key, source_artifacts.get("sample_file") or source_mode, context.raw_item)
        mapping = existing_mapping or self._trusted_mapping(calibration.mapping)
        parsed_brief = self.interpreter.build(context, field_mapping=mapping)
        findings = [
            self._mapping_check(calibration.mapping),
            self._existing_mapping_check(existing_mapping, calibration.mapping),
            self._brief_completeness_check(parsed_brief.missing_information),
            self._evidence_check(context),
            self._doc_link_check(context),
            self._safety_check(),
        ]
        blockers = [finding.action for finding in findings if finding.severity == "blocker" and finding.action]
        warnings = [finding.action for finding in findings if finding.severity == "warning" and finding.action]
        status = "blocked" if blockers else "needs_field_review" if warnings else "ready_for_creative_pack"
        return WorkItemIntakeDiagnosticsReport(
            project_key=project_key,
            work_item_id=context.work_item_id,
            title=context.title,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_mode=source_mode,
            status=status,
            field_mapping=calibration.mapping,
            mapping_candidates=calibration.candidates,
            parsed_brief=parsed_brief,
            findings=findings,
            warnings=list(dict.fromkeys(warnings + calibration.warnings)),
            blockers=list(dict.fromkeys(blockers)),
            next_actions=self._next_actions(status, context, existing_mapping),
            source_artifacts=source_artifacts,
        )

    @staticmethod
    def _trusted_mapping(mapping: FieldMapping) -> FieldMapping:
        fields = {
            field: path
            for field, path in mapping.fields.items()
            if mapping.confidence.get(field, 0.0) >= 0.55
        }
        confidence = {field: mapping.confidence.get(field, 0.0) for field in fields}
        notes = list(mapping.notes) + ["入口诊断解析需求卡时只使用 confidence >= 0.55 的自动字段映射，低置信度字段保留给人工确认。"]
        return FieldMapping(project_key=mapping.project_key, fields=fields, confidence=confidence, notes=notes)

    @staticmethod
    def render_markdown(report: WorkItemIntakeDiagnosticsReport) -> str:
        lines = [
            f"# 工作项入口诊断 - {report.title}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 工作项：`{report.work_item_id}`",
            f"- 来源：`{report.source_mode}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            "",
            "## 来源产物",
        ]
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in report.source_artifacts.items())
        lines.extend(
            [
                "",
                "## 解析出的设计需求卡",
                f"- 游戏：{report.parsed_brief.game_name}",
                f"- 玩法理解：{report.parsed_brief.gameplay_summary}",
                f"- 目标：{report.parsed_brief.objective}",
                f"- 受众：{report.parsed_brief.target_audience}",
                f"- 平台：{report.parsed_brief.platform}",
                f"- 截止时间：{report.parsed_brief.deadline}",
                f"- 尺寸：{', '.join(report.parsed_brief.sizes) if report.parsed_brief.sizes else '待确认'}",
                f"- 交付物：{', '.join(report.parsed_brief.deliverables) if report.parsed_brief.deliverables else '待确认'}",
                f"- 同品类底座：`{report.parsed_brief.same_category}`",
            ]
        )
        lines.extend(["", "## 推荐字段映射"])
        for canonical, field_path in report.field_mapping.fields.items():
            score = report.field_mapping.confidence.get(canonical, 0.0)
            lines.append(f"- `{canonical}` -> `{field_path}` | confidence={score:.2f}")
        lines.extend(["", "## 字段候选"])
        for canonical, candidates in report.mapping_candidates.items():
            lines.append(f"### {canonical}")
            lines.extend(f"- {item}" for item in candidates or ["无"])
        lines.extend(["", "## 缺失信息", *(f"- {item}" for item in report.parsed_brief.missing_information or ["无"])])
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in report.blockers or ["无"])])
        lines.extend(["", "## 风险提醒", *(f"- {item}" for item in report.warnings or ["无"])])
        lines.append("")
        lines.append("## 检查项")
        for finding in report.findings:
            lines.extend(
                [
                    f"### {finding.check_id} {finding.title}",
                    f"- 状态：`{finding.status}`",
                    f"- 严重级别：`{finding.severity}`",
                    *(f"- 证据：{item}" for item in finding.evidence or ["无"]),
                    f"- 建议动作：{finding.action or '无'}",
                    "",
                ]
            )
        lines.extend(["## 下一步", *(f"- {item}" for item in report.next_actions)])
        return "\n".join(lines)

    @staticmethod
    def _mapping_check(mapping: FieldMapping) -> WorkItemIntakeFinding:
        missing = [field for field in ("objective", "audience", "platform", "sizes", "deliverables", "deadline") if field not in mapping.fields]
        low_confidence = [f"{field}={score:.2f}" for field, score in mapping.confidence.items() if score < 0.55]
        evidence = [f"已识别字段：{len(mapping.fields)}", f"低置信度：{len(low_confidence)}"] + low_confidence[:6]
        if missing:
            return WorkItemIntakeFinding("MAPPING", "字段映射覆盖", "missing_fields", "warning", evidence + missing, "请先校准缺失字段，避免需求卡缺项。")
        if low_confidence:
            return WorkItemIntakeFinding("MAPPING", "字段映射覆盖", "low_confidence", "warning", evidence, "字段映射置信度偏低，建议人工确认后再长期复用。")
        return WorkItemIntakeFinding("MAPPING", "字段映射覆盖", "pass", "info", evidence)

    @staticmethod
    def _existing_mapping_check(existing_mapping: FieldMapping | None, suggested_mapping: FieldMapping) -> WorkItemIntakeFinding:
        if not existing_mapping:
            return WorkItemIntakeFinding(
                "MEMORY",
                "已有字段记忆",
                "missing",
                "warning",
                ["未找到本项目 field_mapping.json"],
                "如诊断结果可信，可运行 calibrate-field-mapping 保存字段映射。",
            )
        changed = [
            field
            for field, suggested in suggested_mapping.fields.items()
            if existing_mapping.fields.get(field) and existing_mapping.fields.get(field) != suggested
        ]
        evidence = [f"已有映射：{len(existing_mapping.fields)}", f"建议差异：{len(changed)}"] + changed[:6]
        if changed:
            return WorkItemIntakeFinding("MEMORY", "已有字段记忆", "drift", "warning", evidence, "当前样本与已有字段映射不完全一致，请确认 Meegle 模板是否变化。")
        return WorkItemIntakeFinding("MEMORY", "已有字段记忆", "pass", "info", evidence)

    @staticmethod
    def _brief_completeness_check(missing_information: list[str]) -> WorkItemIntakeFinding:
        evidence = missing_information[:6] or ["无缺失信息"]
        if len(missing_information) >= 4:
            return WorkItemIntakeFinding("BRIEF", "需求卡完整性", "too_many_missing", "blocker", evidence, "缺失信息过多，先澄清需求再进入创作包。")
        if missing_information:
            return WorkItemIntakeFinding("BRIEF", "需求卡完整性", "needs_clarification", "warning", evidence, "生成创作包前请确认这些缺失项是否可接受。")
        return WorkItemIntakeFinding("BRIEF", "需求卡完整性", "pass", "info", evidence)

    @staticmethod
    def _evidence_check(context: WorkItemContext) -> WorkItemIntakeFinding:
        flat_count = len(flatten_pairs(context.raw_item))
        evidence = [f"扁平字段：{flat_count}", f"评论：{len(context.comments)}", f"文档内容：{len(context.docs)}"]
        if flat_count < 3 and not context.comments and not context.docs:
            return WorkItemIntakeFinding("EVIDENCE", "需求证据量", "thin", "warning", evidence, "工作项字段和补充证据较少，建议拉取关联文档或评论。")
        return WorkItemIntakeFinding("EVIDENCE", "需求证据量", "pass", "info", evidence)

    @staticmethod
    def _doc_link_check(context: WorkItemContext) -> WorkItemIntakeFinding:
        evidence = [f"关联文档链接：{len(context.doc_links)}", f"已读取文档：{len(context.docs)}"]
        if context.doc_links and not context.docs:
            return WorkItemIntakeFinding("DOCS", "关联文档", "links_not_fetched", "warning", evidence, "已发现文档链接，建议运行 fetch-requirement-docs 或完整设计闭环读取文档。")
        if not context.doc_links:
            return WorkItemIntakeFinding("DOCS", "关联文档", "none", "info", evidence, "未发现关联文档链接；如需求在文档中，请补充链接。")
        return WorkItemIntakeFinding("DOCS", "关联文档", "pass", "info", evidence)

    @staticmethod
    def _safety_check() -> WorkItemIntakeFinding:
        return WorkItemIntakeFinding(
            "SAFETY",
            "安全门控",
            "pass",
            "info",
            ["入口诊断只读取/解析需求并写本地报告，不发布 Meegle、不流转工作项、不覆盖正式资产。"],
            "确认字段映射和需求卡后再进入创作包。",
        )

    @staticmethod
    def _next_actions(status: str, context: WorkItemContext, existing_mapping: FieldMapping | None) -> list[str]:
        actions: list[str] = []
        if not existing_mapping:
            actions.append(f"如字段映射可信，运行 python -m agent.cli calibrate-field-mapping --project-key {context.project_key} --sample-file <sample.json> 保存映射。")
        if context.doc_links and not context.docs:
            actions.append(f"运行 python -m agent.cli fetch-requirement-docs --project-key {context.project_key} --work-item-id {context.work_item_id} 读取关联文档。")
        if status == "blocked":
            actions.append("先补齐阻塞级缺失信息，再进入 build-creative-pack。")
        else:
            actions.append(f"确认诊断无误后运行 python -m agent.cli build-creative-pack --project-key {context.project_key} --work-item-id {context.work_item_id}。")
        actions.append("诊断报告不会自动修改 Meegle 或发布评论；所有对外动作仍需单独确认。")
        return list(dict.fromkeys(actions))

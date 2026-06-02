from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.models import CreativePack, DeliveryPreparation, DeliveryReadinessFinding, DeliveryReadinessReport, KnowledgeLevel


class DeliveryReadinessAuditor:
    def build(
        self,
        project_key: str,
        work_item_id: str,
        creative_pack: CreativePack | None,
        style_transfer: dict[str, Any] | None,
        style_alignment: dict[str, Any] | None,
        generation_results: dict[str, Any] | None,
        candidate_style_drift: dict[str, Any] | None,
        candidate_comparison: dict[str, Any] | None,
        candidate_review: dict[str, Any] | None,
        psd_handoff_plan: dict[str, Any] | None,
        psd_handoff_package: dict[str, Any] | None,
        psd_slice_spec_report: dict[str, Any] | None,
        delivery_package: DeliveryPreparation | None,
        source_artifacts: dict[str, str | None],
    ) -> DeliveryReadinessReport:
        findings = [
            self._creative_pack_check(creative_pack),
            self._style_confidence_check(creative_pack),
            self._style_transfer_check(style_transfer),
            self._style_alignment_check(style_alignment),
            self._generation_results_check(generation_results),
            self._candidate_style_drift_check(candidate_style_drift),
            self._candidate_comparison_check(candidate_comparison, generation_results),
            self._candidate_review_check(candidate_review),
            self._psd_handoff_check(psd_handoff_plan),
            self._psd_package_check(psd_handoff_package),
            self._psd_slice_spec_check(psd_slice_spec_report),
            self._delivery_staging_check(delivery_package),
            self._safety_gate_check(),
        ]
        blocking_items = [finding.action for finding in findings if finding.severity == "blocker" and finding.action]
        warnings = [finding.action for finding in findings if finding.severity == "warning" and finding.action]
        status = "blocked" if blocking_items else "needs_designer_confirmation" if warnings else "ready_for_designer_confirmation"
        approval_checklist = self._approval_checklist(findings)
        return DeliveryReadinessReport(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            requires_designer_confirmation=True,
            findings=findings,
            blocking_items=list(dict.fromkeys(blocking_items)),
            warnings=list(dict.fromkeys(warnings)),
            approval_checklist=approval_checklist,
            source_artifacts=source_artifacts,
        )

    @staticmethod
    def render_markdown(report: DeliveryReadinessReport) -> str:
        lines = [
            f"# 交付前质量门 - {report.work_item_id}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            f"- 需要设计师确认：{'是' if report.requires_designer_confirmation else '否'}",
            "",
            "## 来源产物",
        ]
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in report.source_artifacts.items())
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in report.blocking_items or ["无"])])
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
        lines.extend(["## 人工确认清单", *(f"- [ ] {item}" for item in report.approval_checklist)])
        return "\n".join(lines)

    @staticmethod
    def _creative_pack_check(creative_pack: CreativePack | None) -> DeliveryReadinessFinding:
        if not creative_pack:
            return DeliveryReadinessFinding(
                check_id="REQ",
                title="需求与创作包",
                status="missing",
                severity="blocker",
                action="先生成 creative_pack，再进入交付检查。",
            )
        evidence = [
            f"标题：{creative_pack.brief.title}",
            f"尺寸：{', '.join(creative_pack.brief.sizes) if creative_pack.brief.sizes else '待确认'}",
            f"交付物：{', '.join(creative_pack.brief.deliverables) if creative_pack.brief.deliverables else '待确认'}",
        ]
        missing = list(creative_pack.brief.missing_information)
        if missing:
            return DeliveryReadinessFinding(
                check_id="REQ",
                title="需求与创作包",
                status="needs_closure",
                severity="warning",
                evidence=evidence + [f"未闭合：{'; '.join(missing[:5])}"],
                action="交付前请确认创作包中的缺失信息已闭合或已明确接受风险。",
            )
        return DeliveryReadinessFinding("REQ", "需求与创作包", "pass", "info", evidence=evidence)

    @staticmethod
    def _style_confidence_check(creative_pack: CreativePack | None) -> DeliveryReadinessFinding:
        if not creative_pack:
            return DeliveryReadinessFinding("STYLE", "风格信度", "missing", "blocker", action="缺少创作包，无法检查风格信度。")
        pending = [
            rule.statement
            for rule in creative_pack.style_card.rules
            if rule.level in {KnowledgeLevel.K3, "K3"}
        ]
        confirmed = [
            rule.statement
            for rule in creative_pack.style_card.rules
            if rule.level in {KnowledgeLevel.K1, KnowledgeLevel.K2, "K1", "K2"}
        ]
        evidence = [f"K1/K2 规则：{len(confirmed)}", f"K3 假设：{len(pending)}"]
        if pending:
            return DeliveryReadinessFinding(
                check_id="STYLE",
                title="风格信度",
                status="has_k3",
                severity="warning",
                evidence=evidence + pending[:3],
                action="交付前请确认 K3 假设未被当作正式风格结论；必要时回写评审升级或驳回。",
            )
        return DeliveryReadinessFinding("STYLE", "风格信度", "pass", "info", evidence=evidence)

    @staticmethod
    def _style_transfer_check(style_transfer: dict[str, Any] | None) -> DeliveryReadinessFinding:
        if not style_transfer:
            return DeliveryReadinessFinding(
                "STYLE_TRANSFER",
                "风格迁移与项目覆盖",
                "missing",
                "warning",
                action="跨同品类复用或进入出图前建议先生成 style_transfer_report，确认项目覆盖层没有冲突。",
            )
        status = str(style_transfer.get("status", "unknown"))
        blockers = style_transfer.get("blockers", [])
        warnings = style_transfer.get("warnings", [])
        transferable = style_transfer.get("transferable_rules", [])
        overrides = style_transfer.get("project_overrides", [])
        evidence = [
            f"状态：{status}",
            f"可迁移规则：{len(transferable)}",
            f"项目覆盖：{len(overrides)}",
            f"阻塞项：{len(blockers)}",
        ]
        if blockers or status == "blocked":
            return DeliveryReadinessFinding(
                "STYLE_TRANSFER",
                "风格迁移与项目覆盖",
                "blocked",
                "blocker",
                evidence + blockers[:3],
                "先处理同品类底座与项目覆盖层冲突，再进入出图、PSD 或交付。",
            )
        if warnings or status == "needs_designer_review":
            return DeliveryReadinessFinding(
                "STYLE_TRANSFER",
                "风格迁移与项目覆盖",
                "needs_review",
                "warning",
                evidence + warnings[:3],
                "设计师需确认哪些同品类规则可迁移，哪些必须被项目覆盖。",
            )
        return DeliveryReadinessFinding("STYLE_TRANSFER", "风格迁移与项目覆盖", "pass", "info", evidence=evidence)

    @staticmethod
    def _style_alignment_check(style_alignment: dict[str, Any] | None) -> DeliveryReadinessFinding:
        if not style_alignment:
            return DeliveryReadinessFinding(
                "STYLE_GATE",
                "风格一致性闸门",
                "missing",
                "warning",
                action="出图或交付前建议先生成 style_alignment_report，检查 K1/K2、禁忌项和 K3 边界。",
            )
        status = str(style_alignment.get("status", "unknown"))
        blockers = style_alignment.get("blockers", [])
        warnings = style_alignment.get("warnings", [])
        evidence = [f"状态：{status}", f"阻塞项：{len(blockers)}", f"风险提醒：{len(warnings)}"]
        if blockers or status == "blocked":
            return DeliveryReadinessFinding(
                "STYLE_GATE",
                "风格一致性闸门",
                "blocked",
                "blocker",
                evidence + blockers[:3],
                "先处理风格一致性报告中的阻塞项，再进入出图、PSD 或交付。",
            )
        if warnings or status == "needs_designer_review":
            return DeliveryReadinessFinding(
                "STYLE_GATE",
                "风格一致性闸门",
                "needs_review",
                "warning",
                evidence + warnings[:3],
                "设计师需复核风格一致性风险，并确认是否允许继续。",
            )
        return DeliveryReadinessFinding("STYLE_GATE", "风格一致性闸门", "pass", "info", evidence=evidence)

    @staticmethod
    def _generation_results_check(generation_results: dict[str, Any] | None) -> DeliveryReadinessFinding:
        if not generation_results:
            return DeliveryReadinessFinding(
                "GEN",
                "生成结果登记",
                "missing",
                "warning",
                action="如果本次需要图片素材，请先 register-image-results 登记候选图；纯 PSD/切图任务可人工确认跳过。",
            )
        assets = generation_results.get("assets", [])
        missing = generation_results.get("missing_assets", [])
        candidates = generation_results.get("delivery_candidates", [])
        evidence = [f"资产数：{len(assets)}", f"候选数：{len(candidates)}", f"缺失本地资产：{len(missing)}"]
        if missing:
            return DeliveryReadinessFinding("GEN", "生成结果登记", "missing_assets", "blocker", evidence, "先修正缺失的本地生成图路径。")
        if not candidates:
            return DeliveryReadinessFinding("GEN", "生成结果登记", "no_candidates", "warning", evidence, "请至少标记一张候选图，或确认本次无需生成图。")
        return DeliveryReadinessFinding("GEN", "生成结果登记", "pass", "info", evidence=evidence)

    @staticmethod
    def _candidate_style_drift_check(candidate_style_drift: dict[str, Any] | None) -> DeliveryReadinessFinding:
        if not candidate_style_drift:
            return DeliveryReadinessFinding(
                "DRIFT",
                "候选图风格偏移预警",
                "missing",
                "warning",
                action="候选图进入评审、PSD 或交付前建议运行 create-candidate-style-drift-report。",
            )
        status = str(candidate_style_drift.get("status", "unknown"))
        blockers = candidate_style_drift.get("blockers", [])
        warnings = candidate_style_drift.get("warnings", [])
        items = candidate_style_drift.get("items", [])
        evidence = [f"状态：{status}", f"候选项：{len(items)}", f"阻塞项：{len(blockers)}", f"风险提醒：{len(warnings)}"]
        if blockers or status == "blocked":
            return DeliveryReadinessFinding(
                "DRIFT",
                "候选图风格偏移预警",
                "blocked",
                "blocker",
                evidence + blockers[:3],
                "先处理候选图风格偏移阻塞项，再进入 PSD 或交付。",
            )
        if warnings or status == "needs_designer_review":
            return DeliveryReadinessFinding(
                "DRIFT",
                "候选图风格偏移预警",
                "needs_review",
                "warning",
                evidence + warnings[:3],
                "设计师需复核候选图偏移风险后再采纳。",
            )
        return DeliveryReadinessFinding("DRIFT", "候选图风格偏移预警", "pass", "info", evidence=evidence)

    @staticmethod
    def _candidate_comparison_check(
        candidate_comparison: dict[str, Any] | None,
        generation_results: dict[str, Any] | None,
    ) -> DeliveryReadinessFinding:
        if not generation_results:
            return DeliveryReadinessFinding(
                "COMPARE",
                "候选方案对比矩阵",
                "not_applicable",
                "info",
                evidence=["尚未登记生成候选图，本轮暂不要求候选方案矩阵。"],
            )
        if not candidate_comparison:
            return DeliveryReadinessFinding(
                "COMPARE",
                "候选方案对比矩阵",
                "missing",
                "warning",
                action="已有生成图索引，进入 PSD 或交付前建议运行 create-candidate-comparison-matrix。",
            )
        status = str(candidate_comparison.get("status", "unknown"))
        blockers = candidate_comparison.get("blockers", [])
        warnings = candidate_comparison.get("warnings", [])
        rows = candidate_comparison.get("rows", [])
        recommended = candidate_comparison.get("recommended_variant_ids", [])
        revise = candidate_comparison.get("revise_variant_ids", [])
        evidence = [
            f"状态：{status}",
            f"方案数：{len(rows)}",
            f"推荐采纳：{len(recommended)}",
            f"建议修正：{len(revise)}",
            f"阻塞项：{len(blockers)}",
        ]
        if blockers or status == "blocked":
            return DeliveryReadinessFinding(
                "COMPARE",
                "候选方案对比矩阵",
                "blocked",
                "blocker",
                evidence + blockers[:3],
                "先处理候选方案对比矩阵中的阻塞项，再进入 PSD 或交付。",
            )
        if warnings or status == "needs_designer_decision":
            return DeliveryReadinessFinding(
                "COMPARE",
                "候选方案对比矩阵",
                "needs_decision",
                "warning",
                evidence + warnings[:3],
                "设计师需明确采纳、修正或驳回哪个候选方案。",
            )
        return DeliveryReadinessFinding("COMPARE", "候选方案对比矩阵", "pass", "info", evidence=evidence)

    @staticmethod
    def _candidate_review_check(candidate_review: dict[str, Any] | None) -> DeliveryReadinessFinding:
        if not candidate_review:
            return DeliveryReadinessFinding(
                "REVIEW",
                "候选图评审回写",
                "missing",
                "warning",
                action="建议先运行 ingest-candidate-review，把采纳/驳回/待修正原因沉淀进记忆。",
            )
        accepted = candidate_review.get("accepted_variant_ids", [])
        rejected = candidate_review.get("rejected_variant_ids", [])
        pending = candidate_review.get("pending_variant_ids", [])
        evidence = [f"采纳：{len(accepted)}", f"驳回：{len(rejected)}", f"待验证：{len(pending)}"]
        if not accepted:
            return DeliveryReadinessFinding("REVIEW", "候选图评审回写", "no_accepted_variant", "warning", evidence, "交付前请明确至少一个采纳方向或说明本次不依赖生成候选图。")
        return DeliveryReadinessFinding("REVIEW", "候选图评审回写", "pass", "info", evidence=evidence)

    @staticmethod
    def _psd_handoff_check(psd_handoff_plan: dict[str, Any] | None) -> DeliveryReadinessFinding:
        if not psd_handoff_plan:
            return DeliveryReadinessFinding(
                "PSD",
                "PSD/切图交接计划",
                "missing",
                "warning",
                action="如需 PSD 或切图，请先运行 create-psd-handoff-plan。",
            )
        assets = psd_handoff_plan.get("assets", [])
        slicing_tasks = psd_handoff_plan.get("slicing_tasks", [])
        warnings = psd_handoff_plan.get("warnings", [])
        evidence = [f"交接资产：{len(assets)}", f"切图任务：{len(slicing_tasks)}", f"计划警告：{len(warnings)}"]
        if warnings:
            return DeliveryReadinessFinding("PSD", "PSD/切图交接计划", "has_warnings", "warning", evidence + warnings[:3], "先处理 PSD 交接计划里的警告。")
        if not slicing_tasks:
            return DeliveryReadinessFinding("PSD", "PSD/切图交接计划", "no_slicing_tasks", "warning", evidence, "请补充切图任务或确认本次只交整图。")
        return DeliveryReadinessFinding("PSD", "PSD/切图交接计划", "pass", "info", evidence=evidence)

    @staticmethod
    def _psd_package_check(psd_handoff_package: dict[str, Any] | None) -> DeliveryReadinessFinding:
        if not psd_handoff_package:
            return DeliveryReadinessFinding(
                "PSD_STAGE",
                "PSD 交接 staging",
                "missing",
                "warning",
                action="建议运行 prepare-psd-handoff-package，把候选图和确认单放进安全 staging。",
            )
        items = psd_handoff_package.get("items", [])
        warnings = psd_handoff_package.get("warnings", [])
        evidence = [f"staging 项：{len(items)}", f"警告：{len(warnings)}", f"目录：{psd_handoff_package.get('staged_root', '未知')}"]
        if warnings:
            return DeliveryReadinessFinding("PSD_STAGE", "PSD 交接 staging", "has_warnings", "warning", evidence + warnings[:3], "先复核 PSD staging 警告，尤其是远程引用或缺失文件。")
        return DeliveryReadinessFinding("PSD_STAGE", "PSD 交接 staging", "pass", "info", evidence=evidence)

    @staticmethod
    def _psd_slice_spec_check(psd_slice_spec_report: dict[str, Any] | None) -> DeliveryReadinessFinding:
        if not psd_slice_spec_report:
            return DeliveryReadinessFinding(
                "PSD_SPEC",
                "PSD/切图规格核对",
                "missing",
                "warning",
                action="进入 PSD 精修或切图前建议运行 create-psd-slice-spec-report，核对图层、切图任务和命名样例。",
            )
        status = str(psd_slice_spec_report.get("status", "unknown"))
        blockers = psd_slice_spec_report.get("blockers", [])
        warnings = psd_slice_spec_report.get("warnings", [])
        layer_groups = psd_slice_spec_report.get("required_layer_groups", [])
        slicing_tasks = psd_slice_spec_report.get("slicing_tasks", [])
        naming_examples = psd_slice_spec_report.get("naming_examples", [])
        evidence = [
            f"状态：{status}",
            f"必要图层组：{len(layer_groups)}",
            f"切图任务：{len(slicing_tasks)}",
            f"命名样例：{len(naming_examples)}",
        ]
        if blockers or status == "blocked":
            return DeliveryReadinessFinding(
                "PSD_SPEC",
                "PSD/切图规格核对",
                "blocked",
                "blocker",
                evidence + blockers[:3],
                "先处理 PSD/切图规格核对中的阻塞项，再进入 PSD 或切图。",
            )
        if warnings or status == "needs_designer_review":
            return DeliveryReadinessFinding(
                "PSD_SPEC",
                "PSD/切图规格核对",
                "needs_review",
                "warning",
                evidence + warnings[:3],
                "设计师需复核图层组、切图任务和命名样例后再进入 PSD/切图。",
            )
        return DeliveryReadinessFinding("PSD_SPEC", "PSD/切图规格核对", "pass", "info", evidence=evidence)

    @staticmethod
    def _delivery_staging_check(delivery_package: DeliveryPreparation | None) -> DeliveryReadinessFinding:
        if not delivery_package:
            return DeliveryReadinessFinding(
                "DELIVERY_STAGE",
                "正式交付 staging",
                "missing",
                "warning",
                action="正式对外交付前建议运行 prepare-delivery-package 生成安全 staging 包。",
            )
        evidence = [f"文件数：{len(delivery_package.files)}", f"目录：{delivery_package.staged_root}", f"警告：{len(delivery_package.warnings)}"]
        if delivery_package.warnings:
            return DeliveryReadinessFinding("DELIVERY_STAGE", "正式交付 staging", "has_warnings", "warning", evidence + delivery_package.warnings[:3], "先处理交付 staging 警告，再对外发送。")
        if not delivery_package.files:
            return DeliveryReadinessFinding("DELIVERY_STAGE", "正式交付 staging", "empty", "blocker", evidence, "staging 包没有文件，不能进入正式交付。")
        return DeliveryReadinessFinding("DELIVERY_STAGE", "正式交付 staging", "pass", "info", evidence=evidence)

    @staticmethod
    def _safety_gate_check() -> DeliveryReadinessFinding:
        return DeliveryReadinessFinding(
            check_id="SAFETY",
            title="安全门控",
            status="pass",
            severity="info",
            evidence=["报告只做检查，不发布 Meegle、不流转节点、不覆盖正式文件。"],
            action="正式发送、覆盖文件或工作流流转仍需设计师显式确认。",
        )

    @staticmethod
    def _approval_checklist(findings: list[DeliveryReadinessFinding]) -> list[str]:
        checklist = [
            "我已复核需求摘要、尺寸、交付物和未闭合问题。",
            "我已确认 K3 假设不会被当作正式风格结论。",
            "我已检查候选图评审、PSD 图层/切图计划和 staging 包。",
            "我确认本次报告未自动发布、未流转工作项、未覆盖正式文件。",
        ]
        if any(finding.severity == "blocker" for finding in findings):
            checklist.insert(0, "先处理全部阻塞项，再进入正式交付确认。")
        else:
            checklist.append("如需对外发送或 Meegle 回写，再单独执行带确认门控的发布命令。")
        return checklist

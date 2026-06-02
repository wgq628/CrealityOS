from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import ProjectProfile, SessionResumeReport, SessionSnapshot, StyleCard


class SessionResumeBuilder:
    IMPORTANT_ARTIFACTS = (
        "制作任务单.md",
        "中文提示词.md",
        "交付检查.md",
        "design_brief.md",
        "requirement_clarification_report.md",
        "requirement_change_report.md",
        "style_transfer_report.md",
        "style_alignment_report.md",
        "design_decision_record.md",
        "creative_pack.md",
        "image_generation_batch.md",
        "candidate_evaluation.md",
        "generated_gallery.md",
        "candidate_style_drift_report.md",
        "candidate_comparison_matrix.md",
        "candidate_review.md",
        "psd_handoff_plan.md",
        "psd_handoff_package.md",
        "psd_slice_spec_report.md",
        "delivery_readiness_report.md",
        "design_workflow_plan.md",
        "designer_review_packet.md",
        "latest_learning_digest.md",
        "latest_audit.md",
        "latest_transition.md",
    )

    def build(
        self,
        project_key: str,
        snapshot: SessionSnapshot,
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
        recent_review_notes: list[str],
        decision_payload: dict[str, Any] | None,
        style_alignment_payload: dict[str, Any] | None,
    ) -> SessionResumeReport:
        artifact_index = self._artifact_index(snapshot)
        unresolved = list(snapshot.unresolved_questions)
        if decision_payload:
            unresolved.extend(decision_payload.get("open_questions", []))
        if profile and not profile.default_sizes:
            unresolved.append("项目档案尚未补充默认尺寸")
        status = self._status(snapshot, artifact_index, unresolved, style_alignment_payload)
        return SessionResumeReport(
            project_key=project_key,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            active_work_item_id=snapshot.active_work_item_id,
            active_title=snapshot.title,
            same_category=snapshot.same_category,
            output_dir=snapshot.output_dir,
            key_decisions=self._key_decisions(snapshot, decision_payload, style_card, profile),
            unresolved_questions=list(dict.fromkeys(item for item in unresolved if item)),
            artifact_index=artifact_index,
            style_gate_status=str((style_alignment_payload or {}).get("status", "missing")),
            decision_summary=self._decision_summary(decision_payload),
            recent_feedback=recent_review_notes,
            next_commands=self._next_commands(project_key, snapshot, artifact_index, unresolved, style_alignment_payload),
            safety_notes=self._safety_notes(style_alignment_payload),
        )

    @staticmethod
    def render_markdown(report: SessionResumeReport) -> str:
        lines = [
            f"# 会话恢复简报 - {report.project_key}",
            "",
            f"- 生成时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            f"- 活跃工作项：`{report.active_work_item_id or '无'}`",
            f"- 标题：{report.active_title}",
            f"- 同品类底座：`{report.same_category}`",
            f"- 输出目录：`{report.output_dir or '无'}`",
            f"- 风格闸门：`{report.style_gate_status}`",
            "",
            "## 先接着做什么",
        ]
        lines.extend(f"- `{item}`" for item in report.next_commands)
        lines.extend(["", "## 关键决策", *(f"- {item}" for item in report.key_decisions or ["无"])])
        lines.extend(["", "## 决策摘要", *(f"- {item}" for item in report.decision_summary or ["无"])])
        lines.extend(["", "## 未闭合问题", *(f"- {item}" for item in report.unresolved_questions or ["无"])])
        lines.append("")
        lines.append("## 产物索引")
        for key, value in report.artifact_index.items():
            lines.append(f"- {key}: `{value or '缺失'}`")
        lines.extend(["", "## 最近反馈", *(f"- {item}" for item in report.recent_feedback or ["暂无近期反馈"])])
        lines.extend(["", "## 安全说明", *(f"- {item}" for item in report.safety_notes)])
        return "\n".join(lines)

    @classmethod
    def _artifact_index(cls, snapshot: SessionSnapshot) -> dict[str, str | None]:
        artifacts: dict[str, str | None] = {Path(name).stem: None for name in cls.IMPORTANT_ARTIFACTS}
        output_dir = Path(snapshot.output_dir)
        candidates: list[Path] = []
        if output_dir.exists():
            candidates.extend(path for path in output_dir.rglob("*.md") if path.name in cls.IMPORTANT_ARTIFACTS)
        for raw in snapshot.last_artifacts:
            path = Path(raw)
            if path.exists() and path.name in cls.IMPORTANT_ARTIFACTS:
                candidates.append(path)
        for path in candidates:
            artifacts[path.stem] = str(path)
        return artifacts

    @staticmethod
    def _status(
        snapshot: SessionSnapshot,
        artifact_index: dict[str, str | None],
        unresolved: list[str],
        style_alignment_payload: dict[str, Any] | None,
    ) -> str:
        if style_alignment_payload and style_alignment_payload.get("status") == "blocked":
            return "blocked_by_style_gate"
        if unresolved:
            return "needs_clarification"
        if artifact_index.get("delivery_readiness_report"):
            return "ready_for_delivery_review"
        if artifact_index.get("candidate_review"):
            return "candidate_reviewed"
        if artifact_index.get("creative_pack"):
            return "creative_pack_ready"
        return "snapshot_only"

    @staticmethod
    def _key_decisions(
        snapshot: SessionSnapshot,
        decision_payload: dict[str, Any] | None,
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
    ) -> list[str]:
        decisions = list(snapshot.key_decisions)
        if decision_payload:
            for item in decision_payload.get("decisions", [])[:5]:
                statement = item.get("statement")
                level = item.get("level")
                if statement:
                    decisions.append(f"[{level}] {statement}")
        if profile:
            decisions.extend(f"[K1/profile] {item}" for item in profile.must_have_rules[:3])
        if style_card:
            decisions.extend(f"[{rule.level}] {rule.statement}" for rule in style_card.rules[:3])
        return list(dict.fromkeys(decisions))

    @staticmethod
    def _decision_summary(decision_payload: dict[str, Any] | None) -> list[str]:
        if not decision_payload:
            return ["未找到 design_decision_record，请先运行 create-design-decision-record。"]
        items: list[str] = []
        for decision in decision_payload.get("decisions", [])[:6]:
            category = decision.get("category", "决策")
            statement = decision.get("statement", "")
            requires = "需确认" if decision.get("requires_designer_confirmation") else "已可用"
            if statement:
                items.append(f"{category}：{statement}（{requires}）")
        return items

    @staticmethod
    def _next_commands(
        project_key: str,
        snapshot: SessionSnapshot,
        artifact_index: dict[str, str | None],
        unresolved: list[str],
        style_alignment_payload: dict[str, Any] | None,
    ) -> list[str]:
        commands = [
            f"python -m agent.cli create-design-decision-record --project-key {project_key} --work-item-id {snapshot.active_work_item_id}",
            f"python -m agent.cli create-designer-review-packet --project-key {project_key} --work-item-id {snapshot.active_work_item_id}",
        ]
        if unresolved:
            commands.insert(0, f"python -m agent.cli create-requirement-clarification-report --project-key {project_key} --work-item-id {snapshot.active_work_item_id}")
        if not artifact_index.get("style_transfer_report"):
            commands.insert(0, f"python -m agent.cli create-style-transfer-report --project-key {project_key} --work-item-id {snapshot.active_work_item_id}")
        if not artifact_index.get("style_alignment_report") or (style_alignment_payload and style_alignment_payload.get("status") == "blocked"):
            commands.insert(0, f"python -m agent.cli create-style-alignment-report --project-key {project_key} --work-item-id {snapshot.active_work_item_id}")
        if artifact_index.get("image_generation_batch") and not artifact_index.get("generated_gallery"):
            commands.append(f"python -m agent.cli create-image-generation-jobs --project-key {project_key} --work-item-id {snapshot.active_work_item_id} --variant V01")
        if artifact_index.get("generated_gallery") and not artifact_index.get("candidate_style_drift_report"):
            commands.append(f"python -m agent.cli create-candidate-style-drift-report --project-key {project_key} --work-item-id {snapshot.active_work_item_id}")
        if artifact_index.get("generated_gallery") and not artifact_index.get("candidate_comparison_matrix"):
            commands.append(f"python -m agent.cli create-candidate-comparison-matrix --project-key {project_key} --work-item-id {snapshot.active_work_item_id}")
        if artifact_index.get("psd_handoff_plan") and not artifact_index.get("psd_slice_spec_report"):
            commands.append(f"python -m agent.cli create-psd-slice-spec-report --project-key {project_key} --work-item-id {snapshot.active_work_item_id}")
        if not artifact_index.get("design_workflow_plan"):
            commands.append(f"python -m agent.cli create-design-workflow-plan --project-key {project_key} --work-item-id {snapshot.active_work_item_id}")
        commands.append(f"python -m agent.cli metacognition-audit --project-key {project_key}")
        return list(dict.fromkeys(commands))

    @staticmethod
    def _safety_notes(style_alignment_payload: dict[str, Any] | None) -> list[str]:
        notes = [
            "恢复简报只读取和生成本地文件，不发布 Meegle、不流转工作项、不覆盖正式资产。",
            "继续执行出图、PSD/切图、Meegle 回写或正式交付前仍需设计师确认。",
            "K3 假设必须继续保持为待验证，不得在恢复后自动升级。",
        ]
        if style_alignment_payload and style_alignment_payload.get("status") == "blocked":
            notes.insert(0, "风格闸门当前阻塞，先修正风格风险再继续出图。")
        return notes

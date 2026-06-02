from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.artifact_resolver import IMPORTANT_ARTIFACT_FILES, collect_artifacts
from agent.models import DesignWorkflowPlan, DesignWorkflowStep


class DesignWorkflowPlanner:
    IMPORTANT_FILES = IMPORTANT_ARTIFACT_FILES

    def build(
        self,
        project_key: str,
        work_item_id: str,
        title: str,
        output_dir: Path | None,
        artifact_index: dict[str, str | None],
        payloads: dict[str, dict[str, Any] | None],
    ) -> DesignWorkflowPlan:
        steps = [
            self._step("brief", "需求理解", "生成设计师制作任务单", "design_brief", f"python -m agent.cli process-feishu-requirement --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads),
            self._clarification_step(project_key, work_item_id, artifact_index, payloads),
            self._step("creative_pack", "创作准备", "生成系统创作状态", "creative_pack", f"python -m agent.cli process-feishu-requirement --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["brief"]),
            self._report_step("style_transfer", "创作准备", "后台确认风格迁移边界", "style_transfer_report", f"python -m agent.cli create-style-transfer-report --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["creative_pack"]),
            self._report_step("style_alignment", "创作准备", "后台检查风格一致性", "style_alignment_report", f"python -m agent.cli create-style-alignment-report --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["creative_pack"]),
            self._step("decision_record", "创作准备", "后台记录设计依据", "design_decision_record", f"python -m agent.cli create-design-decision-record --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["creative_pack"]),
            self._step("image_batch", "出图准备", "生成中文提示词", "image_generation_batch", f"python -m agent.cli prepare-image-direction --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["style_alignment"]),
            self._step("image_jobs", "出图准备", "准备待确认出图任务", "image_generation_jobs", f"python -m agent.cli create-image-generation-jobs --project-key {project_key} --work-item-id {work_item_id} --variant V01", artifact_index, payloads, depends_on=["image_batch"], requires_confirmation=True),
            self._step("image_execution_package", "出图准备", "准备人工出图执行包", "image_execution_package", f"python -m agent.cli prepare-image-execution-package --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["image_jobs"], requires_confirmation=True),
            self._step("generation_results", "候选评审", "登记生成图与候选索引", "image_generation_results", f"python -m agent.cli register-image-results --project-key {project_key} --work-item-id {work_item_id} --results-file <generation_results.json>", artifact_index, payloads, depends_on=["image_execution_package"]),
            self._report_step("candidate_drift", "候选评审", "检查候选图风格偏移", "candidate_style_drift_report", f"python -m agent.cli create-candidate-style-drift-report --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["generation_results"]),
            self._report_step("candidate_comparison", "候选评审", "对比候选方案并给出建议", "candidate_comparison_matrix", f"python -m agent.cli create-candidate-comparison-matrix --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["generation_results", "candidate_drift"]),
            self._step("candidate_review", "候选评审", "回写设计师候选评审", "candidate_review", f"python -m agent.cli ingest-candidate-review --project-key {project_key} --category <same-category> --work-item-id {work_item_id} --review-file <candidate_review.json>", artifact_index, payloads, depends_on=["candidate_comparison"], requires_confirmation=True),
            self._step("psd_plan", "PSD/切图", "生成 PSD 交接计划", "psd_handoff_plan", f"python -m agent.cli create-psd-handoff-plan --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["candidate_review"], requires_confirmation=True),
            self._step("psd_package", "PSD/切图", "准备 PSD 安全 staging 包", "psd_handoff_package", f"python -m agent.cli prepare-psd-handoff-package --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["psd_plan"], requires_confirmation=True),
            self._report_step("psd_spec", "PSD/切图", "核对 PSD/切图规格", "psd_slice_spec_report", f"python -m agent.cli create-psd-slice-spec-report --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["psd_plan"]),
            self._report_step("delivery_readiness", "交付确认", "生成交付检查单", "delivery_readiness_report", f"python -m agent.cli prepare-delivery-review --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["psd_spec"], requires_confirmation=True),
            self._step("review_packet", "交付确认", "生成设计师评审包", "designer_review_packet", f"python -m agent.cli create-designer-review-packet --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["delivery_readiness"]),
            self._step("meegle_writeback", "飞书协同", "准备 Meegle 回写草稿", "meegle_writeback_draft", f"python -m agent.cli create-meegle-writeback-draft --project-key {project_key} --work-item-id {work_item_id}", artifact_index, payloads, depends_on=["review_packet"], requires_confirmation=True),
        ]
        steps = self._resolve_waiting_steps(steps)
        blockers = [item for step in steps if step.status == "blocked" for item in step.evidence]
        ready_steps = [step for step in steps if step.status == "ready"]
        next_commands = [step.command for step in ready_steps[:3]]
        status = self._status(steps, blockers)
        return DesignWorkflowPlan(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            output_dir=str(output_dir) if output_dir else None,
            steps=steps,
            blockers=list(dict.fromkeys(blockers)),
            next_commands=next_commands or ["先生成或恢复创作包，再刷新设计工作流计划。"],
            safety_notes=[
                "工作流计划只读本地产物并写入本地计划文件，不自动发布 Meegle。",
                "所有出图、PSD 导出、正式交付、覆盖文件和工作流流转仍需设计师显式确认。",
                "K3 待验证风格只能作为探索项，不能因为计划推进而自动升级为 K1/K2。",
            ],
            artifact_index=artifact_index,
        )

    @staticmethod
    def render_markdown(plan: DesignWorkflowPlan) -> str:
        lines = [
            f"# 设计工作流计划 - {plan.title}",
            "",
            f"- 项目：`{plan.project_key}`",
            f"- 工作项：`{plan.work_item_id}`",
            f"- 创建时间：`{plan.created_at}`",
            f"- 状态：`{plan.status}`",
            f"- 输出目录：`{plan.output_dir or '未绑定'}`",
            "",
            "## 下一步命令",
            *(f"- `{command}`" for command in plan.next_commands),
            "",
            "## 步骤看板",
            "| 阶段 | 步骤 | 状态 | 命令 |",
            "|---|---|---|---|",
        ]
        for step in plan.steps:
            lines.append(f"| {step.phase} | {step.title} | `{step.status}` | `{step.command}` |")
        lines.extend(["", "## 关键证据"])
        for step in plan.steps:
            if step.evidence:
                lines.append(f"### {step.step_id} {step.title}")
                lines.extend(f"- {item}" for item in step.evidence)
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in plan.blockers or ["无"])])
        lines.extend(["", "## 产物索引"])
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in plan.artifact_index.items())
        lines.extend(["", "## 安全说明", *(f"- {item}" for item in plan.safety_notes)])
        return "\n".join(lines)

    @classmethod
    def collect_artifacts(cls, output_dir: Path | None, extra_artifacts: list[str] | None = None) -> dict[str, str | None]:
        return collect_artifacts(output_dir, extra_artifacts)

    def _step(
        self,
        step_id: str,
        phase: str,
        title: str,
        artifact_key: str,
        command: str,
        artifact_index: dict[str, str | None],
        payloads: dict[str, dict[str, Any] | None],
        depends_on: list[str] | None = None,
        requires_confirmation: bool = False,
    ) -> DesignWorkflowStep:
        artifact = artifact_index.get(artifact_key)
        status = "done" if artifact else "ready"
        evidence = [f"产物：{artifact}"] if artifact else []
        payload = payloads.get(artifact_key)
        if payload and payload.get("status"):
            evidence.append(f"状态：{payload.get('status')}")
        return DesignWorkflowStep(
            step_id=step_id,
            phase=phase,
            title=title,
            status=status,
            command=command,
            depends_on=depends_on or [],
            artifacts=[artifact] if artifact else [],
            evidence=evidence,
            requires_designer_confirmation=requires_confirmation,
        )

    def _report_step(
        self,
        step_id: str,
        phase: str,
        title: str,
        artifact_key: str,
        command: str,
        artifact_index: dict[str, str | None],
        payloads: dict[str, dict[str, Any] | None],
        depends_on: list[str] | None = None,
        requires_confirmation: bool = False,
    ) -> DesignWorkflowStep:
        step = self._step(step_id, phase, title, artifact_key, command, artifact_index, payloads, depends_on, requires_confirmation)
        payload = payloads.get(artifact_key) or {}
        status = str(payload.get("status", ""))
        blockers = payload.get("blockers") or payload.get("blocking_items") or []
        if step.artifacts and (status == "blocked" or blockers):
            step.status = "blocked"
            step.evidence.extend(str(item) for item in blockers[:4])
        elif step.artifacts and status in {"needs_designer_review", "needs_designer_decision", "needs_designer_confirmation"}:
            step.status = "needs_designer_confirmation"
        return step

    def _clarification_step(
        self,
        project_key: str,
        work_item_id: str,
        artifact_index: dict[str, str | None],
        payloads: dict[str, dict[str, Any] | None],
    ) -> DesignWorkflowStep:
        step = self._step(
            "clarification",
            "需求理解",
            "闭合需求澄清问题",
            "requirement_clarification_report",
            f"python -m agent.cli create-requirement-clarification-report --project-key {project_key} --work-item-id {work_item_id}",
            artifact_index,
            payloads,
            depends_on=["brief"],
            requires_confirmation=True,
        )
        payload = payloads.get("requirement_clarification_report") or {}
        questions = payload.get("questions", [])
        blockers = [item for item in questions if item.get("severity") == "blocker"] if isinstance(questions, list) else []
        if blockers:
            step.status = "blocked"
            step.evidence.extend(str(item.get("question")) for item in blockers[:4] if item.get("question"))
        elif questions and not payload.get("safe_to_continue", False):
            step.status = "needs_designer_confirmation"
            step.evidence.append(f"待澄清问题：{len(questions)}")
        return step

    @staticmethod
    def _resolve_waiting_steps(steps: list[DesignWorkflowStep]) -> list[DesignWorkflowStep]:
        by_id = {step.step_id: step for step in steps}
        for step in steps:
            if step.status != "ready":
                continue
            missing = [dep for dep in step.depends_on if dep in by_id and by_id[dep].status not in {"done", "needs_designer_confirmation"}]
            if missing:
                step.status = "waiting"
                step.evidence.append("等待前置步骤：" + "、".join(missing))
        return steps

    @staticmethod
    def _status(steps: list[DesignWorkflowStep], blockers: list[str]) -> str:
        if blockers:
            return "blocked"
        if any(step.status == "ready" for step in steps):
            return "in_progress"
        if any(step.status == "needs_designer_confirmation" for step in steps):
            return "needs_designer_confirmation"
        return "ready_for_meegle_writeback_or_delivery"

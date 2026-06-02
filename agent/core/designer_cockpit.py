from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import DesignerCockpitReport, SessionSnapshot


class DesignerCockpitBuilder:
    def build(
        self,
        project_key: str,
        work_item_id: str | None,
        snapshot: SessionSnapshot | None,
        output_dir: Path | None,
        artifact_index: dict[str, str | None],
        payloads: dict[str, dict[str, Any] | None],
        learning_digest: dict[str, Any] | None = None,
    ) -> DesignerCockpitReport:
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        title = snapshot.title if snapshot else effective_work_item_id or "未绑定工作项"
        blockers = self._blockers(payloads)
        confirmations = self._confirmations(payloads, artifact_index)
        next_commands = self._next_commands(project_key, effective_work_item_id, payloads, artifact_index, snapshot)
        status = self._status(blockers, confirmations, artifact_index, payloads, snapshot)
        summary = self._summary(title, status, blockers, confirmations, artifact_index, learning_digest)
        return DesignerCockpitReport(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            title=title,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            summary=summary,
            output_dir=str(output_dir) if output_dir else None,
            blockers=blockers,
            confirmations=confirmations,
            artifact_index=artifact_index,
            next_commands=next_commands,
            safety_notes=[
                "驾驶舱只读取本地状态并写入本地报告，不发布 Meegle、不执行出图、不打开 Photoshop。",
                "所有对外发送、工作流流转、正式交付和文件覆盖仍需单独确认。",
                "K3 待验证风格只能作为探索边界，不能因为流程推进自动升级为确定规则。",
            ],
        )

    @staticmethod
    def render_markdown(report: DesignerCockpitReport) -> str:
        lines = [
            f"# 设计师副驾驾驶舱 - {report.title}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 工作项：`{report.work_item_id or '未绑定'}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            f"- 输出目录：`{report.output_dir or '未绑定'}`",
            "",
            "## 当前结论",
            report.summary,
            "",
            "## 下一步命令",
            *(f"- `{command}`" for command in report.next_commands),
            "",
            "## 阻塞项",
            *(f"- {item}" for item in report.blockers or ["无"]),
            "",
            "## 待设计师确认",
            *(f"- {item}" for item in report.confirmations or ["无"]),
            "",
            "## 关键产物",
        ]
        for key, value in report.artifact_index.items():
            lines.append(f"- {key}: `{value or '缺失'}`")
        lines.extend(["", "## 安全说明", *(f"- {item}" for item in report.safety_notes)])
        return "\n".join(lines)

    @staticmethod
    def _blockers(payloads: dict[str, dict[str, Any] | None]) -> list[str]:
        blockers: list[str] = []
        for key in ("style_alignment_report", "delivery_readiness_report", "candidate_comparison_matrix", "design_workflow_plan"):
            payload = payloads.get(key) or {}
            for field in ("blockers", "blocking_items"):
                values = payload.get(field)
                if isinstance(values, list):
                    blockers.extend(str(item) for item in values if item)
        return list(dict.fromkeys(blockers))

    @staticmethod
    def _confirmations(
        payloads: dict[str, dict[str, Any] | None],
        artifact_index: dict[str, str | None],
    ) -> list[str]:
        confirmations: list[str] = []
        workflow = payloads.get("design_workflow_plan") or {}
        for step in workflow.get("steps", []) if isinstance(workflow.get("steps"), list) else []:
            if not isinstance(step, dict):
                continue
            if step.get("requires_designer_confirmation") and step.get("status") in {"ready", "needs_designer_confirmation", "done"}:
                confirmations.append(f"{step.get('phase', '流程')} / {step.get('title', step.get('step_id', '待确认步骤'))}")
        readiness = payloads.get("delivery_readiness_report") or {}
        for item in readiness.get("approval_checklist", []) if isinstance(readiness.get("approval_checklist"), list) else []:
            confirmations.append(str(item))
        if artifact_index.get("image_generation_jobs") and not artifact_index.get("image_generation_results"):
            confirmations.append("已准备出图任务，执行真实出图前需要确认 generation_approval_ticket。")
        if artifact_index.get("meegle_writeback_draft"):
            confirmations.append("已生成 Meegle 回写草稿，发布前需要确认发布门控。")
        return list(dict.fromkeys(confirmations))

    @staticmethod
    def _next_commands(
        project_key: str,
        work_item_id: str | None,
        payloads: dict[str, dict[str, Any] | None],
        artifact_index: dict[str, str | None],
        snapshot: SessionSnapshot | None,
    ) -> list[str]:
        workflow = payloads.get("design_workflow_plan") or {}
        commands = workflow.get("next_commands")
        if isinstance(commands, list) and commands:
            return [str(command) for command in commands[:3]]
        if not artifact_index.get("creative_pack"):
            return [
                f"python -m agent.cli resume-session --project-key {project_key}"
                if snapshot
                else f"python -m agent.cli build-local-creative-pack --project-key {project_key} --work-item-id <id> --title <title> --requirement-file <req.md>"
            ]
        if not artifact_index.get("design_workflow_plan") and work_item_id:
            return [f"python -m agent.cli create-design-workflow-plan --project-key {project_key} --work-item-id {work_item_id}"]
        if not artifact_index.get("designer_review_packet") and work_item_id:
            return [f"python -m agent.cli create-designer-review-packet --project-key {project_key} --work-item-id {work_item_id}"]
        return [f"python -m agent.cli doctor --project-key {project_key}"]

    @staticmethod
    def _status(
        blockers: list[str],
        confirmations: list[str],
        artifact_index: dict[str, str | None],
        payloads: dict[str, dict[str, Any] | None],
        snapshot: SessionSnapshot | None,
    ) -> str:
        if blockers:
            return "blocked"
        workflow = payloads.get("design_workflow_plan") or {}
        if workflow.get("status"):
            return str(workflow["status"])
        readiness = payloads.get("delivery_readiness_report") or {}
        if readiness.get("status"):
            return str(readiness["status"])
        if confirmations:
            return "needs_designer_confirmation"
        if not snapshot and not artifact_index.get("creative_pack"):
            return "draft"
        if artifact_index.get("creative_pack"):
            return "in_progress"
        return "draft"

    @staticmethod
    def _summary(
        title: str,
        status: str,
        blockers: list[str],
        confirmations: list[str],
        artifact_index: dict[str, str | None],
        learning_digest: dict[str, Any] | None,
    ) -> str:
        existing = sum(1 for value in artifact_index.values() if value)
        parts = [f"`{title}` 当前状态为 `{status}`，已找到 {existing} 个关键产物。"]
        if blockers:
            parts.append(f"优先处理 {len(blockers)} 个阻塞项。")
        elif confirmations:
            parts.append(f"当前主要动作是完成 {len(confirmations)} 个设计师确认。")
        elif not artifact_index.get("creative_pack"):
            parts.append("当前还没有创作包，建议先建立或恢复工作项上下文。")
        else:
            parts.append("当前没有检测到硬阻塞，可以按下一步命令继续推进。")
        if learning_digest:
            checklist = learning_digest.get("next_time_checklist") or []
            if checklist:
                parts.append(f"学习摘要已有 {len(checklist)} 条下次检查项可复用。")
        return "".join(parts)

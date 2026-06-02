from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent.models import MeegleTransitionDraft, MeegleTransitionReceipt


TRANSITION_CONFIRM_TOKEN = "TRANSITION_MEEGLE_WORKFLOW"


class MeegleTransitionGate:
    VALID_ACTIONS = {"confirm", "rollback"}

    def build_draft(
        self,
        project_key: str,
        work_item_id: str,
        action: str,
        node_id: str | None,
        node_names: list[str] | None,
        rollback_reason: str | None,
    ) -> MeegleTransitionDraft:
        action = action.lower()
        warnings = self._validate(action, node_id, node_names, rollback_reason)
        command = self.command_preview(project_key, work_item_id, action, node_id, node_names, rollback_reason)
        return MeegleTransitionDraft(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            action=action,
            node_id=node_id,
            node_names=node_names or [],
            rollback_reason=rollback_reason,
            command_preview=command,
            warnings=warnings,
            approval_checklist=self._approval_checklist(action),
        )

    def validate_confirmation(self, execute: bool, confirm_token: str | None, approval_file: str | None) -> tuple[bool, str, list[str]]:
        warnings: list[str] = []
        if confirm_token == TRANSITION_CONFIRM_TOKEN:
            return True, "token", warnings
        if approval_file:
            path = Path(approval_file)
            if not path.exists():
                warnings.append(f"确认文件不存在：{approval_file}")
            else:
                content = path.read_text(encoding="utf-8")
                if "[x] 允许流转 Meegle 工作项" in content or "[X] 允许流转 Meegle 工作项" in content:
                    return True, "approval_file", warnings
                warnings.append("确认文件未勾选“允许流转 Meegle 工作项”。")
        if execute:
            raise PermissionError(
                f"Workflow transition requires --confirm-token {TRANSITION_CONFIRM_TOKEN} or an approval file with '[x] 允许流转 Meegle 工作项'."
            )
        return False, "dry-run", warnings

    @staticmethod
    def render_draft_markdown(draft: MeegleTransitionDraft) -> str:
        return "\n".join(
            [
                f"# Meegle 工作流流转草稿 - {draft.work_item_id}",
                "",
                f"- 项目：`{draft.project_key}`",
                f"- 创建时间：`{draft.created_at}`",
                f"- 动作：`{draft.action}`",
                f"- 节点 ID：`{draft.node_id or '无'}`",
                f"- 节点名称：{', '.join(draft.node_names) if draft.node_names else '无'}",
                f"- 回滚原因：{draft.rollback_reason or '无'}",
                "",
                "## 命令预览",
                "```bash",
                " ".join(draft.command_preview),
                "```",
                "",
                "## 警告",
                *(f"- {item}" for item in draft.warnings or ["无"]),
                "",
                "## 流转前确认",
                *(f"- [ ] {item}" for item in draft.approval_checklist),
            ]
        )

    @staticmethod
    def render_approval_ticket(draft: MeegleTransitionDraft) -> str:
        return "\n".join(
            [
                f"# Meegle 工作流流转确认单 - {draft.work_item_id}",
                "",
                f"- 项目：`{draft.project_key}`",
                f"- 动作：`{draft.action}`",
                f"- 节点：`{draft.node_id or ', '.join(draft.node_names) or '未指定'}`",
                "",
                "## 安全说明",
                "- 当前只生成流转草稿，未调用 Meegle 工作流接口。",
                "- 流转可能改变需求状态，请确认节点、必填项和交付物已准备好。",
                "- 真实流转必须由设计师显式确认。",
                "",
                "## 确认项",
                *(f"- [ ] {item}" for item in draft.approval_checklist),
                "",
                "## 结果",
                "- [ ] 允许流转 Meegle 工作项",
                "- [ ] 暂不流转，继续修改设计产物或草稿",
            ]
        )

    @staticmethod
    def build_receipt(
        draft: MeegleTransitionDraft,
        executed: bool,
        confirmation_method: str,
        response: dict,
        warnings: list[str],
    ) -> MeegleTransitionReceipt:
        return MeegleTransitionReceipt(
            project_key=draft.project_key,
            work_item_id=draft.work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            action=draft.action,
            mode="execute" if executed else "dry-run",
            executed=executed,
            confirmation_method=confirmation_method,
            command_preview=draft.command_preview,
            response=response,
            warnings=warnings,
        )

    @staticmethod
    def render_receipt_markdown(receipt: MeegleTransitionReceipt) -> str:
        return "\n".join(
            [
                f"# Meegle 工作流流转回执 - {receipt.work_item_id}",
                "",
                f"- 项目：`{receipt.project_key}`",
                f"- 创建时间：`{receipt.created_at}`",
                f"- 动作：`{receipt.action}`",
                f"- 模式：`{receipt.mode}`",
                f"- 已执行：{'是' if receipt.executed else '否'}",
                f"- 确认方式：`{receipt.confirmation_method}`",
                "",
                "## 命令预览",
                "```bash",
                " ".join(receipt.command_preview),
                "```",
                "",
                "## 响应",
                "```json",
                str(receipt.response),
                "```",
                "",
                "## 警告",
                *(f"- {item}" for item in receipt.warnings or ["无"]),
            ]
        )

    @staticmethod
    def command_preview(
        project_key: str,
        work_item_id: str,
        action: str,
        node_id: str | None,
        node_names: list[str] | None,
        rollback_reason: str | None,
    ) -> list[str]:
        command = [
            "meegle",
            "workflow",
            "transition",
            "--project-key",
            project_key,
            "--work-item-id",
            work_item_id,
            "--action",
            action,
        ]
        if node_id:
            command.extend(["--node-id", node_id])
        if node_names:
            command.extend(["--node-ids", ",".join(node_names)])
        if rollback_reason:
            command.extend(["--rollback-reason", rollback_reason])
        command.extend(["--format", "json"])
        return command

    def _validate(self, action: str, node_id: str | None, node_names: list[str] | None, rollback_reason: str | None) -> list[str]:
        warnings: list[str] = []
        if action not in self.VALID_ACTIONS:
            raise ValueError(f"Unsupported workflow action: {action}")
        if not node_id and not node_names:
            raise ValueError("A node_id or at least one node name is required for workflow transition.")
        if action == "rollback" and not rollback_reason:
            warnings.append("rollback 通常需要填写 rollback_reason。")
        if node_id and node_names:
            warnings.append("同时提供 node_id 和 node_names 时，实际命令会同时携带两者，请确认符合 Meegle CLI 预期。")
        return warnings

    @staticmethod
    def _approval_checklist(action: str) -> list[str]:
        checklist = [
            "确认工作项、项目空间和目标节点无误。",
            "确认设计产物、评审结论或 PSD/切图包已准备到当前节点要求。",
            "确认没有未闭合的高风险 K3 假设会影响流转。",
            "确认流转后对协作者可见，且不会误导需求方。",
            "确认由设计师人工批准后再执行。",
        ]
        if action == "rollback":
            checklist.insert(1, "确认回滚原因清楚，且不会丢失必要上下文。")
        return checklist

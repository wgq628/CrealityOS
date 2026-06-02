from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent.models import MeeglePublishReceipt


CONFIRM_TOKEN = "PUBLISH_MEEGLE_WRITEBACK"


class MeeglePublishGate:
    def validate_confirmation(self, execute: bool, confirm_token: str | None, approval_file: str | None) -> tuple[bool, str, list[str]]:
        warnings: list[str] = []
        if confirm_token == CONFIRM_TOKEN:
            return True, "token", warnings
        if approval_file:
            path = Path(approval_file)
            if not path.exists():
                warnings.append(f"确认文件不存在：{approval_file}")
            else:
                content = path.read_text(encoding="utf-8")
                if "[x] 允许发布到 Meegle 评论" in content or "[X] 允许发布到 Meegle 评论" in content:
                    return True, "approval_file", warnings
                warnings.append("确认文件未勾选“允许发布到 Meegle 评论”。")
        if execute:
            raise PermissionError(
                f"Publishing requires --confirm-token {CONFIRM_TOKEN} or an approval file with '[x] 允许发布到 Meegle 评论'."
            )
        return False, "dry-run", warnings

    @staticmethod
    def build_receipt(
        project_key: str,
        work_item_id: str,
        comment_path: str,
        command_preview: list[str],
        executed: bool,
        confirmation_method: str,
        response: dict,
        warnings: list[str],
    ) -> MeeglePublishReceipt:
        return MeeglePublishReceipt(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            mode="execute" if executed else "dry-run",
            executed=executed,
            confirmation_method=confirmation_method,
            comment_path=comment_path,
            command_preview=command_preview,
            response=response,
            warnings=warnings,
        )

    @staticmethod
    def render_markdown(receipt: MeeglePublishReceipt) -> str:
        lines = [
            f"# Meegle 发布回执 - {receipt.work_item_id}",
            "",
            f"- 项目：`{receipt.project_key}`",
            f"- 创建时间：`{receipt.created_at}`",
            f"- 模式：`{receipt.mode}`",
            f"- 已执行：{'是' if receipt.executed else '否'}",
            f"- 确认方式：`{receipt.confirmation_method}`",
            f"- 评论文件：`{receipt.comment_path}`",
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
        return "\n".join(lines)

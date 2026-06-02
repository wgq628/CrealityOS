from __future__ import annotations

from datetime import datetime

from agent.models import DesignCycleReport


class DesignCycleReporter:
    def build(
        self,
        project_key: str,
        work_item_id: str,
        title: str,
        source_mode: str,
        artifacts: dict[str, str],
        skipped_steps: list[str],
        next_actions: list[str],
    ) -> DesignCycleReport:
        return DesignCycleReport(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            source_mode=source_mode,
            created_at=datetime.now().isoformat(timespec="seconds"),
            artifacts=artifacts,
            skipped_steps=skipped_steps,
            next_actions=next_actions,
        )

    @staticmethod
    def render_markdown(report: DesignCycleReport) -> str:
        return "\n".join(
            [
                f"# 设计闭环报告 - {report.title}",
                "",
                f"- 项目：`{report.project_key}`",
                f"- 工作项：`{report.work_item_id}`",
                f"- 来源模式：`{report.source_mode}`",
                f"- 生成时间：`{report.created_at}`",
                "",
                "## 产物索引",
                *(f"- {key}: `{value}`" for key, value in report.artifacts.items()),
                "",
                "## 跳过步骤",
                *(f"- {item}" for item in report.skipped_steps or ["无"]),
                "",
                "## 下一步",
                *(f"- {item}" for item in report.next_actions or ["继续补充设计师反馈并更新项目档案。"]),
            ]
        )

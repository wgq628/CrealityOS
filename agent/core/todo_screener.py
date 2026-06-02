from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.models import TodoScreenItem, TodoScreeningReport
from agent.utils import flatten_pairs, stringify


DESIGN_KEYWORDS = {
    "平面": 0.25,
    "设计": 0.2,
    "素材": 0.22,
    "广告": 0.18,
    "海报": 0.24,
    "主视觉": 0.25,
    "kv": 0.25,
    "banner": 0.24,
    "icon": 0.18,
    "图标": 0.18,
    "按钮": 0.16,
    "切图": 0.25,
    "psd": 0.25,
    "png": 0.12,
    "jpg": 0.1,
    "买量": 0.18,
    "投放": 0.14,
}


class TodoScreener:
    def screen(self, items: list[dict[str, Any]], action: str) -> TodoScreeningReport:
        screened: list[TodoScreenItem] = []
        warnings: list[str] = []
        for raw in items:
            score, reasons = self._score(raw)
            if score <= 0:
                continue
            screened.append(
                TodoScreenItem(
                    rank=0,
                    work_item_id=self._pick_first(raw, ("work_item_id", "id", "workItemId", "workItemID")),
                    project_key=self._pick_first(raw, ("project_key", "projectKey", "simple_name", "simpleName")),
                    title=self._pick_title(raw),
                    score=round(min(score, 1.0), 2),
                    reasons=reasons,
                    suggested_action="run-feishu-design-cycle",
                    raw=raw,
                )
            )
        screened.sort(key=lambda item: (-item.score, item.title))
        for index, item in enumerate(screened, start=1):
            item.rank = index
            if not item.work_item_id:
                warnings.append(f"第 {index} 个候选缺少 work_item_id，需要打开待办详情确认")
            if not item.project_key:
                warnings.append(f"第 {index} 个候选缺少 project_key，需要从空间或 URL 补齐")
        return TodoScreeningReport(
            created_at=datetime.now().isoformat(timespec="seconds"),
            action=action,
            total_count=len(items),
            design_count=len(screened),
            items=screened,
            warnings=warnings,
        )

    @staticmethod
    def render_markdown(report: TodoScreeningReport) -> str:
        lines = [
            "# 飞书待办设计需求筛选",
            "",
            f"- 扫描类型：`{report.action}`",
            f"- 扫描时间：`{report.created_at}`",
            f"- 待办数量：`{report.total_count}`",
            f"- 设计候选：`{report.design_count}`",
            "",
            "## 候选列表",
        ]
        if not report.items:
            lines.append("- 未发现明显设计需求候选")
        for item in report.items:
            lines.extend(
                [
                    f"### {item.rank}. {item.title}",
                    f"- 分数：`{item.score}`",
                    f"- 项目：`{item.project_key or '待确认'}`",
                    f"- 工作项：`{item.work_item_id or '待确认'}`",
                    f"- 建议动作：`{item.suggested_action}`",
                    f"- 命中依据：{'; '.join(item.reasons)}",
                    "",
                ]
            )
        lines.extend(["## 警告", *(f"- {item}" for item in report.warnings or ["无"])])
        return "\n".join(lines)

    @staticmethod
    def _score(raw: dict[str, Any]) -> tuple[float, list[str]]:
        text = stringify(raw).lower()
        score = 0.0
        reasons: list[str] = []
        for keyword, weight in DESIGN_KEYWORDS.items():
            if keyword.lower() in text:
                score += weight
                reasons.append(f"命中 `{keyword}`")
        for key, value in flatten_pairs(raw):
            lower_key = key.lower()
            lower_value = value.lower()
            if any(token in lower_key for token in ("name", "title", "summary", "标题", "名称")):
                if any(keyword.lower() in lower_value for keyword in DESIGN_KEYWORDS):
                    score += 0.15
                    reasons.append(f"标题/名称字段包含设计关键词：{key}")
            if any(token in lower_key for token in ("status", "node", "state", "状态", "节点")):
                if any(token in lower_value for token in ("设计", "美术", "制作")):
                    score += 0.15
                    reasons.append(f"流程节点指向设计工作：{key}")
        return min(score, 1.0), list(dict.fromkeys(reasons))

    @staticmethod
    def _pick_title(raw: dict[str, Any]) -> str:
        return TodoScreener._pick_first(raw, ("title", "name", "summary", "subject")) or "未命名待办"

    @staticmethod
    def _pick_first(raw: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        flat = dict(flatten_pairs(raw))
        for key in keys:
            if key in raw and raw[key]:
                return stringify(raw[key])
            if key in flat and flat[key]:
                return flat[key]
        lowered = {key.lower(): value for key, value in flat.items()}
        for key in keys:
            value = lowered.get(key.lower())
            if value:
                return value
        return None

from __future__ import annotations

from agent.models import DesignBrief, WorkItemContext
from agent.utils import stringify


class RiskDetector:
    def detect(self, brief: DesignBrief, context: WorkItemContext) -> list[str]:
        risks = list(brief.missing_information)
        combined_text = stringify(context.raw_item) + "\n" + "\n".join(comment.get("content", "") for comment in context.comments)

        if len(brief.sizes) > 1:
            risks.append("存在多个尺寸或比例，请确认是否需要一稿多尺寸适配")

        if "写实" in combined_text and "Q版" in combined_text:
            risks.append("同时出现“写实”和“Q版”信号，风格方向可能冲突")
        if "极简" in combined_text and "信息量大" in combined_text:
            risks.append("同时要求极简与高信息密度，建议先确认优先级")
        if "PSD" in combined_text and "切图" not in combined_text and "图层" not in combined_text:
            risks.append("提到 PSD 但未说明图层或切图要求，后续交付可能返工")
        if not context.docs:
            risks.append("未读取到关联需求文档，创作依据可能不完整")

        return list(dict.fromkeys(risks))

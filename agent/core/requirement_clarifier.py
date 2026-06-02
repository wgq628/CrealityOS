from __future__ import annotations

from datetime import datetime

from agent.models import ClarificationQuestion, DesignBrief, RequirementClarificationReport


class RequirementClarifier:
    TOPIC_MAP = (
        ("设计目标", "缺少明确设计目标或转化诉求", "这张素材最重要的目标是什么：点击、预约、付费、活动参与，还是品牌曝光？", "没有目标会影响构图优先级和信息层级。", "blocker", "先按提升点击转化处理，但必须在评审前确认。"),
        ("目标受众", "缺少目标受众定义", "这次面向哪类玩家或用户？新用户、老用户、核心玩家、泛用户，还是特定地区/年龄层？", "受众不清会影响角色表现、文案语气和美术密度。", "warning", "先按同品类核心玩家处理。"),
        ("投放平台", "缺少投放平台或使用场景", "素材将用于哪个平台或场景？如 Facebook、TikTok、穿山甲、微信、商店页、活动页等。", "不同平台对比例、文案安全区和信息密度要求不同。", "warning", "先按通用买量素材处理，并保留安全区。"),
        ("尺寸比例", "缺少尺寸或比例信息", "请确认最终尺寸或比例，以及是否需要一稿多尺寸适配。", "缺尺寸会影响构图、安全区和后续切图返工。", "blocker", "先用 1080x1920 竖版草案探索，不进入正式交付。"),
        ("交付物", "缺少交付物格式说明", "请确认需要交付 PSD、PNG/JPG/WebP、切图、动效、还是仅参考稿。", "交付格式会影响图层规划、命名和导出清单。", "blocker", "先按 PSD + PNG 规划，但正式交付前必须确认。"),
        ("截止时间", "缺少明确截止时间", "请确认期望首稿时间和最终交付时间。", "排期不清会影响方案深度和是否走多轮出图。", "warning", "先按普通优先级处理，不承诺当天交付。"),
    )

    def build(self, brief: DesignBrief, risks: list[str]) -> RequirementClarificationReport:
        questions = self._questions(brief, risks)
        assumptions = self._assumptions(brief, questions)
        safe_to_continue = not any(question.severity == "blocker" for question in questions)
        comment = self._comment_draft(brief, questions, assumptions, safe_to_continue)
        return RequirementClarificationReport(
            project_key=brief.project_key or "unknown-project",
            work_item_id=brief.work_item_id,
            title=brief.title,
            created_at=datetime.now().isoformat(timespec="seconds"),
            safe_to_continue=safe_to_continue,
            questions=questions,
            assumptions=assumptions,
            comment_draft=comment,
            next_actions=self._next_actions(questions, safe_to_continue),
        )

    @staticmethod
    def render_markdown(report: RequirementClarificationReport) -> str:
        lines = [
            f"# 需求澄清清单 - {report.title}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 工作项：`{report.work_item_id}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 可继续探索：{'是' if report.safe_to_continue else '否，存在阻塞项'}",
            "",
            "## 待确认问题",
        ]
        if not report.questions:
            lines.append("- 暂无必须澄清的问题")
        for question in report.questions:
            lines.extend(
                [
                    f"### {question.question_id} {question.topic}",
                    f"- 严重级别：`{question.severity}`",
                    f"- 问题：{question.question}",
                    f"- 原因：{question.reason}",
                    f"- 临时默认：{question.suggested_default}",
                    "",
                ]
            )
        lines.extend(["## 临时假设", *(f"- {item}" for item in report.assumptions or ["无"])])
        lines.extend(["", "## 飞书评论草稿", report.comment_draft])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in report.next_actions)])
        return "\n".join(lines)

    def _questions(self, brief: DesignBrief, risks: list[str]) -> list[ClarificationQuestion]:
        questions: list[ClarificationQuestion] = []
        signals = list(dict.fromkeys(list(brief.missing_information) + list(risks)))
        for topic, trigger, question, reason, severity, suggested_default in self.TOPIC_MAP:
            if trigger in signals:
                questions.append(
                    ClarificationQuestion(
                        question_id=f"Q{len(questions) + 1:02d}",
                        topic=topic,
                        question=question,
                        reason=reason,
                        severity=severity,
                        suggested_default=suggested_default,
                    )
                )
        if any("多个尺寸" in risk for risk in risks):
            questions.append(
                ClarificationQuestion(
                    question_id=f"Q{len(questions) + 1:02d}",
                    topic="多尺寸适配",
                    question="当前出现多个尺寸/比例，请确认是同一创意多尺寸适配，还是不同素材任务。",
                    reason="多尺寸会影响构图母版和 PSD 图层安全区。",
                    severity="warning",
                    suggested_default="先按主尺寸做母版，其他尺寸只做适配预留。",
                )
            )
        if any("PSD" in risk and "图层" in risk for risk in risks):
            questions.append(
                ClarificationQuestion(
                    question_id=f"Q{len(questions) + 1:02d}",
                    topic="PSD/切图要求",
                    question="PSD 是否需要可编辑图层、切图层、按钮/底板/icon 独立导出，还是只交源文件？",
                    reason="PSD 要求不清会导致后续重建和切图返工。",
                    severity="warning",
                    suggested_default="先按 background / subject / copy / CTA / effects / exports 分组规划。",
                )
            )
        return questions

    @staticmethod
    def _assumptions(brief: DesignBrief, questions: list[ClarificationQuestion]) -> list[str]:
        assumptions = [question.suggested_default for question in questions if question.suggested_default]
        if brief.same_category:
            assumptions.append(f"风格底座暂按 `{brief.same_category}` 处理，项目档案可覆盖。")
        return list(dict.fromkeys(assumptions))

    @staticmethod
    def _comment_draft(
        brief: DesignBrief,
        questions: list[ClarificationQuestion],
        assumptions: list[str],
        safe_to_continue: bool,
    ) -> str:
        lines = [
            f"## 设计需求澄清：{brief.title}",
            "",
            f"- 工作项：`{brief.work_item_id}`",
            f"- 当前判断：{'可先探索，但需确认以下问题' if safe_to_continue else '存在阻塞项，建议先补齐再进入正式制作'}",
            "",
            "### 需要确认",
        ]
        if not questions:
            lines.append("- 当前暂无明显缺失项。")
        for question in questions:
            lines.append(f"- [{question.severity}] {question.question}")
        lines.extend(["", "### 我会先按以下临时假设推进", *(f"- {item}" for item in assumptions or ["无"])])
        lines.append("")
        lines.append("_注：本草稿仅供设计师确认后回写，不会自动发布到飞书。_")
        return "\n".join(lines)

    @staticmethod
    def _next_actions(questions: list[ClarificationQuestion], safe_to_continue: bool) -> list[str]:
        if not questions:
            return ["可继续生成创作包、出图批次或 PSD/切图计划。"]
        actions = [
            "设计师先复核澄清问题，必要时复制评论草稿到 Meegle 或需求文档。",
            "需求方回复后，把确认结果写入项目档案、反馈或重新生成创作包。",
        ]
        if not safe_to_continue:
            actions.insert(0, "存在阻塞项：不要把当前创作包当作可交付版本，只能做方向探索。")
        return actions

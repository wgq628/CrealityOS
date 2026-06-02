from __future__ import annotations

from datetime import datetime

from agent.models import KnowledgeLevel, LearningDigest, ProjectProfile, ReviewReport, SessionSnapshot, StyleCard


class LearningDigestBuilder:
    def build(
        self,
        project_key: str,
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
        snapshot: SessionSnapshot | None,
        recent_reviews: list[ReviewReport],
    ) -> LearningDigest:
        same_category = self._same_category(project_key, style_card, profile, snapshot)
        confirmed = self._confirmed_defaults(style_card, profile)
        avoid = self._avoid_next_time(style_card, profile, recent_reviews)
        hypotheses = self._hypotheses(style_card)
        open_questions = self._open_questions(style_card, snapshot, profile)
        feedback = self._recent_feedback(recent_reviews)
        checklist = self._next_time_checklist(confirmed, avoid, hypotheses, open_questions)
        commands = self._recommended_commands(project_key, snapshot)
        return LearningDigest(
            project_key=project_key,
            created_at=datetime.now().isoformat(timespec="seconds"),
            active_work_item_id=snapshot.active_work_item_id if snapshot else None,
            same_category=same_category,
            confirmed_defaults=confirmed,
            avoid_next_time=avoid,
            hypotheses_to_verify=hypotheses,
            open_questions=open_questions,
            recent_feedback=feedback,
            next_time_checklist=checklist,
            recommended_commands=commands,
        )

    @staticmethod
    def render_markdown(digest: LearningDigest) -> str:
        return "\n".join(
            [
                f"# 学习复盘 - {digest.project_key}",
                "",
                f"- 生成时间：`{digest.created_at}`",
                f"- 活跃工作项：`{digest.active_work_item_id or '无'}`",
                f"- 同品类底座：`{digest.same_category}`",
                "",
                "## 下次默认沿用",
                *(f"- {item}" for item in digest.confirmed_defaults or ["暂无 K1/K2 级默认规则"]),
                "",
                "## 下次默认避开",
                *(f"- {item}" for item in digest.avoid_next_time or ["暂无明确禁忌"]),
                "",
                "## 仍需验证",
                *(f"- [K3] {item}" for item in digest.hypotheses_to_verify or ["暂无 K3 假设"]),
                "",
                "## 未闭合问题",
                *(f"- {item}" for item in digest.open_questions or ["无"]),
                "",
                "## 最近反馈摘录",
                *(f"- {item}" for item in digest.recent_feedback or ["暂无近期反馈"]),
                "",
                "## 下一次创作前检查",
                *(f"- [ ] {item}" for item in digest.next_time_checklist),
                "",
                "## 建议命令",
                *(f"- `{item}`" for item in digest.recommended_commands),
            ]
        )

    @staticmethod
    def _same_category(
        project_key: str,
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
        snapshot: SessionSnapshot | None,
    ) -> str:
        if style_card:
            return style_card.same_category
        if profile:
            return profile.same_category
        if snapshot:
            return snapshot.same_category
        return f"{project_key}-uncalibrated"

    @staticmethod
    def _confirmed_defaults(style_card: StyleCard | None, profile: ProjectProfile | None) -> list[str]:
        items: list[str] = []
        if profile:
            items.extend(f"[K1/project-profile] {rule}" for rule in profile.must_have_rules)
            items.extend(f"[K2/profile-keyword] 保持项目视觉关键词：{keyword}" for keyword in profile.visual_keywords[:6])
        if style_card:
            for rule in style_card.rules:
                if rule.level in {KnowledgeLevel.K1, KnowledgeLevel.K2, "K1", "K2"}:
                    items.append(f"[{rule.level}] {rule.statement}")
        return list(dict.fromkeys(items))

    @staticmethod
    def _avoid_next_time(
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
        recent_reviews: list[ReviewReport],
    ) -> list[str]:
        items: list[str] = []
        if profile:
            items.extend(profile.forbidden_rules)
        if style_card:
            items.extend(style_card.do_not)
            for rule in style_card.rules:
                if any(token in rule.statement for token in ("禁止", "避免", "不要")):
                    items.append(rule.statement)
        for report in recent_reviews:
            items.extend(item.statement for item in report.rejected)
        return list(dict.fromkeys(items))

    @staticmethod
    def _hypotheses(style_card: StyleCard | None) -> list[str]:
        if not style_card:
            return []
        return list(dict.fromkeys(rule.statement for rule in style_card.rules if rule.level in {KnowledgeLevel.K3, "K3"}))

    @staticmethod
    def _open_questions(
        style_card: StyleCard | None,
        snapshot: SessionSnapshot | None,
        profile: ProjectProfile | None,
    ) -> list[str]:
        items: list[str] = []
        if style_card:
            items.extend(style_card.open_questions)
        if snapshot:
            items.extend(snapshot.unresolved_questions)
        if profile and not profile.default_sizes:
            items.append("项目默认尺寸尚未确认")
        if profile and not profile.required_deliverables:
            items.append("项目固定交付物尚未确认")
        return list(dict.fromkeys(items))

    @staticmethod
    def _recent_feedback(recent_reviews: list[ReviewReport]) -> list[str]:
        items: list[str] = []
        for report in recent_reviews:
            label = report.work_item_id or "general"
            for insight in report.accepted[:3]:
                items.append(f"{label} accepted: {insight.statement}")
            for insight in report.pending[:3]:
                items.append(f"{label} pending: {insight.statement}")
            for insight in report.rejected[:3]:
                items.append(f"{label} rejected: {insight.statement}")
        return list(dict.fromkeys(items))

    @staticmethod
    def _next_time_checklist(
        confirmed: list[str],
        avoid: list[str],
        hypotheses: list[str],
        open_questions: list[str],
    ) -> list[str]:
        checklist = [
            "先对照 K1/K2 默认规则生成创作包，不把 K3 当成确定结论",
            "先暴露缺尺寸、缺文案、缺交付格式、缺参考图等风险，再给方案",
        ]
        if confirmed:
            checklist.append("创作前确认本次需求没有违反已确认默认规则")
        if avoid:
            checklist.append("出图/切图前检查禁忌项和近期驳回点")
        if hypotheses:
            checklist.append("把 K3 假设写进不确定项，等待设计师确认后再升级")
        if open_questions:
            checklist.append("优先闭合未确认问题，再进入 PSD/切图执行")
        checklist.append("正式导出、覆盖文件、对外发送前必须人工确认")
        return checklist

    @staticmethod
    def _recommended_commands(project_key: str, snapshot: SessionSnapshot | None) -> list[str]:
        commands = [
            f"python -m agent.cli resume-session --project-key {project_key}",
            f"python -m agent.cli metacognition-audit --project-key {project_key}",
        ]
        if snapshot:
            commands.append(f"python -m agent.cli create-learning-digest --project-key {project_key}")
            commands.append(
                f"python -m agent.cli plan-automation --project-key {project_key} --work-item-id {snapshot.active_work_item_id} --asset-root <asset-root>"
            )
        else:
            commands.append(f"python -m agent.cli screen-todos --action todo --max-pages 1")
        return commands

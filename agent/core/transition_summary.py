from __future__ import annotations

from datetime import datetime

from agent.models import ProjectProfile, SessionSnapshot, StyleCard, TransitionSummary


class TransitionSummaryBuilder:
    def build(
        self,
        project_key: str,
        snapshot: SessionSnapshot | None,
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
        capability_delta: list[str],
        recent_review_notes: list[str],
    ) -> TransitionSummary:
        active_work_item_id = snapshot.active_work_item_id if snapshot else None
        active_title = snapshot.title if snapshot else "暂无活跃任务"
        progress_summary = self._progress_summary(snapshot, style_card, profile, recent_review_notes)
        key_decisions = list(snapshot.key_decisions if snapshot else [])
        if profile and profile.must_have_rules:
            key_decisions.extend(f"项目固定规则：{item}" for item in profile.must_have_rules[:3])
        unresolved = list(snapshot.unresolved_questions if snapshot else [])
        if profile and not profile.default_sizes:
            unresolved.append("项目档案尚未补充默认尺寸")
        artifacts = list(snapshot.last_artifacts if snapshot else [])
        restart = self._restart_instructions(snapshot, profile)
        return TransitionSummary(
            project_key=project_key,
            created_at=datetime.now().isoformat(timespec="seconds"),
            active_work_item_id=active_work_item_id,
            active_title=active_title,
            progress_summary=progress_summary,
            key_decisions=list(dict.fromkeys(key_decisions)),
            unresolved_questions=list(dict.fromkeys(unresolved)),
            recent_artifacts=artifacts,
            capability_delta=capability_delta,
            restart_instructions=restart,
        )

    @staticmethod
    def render_markdown(summary: TransitionSummary) -> str:
        return "\n".join(
            [
                f"# 会话过渡摘要 - {summary.project_key}",
                "",
                f"- 生成时间：`{summary.created_at}`",
                f"- 活跃工作项：`{summary.active_work_item_id or '无'}`",
                f"- 标题：{summary.active_title}",
                "",
                "## 当前进度",
                summary.progress_summary,
                "",
                "## 关键决策",
                *(f"- {item}" for item in summary.key_decisions or ["无"]),
                "",
                "## 未闭合问题",
                *(f"- {item}" for item in summary.unresolved_questions or ["无"]),
                "",
                "## 最近产物",
                *(f"- {item}" for item in summary.recent_artifacts or ["无"]),
                "",
                "## 本次能力增量",
                *(f"- {item}" for item in summary.capability_delta or ["暂无新增摘要"]),
                "",
                "## 新会话恢复指令",
                *(f"- {item}" for item in summary.restart_instructions),
            ]
        )

    @staticmethod
    def _progress_summary(
        snapshot: SessionSnapshot | None,
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
        recent_review_notes: list[str],
    ) -> str:
        parts: list[str] = []
        if snapshot:
            parts.append(f"当前已形成 {len(snapshot.last_artifacts)} 份主要产物，并保留 {len(snapshot.unresolved_questions)} 个待确认问题。")
        if style_card:
            parts.append(f"风格卡累计 {len(style_card.rules)} 条规则，视觉关键词 {len(style_card.visual_keywords)} 个。")
        if profile:
            parts.append(f"项目档案已建立，固定规则 {len(profile.must_have_rules)} 条，禁忌项 {len(profile.forbidden_rules)} 条。")
        if recent_review_notes:
            parts.append(f"最近有 {len(recent_review_notes)} 条设计师反馈可继续用于升级风格规则。")
        return " ".join(parts) if parts else "当前尚无足够上下文，建议先拉取一次真实需求并生成创作包。"

    @staticmethod
    def _restart_instructions(snapshot: SessionSnapshot | None, profile: ProjectProfile | None) -> list[str]:
        steps = [
            "先读取最新 transition summary，再读取对应的 project_profile、style_card 和最近 review_report。",
            "确认活跃工作项是否仍然有效，再继续 build-creative-pack 或 plan-automation。",
        ]
        if snapshot and snapshot.unresolved_questions:
            steps.append("优先处理未闭合问题，避免沿用带风险的旧假设。")
        if profile and profile.must_have_rules:
            steps.append("任何新产出都必须先对照项目固定规则检查。")
        return steps

from __future__ import annotations

from dataclasses import replace

from agent.memory.store import MemoryStore
from agent.models import KnowledgeLevel, ReviewInsight, ReviewReport, StyleCard, StyleRule


STYLE_KEYWORDS = {
    "二次元": ("角色脸部和情绪表达要明确，避免过于写实的质感", "来自需求文本中的二次元信号"),
    "写实": ("材质和光影以真实体积关系为准，避免过度卡通化", "来自需求文本中的写实信号"),
    "国风": ("保留东方纹样和留白节奏，避免西幻符号抢主题", "来自需求文本中的国风信号"),
    "Q版": ("比例可爱化，但主体识别必须清楚", "来自需求文本中的Q版信号"),
    "活动海报": ("主标题和利益点优先，构图需要留出文案区", "来自任务类型信号"),
    "角色突出": ("主体角色需要高对比和清晰轮廓，压低背景抢夺感", "来自需求中的主体强调"),
    "投放素材": ("投放素材优先保证玩法一眼可懂、主元素突出、转化路径清晰", "来自投放美术任务信号"),
}


class StyleLearner:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def synthesize(self, project_key: str, same_category: str, signals: list[str], missing_information: list[str]) -> StyleCard:
        shared = self.store.load_style_base(same_category)
        project = self.store.load_style_card(project_key)

        merged = StyleCard(
            project_key=project_key,
            same_category=same_category,
            visual_keywords=[],
            composition_preferences=[],
            color_rules=[],
            material_rules=[],
            typography_rules=[],
            ui_mood=[],
            do_not=[],
            rules=[],
            open_questions=list(missing_information),
            evidence_summary=[],
        )

        for source in (shared, project):
            if not source:
                continue
            merged.visual_keywords.extend(source.visual_keywords)
            merged.composition_preferences.extend(source.composition_preferences)
            merged.color_rules.extend(source.color_rules)
            merged.material_rules.extend(source.material_rules)
            merged.typography_rules.extend(source.typography_rules)
            merged.ui_mood.extend(source.ui_mood)
            merged.do_not.extend(source.do_not)
            merged.open_questions.extend(source.open_questions)
            merged.evidence_summary.extend(source.evidence_summary)
            for rule in source.rules:
                self._merge_rule(merged.rules, replace(rule))

        for signal in signals:
            if signal not in STYLE_KEYWORDS:
                continue
            statement, rationale = STYLE_KEYWORDS[signal]
            self._merge_rule(
                merged.rules,
                StyleRule(
                    statement=statement,
                    level=KnowledgeLevel.K3,
                    rationale=rationale,
                    source_refs=[f"signal:{signal}"],
                    scope="shared",
                ),
            )
            merged.visual_keywords.append(signal)

        merged.visual_keywords = list(dict.fromkeys(merged.visual_keywords))
        merged.composition_preferences = list(dict.fromkeys(merged.composition_preferences))
        merged.color_rules = list(dict.fromkeys(merged.color_rules))
        merged.material_rules = list(dict.fromkeys(merged.material_rules))
        merged.typography_rules = list(dict.fromkeys(merged.typography_rules))
        merged.ui_mood = list(dict.fromkeys(merged.ui_mood))
        merged.do_not = list(dict.fromkeys(merged.do_not))
        merged.open_questions = list(dict.fromkeys(merged.open_questions))
        merged.evidence_summary = list(dict.fromkeys(merged.evidence_summary))
        return merged

    def ingest_feedback(
        self,
        project_key: str,
        same_category: str,
        work_item_id: str | None,
        feedback: str,
        decision: str,
        share_to_base: bool = False,
    ) -> ReviewReport:
        project_card = self.store.load_style_card(project_key) or StyleCard(
            project_key=project_key,
            same_category=same_category,
            visual_keywords=[],
            composition_preferences=[],
            color_rules=[],
            material_rules=[],
            typography_rules=[],
            ui_mood=[],
            do_not=[],
            rules=[],
            open_questions=[],
            evidence_summary=[],
        )
        shared_base = self.store.load_style_base(same_category) or StyleCard(
            project_key=f"{same_category}-shared",
            same_category=same_category,
            visual_keywords=[],
            composition_preferences=[],
            color_rules=[],
            material_rules=[],
            typography_rules=[],
            ui_mood=[],
            do_not=[],
            rules=[],
            open_questions=[],
            evidence_summary=[],
        )

        accepted: list[ReviewInsight] = []
        rejected: list[ReviewInsight] = []
        pending: list[ReviewInsight] = []

        for line in [item.strip("-• \t") for item in feedback.splitlines() if item.strip()]:
            insight = self._feedback_to_insight(line, decision, share_to_base)
            if decision == "approved":
                accepted.append(insight)
                self._merge_rule(project_card.rules, self._to_rule(insight, work_item_id))
                if share_to_base or insight.applies_to_shared_base:
                    self._merge_rule(shared_base.rules, self._to_rule(insight, work_item_id, scope="shared"))
            elif decision == "rejected":
                rejected.append(insight)
            else:
                pending.append(insight)
                self._merge_rule(project_card.rules, self._to_rule(insight, work_item_id))

        project_card.evidence_summary.append(f"{decision}:{work_item_id or 'general'}")
        self.store.save_style_card(project_card)
        if share_to_base or any(item.applies_to_shared_base for item in accepted):
            self.store.save_style_base(shared_base)

        next_actions = [
            "下次同项目任务优先应用本次确认过的项目级规则",
            "对仍是 K3 的假设继续等待更多项目反馈验证",
        ]
        if share_to_base:
            next_actions.append("已同步到同品类共享风格底座，后续跨项目可复用")

        return ReviewReport(
            project_key=project_key,
            work_item_id=work_item_id,
            decision=decision,
            feedback=feedback,
            accepted=accepted,
            rejected=rejected,
            pending=pending,
            next_actions=next_actions,
        )

    @staticmethod
    def _feedback_to_insight(line: str, decision: str, share_to_base: bool) -> ReviewInsight:
        high_confidence = any(token in line for token in ("必须", "禁止", "一律", "统一"))
        level = KnowledgeLevel.K1 if high_confidence else KnowledgeLevel.K2 if decision == "approved" else KnowledgeLevel.K3
        if any(token in line for token in ("避免", "禁止", "不要")):
            rationale = "来自设计师明确的否定约束"
        elif any(token in line for token in ("保留", "延续", "继续")):
            rationale = "来自设计师确认的延续偏好"
        else:
            rationale = "来自设计师评审反馈"
        return ReviewInsight(
            statement=line,
            level=level,
            rationale=rationale,
            applies_to_shared_base=share_to_base or "通用" in line or "同品类" in line,
        )

    @staticmethod
    def _to_rule(insight: ReviewInsight, work_item_id: str | None, scope: str = "project") -> StyleRule:
        return StyleRule(
            statement=insight.statement,
            level=insight.level,
            rationale=insight.rationale,
            source_refs=[f"review:{work_item_id or 'general'}"],
            evidence_count=1,
            scope=scope,
        )

    @staticmethod
    def _merge_rule(existing_rules: list[StyleRule], incoming: StyleRule) -> None:
        for rule in existing_rules:
            if rule.statement == incoming.statement:
                rule.evidence_count += incoming.evidence_count
                rule.source_refs.extend(ref for ref in incoming.source_refs if ref not in rule.source_refs)
                if incoming.level == KnowledgeLevel.K1 or rule.evidence_count >= 2:
                    rule.level = KnowledgeLevel.K1 if incoming.level == KnowledgeLevel.K1 else KnowledgeLevel.K2
                elif incoming.level == KnowledgeLevel.K2:
                    rule.level = KnowledgeLevel.K2
                return
        existing_rules.append(incoming)

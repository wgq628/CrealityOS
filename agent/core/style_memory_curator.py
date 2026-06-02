from __future__ import annotations

from datetime import datetime

from agent.models import KnowledgeLevel, StyleCard, StyleMemoryCurationAction, StyleMemoryCurationReport


class StyleMemoryCurator:
    AVOID_TOKENS = ("避免", "禁止", "不要", "不能", "避开")

    def build_report(self, style_card: StyleCard | None, apply: bool = False) -> tuple[StyleCard | None, StyleMemoryCurationReport]:
        if not style_card:
            return None, StyleMemoryCurationReport(
                project_key="unknown",
                same_category="unknown",
                created_at=datetime.now().isoformat(timespec="seconds"),
                mode="apply" if apply else "report",
                actions=[],
                warnings=["未找到项目风格卡，无法治理风格记忆。"],
                next_actions=["先生成创作包或摄入反馈/参考图，建立项目 style_card。"],
            )

        actions = self._actions(style_card)
        if apply:
            self._apply_actions(style_card, actions)
        warnings = self._warnings(style_card, actions)
        return style_card, StyleMemoryCurationReport(
            project_key=style_card.project_key,
            same_category=style_card.same_category,
            created_at=datetime.now().isoformat(timespec="seconds"),
            mode="apply" if apply else "report",
            actions=actions,
            warnings=warnings,
            next_actions=self._next_actions(actions, apply),
        )

    @staticmethod
    def render_markdown(report: StyleMemoryCurationReport) -> str:
        lines = [
            f"# 风格记忆治理 - {report.project_key}",
            "",
            f"- 同品类底座：`{report.same_category}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 模式：`{report.mode}`",
            "",
            "## 建议/动作",
        ]
        if not report.actions:
            lines.append("- 暂无需要治理的风格记忆动作")
        for action in report.actions:
            lines.extend(
                [
                    f"### {action.action_id} {action.kind}",
                    f"- 语句：{action.statement}",
                    f"- 当前级别：`{action.current_level or '无'}`",
                    f"- 建议级别：`{action.proposed_level or '无'}`",
                    f"- 已应用：{'是' if action.applied else '否'}",
                    f"- 原因：{action.reason}",
                    *(f"- 证据：{item}" for item in action.evidence or ["无"]),
                    "",
                ]
            )
        lines.extend(["## 警告", *(f"- {item}" for item in report.warnings or ["无"])])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in report.next_actions)])
        return "\n".join(lines)

    def _actions(self, style_card: StyleCard) -> list[StyleMemoryCurationAction]:
        actions: list[StyleMemoryCurationAction] = []
        for index, rule in enumerate(style_card.rules, start=1):
            level = str(rule.level)
            if level == "K3" and rule.evidence_count >= 2:
                actions.append(
                    StyleMemoryCurationAction(
                        action_id=f"PROMOTE-{index:03d}",
                        kind="promote_k3_to_k2",
                        statement=rule.statement,
                        current_level=level,
                        proposed_level="K2",
                        reason="同一风格判断已有多次证据，可由待验证假设升级为已验证风格。",
                        evidence=[f"evidence_count={rule.evidence_count}", *rule.source_refs],
                    )
                )
            if level in {"K1", "K2"} and self._is_avoid_statement(rule.statement) and rule.statement not in style_card.do_not:
                actions.append(
                    StyleMemoryCurationAction(
                        action_id=f"AVOID-{index:03d}",
                        kind="sync_confirmed_avoid_to_do_not",
                        statement=rule.statement,
                        current_level=level,
                        proposed_level=level,
                        reason="已确认的否定约束应同步到 do_not，确保后续负面提示词默认避开。",
                        evidence=[*rule.source_refs],
                    )
                )
        overlap = sorted(set(style_card.visual_keywords).intersection(style_card.do_not))
        for index, keyword in enumerate(overlap, start=1):
            actions.append(
                StyleMemoryCurationAction(
                    action_id=f"CONFLICT-{index:03d}",
                    kind="keyword_conflict",
                    statement=keyword,
                    current_level=None,
                    proposed_level=None,
                    reason="同一关键词同时出现在视觉关键词和禁忌项中，需要设计师确认保留方向。",
                    evidence=["visual_keywords", "do_not"],
                )
            )
        return actions

    def _apply_actions(self, style_card: StyleCard, actions: list[StyleMemoryCurationAction]) -> None:
        for action in actions:
            if action.kind == "promote_k3_to_k2":
                for rule in style_card.rules:
                    if rule.statement == action.statement and str(rule.level) == "K3":
                        rule.level = KnowledgeLevel.K2
                        action.applied = True
                        break
            elif action.kind == "sync_confirmed_avoid_to_do_not":
                if action.statement not in style_card.do_not:
                    style_card.do_not.append(action.statement)
                    action.applied = True
        style_card.do_not = list(dict.fromkeys(style_card.do_not))

    def _warnings(self, style_card: StyleCard, actions: list[StyleMemoryCurationAction]) -> list[str]:
        warnings: list[str] = []
        conflict_count = sum(1 for action in actions if action.kind == "keyword_conflict")
        stale_k3 = [rule.statement for rule in style_card.rules if str(rule.level) == "K3" and rule.evidence_count <= 1]
        if conflict_count:
            warnings.append(f"发现 {conflict_count} 个关键词同时存在于视觉关键词和禁忌项，需要人工裁决。")
        if stale_k3:
            warnings.append(f"仍有 {len(stale_k3)} 条单证据 K3 假设，继续保留待验证。")
        if not style_card.rules:
            warnings.append("风格卡暂无规则，建议先摄入项目档案、参考图或评审反馈。")
        return warnings

    @staticmethod
    def _next_actions(actions: list[StyleMemoryCurationAction], apply: bool) -> list[str]:
        if not actions:
            return ["当前没有明显需要治理的风格记忆；继续用真实需求和评审反馈积累证据。"]
        next_actions = [
            "复核治理报告，确认升级、避坑同步和冲突项是否符合项目真实风格。",
            "治理后重新生成 creative_pack，确认 K1/K2 规则进入执行提示词，K3 仍留在不确定项。",
        ]
        if not apply:
            next_actions.insert(0, "本次仅生成建议，未修改 style_card；确认后可用 --apply 显式写回。")
        else:
            next_actions.insert(0, "已应用安全动作；关键词冲突仍需人工修改项目档案或风格卡。")
        return next_actions

    @classmethod
    def _is_avoid_statement(cls, statement: str) -> bool:
        return any(token in statement for token in cls.AVOID_TOKENS)

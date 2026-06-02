from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.models import CreativePack, DesignDecisionItem, DesignDecisionRecord, KnowledgeLevel


class DesignDecisionRecorder:
    def build(
        self,
        creative_pack: CreativePack,
        clarification_payload: dict[str, Any] | None = None,
        style_alignment_payload: dict[str, Any] | None = None,
        source_artifacts: dict[str, str | None] | None = None,
    ) -> DesignDecisionRecord:
        decisions = self._decisions(creative_pack, style_alignment_payload)
        assumptions = self._assumptions(creative_pack, clarification_payload)
        open_questions = self._open_questions(creative_pack, clarification_payload, style_alignment_payload)
        return DesignDecisionRecord(
            project_key=creative_pack.brief.project_key or "unknown-project",
            work_item_id=creative_pack.brief.work_item_id,
            title=creative_pack.brief.title,
            created_at=datetime.now().isoformat(timespec="seconds"),
            decisions=decisions,
            assumptions=assumptions,
            open_questions=open_questions,
            safety_notes=self._safety_notes(style_alignment_payload),
            source_artifacts=source_artifacts or {},
            next_actions=self._next_actions(open_questions, style_alignment_payload),
        )

    @staticmethod
    def render_markdown(record: DesignDecisionRecord) -> str:
        lines = [
            f"# 设计决策记录 - {record.title}",
            "",
            f"- 项目：`{record.project_key}`",
            f"- 工作项：`{record.work_item_id}`",
            f"- 创建时间：`{record.created_at}`",
            "",
            "## 来源产物",
        ]
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in record.source_artifacts.items())
        lines.append("")
        lines.append("## 决策")
        for decision in record.decisions:
            lines.extend(
                [
                    f"### {decision.decision_id} {decision.category}",
                    f"- 结论：{decision.statement}",
                    f"- 信度：`{decision.level}`",
                    f"- 需要设计师确认：{'是' if decision.requires_designer_confirmation else '否'}",
                    f"- 理由：{decision.rationale}",
                    *(f"- 证据：{item}" for item in decision.evidence or ["无"]),
                    "",
                ]
            )
        lines.extend(["## 临时假设", *(f"- {item}" for item in record.assumptions or ["无"])])
        lines.extend(["", "## 未闭合问题", *(f"- {item}" for item in record.open_questions or ["无"])])
        lines.extend(["", "## 安全说明", *(f"- {item}" for item in record.safety_notes)])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in record.next_actions)])
        return "\n".join(lines)

    def _decisions(self, creative_pack: CreativePack, style_alignment_payload: dict[str, Any] | None) -> list[DesignDecisionItem]:
        brief = creative_pack.brief
        decisions = [
            DesignDecisionItem(
                decision_id="D01",
                category="需求范围",
                statement=f"本轮按 `{brief.same_category}` 同品类底座处理 `{brief.title}`。",
                rationale="同品类底座用于复用共性风格，但项目档案和设计师反馈拥有覆盖优先级。",
                evidence=[f"same_category={brief.same_category}", f"raw_signals={', '.join(brief.raw_signals) or '无'}"],
                level="K3" if brief.same_category == "general-game-design" else "K2",
                requires_designer_confirmation=brief.same_category == "general-game-design",
            ),
            DesignDecisionItem(
                decision_id="D02",
                category="交付规划",
                statement=self._delivery_statement(creative_pack),
                rationale="尺寸、交付物和切图约束会决定构图安全区、PSD 图层和导出清单。",
                evidence=[
                    f"尺寸：{', '.join(brief.sizes) if brief.sizes else '待确认'}",
                    f"交付物：{', '.join(brief.deliverables) if brief.deliverables else '待确认'}",
                    f"切图说明：{'; '.join(creative_pack.delivery_manifest.slicing_notes[:3])}",
                ],
                level="K2" if brief.sizes and brief.deliverables else "K3",
                requires_designer_confirmation=bool(brief.missing_information),
            ),
        ]
        decisions.extend(self._style_decisions(creative_pack))
        if style_alignment_payload:
            decisions.append(
                DesignDecisionItem(
                    decision_id=f"D{len(decisions) + 1:02d}",
                    category="风格闸门",
                    statement=f"风格一致性状态为 `{style_alignment_payload.get('status', 'unknown')}`。",
                    rationale="出图前需要确认 K1/K2、禁忌项和 K3 边界没有偏移。",
                    evidence=[
                        f"阻塞项：{len(style_alignment_payload.get('blockers', []))}",
                        f"风险提醒：{len(style_alignment_payload.get('warnings', []))}",
                    ],
                    level="K2",
                    requires_designer_confirmation=bool(style_alignment_payload.get("blockers") or style_alignment_payload.get("warnings")),
                )
            )
        return decisions

    @staticmethod
    def _delivery_statement(creative_pack: CreativePack) -> str:
        manifest = creative_pack.delivery_manifest
        formats = ", ".join({item.format_hint for item in manifest.export_items}) if manifest.export_items else "待确认"
        sizes = ", ".join({item.size for item in manifest.export_items}) if manifest.export_items else "待确认"
        return f"按 `{formats}` 输出、`{sizes}` 尺寸组织交付，并保留人工确认门。"

    def _style_decisions(self, creative_pack: CreativePack) -> list[DesignDecisionItem]:
        decisions: list[DesignDecisionItem] = []
        confirmed_rules = [
            rule
            for rule in creative_pack.style_card.rules
            if str(rule.level) in {KnowledgeLevel.K1.value, KnowledgeLevel.K2.value}
        ]
        k3_rules = [
            rule
            for rule in creative_pack.style_card.rules
            if str(rule.level) == KnowledgeLevel.K3.value
        ]
        if confirmed_rules:
            decisions.append(
                DesignDecisionItem(
                    decision_id="D03",
                    category="已验证风格",
                    statement=f"本轮执行 {len(confirmed_rules)} 条 K1/K2 风格规则。",
                    rationale="已确认规则可以进入提示词、构图、PSD 建议或负面约束。",
                    evidence=[f"[{rule.level}] {rule.statement}" for rule in confirmed_rules[:5]],
                    level="K2",
                    requires_designer_confirmation=False,
                )
            )
        if creative_pack.style_card.do_not:
            decisions.append(
                DesignDecisionItem(
                    decision_id=f"D{len(decisions) + 3:02d}",
                    category="禁忌项",
                    statement="本轮把项目禁忌项纳入负面约束。",
                    rationale="禁忌项用于减少出图偏移和后续返工。",
                    evidence=creative_pack.style_card.do_not[:6],
                    level="K2",
                    requires_designer_confirmation=False,
                )
            )
        if k3_rules:
            decisions.append(
                DesignDecisionItem(
                    decision_id=f"D{len(decisions) + 3:02d}",
                    category="待验证风格",
                    statement=f"保留 {len(k3_rules)} 条 K3 作为探索，不当作确定规则。",
                    rationale="单次需求信号不能直接升级为长期项目风格。",
                    evidence=[rule.statement for rule in k3_rules[:5]],
                    level="K3",
                    requires_designer_confirmation=True,
                )
            )
        return decisions

    @staticmethod
    def _assumptions(creative_pack: CreativePack, clarification_payload: dict[str, Any] | None) -> list[str]:
        assumptions = list((clarification_payload or {}).get("assumptions", []))
        assumptions.extend(item for item in creative_pack.uncertainties if "K3" in item or "待确认" in item)
        return list(dict.fromkeys(assumptions))

    @staticmethod
    def _open_questions(
        creative_pack: CreativePack,
        clarification_payload: dict[str, Any] | None,
        style_alignment_payload: dict[str, Any] | None,
    ) -> list[str]:
        questions: list[str] = []
        questions.extend(creative_pack.brief.missing_information)
        questions.extend(creative_pack.style_card.open_questions)
        questions.extend(question.get("question", "") for question in (clarification_payload or {}).get("questions", []))
        questions.extend((style_alignment_payload or {}).get("warnings", []))
        questions.extend((style_alignment_payload or {}).get("blockers", []))
        return [item for item in dict.fromkeys(questions) if item]

    @staticmethod
    def _safety_notes(style_alignment_payload: dict[str, Any] | None) -> list[str]:
        notes = [
            "本记录只解释本地副驾判断，不发布 Meegle、不流转节点、不覆盖正式文件。",
            "正式对外沟通、交付、PSD 导出或工作流流转仍需设计师显式确认。",
            "K3 待验证假设只能作为探索，不能写成确定结论。",
        ]
        if style_alignment_payload and style_alignment_payload.get("status") == "blocked":
            notes.insert(0, "风格一致性报告存在阻塞项，不应创建正式出图任务。")
        return notes

    @staticmethod
    def _next_actions(open_questions: list[str], style_alignment_payload: dict[str, Any] | None) -> list[str]:
        actions: list[str] = []
        if open_questions:
            actions.append("先让设计师复核未闭合问题，必要时把澄清评论草稿回写到 Meegle。")
        if style_alignment_payload and style_alignment_payload.get("status") == "blocked":
            actions.append("先修正风格一致性阻塞项，再重新生成创作包或风格报告。")
        actions.extend(
            [
                "评审创作包和出图批次时，把采纳/驳回理由继续沉淀为 review_report。",
                "下次会话恢复时优先读取本决策记录，避免重复解释本轮判断依据。",
            ]
        )
        return list(dict.fromkeys(actions))

from __future__ import annotations

from datetime import datetime

from agent.models import CreativePack, KnowledgeLevel, StyleAlignmentFinding, StyleAlignmentReport


class StyleAlignmentAuditor:
    def build(
        self,
        creative_pack: CreativePack,
        source_artifacts: dict[str, str | None] | None = None,
    ) -> StyleAlignmentReport:
        findings = [
            self._confirmed_rule_coverage(creative_pack),
            self._forbidden_rule_coverage(creative_pack),
            self._k3_leakage_check(creative_pack),
            self._style_memory_depth(creative_pack),
            self._open_question_check(creative_pack),
        ]
        blockers = [finding.action for finding in findings if finding.severity == "blocker" and finding.action]
        warnings = [finding.action for finding in findings if finding.severity == "warning" and finding.action]
        status = "blocked" if blockers else "needs_designer_review" if warnings else "aligned"
        confirmed = self._confirmed_rules(creative_pack)
        k3 = self._k3_rules(creative_pack)
        return StyleAlignmentReport(
            project_key=creative_pack.brief.project_key or "unknown-project",
            work_item_id=creative_pack.brief.work_item_id,
            title=creative_pack.brief.title,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            findings=findings,
            confirmed_rule_count=len(confirmed),
            k3_hypothesis_count=len(k3),
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            next_actions=self._next_actions(status, blockers, warnings),
            source_artifacts=source_artifacts or {},
        )

    @staticmethod
    def render_markdown(report: StyleAlignmentReport) -> str:
        lines = [
            f"# 风格一致性报告 - {report.title}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 工作项：`{report.work_item_id}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            f"- 已确认规则数：`{report.confirmed_rule_count}`",
            f"- K3 假设数：`{report.k3_hypothesis_count}`",
            "",
            "## 来源产物",
        ]
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in report.source_artifacts.items())
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in report.blockers or ["无"])])
        lines.extend(["", "## 风险提醒", *(f"- {item}" for item in report.warnings or ["无"])])
        lines.append("")
        lines.append("## 检查项")
        for finding in report.findings:
            lines.extend(
                [
                    f"### {finding.check_id} {finding.title}",
                    f"- 状态：`{finding.status}`",
                    f"- 严重级别：`{finding.severity}`",
                    *(f"- 证据：{item}" for item in finding.evidence or ["无"]),
                    f"- 建议动作：{finding.action or '无'}",
                    "",
                ]
            )
        lines.extend(["## 下一步", *(f"- {item}" for item in report.next_actions)])
        return "\n".join(lines)

    @staticmethod
    def _confirmed_rules(creative_pack: CreativePack) -> list[str]:
        return [
            rule.statement
            for rule in creative_pack.style_card.rules
            if str(rule.level) in {KnowledgeLevel.K1.value, KnowledgeLevel.K2.value}
        ]

    @staticmethod
    def _k3_rules(creative_pack: CreativePack) -> list[str]:
        return [
            rule.statement
            for rule in creative_pack.style_card.rules
            if str(rule.level) == KnowledgeLevel.K3.value
        ]

    @staticmethod
    def _is_avoid_rule(statement: str) -> bool:
        return any(token in statement for token in ("避免", "禁止", "不要", "不能", "不可", "弱化", "减少"))

    @staticmethod
    def _norm(value: str) -> str:
        return "".join(value.lower().split())

    def _contains(self, haystack: str, needle: str) -> bool:
        normalized_needle = self._norm(needle)
        if not normalized_needle:
            return False
        return normalized_needle in self._norm(haystack)

    def _confirmed_rule_coverage(self, creative_pack: CreativePack) -> StyleAlignmentFinding:
        confirmed = [rule for rule in self._confirmed_rules(creative_pack) if not self._is_avoid_rule(rule)]
        executable_text = "\n".join(
            creative_pack.prompt_pack.positive
            + creative_pack.references
            + creative_pack.composition_suggestions
            + creative_pack.psd_guidance
        )
        missing = [rule for rule in confirmed if not self._contains(executable_text, rule)]
        evidence = [f"正向 K1/K2 规则：{len(confirmed)}", f"已覆盖：{len(confirmed) - len(missing)}"]
        if missing:
            return StyleAlignmentFinding(
                "CONFIRMED_RULES",
                "已确认风格规则覆盖",
                "partial",
                "warning",
                evidence + missing[:5],
                "部分 K1/K2 风格规则没有进入创作包正向约束，请确认是否应补进提示词、构图或 PSD 建议。",
            )
        return StyleAlignmentFinding("CONFIRMED_RULES", "已确认风格规则覆盖", "pass", "info", evidence)

    def _forbidden_rule_coverage(self, creative_pack: CreativePack) -> StyleAlignmentFinding:
        avoid_rules = [
            rule
            for rule in self._confirmed_rules(creative_pack)
            if self._is_avoid_rule(rule)
        ] + list(creative_pack.style_card.do_not)
        avoid_rules = list(dict.fromkeys(avoid_rules))
        negative_text = "\n".join(creative_pack.prompt_pack.negative + creative_pack.style_card.do_not)
        missing = [rule for rule in avoid_rules if not self._contains(negative_text, rule)]
        evidence = [f"禁忌/负向规则：{len(avoid_rules)}", f"已进入负面约束：{len(avoid_rules) - len(missing)}"]
        if missing:
            return StyleAlignmentFinding(
                "FORBIDDEN_RULES",
                "禁忌项负面约束",
                "partial",
                "warning",
                evidence + missing[:5],
                "部分禁忌项没有进入 Negative 或 do_not，请补齐后再执行出图。",
            )
        return StyleAlignmentFinding("FORBIDDEN_RULES", "禁忌项负面约束", "pass", "info", evidence)

    def _k3_leakage_check(self, creative_pack: CreativePack) -> StyleAlignmentFinding:
        k3_rules = self._k3_rules(creative_pack)
        positive_text = "\n".join(creative_pack.prompt_pack.positive)
        leaked = [rule for rule in k3_rules if self._contains(positive_text, rule)]
        evidence = [f"K3 假设：{len(k3_rules)}", f"误入 Positive：{len(leaked)}"]
        if leaked:
            return StyleAlignmentFinding(
                "K3_LEAKAGE",
                "K3 不进入正式提示词",
                "failed",
                "blocker",
                evidence + leaked[:5],
                "存在 K3 待验证假设进入 Positive 提示词，必须移到探索/不确定项后再出图。",
            )
        return StyleAlignmentFinding("K3_LEAKAGE", "K3 不进入正式提示词", "pass", "info", evidence)

    def _style_memory_depth(self, creative_pack: CreativePack) -> StyleAlignmentFinding:
        confirmed = self._confirmed_rules(creative_pack)
        evidence = [
            f"K1/K2 规则：{len(confirmed)}",
            f"视觉关键词：{len(creative_pack.style_card.visual_keywords)}",
            f"证据摘要：{len(creative_pack.style_card.evidence_summary)}",
        ]
        if not confirmed:
            return StyleAlignmentFinding(
                "MEMORY_DEPTH",
                "风格记忆深度",
                "thin",
                "warning",
                evidence,
                "当前项目缺少 K1/K2 已验证风格规则，建议先摄入参考图或设计师反馈再批量出图。",
            )
        return StyleAlignmentFinding("MEMORY_DEPTH", "风格记忆深度", "pass", "info", evidence)

    @staticmethod
    def _open_question_check(creative_pack: CreativePack) -> StyleAlignmentFinding:
        questions = list(dict.fromkeys(creative_pack.style_card.open_questions + creative_pack.brief.missing_information))
        evidence = questions[:6] or ["无未闭合风格/需求问题"]
        if questions:
            return StyleAlignmentFinding(
                "OPEN_QUESTIONS",
                "未闭合风格/需求问题",
                "needs_review",
                "warning",
                evidence,
                "出图或 PSD 交付前，请确认这些问题只影响探索，不影响正式交付判断。",
            )
        return StyleAlignmentFinding("OPEN_QUESTIONS", "未闭合风格/需求问题", "pass", "info", evidence)

    @staticmethod
    def _next_actions(status: str, blockers: list[str], warnings: list[str]) -> list[str]:
        if blockers:
            return [
                "先处理阻塞项，尤其是 K3 误入正式 Positive 提示词。",
                "重新生成创作包或风格一致性报告后，再创建出图任务。",
            ]
        actions = [
            "设计师复核风格一致性报告，确认 K1/K2 与禁忌项覆盖是否符合项目审美。",
            "如报告仅剩可接受风险，可继续评审 image_generation_batch 或创建出图任务。",
        ]
        if warnings:
            actions.insert(0, "存在风格风险提醒：建议先补齐记忆、澄清问题或修正提示词。")
        if status == "aligned":
            actions.append("当前风格约束通过本地预检，可作为出图/PSD 规划前置依据。")
        return actions

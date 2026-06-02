from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.models import ProjectProfile, StyleCard, StyleRule, StyleTransferFinding, StyleTransferReport


class StyleTransferAuditor:
    def build(
        self,
        project_key: str,
        work_item_id: str,
        same_category: str,
        shared_base: StyleCard | None,
        effective_style: StyleCard | None,
        profile: ProjectProfile | None,
        source_artifacts: dict[str, str | None],
    ) -> StyleTransferReport:
        transferable_rules = self._transferable_rules(shared_base, effective_style, profile)
        project_overrides = self._project_overrides(effective_style, profile)
        blocked_shared_rules = self._blocked_shared_rules(shared_base, effective_style, profile)
        k3_hypotheses = self._k3_hypotheses(effective_style)
        findings = [
            self._shared_base_check(shared_base),
            self._project_overlay_check(project_overrides, profile),
            self._conflict_check(blocked_shared_rules),
            self._k3_boundary_check(k3_hypotheses),
        ]
        blockers = [finding.action for finding in findings if finding.severity == "blocker" and finding.action]
        warnings = [finding.action for finding in findings if finding.severity == "warning" and finding.action]
        status = "blocked" if blockers else "needs_designer_review" if warnings else "transfer_ready"
        return StyleTransferReport(
            project_key=project_key,
            work_item_id=work_item_id,
            same_category=same_category,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            transferable_rules=transferable_rules,
            project_overrides=project_overrides,
            blocked_shared_rules=blocked_shared_rules,
            k3_hypotheses=k3_hypotheses,
            findings=findings,
            warnings=list(dict.fromkeys(warnings)),
            blockers=list(dict.fromkeys(blockers)),
            next_actions=self._next_actions(status, blocked_shared_rules, k3_hypotheses),
            source_artifacts=source_artifacts,
        )

    @staticmethod
    def render_markdown(report: StyleTransferReport) -> str:
        lines = [
            f"# 风格迁移与项目覆盖报告 - {report.work_item_id}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 同品类底座：`{report.same_category}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            "",
            "## 来源产物",
        ]
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in report.source_artifacts.items())
        lines.extend(["", "## 可迁移的同品类规则", *(f"- {item}" for item in report.transferable_rules or ["暂无"])] )
        lines.extend(["", "## 项目级覆盖/硬规则", *(f"- {item}" for item in report.project_overrides or ["暂无"])] )
        lines.extend(["", "## 被项目覆盖或阻断的同品类规则", *(f"- {item}" for item in report.blocked_shared_rules or ["无"])] )
        lines.extend(["", "## K3 待验证假设", *(f"- {item}" for item in report.k3_hypotheses or ["无"])] )
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in report.blockers or ["无"])] )
        lines.extend(["", "## 风险提醒", *(f"- {item}" for item in report.warnings or ["无"])] )
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

    def _transferable_rules(
        self,
        shared_base: StyleCard | None,
        effective_style: StyleCard | None,
        profile: ProjectProfile | None,
    ) -> list[str]:
        blocked = set(self._blocked_shared_rules(shared_base, effective_style, profile))
        rules: list[str] = []
        for rule in (shared_base.rules if shared_base else []):
            if self._level(rule) in {"K1", "K2"} and rule.statement not in blocked:
                rules.append(f"[{self._level(rule)}] {rule.statement}")
        for keyword in (shared_base.visual_keywords if shared_base else []):
            if not self._is_blocked(keyword, effective_style, profile):
                rules.append(f"[keyword] {keyword}")
        return list(dict.fromkeys(rules))

    @staticmethod
    def _project_overrides(effective_style: StyleCard | None, profile: ProjectProfile | None) -> list[str]:
        overrides: list[str] = []
        if profile:
            overrides.extend(f"[K1/profile] {item}" for item in profile.must_have_rules)
            overrides.extend(f"[forbidden/profile] {item}" for item in profile.forbidden_rules)
            overrides.extend(f"[keyword/profile] {item}" for item in profile.visual_keywords)
        if effective_style:
            for rule in effective_style.rules:
                if str(rule.scope) == "project" and str(rule.level) in {"K1", "K2"}:
                    overrides.append(f"[{rule.level}/{rule.scope}] {rule.statement}")
            overrides.extend(f"[do_not] {item}" for item in effective_style.do_not)
        return list(dict.fromkeys(overrides))

    def _blocked_shared_rules(
        self,
        shared_base: StyleCard | None,
        effective_style: StyleCard | None,
        profile: ProjectProfile | None,
    ) -> list[str]:
        if not shared_base:
            return []
        blocked: list[str] = []
        for rule in shared_base.rules:
            if self._is_blocked(rule.statement, effective_style, profile):
                blocked.append(rule.statement)
        for keyword in shared_base.visual_keywords:
            if self._is_blocked(keyword, effective_style, profile):
                blocked.append(keyword)
        return list(dict.fromkeys(blocked))

    @staticmethod
    def _k3_hypotheses(effective_style: StyleCard | None) -> list[str]:
        if not effective_style:
            return []
        return list(dict.fromkeys(rule.statement for rule in effective_style.rules if str(rule.level) == "K3"))

    @staticmethod
    def _shared_base_check(shared_base: StyleCard | None) -> StyleTransferFinding:
        if not shared_base:
            return StyleTransferFinding(
                "BASE",
                "同品类底座",
                "missing",
                "warning",
                action="当前没有同品类共享风格底座；建议先摄入可复用参考或把确认过的反馈 share-to-base。",
            )
        evidence = [
            f"共享规则：{len(shared_base.rules)}",
            f"共享关键词：{len(shared_base.visual_keywords)}",
            f"共享禁忌：{len(shared_base.do_not)}",
        ]
        return StyleTransferFinding("BASE", "同品类底座", "pass", "info", evidence)

    @staticmethod
    def _project_overlay_check(project_overrides: list[str], profile: ProjectProfile | None) -> StyleTransferFinding:
        evidence = [f"项目覆盖项：{len(project_overrides)}"]
        if not profile:
            return StyleTransferFinding("OVERLAY", "项目覆盖层", "missing_profile", "warning", evidence, "缺少项目档案，项目级硬规则和禁忌项不够稳。")
        if not project_overrides:
            return StyleTransferFinding("OVERLAY", "项目覆盖层", "thin", "warning", evidence, "项目覆盖层较薄，容易把同品类风格误当成本项目风格。")
        return StyleTransferFinding("OVERLAY", "项目覆盖层", "pass", "info", evidence + project_overrides[:5])

    @staticmethod
    def _conflict_check(blocked_shared_rules: list[str]) -> StyleTransferFinding:
        evidence = [f"被阻断规则：{len(blocked_shared_rules)}"] + blocked_shared_rules[:5]
        if blocked_shared_rules:
            return StyleTransferFinding(
                "CONFLICT",
                "底座与项目冲突",
                "blocked",
                "blocker",
                evidence,
                "同品类底座存在被项目禁忌或覆盖规则阻断的内容，生成创作包前需设计师确认取舍。",
            )
        return StyleTransferFinding("CONFLICT", "底座与项目冲突", "pass", "info", evidence)

    @staticmethod
    def _k3_boundary_check(k3_hypotheses: list[str]) -> StyleTransferFinding:
        evidence = [f"K3 假设：{len(k3_hypotheses)}"] + k3_hypotheses[:5]
        if k3_hypotheses:
            return StyleTransferFinding(
                "K3",
                "待验证风格边界",
                "needs_review",
                "warning",
                evidence,
                "K3 只能作为探索方向或不确定项，不得直接升级为可迁移规则。",
            )
        return StyleTransferFinding("K3", "待验证风格边界", "pass", "info", evidence)

    @staticmethod
    def _next_actions(status: str, blocked_shared_rules: list[str], k3_hypotheses: list[str]) -> list[str]:
        if status == "blocked":
            return [
                "先确认被项目覆盖或阻断的同品类规则是否应该排除。",
                "修正项目 profile 或同品类 style_base 后重新生成创作包。",
            ]
        actions = [
            "用本报告复核：同品类底座是否真的适合当前项目，而不是机械套用。",
            "重新生成 style_alignment_report，确认 K1/K2 进入执行约束、K3 没有进入正式 Positive。",
        ]
        if k3_hypotheses:
            actions.insert(0, "把 K3 假设留给探索方案或待确认清单，等待设计师反馈后再升级。")
        return actions

    def _is_blocked(self, statement: str, effective_style: StyleCard | None, profile: ProjectProfile | None) -> bool:
        blockers: list[str] = []
        if effective_style:
            blockers.extend(effective_style.do_not)
        if profile:
            blockers.extend(profile.forbidden_rules)
        return any(self._overlaps(statement, blocker) for blocker in blockers)

    @staticmethod
    def _level(rule: StyleRule) -> str:
        return str(rule.level)

    @staticmethod
    def _norm(value: str) -> str:
        return "".join(str(value).lower().split())

    def _overlaps(self, left: str, right: str) -> bool:
        left_norm = self._norm(left)
        right_norm = self._norm(right)
        if not left_norm or not right_norm:
            return False
        return left_norm in right_norm or right_norm in left_norm

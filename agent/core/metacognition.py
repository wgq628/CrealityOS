from __future__ import annotations

from datetime import datetime

from agent.models import (
    AssetIndex,
    AuditFinding,
    DeliveryPreparation,
    KnowledgeLevel,
    MetacognitionAudit,
    ProjectProfile,
    SessionSnapshot,
    StyleCard,
)


class MetacognitionAuditor:
    def build(
        self,
        project_key: str,
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
        snapshot: SessionSnapshot | None,
        asset_index: AssetIndex | None,
        delivery: DeliveryPreparation | None,
        recent_review_notes: list[str],
    ) -> MetacognitionAudit:
        consistency = self._consistency(style_card, profile, snapshot)
        validity = self._validity(style_card, recent_review_notes)
        blind_spots = self._blind_spots(profile, asset_index, delivery, snapshot)
        memory_health = self._memory_health(style_card, profile, snapshot, recent_review_notes)
        actions = self._actions(consistency, validity, blind_spots, memory_health)
        capability_delta = self._capability_delta(style_card, recent_review_notes)
        return MetacognitionAudit(
            project_key=project_key,
            created_at=datetime.now().isoformat(timespec="seconds"),
            consistency=consistency,
            validity=validity,
            blind_spots=blind_spots,
            memory_health=memory_health,
            actions=actions,
            capability_delta=capability_delta,
        )

    @staticmethod
    def render_markdown(audit: MetacognitionAudit) -> str:
        def render_finding(title: str, finding: AuditFinding) -> list[str]:
            return [
                f"## {title}",
                f"- 状态：`{finding.status}`",
                f"- 摘要：{finding.summary}",
                *(f"- 证据：{item}" for item in finding.evidence or ["无"]),
                "",
            ]

        lines = [
            f"# 元认知审计 - {audit.project_key}",
            "",
            f"- 审计时间：`{audit.created_at}`",
            "",
        ]
        lines.extend(render_finding("一致性", audit.consistency))
        lines.extend(render_finding("有效性", audit.validity))
        lines.extend(render_finding("盲点", audit.blind_spots))
        lines.extend(render_finding("记忆健康", audit.memory_health))
        lines.extend(["## 行动项", *(f"- {item}" for item in audit.actions)])
        lines.extend(["", "## 能力增量", *(f"- {item}" for item in audit.capability_delta or ["暂无新增能力摘要"])])
        return "\n".join(lines)

    def _consistency(self, style_card: StyleCard | None, profile: ProjectProfile | None, snapshot: SessionSnapshot | None) -> AuditFinding:
        evidence: list[str] = []
        status = "green"
        if not style_card:
            return AuditFinding("consistency", "yellow", "尚无风格卡，无法判断风格一致性。", [])

        k3_rules = [rule.statement for rule in style_card.rules if rule.level == KnowledgeLevel.K3]
        if k3_rules:
            evidence.append(f"存在 {len(k3_rules)} 条 K3 待验证规则")
            status = "yellow"
        if profile and profile.must_have_rules:
            missing_profile_rules = [rule for rule in profile.must_have_rules if rule not in [item.statement for item in style_card.rules]]
            if missing_profile_rules:
                evidence.append(f"项目固定规则尚未完全进入风格卡：{'; '.join(missing_profile_rules[:3])}")
                status = "yellow"
        if snapshot and snapshot.unresolved_questions:
            evidence.append(f"当前仍有 {len(snapshot.unresolved_questions)} 个未闭合问题")
        summary = "风格结论整体可用，但仍有待验证假设需要继续收敛。" if status == "yellow" else "项目风格规则与会话状态基本一致。"
        return AuditFinding("consistency", status, summary, evidence)

    def _validity(self, style_card: StyleCard | None, recent_review_notes: list[str]) -> AuditFinding:
        if not style_card:
            return AuditFinding("validity", "yellow", "尚无风格卡，无法评估规则有效性。", [])
        evidence: list[str] = []
        status = "green"
        promotable = [rule.statement for rule in style_card.rules if rule.level == KnowledgeLevel.K3 and rule.evidence_count >= 2]
        if promotable:
            evidence.append(f"以下规则可考虑从 K3 升到 K2：{'; '.join(promotable[:3])}")
            status = "yellow"
        if recent_review_notes:
            evidence.append(f"最近有 {len(recent_review_notes)} 条评审回写可作为验证依据")
        if not recent_review_notes:
            evidence.append("近期没有新的设计师反馈，学习闭环可能停滞")
            status = "yellow"
        summary = "有足够反馈推动风格规则演进。" if status == "green" else "需要更多设计师反馈来验证或升级规则。"
        return AuditFinding("validity", status, summary, evidence)

    def _blind_spots(
        self,
        profile: ProjectProfile | None,
        asset_index: AssetIndex | None,
        delivery: DeliveryPreparation | None,
        snapshot: SessionSnapshot | None,
    ) -> AuditFinding:
        evidence: list[str] = []
        status = "green"
        if not profile or not profile.default_sizes:
            evidence.append("项目档案缺少默认尺寸")
            status = "yellow"
        if not profile or not profile.visual_keywords:
            evidence.append("项目档案缺少项目级视觉关键词")
            status = "yellow"
        if not asset_index:
            evidence.append("尚未建立本地资产索引")
            status = "yellow"
        elif not any(card.extension in {".psd", ".psb"} for card in asset_index.asset_cards):
            evidence.append("资产索引中未发现 PSD/PSB 源文件")
            status = "yellow"
        if not delivery:
            evidence.append("尚未生成最新交付 staging 包")
            status = "yellow"
        if snapshot and snapshot.unresolved_questions:
            evidence.append("未闭合问题可能影响本次产出稳定性")
        summary = "当前还存在几个影响自动化稳定性的缺口。" if status == "yellow" else "主要闭环要素已经齐备。"
        return AuditFinding("blind_spots", status, summary, evidence)

    def _memory_health(
        self,
        style_card: StyleCard | None,
        profile: ProjectProfile | None,
        snapshot: SessionSnapshot | None,
        recent_review_notes: list[str],
    ) -> AuditFinding:
        evidence: list[str] = []
        status = "green"
        if style_card:
            evidence.append(f"风格卡规则数：{len(style_card.rules)}")
        else:
            evidence.append("风格卡缺失")
            status = "yellow"
        if profile:
            evidence.append(f"项目档案禁忌项：{len(profile.forbidden_rules)}")
        else:
            evidence.append("项目档案缺失")
            status = "yellow"
        if snapshot:
            evidence.append(f"最近会话产物数：{len(snapshot.last_artifacts)}")
        else:
            evidence.append("没有可恢复的最近会话快照")
            status = "yellow"
        if not recent_review_notes:
            evidence.append("没有近期评审记录，长期学习记忆偏弱")
            status = "yellow"
        summary = "项目记忆已经开始沉淀。" if status == "green" else "记忆层已有基础，但还需要更多持续回写。"
        return AuditFinding("memory_health", status, summary, evidence)

    @staticmethod
    def _actions(*findings: AuditFinding) -> list[str]:
        actions: list[str] = []
        for finding in findings:
            if finding.status != "green":
                if finding.category == "consistency":
                    actions.append("优先处理 K3 假设和未闭合问题，避免把不稳定风格当成定论。")
                elif finding.category == "validity":
                    actions.append("对最近产出的创作包补充设计师反馈，推动规则升降级。")
                elif finding.category == "blind_spots":
                    actions.append("补齐项目档案尺寸/关键词、资产索引和交付 staging 信息。")
                elif finding.category == "memory_health":
                    actions.append("保持每次评审后回写 review report，并定期生成 transition summary。")
        return list(dict.fromkeys(actions)) or ["当前状态健康，继续用真实需求推进风格沉淀。"]

    @staticmethod
    def _capability_delta(style_card: StyleCard | None, recent_review_notes: list[str]) -> list[str]:
        delta: list[str] = []
        if style_card:
            k1_count = sum(1 for rule in style_card.rules if rule.level == KnowledgeLevel.K1)
            k2_count = sum(1 for rule in style_card.rules if rule.level == KnowledgeLevel.K2)
            delta.append(f"当前已沉淀 {k1_count} 条 K1 固定规则，{k2_count} 条 K2 已验证风格规则。")
        if recent_review_notes:
            delta.append(f"最近 {len(recent_review_notes)} 条评审反馈已进入可复用记忆。")
        return delta

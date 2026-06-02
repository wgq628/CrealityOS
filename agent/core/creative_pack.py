from __future__ import annotations

from agent.models import CreativePack, DeliveryItem, DeliveryManifest, DesignBrief, KnowledgeLevel, ProjectProfile, PromptPack, StyleCard, StyleRule


class CreativePackBuilder:
    def build(self, brief: DesignBrief, style_card: StyleCard, profile: ProjectProfile | None = None) -> CreativePack:
        prompt_pack = PromptPack(
            positive=self._build_positive_prompts(brief, style_card, profile),
            negative=self._build_negative_prompts(brief, style_card, profile),
            reference_groups=self._build_reference_groups(brief, style_card),
        )
        references = self._build_references(style_card)
        composition = self._build_composition_suggestions(brief, style_card)
        psd_guidance = self._build_psd_guidance(brief, style_card)
        uncertainties = list(dict.fromkeys(brief.missing_information + style_card.open_questions + self._pending_uncertainties(style_card)))
        manifest = self._build_manifest(brief, style_card, profile)

        return CreativePack(
            brief=brief,
            style_card=style_card,
            references=references,
            prompt_pack=prompt_pack,
            composition_suggestions=composition,
            psd_guidance=psd_guidance,
            uncertainties=uncertainties,
            delivery_manifest=manifest,
        )

    @staticmethod
    def _build_positive_prompts(brief: DesignBrief, style_card: StyleCard, profile: ProjectProfile | None) -> list[str]:
        rules = [rule.statement for rule in CreativePackBuilder._confirmed_rules(style_card)[:5]]
        prompt = [
            brief.same_category,
            f"游戏项目：{brief.game_name}" if brief.game_name != "待确认" else "",
            f"玩法理解：{brief.gameplay_summary}" if brief.gameplay_summary != "待确认" else "",
            f"风格方向：{brief.style_direction}" if brief.style_direction != "待确认" else "",
            brief.objective,
            brief.platform,
            ", ".join(style_card.visual_keywords[:5]) or "game key visual",
        ]
        if profile and profile.gameplay_tags:
            prompt.append("玩法标签：" + ",".join(profile.gameplay_tags[:4]))
        if rules:
            prompt.append(" | ".join(rules))
        return [
            "，".join(part for part in prompt if part and part != "待确认"),
            "主体突出，层级清晰，保留文案区与按钮区，适配买量或活动转化场景",
        ]

    @staticmethod
    def _build_negative_prompts(brief: DesignBrief, style_card: StyleCard, profile: ProjectProfile | None) -> list[str]:
        negatives = list(style_card.do_not)
        if profile:
            negatives.extend(profile.forbidden_rules)
        negatives.extend(
            [
                "避免信息层级混乱",
                "避免主体与背景对比不足",
                "避免字体风格和项目世界观冲突",
            ]
        )
        if "待确认" in (brief.platform, brief.target_audience):
            negatives.append("避免在平台和受众未确认前做过度细化的媒介假设")
        return list(dict.fromkeys(negatives))

    @staticmethod
    def _build_reference_groups(brief: DesignBrief, style_card: StyleCard) -> list[str]:
        groups = [
            f"同品类风格底座：{brief.same_category}",
            f"游戏玩法参考：{brief.gameplay_summary}" if brief.gameplay_summary != "待确认" else "游戏玩法参考：待确认",
            f"平面任务拆解：{'；'.join(brief.task_breakdown[:5])}" if brief.task_breakdown else "平面任务拆解：待确认",
            f"投放美术风格方向：{brief.style_direction}" if brief.style_direction != "待确认" else "投放美术风格方向：待确认",
            "信息层级参考：标题/利益点/按钮/主体的优先级案例",
            "构图参考：主体站位、留白结构、文案安全区",
        ]
        if brief.reference_assets:
            groups.append("平面需求参考图/路径：" + "；".join(brief.reference_assets[:6]))
        pending = CreativePackBuilder._pending_rules(style_card)
        if pending:
            groups.append("K3待验证探索：" + "；".join(rule.statement for rule in pending[:3]))
        return groups

    @staticmethod
    def _build_references(style_card: StyleCard) -> list[str]:
        references = []
        for rule in CreativePackBuilder._ordered_rules(style_card)[:8]:
            prefix = "待验证" if CreativePackBuilder._is_pending(rule) else "已确认"
            references.append(f"[{rule.level} {prefix}] {rule.statement} | 依据：{rule.rationale}")
        return references or ["当前尚无已验证风格规则，先以 K3 假设探索并等待设计师确认"]

    @staticmethod
    def _build_composition_suggestions(brief: DesignBrief, style_card: StyleCard) -> list[str]:
        suggestions = [
            "先确认主体、利益点、按钮三层优先级，再决定背景复杂度",
            "为尺寸适配预留裁切安全区，避免主元素靠边",
        ]
        if brief.sizes:
            suggestions.append(f"本次至少考虑 {', '.join(brief.sizes)} 的裁切一致性")
        if "9:16" in brief.sizes:
            suggestions.append("默认按 9:16 竖版投放素材组织主视觉、玩法演示区和底部行动区")
        if brief.task_breakdown:
            suggestions.extend(brief.task_breakdown[:2])
        if any(keyword in style_card.visual_keywords for keyword in ("活动海报", "角色突出")):
            suggestions.append("角色主体建议占据中心或黄金分割点，并与文案区形成清楚分层")
        return suggestions

    @staticmethod
    def _build_psd_guidance(brief: DesignBrief, style_card: StyleCard) -> list[str]:
        if CreativePackBuilder._is_storyboard_request(brief, style_card):
            guidance = [
                "剧情向片头/分镜优先检查横竖构图适配，不默认进入 PSD 分层或切图流程",
                "横竖适配时保护角色表情、关键道具、视角关系和动作情绪",
                "除非需求明确要求 PSD/切图，否则交付检查只关注画面成片/分镜图输出",
            ]
            if brief.deliverables:
                guidance.append(f"交付物涉及：{', '.join(brief.deliverables)}，按成片/分镜图输出核对")
            return guidance
        guidance = [
            "分组建议：background / subject / copy / CTA / effects / exports",
            "把后续可能切图的按钮、角标、卡片底版单独分层",
            "保留可替换文案和可扩展安全区，减少多尺寸返工",
        ]
        if brief.deliverables:
            guidance.append(f"交付物涉及：{', '.join(brief.deliverables)}，请提前规划对应图层命名")
        return guidance

    @staticmethod
    def _build_manifest(brief: DesignBrief, style_card: StyleCard, profile: ProjectProfile | None) -> DeliveryManifest:
        profile_sizes = profile.default_sizes if profile else []
        sizes = profile_sizes if profile_sizes and brief.sizes == ["9:16"] else brief.sizes or profile_sizes or ["待确认尺寸"]
        if CreativePackBuilder._is_storyboard_request(brief, style_card):
            format_hint = " + ".join(brief.deliverables or ["PNG", "JPG"])
        else:
            format_hint = " + ".join(profile.export_formats) if profile and profile.export_formats else "PSD + PNG"
        export_items = [
            DeliveryItem(
                name=CreativePackBuilder._render_export_name(brief, profile, size),
                size=size,
                format_hint=format_hint,
                notes="导出前确认裁切安全区与文字清晰度",
            )
            for size in sizes
        ]
        naming_rules = [
            profile.delivery_naming_template if profile else f"{brief.project_key or 'project'}_{brief.work_item_id}_scene_v001",
            "正式导出前先确认尺寸、语言版本和平台后缀",
        ]
        if CreativePackBuilder._is_storyboard_request(brief, style_card):
            slicing_notes = [
                "不要覆盖已有正式资产",
                "本单按剧情向分镜/片头画面核对横竖适配，不默认要求 PSD 源文件或独立切图。",
                "确认每个尺寸下角色表情、关键道具、视角关系和动作情绪不被裁切破坏。",
            ]
        else:
            slicing_notes = [
                "不要覆盖已有正式资产",
                "切图前确认是否需要 1x/2x 或 Android/iOS 双端规格",
                "如存在按钮、底板、icon，请输出独立切图说明",
            ]
        if profile and not CreativePackBuilder._is_storyboard_request(brief, style_card):
            slicing_notes.extend(profile.slice_requirements)
        for rule in style_card.rules:
            if rule.level == "K1" and ("命名" in rule.statement or "尺寸" in rule.statement):
                naming_rules.append(rule.statement)
        return DeliveryManifest(
            project_key=brief.project_key or "unknown-project",
            work_item_id=brief.work_item_id,
            naming_rules=list(dict.fromkeys(naming_rules)),
            export_items=export_items,
            slicing_notes=slicing_notes,
            requires_confirmation=True,
        )

    @staticmethod
    def _render_export_name(brief: DesignBrief, profile: ProjectProfile | None, size: str) -> str:
        if not profile:
            return f"{brief.work_item_id}_{size}"
        template = profile.delivery_naming_template
        return template.format(
            project_key=brief.project_key or "project",
            work_item_id=brief.work_item_id,
            size=size.replace(":", "x"),
            version="v001",
        )

    @staticmethod
    def _confirmed_rules(style_card: StyleCard) -> list[StyleRule]:
        return [rule for rule in CreativePackBuilder._ordered_rules(style_card) if CreativePackBuilder._is_confirmed(rule)]

    @staticmethod
    def _pending_rules(style_card: StyleCard) -> list[StyleRule]:
        return [rule for rule in CreativePackBuilder._ordered_rules(style_card) if CreativePackBuilder._is_pending(rule)]

    @staticmethod
    def _pending_uncertainties(style_card: StyleCard) -> list[str]:
        return [f"K3待验证风格：{rule.statement}" for rule in CreativePackBuilder._pending_rules(style_card)]

    @staticmethod
    def _ordered_rules(style_card: StyleCard) -> list[StyleRule]:
        rank = {"K1": 0, "K2": 1, "K3": 2, "K4": 3}
        return sorted(style_card.rules, key=lambda rule: (rank.get(str(rule.level), 9), rule.statement))

    @staticmethod
    def _is_confirmed(rule: StyleRule) -> bool:
        return rule.level in {KnowledgeLevel.K1, KnowledgeLevel.K2, "K1", "K2"}

    @staticmethod
    def _is_pending(rule: StyleRule) -> bool:
        return rule.level in {KnowledgeLevel.K3, "K3"}

    @staticmethod
    def _is_storyboard_request(brief: DesignBrief, style_card: StyleCard) -> bool:
        text = "\n".join(
            [
                brief.objective,
                brief.source_requirement_summary,
                *brief.task_breakdown,
                brief.style_direction,
                *style_card.visual_keywords,
                *(rule.statement for rule in style_card.rules),
            ]
        )
        return any(token in text for token in ("剧情", "片头", "分镜", "镜头", "画面描述"))

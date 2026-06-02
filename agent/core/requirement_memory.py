from __future__ import annotations

from datetime import datetime

from agent.memory.store import MemoryStore
from agent.models import DesignBrief, KnowledgeLevel, ProjectProfile, RequirementMemoryReport, StyleCard, StyleRule


class RequirementMemoryEngine:
    """Conservative self-learning from parsed flat-design requirements into local memory."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def learn(self, brief: DesignBrief, profile: ProjectProfile) -> RequirementMemoryReport:
        project_key = profile.project_key
        learned_gameplay_tags = self._gameplay_tags(brief)
        learned_visual_keywords = self._visual_keywords(brief)
        learned_default_sizes = self._default_sizes(brief)
        learned_deliverables = self._deliverables(brief)
        learned_slice_requirements = self._slice_requirements(brief)
        learned_style_rules = self._style_rules(brief)

        self._merge_profile(profile, brief, learned_gameplay_tags, learned_visual_keywords, learned_default_sizes, learned_deliverables, learned_slice_requirements)
        profile_path = self.store.save_project_profile(profile)

        style_card = self.store.load_style_card(project_key) or self._blank_style_card(project_key, brief.same_category)
        self._merge_style_card(style_card, learned_visual_keywords, learned_style_rules, brief)
        style_path = self.store.save_style_card(style_card)

        warnings: list[str] = []
        if not brief.reference_assets:
            warnings.append("本次平面需求描述未提取到参考图或素材路径，后续风格学习证据会偏弱。")
        if brief.platform == "待确认":
            warnings.append("投放平台仍未确认，先按通用投放素材处理。")

        return RequirementMemoryReport(
            project_key=project_key,
            work_item_id=brief.work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            game_name=brief.game_name,
            same_category=brief.same_category,
            learned_audience=brief.target_audience,
            learned_gameplay_tags=learned_gameplay_tags,
            learned_visual_keywords=learned_visual_keywords,
            learned_default_sizes=learned_default_sizes,
            learned_deliverables=learned_deliverables,
            learned_style_rules=learned_style_rules,
            learned_slice_requirements=learned_slice_requirements,
            source_requirement_summary=brief.source_requirement_summary,
            task_breakdown=brief.task_breakdown,
            memory_paths={
                "project_profile": str(profile_path),
                "style_card": str(style_path),
            },
            warnings=warnings,
            next_time_defaults=self._next_time_defaults(brief, learned_default_sizes, learned_deliverables),
        )

    @staticmethod
    def render_markdown(report: RequirementMemoryReport) -> str:
        return "\n".join(
            [
                f"# 需求自学记忆 - {report.game_name}",
                "",
                f"- 项目：`{report.project_key}`",
                f"- 工作项：`{report.work_item_id}`",
                f"- 创建时间：`{report.created_at}`",
                f"- 同品类底座：`{report.same_category}`",
                f"- 受众：{report.learned_audience}",
                "",
                "## 平面需求摘要",
                report.source_requirement_summary,
                "",
                "## 本次要做什么",
                *(f"- {item}" for item in report.task_breakdown or ["待确认"]),
                "",
                "## 学到的玩法与受众",
                *(f"- {item}" for item in report.learned_gameplay_tags or ["待确认"]),
                "",
                "## 学到的画风/投放美术方向",
                *(f"- {item}" for item in report.learned_visual_keywords or ["待确认"]),
                "",
                "## 学到的尺寸与交付",
                f"- 默认尺寸/比例：{', '.join(report.learned_default_sizes) if report.learned_default_sizes else '待确认'}",
                f"- 交付物：{', '.join(report.learned_deliverables) if report.learned_deliverables else '待确认'}",
                "",
                "## 写入的风格规则",
                *(f"- {item}" for item in report.learned_style_rules or ["无"]),
                "",
                "## 切图/PSD 习惯",
                *(f"- {item}" for item in report.learned_slice_requirements or ["待确认"]),
                "",
                "## 记忆文件",
                *(f"- {key}: `{value}`" for key, value in report.memory_paths.items()),
                "",
                "## 提醒",
                *(f"- {item}" for item in report.warnings or ["无"]),
                "",
                "## 下次默认沿用",
                *(f"- {item}" for item in report.next_time_defaults),
            ]
        )

    @staticmethod
    def _merge_profile(
        profile: ProjectProfile,
        brief: DesignBrief,
        gameplay_tags: list[str],
        visual_keywords: list[str],
        default_sizes: list[str],
        deliverables: list[str],
        slice_requirements: list[str],
    ) -> None:
        profile.same_category = brief.same_category or profile.same_category
        if brief.game_name != "待确认" and (
            profile.display_name in {profile.project_key, "", "待确认"} or profile.display_name == brief.work_item_id or profile.display_name.isdigit()
        ):
            profile.display_name = brief.game_name
        RequirementMemoryEngine._extend(profile.gameplay_tags, gameplay_tags)
        RequirementMemoryEngine._extend(profile.visual_keywords, visual_keywords)
        RequirementMemoryEngine._extend(profile.default_sizes, default_sizes)
        RequirementMemoryEngine._extend(profile.required_deliverables, deliverables)
        export_formats = ["PNG" if item == "切图" else item for item in deliverables]
        RequirementMemoryEngine._extend(profile.export_formats, export_formats)
        RequirementMemoryEngine._extend(profile.slice_requirements, slice_requirements)
        RequirementMemoryEngine._extend(
            profile.notes,
            [
                "自学引擎：相同项目下次优先复用平面需求描述里的玩法、受众、尺寸和交付线索。",
                f"最近受众判断：{brief.target_audience}",
            ],
        )

    @staticmethod
    def _merge_style_card(style_card: StyleCard, visual_keywords: list[str], style_rules: list[str], brief: DesignBrief) -> None:
        style_card.same_category = brief.same_category or style_card.same_category
        RequirementMemoryEngine._extend(style_card.visual_keywords, visual_keywords)
        RequirementMemoryEngine._extend(style_card.composition_preferences, brief.task_breakdown[:4])
        if brief.source_requirement_summary != "待确认":
            RequirementMemoryEngine._extend(style_card.evidence_summary, [f"requirement:{brief.work_item_id}:{brief.source_requirement_summary[:120]}"])
        for statement in style_rules:
            RequirementMemoryEngine._merge_rule(
                style_card.rules,
                StyleRule(
                    statement=statement,
                    level=KnowledgeLevel.K3,
                    rationale="来自平面需求描述的自动学习，等待设计师反馈后再升级",
                    source_refs=[f"requirement:{brief.work_item_id}"],
                    evidence_count=1,
                    scope="project",
                ),
            )

    @staticmethod
    def _gameplay_tags(brief: DesignBrief) -> list[str]:
        text = "\n".join([brief.game_name, brief.gameplay_summary, brief.source_requirement_summary, brief.style_direction])
        tags: list[str] = []
        if brief.game_name != "待确认":
            tags.append(brief.game_name)
        if any(token in text for token in ("分类", "收集区", "卡片")):
            tags.extend(["分类整理", "卡片玩法", "休闲益智"])
        if any(token in text for token in ("关卡", "lv3", "lv4")):
            tags.append("关卡排版")
        if "投放" in text or brief.deliverables:
            tags.append("投放素材")
        return list(dict.fromkeys(tags))

    @staticmethod
    def _visual_keywords(brief: DesignBrief) -> list[str]:
        text = "\n".join([brief.gameplay_summary, brief.source_requirement_summary, brief.style_direction])
        keywords = ["投放素材美术", "玩法一眼可懂", "信息层级清晰"]
        if RequirementMemoryEngine._is_storyboard_request(brief):
            keywords.extend(["剧情向分镜", "3D 卡通电影感", "横竖构图适配"])
        if any(token in text for token in ("卡片", "书", "词条")):
            keywords.extend(["卡片/书本/词条可读", "休闲益智清爽排版"])
        if any(token in text for token in ("竞品", "参考图", "参照排版")):
            keywords.append("参考竞品版式结构")
        if not RequirementMemoryEngine._is_storyboard_request(brief) and ("PSD" in brief.deliverables or "切图" in brief.deliverables):
            keywords.append("PSD 分层与切图友好")
        return list(dict.fromkeys(keywords))

    @staticmethod
    def _default_sizes(brief: DesignBrief) -> list[str]:
        return list(dict.fromkeys(brief.sizes or ["9:16"]))

    @staticmethod
    def _deliverables(brief: DesignBrief) -> list[str]:
        deliverables = list(brief.deliverables)
        if RequirementMemoryEngine._is_storyboard_request(brief) and RequirementMemoryEngine._negates_psd_or_slicing(brief):
            deliverables = [item for item in deliverables if item not in {"PSD", "切图"}]
        if not RequirementMemoryEngine._is_storyboard_request(brief) and "PSD" not in deliverables:
            deliverables.append("PSD")
        if "切图" in deliverables and "PNG" not in deliverables:
            deliverables.append("PNG")
        return list(dict.fromkeys(deliverables))

    @staticmethod
    def _slice_requirements(brief: DesignBrief) -> list[str]:
        if RequirementMemoryEngine._is_storyboard_request(brief):
            return [
                "剧情向片头/分镜以横竖构图适配和镜头叙事为主，不默认套用 PSD 分层或切图规则。",
                "除非需求明确要求 PSD/切图，否则交付检查不把 PSD 源文件和独立切图作为必需项。",
                "横竖适配时优先保护角色表情、关键道具、视角关系和动作情绪，不让裁切破坏叙事。",
            ]
        items = [
            "投放素材 PSD 需保留可复用图层分组，便于后续改版。",
            "按钮、底板、卡片、图标等可复用元素独立分层并便于切图。",
        ]
        if "9:16" in brief.sizes:
            items.append("默认按 9:16 竖版投放素材预留上下安全区。")
        if any("三本书" in item or "四本书" in item for item in brief.task_breakdown):
            items.append("三本书/四本书变体需保持共用底板和差异图层清晰。")
        return items

    @staticmethod
    def _style_rules(brief: DesignBrief) -> list[str]:
        rules = [
            "同项目投放美术需求优先读取平面需求描述作为主需求来源。",
            "投放素材默认优先 9:16 竖版构图，除非需求明确指定其他尺寸或比例。",
            "画面必须让玩法目标和可交互元素一眼可懂，避免只做氛围图。",
        ]
        if RequirementMemoryEngine._is_storyboard_request(brief):
            rules.append("剧情向片头/分镜任务优先服务镜头叙事、角色表情和横竖适配，不默认套用 PSD 分层或切图流程。")
        if brief.gameplay_summary != "待确认":
            rules.append(f"本项目玩法理解：{brief.gameplay_summary}")
        if brief.style_direction != "待确认":
            rules.append(f"本项目画风方向：{brief.style_direction}")
        return list(dict.fromkeys(rules))

    @staticmethod
    def _next_time_defaults(brief: DesignBrief, sizes: list[str], deliverables: list[str]) -> list[str]:
        delivery_line = (
            f"剧情向分镜默认交付物先按 `{', '.join(deliverables)}` 处理；除非需求明确要求 PSD/切图，否则不套用 PSD/切图流程。"
            if RequirementMemoryEngine._is_storyboard_request(brief)
            else f"默认交付物先按 `{', '.join(deliverables)}` 规划 PSD 和切图。"
        )
        execution_line = (
            "先拆镜头、角色表情、关键道具、横竖裁切安全区，再进入提示词或分镜执行。"
            if RequirementMemoryEngine._is_storyboard_request(brief)
            else "先拆玩法、参考图、关卡/版本数量，再进入提示词或 PSD 执行。"
        )
        return [
            "先读取平面需求描述，其他字段只做辅助上下文。",
            f"相同项目默认受众先按 `{brief.target_audience}` 处理，除非新需求明确覆盖。",
            f"默认尺寸/比例先按 `{', '.join(sizes)}` 处理，交付前再确认是否多尺寸适配。",
            delivery_line,
            execution_line,
        ]

    @staticmethod
    def _is_storyboard_request(brief: DesignBrief) -> bool:
        text = "\n".join([brief.objective, brief.source_requirement_summary, *brief.task_breakdown, brief.style_direction])
        return any(token in text for token in ("剧情", "片头", "分镜", "镜头", "画面描述"))

    @staticmethod
    def _negates_psd_or_slicing(brief: DesignBrief) -> bool:
        text = "\n".join([brief.objective, brief.source_requirement_summary, *brief.task_breakdown, brief.style_direction])
        return any(token in text for token in ("不套用 PSD", "不默认套用 PSD", "PSD类和切图的不适用", "PSD/切图检查仅在需求明确要求"))

    @staticmethod
    def _blank_style_card(project_key: str, same_category: str) -> StyleCard:
        return StyleCard(
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

    @staticmethod
    def _extend(target: list[str], values: list[str]) -> None:
        target[:] = list(dict.fromkeys(target + [value for value in values if value and value != "待确认"]))

    @staticmethod
    def _merge_rule(existing_rules: list[StyleRule], incoming: StyleRule) -> None:
        for rule in existing_rules:
            if rule.statement == incoming.statement:
                rule.evidence_count += incoming.evidence_count
                rule.source_refs.extend(ref for ref in incoming.source_refs if ref not in rule.source_refs)
                return
        existing_rules.append(incoming)

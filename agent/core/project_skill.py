from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from agent.models import ProjectProfile, ProjectStyleSkillReport, StyleCard
from agent.utils import dump_json, load_json


class ProjectSkillBuilder:
    """Render a local Codex skill from learned project memory."""

    def build(
        self,
        project_key: str,
        memory_root: Path,
        profile: ProjectProfile | None,
        style_card: StyleCard | None,
        output_dir: str | None = None,
    ) -> ProjectStyleSkillReport:
        project_dir = memory_root / "projects" / project_key
        requirement_memory = load_json(project_dir / "latest_requirement_memory_report.json", {})
        learning_digest = load_json(project_dir / "latest_learning_digest.json", {})
        skill_name = self.skill_name(project_key, profile, style_card, requirement_memory)
        skill_dir = self._skill_dir(project_dir, skill_name, output_dir)
        skill_dir.mkdir(parents=True, exist_ok=True)

        source_artifacts = {
            "project_profile": str(project_dir / "project_profile.json") if profile else None,
            "style_card": str(project_dir / "style_card.json") if style_card else None,
            "latest_requirement_memory_report": str(project_dir / "latest_requirement_memory_report.json") if requirement_memory else None,
            "latest_learning_digest": str(project_dir / "latest_learning_digest.json") if learning_digest else None,
        }
        warnings = self._warnings(profile, style_card, requirement_memory)
        missing_memory = not profile or not style_card or not requirement_memory
        status = "draft" if missing_memory else ("needs_designer_confirmation" if warnings else "ready")
        created_at = datetime.now().isoformat(timespec="seconds")
        skill_file = skill_dir / "SKILL.md"
        manifest_file = skill_dir / "skill_manifest.json"
        report = ProjectStyleSkillReport(
            project_key=project_key,
            skill_name=skill_name,
            display_name=self._display_name(project_key, profile, requirement_memory),
            created_at=created_at,
            status=status,
            skill_dir=str(skill_dir),
            skill_file=str(skill_file),
            manifest_file=str(manifest_file),
            source_artifacts=source_artifacts,
            warnings=warnings,
            next_actions=self._next_actions(project_key, skill_name, status),
        )
        skill_file.write_text(
            self.render_skill_markdown(
                report=report,
                profile=profile,
                style_card=style_card,
                requirement_memory=requirement_memory,
                learning_digest=learning_digest,
            ),
            encoding="utf-8",
        )
        dump_json(
            manifest_file,
            {
                "project_key": project_key,
                "skill_name": skill_name,
                "created_at": created_at,
                "status": status,
                "source_artifacts": source_artifacts,
                "warnings": warnings,
            },
        )
        return report

    def render_skill_markdown(
        self,
        report: ProjectStyleSkillReport,
        profile: ProjectProfile | None,
        style_card: StyleCard | None,
        requirement_memory: dict[str, Any],
        learning_digest: dict[str, Any],
    ) -> str:
        description = self._description(report, profile, style_card, requirement_memory)
        audience = self._audience(profile, requirement_memory)
        profile_matches_requirement = self._profile_matches_requirement(profile, requirement_memory)
        profile_gameplay = profile.gameplay_tags if profile and profile_matches_requirement else []
        profile_visual = profile.visual_keywords if profile and profile_matches_requirement else []
        profile_sizes = profile.default_sizes if profile and profile_matches_requirement else []
        profile_deliverables = profile.required_deliverables if profile and profile_matches_requirement else []
        profile_slice_requirements = profile.slice_requirements if profile and profile_matches_requirement else []
        style_visual = style_card.visual_keywords if style_card and profile_matches_requirement else []
        style_composition = style_card.composition_preferences if style_card and profile_matches_requirement else []
        work_item_id = str(requirement_memory.get("work_item_id") or "").strip()
        gameplay = self._items(
            profile_gameplay
            + self._list(requirement_memory.get("learned_gameplay_tags"))
        )
        visual_keywords = self._items(
            profile_visual
            + style_visual
            + self._list(requirement_memory.get("learned_visual_keywords")),
            limit=14,
        )
        sizes = self._items(
            profile_sizes + self._list(requirement_memory.get("learned_default_sizes")),
            default=["9:16"],
        )
        deliverables = self._items(
            profile_deliverables + self._list(requirement_memory.get("learned_deliverables")),
            default=["PSD", "PNG", "切图"],
        )
        storyboard_mode = self._is_storyboard_mode(requirement_memory, visual_keywords, confirmed_rules=[], hypotheses=[])
        composition = self._items(style_composition, limit=8)
        must_have = self._items(profile.must_have_rules if profile and profile_matches_requirement else [], limit=10)
        forbidden = self._items(
            (profile.forbidden_rules if profile and profile_matches_requirement else [])
            + (style_card.do_not if style_card and profile_matches_requirement else []),
            limit=10,
        )
        slice_requirements = self._items(
            profile_slice_requirements + self._list(requirement_memory.get("learned_slice_requirements")),
            limit=10,
        )
        confirmed_rules = self._style_rules(style_card, levels={"K1", "K2"}, work_item_id=work_item_id)
        hypotheses = self._style_rules(style_card, levels={"K3"}, work_item_id=work_item_id)
        storyboard_mode = self._is_storyboard_mode(requirement_memory, visual_keywords, confirmed_rules, hypotheses)
        task_breakdown = self._items(self._list(requirement_memory.get("task_breakdown")), limit=8)
        next_time = self._items(self._list(learning_digest.get("next_time_checklist")), limit=8)
        source_summary = str(requirement_memory.get("source_requirement_summary") or "暂无已学习的平面需求摘要")
        delivery_lines = [
            f"- 默认尺寸：{', '.join(sizes)}",
            f"- 默认交付：{', '.join(deliverables)}",
        ]
        if storyboard_mode:
            delivery_lines.append("- 剧情向片头/分镜按横竖适配和画面叙事核对，不默认套用 PSD 分层或切图规则。")
            psd_section_title = "## 横竖适配与剧情向交付"
            psd_section_items = slice_requirements or [
                "保护角色表情、关键道具、视角关系和动作情绪。",
                "除非需求明确要求 PSD/切图，否则不把 PSD 源文件或独立切图作为必需项。",
            ]
        else:
            delivery_lines.append("- PSD 必须服务后续改版：图层分组、按钮/底板/卡片/图标等可复用元素要独立。")
            psd_section_title = "## PSD 与切图规则"
            psd_section_items = slice_requirements

        lines = [
            "---",
            f"name: {report.skill_name}",
            f"description: {json.dumps(description, ensure_ascii=False)}",
            "---",
            "",
            f"# {report.display_name} 项目风格副驾",
            "",
            "## 使用流程",
            "- 先读取工作项里的 `平面需求描述`，把它作为主需求来源；视频需求、评论和其他字段只做补充校验。",
            "- 从平面需求中提取游戏名称、玩法目标、受众、参考图、尺寸、交付物、切图路径和版本数量。",
            "- 默认按投放素材美术处理：优先保证玩法一眼可懂、主元素突出、转化路径清晰。",
            "- 当需求未写尺寸时，默认先按 `9:16` 竖版投放素材规划；如需求明确指定其他尺寸，以需求为准。",
            "- 输出创作包、评审包或交付检查前，复用本 Skill 的项目规则，并把新确认的反馈写回项目记忆。",
            "",
            "## 项目身份",
            f"- 项目 Key：`{report.project_key}`",
            f"- 游戏/项目名：{report.display_name}",
            f"- 同品类底座：{profile.same_category if profile else (style_card.same_category if style_card else '待学习')}",
            f"- 受众判断：{audience}",
            "",
            "## 玩法与受众信号",
            *self._bullet_lines(gameplay, "待从平面需求描述或项目档案学习"),
            "",
            "## 视觉方向",
            *self._bullet_lines(visual_keywords, "待沉淀视觉关键词"),
            "",
            "## 版式与构图",
            *self._bullet_lines(composition, "先拆解参考图/竞品的信息结构，再做投放平面重排"),
            "",
            "## 尺寸与交付默认值",
            *delivery_lines,
            "",
            psd_section_title,
            *self._bullet_lines(psd_section_items, "按钮、底板、图标等可复用元素独立分层"),
            "",
            "## 已确认/较高置信规则",
            *self._bullet_lines(must_have + confirmed_rules, "暂无 K1/K2 硬规则，先按项目档案和需求证据执行"),
            "",
            "## 禁忌项",
            *self._bullet_lines(forbidden, "暂无明确禁忌项"),
            "",
            "## 待验证假设",
            *self._bullet_lines(hypotheses, "无；如出现 K3 假设，交付前需要设计师确认"),
            "",
            "## 最近平面需求拆解",
            f"- 需求摘要：{source_summary}",
            *self._bullet_lines(task_breakdown, "暂无最近任务拆解"),
            "",
            "## 下次复用清单",
            *self._bullet_lines(next_time, "优先读取 project_profile.json、style_card.json 和最新需求记忆"),
            "",
            "## 安全边界",
            "- K3 规则是系统从需求和参考信息中推断的假设，不能当成项目硬规则直接发布。",
            "- 不自动调用 Pixpark、Photoshop、Meegle 发布或工作项流转；外部副作用必须由显式确认门控制。",
            "- 如果平面需求描述与本 Skill 冲突，以当前需求为准，并把差异记录为新的待确认反馈。",
            "",
            "## 记忆来源",
            *self._source_lines(report.source_artifacts),
        ]
        return "\n".join(lines) + "\n"

    def skill_name(
        self,
        project_key: str,
        profile: ProjectProfile | None,
        style_card: StyleCard | None,
        requirement_memory: dict[str, Any] | None = None,
    ) -> str:
        parts = ["game-style", self._ascii_slug(project_key, "project")]
        memory = requirement_memory or {}
        game_name = str(memory.get("game_name") or "").strip()
        work_item_id = str(memory.get("work_item_id") or "").strip()
        profile_name = profile.display_name if profile else ""
        display = self._ascii_slug(game_name or profile_name, "")
        category = self._ascii_slug((profile.same_category if profile else None) or (style_card.same_category if style_card else ""), "")
        profile_slug = self._ascii_slug(profile_name, "") if profile_name else ""
        if game_name and profile_name and game_name != profile_name and work_item_id:
            parts.append(work_item_id)
        elif display and display not in parts and len(display) >= 3:
            parts.append(display)
        elif profile_slug and profile_slug not in parts and len(profile_slug) >= 3:
            parts.append(profile_slug)
        elif category and category not in parts:
            parts.append(category)
        return "-".join(parts)[:80].strip("-")

    @staticmethod
    def _skill_dir(project_dir: Path, skill_name: str, output_dir: str | None) -> Path:
        if not output_dir:
            return project_dir / "skills" / skill_name
        base = Path(output_dir)
        return base if base.name == skill_name else base / skill_name

    @staticmethod
    def _ascii_slug(value: str, fallback: str) -> str:
        text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        text = re.sub(r"-+", "-", text)
        return text or fallback

    @staticmethod
    def _display_name(project_key: str, profile: ProjectProfile | None, requirement_memory: dict[str, Any]) -> str:
        learned_game = str(requirement_memory.get("game_name") or "").strip()
        if learned_game and learned_game != "待确认":
            return learned_game
        if profile and profile.display_name:
            return profile.display_name
        return project_key

    @staticmethod
    def _audience(profile: ProjectProfile | None, requirement_memory: dict[str, Any]) -> str:
        learned = str(requirement_memory.get("learned_audience") or "").strip()
        if learned and learned != "待确认":
            return learned
        if profile:
            for note in profile.notes:
                if "受众" in note:
                    return note
        return "待从平面需求描述和参考图继续学习"

    @staticmethod
    def _description(
        report: ProjectStyleSkillReport,
        profile: ProjectProfile | None,
        style_card: StyleCard | None,
        requirement_memory: dict[str, Any],
    ) -> str:
        display = report.display_name
        category = profile.same_category if profile else (style_card.same_category if style_card else "game project")
        tags = ", ".join(ProjectSkillBuilder._list(requirement_memory.get("learned_gameplay_tags"))[:5])
        if not tags and profile:
            tags = ", ".join(profile.gameplay_tags[:5])
        audience = ProjectSkillBuilder._audience(profile, requirement_memory)
        return (
            f"Use for CrealityOS project {report.project_key} / {display} {category} 投放素材美术。"
            f" Trigger when handling this game project, 平面需求描述, 9:16 performance ads, PSD/PNG/切图 delivery,"
            f" gameplay/style/audience reuse. Audience: {audience}. Tags: {tags or 'project style memory'}."
        )

    @staticmethod
    def _warnings(profile: ProjectProfile | None, style_card: StyleCard | None, requirement_memory: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if not profile:
            warnings.append("缺少 project_profile.json，Skill 只能作为草稿。")
        if not style_card:
            warnings.append("缺少 style_card.json，尚不能复用已学习风格规则。")
        if not requirement_memory:
            warnings.append("缺少 latest_requirement_memory_report.json，最近平面需求拆解不可用。")
        if style_card and any(str(rule.level) == "K3" for rule in style_card.rules):
            warnings.append("存在 K3 待验证风格假设，交付前仍需设计师确认。")
        return list(dict.fromkeys(warnings))

    @staticmethod
    def _next_actions(project_key: str, skill_name: str, status: str) -> list[str]:
        actions = [
            f"使用 `python -m agent.cli generate-project-skill --project-key {project_key}` 在项目记忆更新后刷新 Skill。",
            f"如需全局启用，可在确认后把 `{skill_name}` 目录复制或安装到 Codex skills 目录。",
        ]
        if status == "draft":
            actions.insert(0, "先跑一次本地或飞书设计流程，让自学引擎沉淀 project_profile、style_card 和需求记忆。")
        return actions

    @staticmethod
    def _list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value:
            return [str(value).strip()]
        return []

    @staticmethod
    def _items(values: list[str], limit: int = 12, default: list[str] | None = None) -> list[str]:
        items = [item.strip() for item in values if item and item.strip()]
        unique = list(dict.fromkeys(items))
        return unique[:limit] or list(default or [])

    @staticmethod
    def _style_rules(style_card: StyleCard | None, levels: set[str], work_item_id: str = "") -> list[str]:
        if not style_card:
            return []
        rules: list[str] = []
        for rule in style_card.rules:
            if str(rule.level) not in levels:
                continue
            if work_item_id and str(rule.level) == "K3":
                if not any(work_item_id in ref for ref in rule.source_refs):
                    continue
            rules.append(f"[{rule.level}] {rule.statement}")
        return rules

    @staticmethod
    def _profile_matches_requirement(profile: ProjectProfile | None, requirement_memory: dict[str, Any]) -> bool:
        game_name = str(requirement_memory.get("game_name") or "").strip()
        if not profile or not game_name or game_name == "待确认":
            return True
        return not profile.display_name or profile.display_name == game_name

    @staticmethod
    def _bullet_lines(items: list[str], empty: str) -> list[str]:
        return [f"- {item}" for item in items] if items else [f"- {empty}"]

    @staticmethod
    def _source_lines(source_artifacts: dict[str, str | None]) -> list[str]:
        return [f"- {key}: `{value or '未生成'}`" for key, value in source_artifacts.items()]

    @staticmethod
    def _is_storyboard_mode(
        requirement_memory: dict[str, Any],
        visual_keywords: list[str],
        confirmed_rules: list[str],
        hypotheses: list[str],
    ) -> bool:
        text = "\n".join(
            [
                str(requirement_memory.get("source_requirement_summary") or ""),
                *ProjectSkillBuilder._list(requirement_memory.get("task_breakdown")),
                *visual_keywords,
                *confirmed_rules,
                *hypotheses,
            ]
        )
        return any(token in text for token in ("剧情", "片头", "分镜", "镜头", "画面描述"))

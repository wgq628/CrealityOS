from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.memory.store import MemoryStore
from agent.models import KnowledgeLevel, ProjectProfile, ProjectProfileUpdateReport, StyleCard, StyleRule
from agent.utils import load_json, stringify


class ProjectProfileManager:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def ensure_profile(self, project_key: str, same_category: str, title: str = "") -> ProjectProfile:
        existing = self.store.load_project_profile(project_key)
        if existing:
            return existing
        profile = ProjectProfile(
            project_key=project_key,
            same_category=same_category,
            display_name=title or project_key,
            gameplay_tags=[],
            visual_keywords=[],
            must_have_rules=[],
            forbidden_rules=[],
            delivery_naming_template="{project_key}_{work_item_id}_{size}_{version}",
            required_deliverables=["PSD", "PNG"],
            export_formats=["PSD", "PNG"],
            default_sizes=[],
            slice_requirements=["按钮、底板、图标等可复用元素独立分层"],
            automation_preferences={
                "photoshop_mode": "dry-run",
                "export_mode": "staging-only",
            },
            notes=["首次自动创建，请按项目真实规范继续补全。"],
        )
        self.store.save_project_profile(profile)
        return profile

    def update_profile_from_file(
        self,
        project_key: str,
        same_category: str,
        profile_file: str,
        replace: bool = False,
    ) -> tuple[ProjectProfile, ProjectProfileUpdateReport]:
        payload = self._load_payload(profile_file)
        source = payload.get("profile", payload)
        if not isinstance(source, dict):
            raise ValueError("Project profile file must contain a JSON object or a profile object.")

        profile = self.ensure_profile(
            project_key=project_key,
            same_category=str(source.get("same_category") or same_category),
            title=str(source.get("display_name") or source.get("name") or project_key),
        )
        if replace:
            profile = self._blank_profile(project_key, str(source.get("same_category") or same_category), profile.display_name)

        changed_fields: list[str] = []
        warnings: list[str] = []

        scalar_aliases = {
            "display_name": ("display_name", "name", "title"),
            "delivery_naming_template": ("delivery_naming_template", "naming_template", "deliveryNamingTemplate"),
        }
        for field_name, aliases in scalar_aliases.items():
            value = self._first(source, aliases)
            if value:
                setattr(profile, field_name, stringify(value).strip())
                changed_fields.append(field_name)

        list_aliases = {
            "gameplay_tags": ("gameplay_tags", "gameplay", "玩法标签"),
            "visual_keywords": ("visual_keywords", "keywords", "style_keywords", "视觉关键词"),
            "must_have_rules": ("must_have_rules", "must_have", "fixed_rules", "必须遵守"),
            "forbidden_rules": ("forbidden_rules", "do_not", "forbidden", "禁忌项"),
            "required_deliverables": ("required_deliverables", "deliverables", "交付物"),
            "export_formats": ("export_formats", "formats", "导出格式"),
            "default_sizes": ("default_sizes", "sizes", "尺寸"),
            "slice_requirements": ("slice_requirements", "slicing", "切图要求"),
            "notes": ("notes", "备注"),
        }
        for field_name, aliases in list_aliases.items():
            if not any(alias in source for alias in aliases):
                continue
            values = self._list_field(self._first(source, aliases))
            current = [] if replace else list(getattr(profile, field_name))
            setattr(profile, field_name, list(dict.fromkeys(current + values)))
            changed_fields.append(field_name)

        automation = self._first(source, ("automation_preferences", "automation", "自动化偏好"))
        if isinstance(automation, dict):
            profile.automation_preferences = dict(automation) if replace else {**profile.automation_preferences, **automation}
            changed_fields.append("automation_preferences")

        profile.same_category = str(source.get("same_category") or same_category or profile.same_category)
        if not profile.visual_keywords:
            warnings.append("项目档案仍缺少视觉关键词，后续风格判断会偏依赖 K3 假设。")
        if not profile.default_sizes:
            warnings.append("项目档案仍缺少默认尺寸，交付前需要额外确认尺寸。")
        if not profile.must_have_rules:
            warnings.append("项目档案尚未沉淀 K1 项目硬规则。")

        self.store.save_project_profile(profile)
        report = ProjectProfileUpdateReport(
            project_key=project_key,
            same_category=profile.same_category,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_file=profile_file,
            mode="replace" if replace else "merge",
            changed_fields=list(dict.fromkeys(changed_fields)),
            warnings=list(dict.fromkeys(warnings)),
            next_actions=self._update_next_actions(profile, changed_fields),
        )
        return profile, report

    def apply_profile_to_style_card(self, style_card: StyleCard, profile: ProjectProfile) -> StyleCard:
        style_card.visual_keywords.extend(profile.visual_keywords)
        style_card.do_not.extend(profile.forbidden_rules)
        style_card.open_questions.extend(profile.notes)
        for statement in profile.must_have_rules:
            self._merge_profile_rule(
                style_card.rules,
                StyleRule(
                    statement=statement,
                    level=KnowledgeLevel.K1,
                    rationale="来自项目档案中的固定规则",
                    source_refs=[f"profile:{profile.project_key}"],
                    scope="project",
                ),
            )
        style_card.visual_keywords = list(dict.fromkeys(style_card.visual_keywords))
        style_card.do_not = list(dict.fromkeys(style_card.do_not))
        style_card.open_questions = list(dict.fromkeys(style_card.open_questions))
        return style_card

    @staticmethod
    def render_markdown(profile: ProjectProfile) -> str:
        return "\n".join(
            [
                f"# 项目档案 - {profile.display_name}",
                "",
                f"- 项目 Key：`{profile.project_key}`",
                f"- 同品类底座：`{profile.same_category}`",
                f"- 玩法标签：{', '.join(profile.gameplay_tags) if profile.gameplay_tags else '待补充'}",
                f"- 视觉关键词：{', '.join(profile.visual_keywords) if profile.visual_keywords else '待补充'}",
                "",
                "## 必须遵守",
                *(f"- {item}" for item in profile.must_have_rules or ["待补充"]),
                "",
                "## 禁忌项",
                *(f"- {item}" for item in profile.forbidden_rules or ["待补充"]),
                "",
                "## 交付规范",
                f"- 命名模板：`{profile.delivery_naming_template}`",
                f"- 必需交付物：{', '.join(profile.required_deliverables)}",
                f"- 默认导出格式：{', '.join(profile.export_formats)}",
                f"- 默认尺寸：{', '.join(profile.default_sizes) if profile.default_sizes else '待补充'}",
                "",
                "## 切图要求",
                *(f"- {item}" for item in profile.slice_requirements or ["待补充"]),
                "",
                "## 自动化偏好",
                *(f"- {key}: {value}" for key, value in profile.automation_preferences.items()),
                "",
                "## 备注",
                *(f"- {item}" for item in profile.notes or ["无"]),
            ]
        )

    @staticmethod
    def render_update_report(report: ProjectProfileUpdateReport) -> str:
        return "\n".join(
            [
                f"# 项目档案更新 - {report.project_key}",
                "",
                f"- 同品类底座：`{report.same_category}`",
                f"- 更新时间：`{report.created_at}`",
                f"- 来源文件：`{report.source_file}`",
                f"- 更新模式：`{report.mode}`",
                "",
                "## 变更字段",
                *(f"- {item}" for item in report.changed_fields or ["无"]),
                "",
                "## 警告",
                *(f"- {item}" for item in report.warnings or ["无"]),
                "",
                "## 下一步",
                *(f"- {item}" for item in report.next_actions),
            ]
        )

    @staticmethod
    def _blank_profile(project_key: str, same_category: str, display_name: str) -> ProjectProfile:
        return ProjectProfile(
            project_key=project_key,
            same_category=same_category,
            display_name=display_name or project_key,
            gameplay_tags=[],
            visual_keywords=[],
            must_have_rules=[],
            forbidden_rules=[],
            delivery_naming_template="{project_key}_{work_item_id}_{size}_{version}",
            required_deliverables=[],
            export_formats=[],
            default_sizes=[],
            slice_requirements=[],
            automation_preferences={},
            notes=[],
        )

    @staticmethod
    def _load_payload(profile_file: str) -> dict[str, Any]:
        path = Path(profile_file)
        if path.suffix.lower() == ".json":
            payload = load_json(path, {})
            if not isinstance(payload, dict):
                raise ValueError("Project profile JSON must be an object.")
            return payload
        payload: dict[str, Any] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or ":" not in text:
                continue
            key, value = text.split(":", 1)
            payload[key.strip()] = value.strip()
        return payload

    @staticmethod
    def _first(source: dict[str, Any], aliases: tuple[str, ...]) -> Any:
        for alias in aliases:
            if alias in source:
                return source[alias]
        lowered = {key.lower(): value for key, value in source.items()}
        for alias in aliases:
            if alias.lower() in lowered:
                return lowered[alias.lower()]
        return None

    @staticmethod
    def _list_field(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [stringify(item).strip() for item in value if stringify(item).strip()]
        text = stringify(value).strip()
        if not text:
            return []
        for sep in ("\n", "；", ";", ","):
            if sep in text:
                return [item.strip() for item in text.split(sep) if item.strip()]
        return [text]

    @staticmethod
    def _update_next_actions(profile: ProjectProfile, changed_fields: list[str]) -> list[str]:
        actions = [
            "下次生成创作包会自动叠加项目档案中的视觉关键词、硬规则和禁忌项。",
            "如本次更新了尺寸、命名或切图要求，请重新生成 delivery_readiness_report 做交付前检查。",
        ]
        if any(field in changed_fields for field in ("must_have_rules", "forbidden_rules", "visual_keywords")):
            actions.append("建议运行 build-local-creative-pack 或 run-feishu-design-cycle 验证新风格约束是否进入创作包。")
        return actions

    @staticmethod
    def _merge_profile_rule(existing_rules: list[StyleRule], incoming: StyleRule) -> None:
        for rule in existing_rules:
            if rule.statement == incoming.statement:
                rule.level = KnowledgeLevel.K1
                rule.source_refs.extend(ref for ref in incoming.source_refs if ref not in rule.source_refs)
                return
        existing_rules.append(incoming)

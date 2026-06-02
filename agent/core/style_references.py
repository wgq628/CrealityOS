from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.memory.store import MemoryStore
from agent.models import KnowledgeLevel, StyleCard, StyleReferenceItem, StyleReferenceReport, StyleRule
from agent.utils import load_json, stringify


class StyleReferenceIngestor:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def ingest(
        self,
        project_key: str,
        same_category: str,
        reference_file: str,
        share_to_base: bool = False,
    ) -> StyleReferenceReport:
        source_path = Path(reference_file)
        raw_items = self._load_raw_items(reference_file)
        references = [self._reference_item(item, index, source_path.parent) for index, item in enumerate(raw_items, start=1)]
        accepted_rules: list[StyleRule] = []
        rejected_rules: list[StyleRule] = []
        pending_rules: list[StyleRule] = []
        warnings: list[str] = []

        project_card = self.store.load_style_card(project_key) or self._empty_card(project_key, same_category)
        shared_card = self.store.load_style_base(same_category) or self._empty_card(f"{same_category}-shared", same_category)

        for ref in references:
            if ref.kind == "local" and not ref.exists:
                warnings.append(f"本地参考图不存在：{ref.uri}")
            target_rules = self._rules_from_reference(ref)
            if ref.role == "negative":
                rejected_rules.extend(target_rules)
                project_card.do_not.extend(ref.keywords)
                for rule in target_rules:
                    self._merge_rule(project_card.rules, rule)
            elif ref.level == KnowledgeLevel.K3:
                pending_rules.extend(target_rules)
                project_card.visual_keywords.extend(ref.keywords)
                for rule in target_rules:
                    self._merge_rule(project_card.rules, rule)
            else:
                accepted_rules.extend(target_rules)
                project_card.visual_keywords.extend(ref.keywords)
                for rule in target_rules:
                    self._merge_rule(project_card.rules, rule)
                    if share_to_base:
                        self._merge_rule(shared_card.rules, replace(rule, scope="shared"))
                if share_to_base:
                    shared_card.visual_keywords.extend(ref.keywords)

            project_card.evidence_summary.append(f"style-reference:{ref.reference_id}:{ref.role}:{ref.level}")

        self._dedupe_card(project_card)
        self.store.save_style_card(project_card)
        if share_to_base:
            self._dedupe_card(shared_card)
            self.store.save_style_base(shared_card)

        return StyleReferenceReport(
            project_key=project_key,
            same_category=same_category,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_file=reference_file,
            references=references,
            accepted_rules=accepted_rules,
            rejected_rules=rejected_rules,
            pending_rules=pending_rules,
            warnings=list(dict.fromkeys(warnings)),
            next_actions=self._next_actions(references, share_to_base),
        )

    @staticmethod
    def render_markdown(report: StyleReferenceReport) -> str:
        def rule_section(title: str, rules: list[StyleRule]) -> list[str]:
            lines = [title]
            if not rules:
                lines.append("- 无")
                return lines
            lines.extend(f"- [{rule.level}] {rule.statement}" for rule in rules)
            return lines

        lines = [
            f"# 风格参考图沉淀 - {report.project_key}",
            "",
            f"- 同品类底座：`{report.same_category}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 来源文件：`{report.source_file}`",
            "",
            "## 参考项",
        ]
        for ref in report.references:
            lines.extend(
                [
                    f"### {ref.reference_id}",
                    f"- URI：`{ref.uri}`",
                    f"- 类型：`{ref.kind}`",
                    f"- 角色：`{ref.role}`",
                    f"- K级：`{ref.level}`",
                    f"- 存在：{'是' if ref.exists else '否'}",
                    f"- 关键词：{', '.join(ref.keywords) if ref.keywords else '无'}",
                    f"- 说明：{'；'.join(ref.notes) if ref.notes else '无'}",
                    f"- 规则：{'；'.join(ref.rules) if ref.rules else '无'}",
                    "",
                ]
            )
        lines.extend(rule_section("## 已采纳规则", report.accepted_rules))
        lines.extend(["", *rule_section("## 禁忌/驳回规则", report.rejected_rules)])
        lines.extend(["", *rule_section("## 待验证规则", report.pending_rules)])
        lines.extend(["", "## 警告", *(f"- {item}" for item in report.warnings or ["无"])])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in report.next_actions)])
        return "\n".join(lines)

    @staticmethod
    def _load_raw_items(reference_file: str) -> list[dict[str, Any]]:
        path = Path(reference_file)
        if path.suffix.lower() == ".json":
            payload = load_json(path, {})
            raw_items = payload.get("references", payload.get("items", [])) if isinstance(payload, dict) else payload
            if not isinstance(raw_items, list):
                raise ValueError("Style reference JSON must contain a list or references/items list.")
            return [item for item in raw_items if isinstance(item, dict)]
        items: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            parts = [part.strip() for part in text.split("|")]
            items.append(
                {
                    "uri": parts[0],
                    "role": parts[1] if len(parts) > 1 else "reference",
                    "keywords": parts[2] if len(parts) > 2 else "",
                    "notes": parts[3] if len(parts) > 3 else "",
                }
            )
        if not items:
            raise ValueError("No style references found.")
        return items

    def _reference_item(self, item: dict[str, Any], index: int, source_dir: Path) -> StyleReferenceItem:
        uri = str(item.get("uri") or item.get("path") or item.get("url") or "").strip()
        if not uri:
            raise ValueError("Every style reference needs uri/path/url.")
        uri = self._resolve_uri(uri, source_dir)
        role = str(item.get("role") or "reference").strip().lower()
        if role not in {"positive", "negative", "reference"}:
            role = "reference"
        level = self._level(item.get("level"), role)
        return StyleReferenceItem(
            reference_id=str(item.get("reference_id") or item.get("id") or f"REF{index:03d}"),
            uri=uri,
            kind=self._kind(uri),
            role=role,
            level=level,
            keywords=self._list_field(item.get("keywords") or item.get("tags")),
            notes=self._list_field(item.get("notes") or item.get("description")),
            rules=self._list_field(item.get("rules") or item.get("learning")),
            exists=self._exists(uri),
        )

    @staticmethod
    def _resolve_uri(uri: str, source_dir: Path) -> str:
        if uri.lower().startswith(("http://", "https://")):
            return uri
        path = Path(uri)
        if path.is_absolute():
            return str(path)
        return str((source_dir / path).resolve())

    @staticmethod
    def _rules_from_reference(ref: StyleReferenceItem) -> list[StyleRule]:
        statements = list(ref.rules)
        if not statements and ref.notes:
            statements = [f"{ref.reference_id} 风格参考：{note}" for note in ref.notes]
        if not statements and ref.keywords:
            statements = [f"{ref.reference_id} 参考关键词：{', '.join(ref.keywords)}"]
        rules: list[StyleRule] = []
        for statement in statements:
            prefix = "避免参考" if ref.role == "negative" else "参考图确认"
            rules.append(
                StyleRule(
                    statement=statement,
                    level=ref.level,
                    rationale=f"{prefix}：{ref.reference_id}",
                    source_refs=[f"style-reference:{ref.reference_id}", ref.uri],
                    evidence_count=1,
                    scope="project",
                )
            )
        return rules

    @staticmethod
    def _empty_card(project_key: str, same_category: str) -> StyleCard:
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
    def _merge_rule(existing: list[StyleRule], incoming: StyleRule) -> None:
        for rule in existing:
            if rule.statement == incoming.statement:
                rule.evidence_count += incoming.evidence_count
                rule.source_refs.extend(ref for ref in incoming.source_refs if ref not in rule.source_refs)
                if incoming.level == KnowledgeLevel.K1:
                    rule.level = KnowledgeLevel.K1
                elif incoming.level == KnowledgeLevel.K2 and rule.level != KnowledgeLevel.K1:
                    rule.level = KnowledgeLevel.K2
                return
        existing.append(incoming)

    @staticmethod
    def _dedupe_card(card: StyleCard) -> None:
        card.visual_keywords = list(dict.fromkeys(card.visual_keywords))
        card.do_not = list(dict.fromkeys(card.do_not))
        card.open_questions = list(dict.fromkeys(card.open_questions))
        card.evidence_summary = list(dict.fromkeys(card.evidence_summary))

    @staticmethod
    def _level(value: Any, role: str) -> KnowledgeLevel:
        if value:
            text = str(value).upper()
            if text in {"K1", "K2", "K3", "K4"}:
                return KnowledgeLevel(text)
        return KnowledgeLevel.K3 if role == "reference" else KnowledgeLevel.K2

    @staticmethod
    def _kind(uri: str) -> str:
        if uri.lower().startswith(("http://", "https://")):
            return "url"
        return "local"

    @staticmethod
    def _exists(uri: str) -> bool:
        if uri.lower().startswith(("http://", "https://")):
            return True
        return Path(uri).exists()

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
    def _next_actions(references: list[StyleReferenceItem], share_to_base: bool) -> list[str]:
        actions = [
            "下次生成创作包前优先读取 style_card 和 latest_style_reference_report。",
            "对 K3 参考保持待验证，不要直接当成项目定论。",
            "用后续候选图评审继续验证这些参考是否真的适合项目。",
        ]
        if share_to_base:
            actions.append("已同步到同品类底座，跨项目使用时仍需项目级覆盖确认。")
        if any(ref.role == "negative" for ref in references):
            actions.append("负面参考已进入避坑项，下次出图前默认检查。")
        return actions

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import CandidateReviewItem, CandidateReviewReport
from agent.utils import load_json, stringify


class CandidateReviewIngestor:
    VALID_DECISIONS = {"approved", "rejected", "revise"}

    def load_items(self, review_file: str, batch_payload: dict | None = None) -> list[CandidateReviewItem]:
        path = Path(review_file)
        if path.suffix.lower() == ".json":
            payload = load_json(path, {})
            raw_items = payload.get("variants", payload.get("items", [])) if isinstance(payload, dict) else payload
            if not isinstance(raw_items, list):
                raise ValueError("Candidate review JSON must contain a list or a variants/items list.")
            return [self._item_from_mapping(item, batch_payload) for item in raw_items]
        return self._items_from_text(path.read_text(encoding="utf-8"), batch_payload)

    def build_report(
        self,
        project_key: str,
        work_item_id: str,
        source_batch: str | None,
        items: list[CandidateReviewItem],
        generated_review_reports: list[str],
    ) -> CandidateReviewReport:
        return CandidateReviewReport(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_batch=source_batch,
            items=items,
            accepted_variant_ids=[item.variant_id for item in items if item.decision == "approved"],
            rejected_variant_ids=[item.variant_id for item in items if item.decision == "rejected"],
            pending_variant_ids=[item.variant_id for item in items if item.decision == "revise"],
            generated_review_reports=generated_review_reports,
            next_actions=self._next_actions(items),
        )

    @staticmethod
    def render_markdown(report: CandidateReviewReport) -> str:
        lines = [
            f"# 候选图评审回写 - {report.work_item_id}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 来源批次：`{report.source_batch or '未绑定'}`",
            f"- 采纳：{', '.join(report.accepted_variant_ids) if report.accepted_variant_ids else '无'}",
            f"- 驳回：{', '.join(report.rejected_variant_ids) if report.rejected_variant_ids else '无'}",
            f"- 待验证：{', '.join(report.pending_variant_ids) if report.pending_variant_ids else '无'}",
            "",
            "## 明细",
        ]
        for item in report.items:
            lines.extend(
                [
                    f"### {item.variant_id} {item.title}",
                    f"- 结论：`{item.decision}`",
                    f"- 分数：{item.scores or '未评分'}",
                    f"- 学习语句：{item.learning_statement or '未填写'}",
                    "",
                    "优点:",
                    *(f"- {value}" for value in item.strengths or ["无"]),
                    "",
                    "问题:",
                    *(f"- {value}" for value in item.issues or ["无"]),
                    "",
                    "修改意见:",
                    *(f"- {value}" for value in item.revision_notes or ["无"]),
                    "",
                    "生成资产:",
                    *(f"- `{value}`" for value in item.generated_assets or ["无"]),
                    "",
                ]
            )
        lines.extend(["## 已生成评审记忆", *(f"- `{path}`" for path in report.generated_review_reports or ["无"])])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in report.next_actions)])
        return "\n".join(lines)

    @staticmethod
    def feedback_for_item(item: CandidateReviewItem) -> str:
        parts: list[str] = []
        label = f"{item.variant_id} {item.title}".strip()
        if item.learning_statement:
            parts.append(f"{label}：{item.learning_statement}")
        if item.strengths:
            parts.append(f"{label} 优点：" + "；".join(item.strengths))
        if item.issues:
            parts.append(f"{label} 问题：" + "；".join(item.issues))
        if item.revision_notes:
            parts.append(f"{label} 修改方向：" + "；".join(item.revision_notes))
        if item.scores:
            score_text = "，".join(f"{key}={value}" for key, value in item.scores.items())
            parts.append(f"{label} 评分：{score_text}")
        return "\n".join(parts) or f"{label}：{item.decision}"

    def _item_from_mapping(self, item: dict[str, Any], batch_payload: dict | None) -> CandidateReviewItem:
        variant_id = str(item.get("variant_id") or item.get("id") or "").strip().upper()
        if not variant_id:
            raise ValueError("Every candidate review item needs a variant_id.")
        decision = str(item.get("decision") or item.get("result") or "revise").strip().lower()
        if decision not in self.VALID_DECISIONS:
            raise ValueError(f"Unsupported candidate decision: {decision}")
        title = str(item.get("title") or self._title_from_batch(variant_id, batch_payload) or variant_id)
        return CandidateReviewItem(
            variant_id=variant_id,
            title=title,
            decision=decision,
            scores=self._scores(item.get("scores", {})),
            strengths=self._list_field(item.get("strengths") or item.get("pros")),
            issues=self._list_field(item.get("issues") or item.get("cons")),
            revision_notes=self._list_field(item.get("revision_notes") or item.get("notes") or item.get("fixes")),
            learning_statement=str(item.get("learning") or item.get("learning_statement") or "").strip(),
            generated_assets=self._list_field(item.get("generated_assets") or item.get("assets")),
        )

    def _items_from_text(self, content: str, batch_payload: dict | None) -> list[CandidateReviewItem]:
        items: list[CandidateReviewItem] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = [token.strip() for token in line.split("|")]
            if len(tokens) < 3 or not tokens[0].upper().startswith("V"):
                continue
            variant_id = tokens[0].upper()
            decision = tokens[1].lower()
            if decision not in self.VALID_DECISIONS:
                decision = "revise"
            title = self._title_from_batch(variant_id, batch_payload) or variant_id
            items.append(
                CandidateReviewItem(
                    variant_id=variant_id,
                    title=title,
                    decision=decision,
                    scores={},
                    strengths=[],
                    issues=[],
                    revision_notes=[tokens[2]],
                    learning_statement=tokens[3] if len(tokens) > 3 else tokens[2],
                    generated_assets=[],
                )
            )
        if not items:
            raise ValueError("No candidate review rows found. Use JSON or lines like: V01 | approved | notes | learning")
        return items

    @staticmethod
    def _title_from_batch(variant_id: str, batch_payload: dict | None) -> str | None:
        for variant in (batch_payload or {}).get("variants", []):
            if str(variant.get("variant_id", "")).upper() == variant_id:
                return str(variant.get("title") or variant_id)
        return None

    @staticmethod
    def _scores(value: Any) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        scores: dict[str, float] = {}
        for key, item in value.items():
            try:
                scores[str(key)] = float(item)
            except (TypeError, ValueError):
                continue
        return scores

    @staticmethod
    def _list_field(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [stringify(item).strip() for item in value if stringify(item).strip()]
        text = stringify(value).strip()
        if not text:
            return []
        separators = ["\n", "；", ";"]
        values = [text]
        for sep in separators:
            if sep in text:
                values = [item.strip() for item in text.split(sep)]
                break
        return [item for item in values if item]

    @staticmethod
    def _next_actions(items: list[CandidateReviewItem]) -> list[str]:
        actions = [
            "对采纳方案进入人工精修、PSD 重建或 Photoshop 自动化检查。",
            "对驳回方案保留偏差原因，下次出图前默认避开。",
            "对 revise 方案保持 K3 待验证，直到再次评审确认。",
        ]
        if not any(item.decision == "approved" for item in items):
            actions.insert(0, "本轮没有采纳方案，建议重新生成出图批次或补充参考图。")
        return actions

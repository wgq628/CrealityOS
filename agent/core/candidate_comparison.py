from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.models import CandidateComparisonMatrix, CandidateComparisonRow


class CandidateComparisonMatrixBuilder:
    DEFAULT_VARIANTS = {
        "V01": ("稳妥项目风格版", "优先贴合已确认项目风格，适合作为第一轮基准稿。"),
        "V02": ("转化强化版", "强化点击转化、利益点和按钮区域。"),
        "V03": ("构图突破版", "探索更大胆的镜头、透视或主体占比。"),
        "V04": ("PSD切图友好版", "优先保证元素可拆、边界清楚。"),
    }

    def build(
        self,
        project_key: str,
        work_item_id: str,
        image_batch: dict[str, Any] | None,
        generation_results: dict[str, Any] | None,
        candidate_style_drift: dict[str, Any] | None,
        candidate_review: dict[str, Any] | None,
        source_artifacts: dict[str, str | None],
    ) -> CandidateComparisonMatrix:
        variant_ids = self._variant_ids(image_batch, generation_results, candidate_style_drift, candidate_review)
        rows = [
            self._row(variant_id, image_batch, generation_results, candidate_style_drift, candidate_review)
            for variant_id in variant_ids
        ]
        blockers = self._blockers(rows, candidate_style_drift)
        warnings = self._warnings(rows, image_batch, generation_results, candidate_review)
        recommended = [row.variant_id for row in rows if row.recommendation.startswith("采纳")]
        rejected = [row.variant_id for row in rows if row.recommendation.startswith("驳回")]
        revise = [row.variant_id for row in rows if row.recommendation.startswith("修正") or row.recommendation.startswith("补评审")]
        status = "blocked" if blockers else "needs_designer_decision" if warnings or not recommended else "candidate_selected"
        return CandidateComparisonMatrix(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            rows=rows,
            recommended_variant_ids=recommended,
            rejected_variant_ids=rejected,
            revise_variant_ids=revise,
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            next_actions=self._next_actions(status, recommended, revise),
            source_artifacts=source_artifacts,
        )

    @staticmethod
    def render_markdown(matrix: CandidateComparisonMatrix) -> str:
        lines = [
            f"# 候选方案对比矩阵 - {matrix.work_item_id}",
            "",
            f"- 项目：`{matrix.project_key}`",
            f"- 创建时间：`{matrix.created_at}`",
            f"- 状态：`{matrix.status}`",
            f"- 推荐采纳：{', '.join(matrix.recommended_variant_ids) if matrix.recommended_variant_ids else '无'}",
            f"- 建议修正/补评审：{', '.join(matrix.revise_variant_ids) if matrix.revise_variant_ids else '无'}",
            f"- 建议驳回：{', '.join(matrix.rejected_variant_ids) if matrix.rejected_variant_ids else '无'}",
            "",
            "## 来源产物",
        ]
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in matrix.source_artifacts.items())
        lines.extend(
            [
                "",
                "## 对比表",
                "| 方案 | 意图 | 资产 | 偏移 | 评审结论 | 风格 | 转化 | PSD | 推荐动作 |",
                "|---|---|---:|---|---|---:|---:|---:|---|",
            ]
        )
        for row in matrix.rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"{row.variant_id} {row.title}",
                        row.intent,
                        str(row.asset_count),
                        row.drift_level,
                        row.review_decision,
                        CandidateComparisonMatrixBuilder._score_text(row.style_fit),
                        CandidateComparisonMatrixBuilder._score_text(row.conversion_score),
                        CandidateComparisonMatrixBuilder._score_text(row.psd_ready_score),
                        row.recommendation,
                    ]
                )
                + " |"
            )
        lines.extend(["", "## 证据摘要"])
        for row in matrix.rows:
            lines.append(f"### {row.variant_id} {row.title}")
            lines.extend(f"- {item}" for item in row.evidence or ["无"])
        lines.extend(["", "## 阻塞项", *(f"- {item}" for item in matrix.blockers or ["无"])])
        lines.extend(["", "## 风险提醒", *(f"- {item}" for item in matrix.warnings or ["无"])])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in matrix.next_actions)])
        return "\n".join(lines)

    def _row(
        self,
        variant_id: str,
        image_batch: dict[str, Any] | None,
        generation_results: dict[str, Any] | None,
        candidate_style_drift: dict[str, Any] | None,
        candidate_review: dict[str, Any] | None,
    ) -> CandidateComparisonRow:
        variant = self._variant_payload(variant_id, image_batch)
        title = str(variant.get("title") or self.DEFAULT_VARIANTS.get(variant_id, (variant_id, ""))[0])
        intent = str(variant.get("intent") or self.DEFAULT_VARIANTS.get(variant_id, ("", "待补充"))[1])
        assets = [item for item in (generation_results or {}).get("assets", []) if str(item.get("variant_id", "")).upper() == variant_id]
        drift_items = [item for item in (candidate_style_drift or {}).get("items", []) if str(item.get("variant_id", "")).upper() == variant_id]
        review = self._review_payload(variant_id, candidate_review)
        drift_level = self._worst_drift(drift_items)
        decision = str(review.get("decision") or "unreviewed")
        scores = review.get("scores", {}) if isinstance(review.get("scores"), dict) else {}
        style_fit = self._score(scores, "style_fit", "style", "风格贴合")
        conversion = self._score(scores, "conversion", "convert", "转化")
        psd_ready = self._score(scores, "psd_ready", "psd", "PSD/切图友好")
        evidence: list[str] = []
        evidence.extend(str(item) for item in review.get("strengths", [])[:3])
        evidence.extend(str(item) for item in review.get("issues", [])[:3])
        evidence.extend(str(item) for item in review.get("revision_notes", [])[:3])
        evidence.extend(str(item.get("recommended_action")) for item in drift_items[:2] if item.get("recommended_action"))
        return CandidateComparisonRow(
            variant_id=variant_id,
            title=title,
            intent=intent,
            asset_count=len(assets),
            drift_level=drift_level,
            review_decision=decision,
            style_fit=style_fit,
            conversion_score=conversion,
            psd_ready_score=psd_ready,
            recommendation=self._recommendation(decision, drift_level, style_fit, conversion, psd_ready, assets),
            evidence=list(dict.fromkeys(item for item in evidence if item)),
        )

    @classmethod
    def _variant_ids(
        cls,
        image_batch: dict[str, Any] | None,
        generation_results: dict[str, Any] | None,
        candidate_style_drift: dict[str, Any] | None,
        candidate_review: dict[str, Any] | None,
    ) -> list[str]:
        ids: list[str] = []
        ids.extend(str(item.get("variant_id", "")).upper() for item in (image_batch or {}).get("variants", []))
        ids.extend(str(item.get("variant_id", "")).upper() for item in (generation_results or {}).get("assets", []))
        ids.extend(str(item.get("variant_id", "")).upper() for item in (candidate_style_drift or {}).get("items", []))
        ids.extend(str(item.get("variant_id", "")).upper() for item in (candidate_review or {}).get("items", []))
        ids = [item for item in ids if item]
        return list(dict.fromkeys(ids or list(cls.DEFAULT_VARIANTS)))

    @staticmethod
    def _variant_payload(variant_id: str, image_batch: dict[str, Any] | None) -> dict[str, Any]:
        for item in (image_batch or {}).get("variants", []):
            if str(item.get("variant_id", "")).upper() == variant_id:
                return item
        return {}

    @staticmethod
    def _review_payload(variant_id: str, candidate_review: dict[str, Any] | None) -> dict[str, Any]:
        for item in (candidate_review or {}).get("items", []):
            if str(item.get("variant_id", "")).upper() == variant_id:
                return item
        return {}

    @staticmethod
    def _worst_drift(items: list[dict[str, Any]]) -> str:
        levels = [str(item.get("drift_level") or "info") for item in items]
        if "blocker" in levels:
            return "blocker"
        if "warning" in levels:
            return "warning"
        return "info" if items else "unknown"

    @staticmethod
    def _score(scores: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            if key in scores:
                try:
                    return float(scores[key])
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    def _score_text(value: float | None) -> str:
        return "-" if value is None else f"{value:g}"

    @staticmethod
    def _recommendation(
        decision: str,
        drift_level: str,
        style_fit: float | None,
        conversion: float | None,
        psd_ready: float | None,
        assets: list[dict[str, Any]],
    ) -> str:
        if drift_level == "blocker":
            return "驳回/重出：存在风格阻塞"
        if decision == "rejected":
            return "驳回：保留为反例学习"
        if decision == "approved" and (style_fit or 0) >= 4 and assets:
            return "采纳：进入 PSD/切图准备"
        if decision == "approved":
            return "采纳但补证据：确认资产和评分"
        if decision == "revise":
            return "修正：保留方向但需要二次处理"
        if not assets:
            return "补评审：尚未登记生成图"
        if drift_level == "warning":
            return "修正：先处理风格风险"
        if style_fit is not None and style_fit < 3:
            return "驳回/重出：风格贴合不足"
        if conversion and conversion >= 4 and (style_fit or 0) >= 3:
            return "修正：转化潜力可保留"
        if psd_ready and psd_ready >= 4 and (style_fit or 0) >= 3:
            return "修正：可作为 PSD 友好备选"
        return "补评审：等待设计师打分"

    @staticmethod
    def _blockers(rows: list[CandidateComparisonRow], candidate_style_drift: dict[str, Any] | None) -> list[str]:
        blockers = list((candidate_style_drift or {}).get("blockers", []))
        if any(row.drift_level == "blocker" and row.recommendation.startswith("采纳") for row in rows):
            blockers.append("存在阻塞级偏移候选被建议采纳，请先修正比较矩阵或候选评审。")
        return blockers

    @staticmethod
    def _warnings(
        rows: list[CandidateComparisonRow],
        image_batch: dict[str, Any] | None,
        generation_results: dict[str, Any] | None,
        candidate_review: dict[str, Any] | None,
    ) -> list[str]:
        warnings: list[str] = []
        if not image_batch:
            warnings.append("缺少 image_generation_batch，无法展示原始方案意图。")
        if not generation_results:
            warnings.append("缺少 image_generation_results，无法确认候选资产。")
        if not candidate_review:
            warnings.append("缺少 candidate_review，矩阵只能给出预评审建议。")
        if not any(row.recommendation.startswith("采纳") for row in rows):
            warnings.append("当前没有明确采纳方案，建议重出图或补充评审。")
        return warnings

    @staticmethod
    def _next_actions(status: str, recommended: list[str], revise: list[str]) -> list[str]:
        if status == "blocked":
            return [
                "先处理矩阵中的阻塞项，尤其是风格偏移或低风格贴合方案。",
                "修正候选评审后重新生成候选方案对比矩阵。",
            ]
        actions = []
        if recommended:
            actions.append("对推荐采纳方案创建 PSD 交接计划或进入人工精修。")
        if revise:
            actions.append("对修正方案补充 revision_notes，再决定重出图或作为 K3 探索保留。")
        actions.append("把最终采纳/驳回/修正原因回写到 candidate_review，形成可复用风格记忆。")
        return actions

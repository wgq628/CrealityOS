from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.models import CandidateStyleDriftFinding, CandidateStyleDriftItem, CandidateStyleDriftReport, CreativePack


class CandidateStyleDriftAuditor:
    DRIFT_TOKENS = ("偏", "跑偏", "不符合", "不像", "违背", "错误", "脏", "灰", "写实", "低对比")

    def build(
        self,
        project_key: str,
        work_item_id: str,
        generation_results: dict[str, Any] | None,
        creative_pack: CreativePack | None,
        style_transfer: dict[str, Any] | None,
        style_alignment: dict[str, Any] | None,
        candidate_review: dict[str, Any] | None,
        source_artifacts: dict[str, str | None],
    ) -> CandidateStyleDriftReport:
        assets = list((generation_results or {}).get("assets", []))
        candidate_items = self._items(assets, creative_pack, candidate_review)
        findings = [
            self._generation_results_check(generation_results),
            self._style_gate_check(style_transfer, style_alignment),
            self._forbidden_notes_check(candidate_items, creative_pack),
            self._review_score_check(candidate_review),
            self._k3_variant_check(candidate_items, creative_pack),
            self._safety_check(),
        ]
        blockers = [finding.action for finding in findings if finding.severity == "blocker" and finding.action]
        warnings = [finding.action for finding in findings if finding.severity == "warning" and finding.action]
        item_blockers = [item.recommended_action for item in candidate_items if item.drift_level == "blocker" and item.recommended_action]
        item_warnings = [item.recommended_action for item in candidate_items if item.drift_level == "warning" and item.recommended_action]
        blockers.extend(item_blockers)
        warnings.extend(item_warnings)
        status = "blocked" if blockers else "needs_designer_review" if warnings else "style_safe_for_review"
        return CandidateStyleDriftReport(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=status,
            items=candidate_items,
            findings=findings,
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys(warnings)),
            next_actions=self._next_actions(status, candidate_review),
            source_artifacts=source_artifacts,
        )

    @staticmethod
    def render_markdown(report: CandidateStyleDriftReport) -> str:
        lines = [
            f"# 候选图风格偏移预警 - {report.work_item_id}",
            "",
            f"- 项目：`{report.project_key}`",
            f"- 创建时间：`{report.created_at}`",
            f"- 状态：`{report.status}`",
            "",
            "## 来源产物",
        ]
        lines.extend(f"- {key}: `{value or '缺失'}`" for key, value in report.source_artifacts.items())
        lines.extend(["", "## 候选图预警"])
        if not report.items:
            lines.append("- 暂无候选图记录")
        for item in report.items:
            lines.extend(
                [
                    f"### {item.variant_id or 'unknown'} {item.asset_id}",
                    f"- 状态：`{item.status}`",
                    f"- 偏移级别：`{item.drift_level}`",
                    f"- 地址：`{item.uri}`",
                    *(f"- 证据：{value}" for value in item.evidence or ["无"]),
                    f"- 建议动作：{item.recommended_action or '无'}",
                    "",
                ]
            )
        lines.extend(["## 阻塞项", *(f"- {item}" for item in report.blockers or ["无"])])
        lines.extend(["", "## 风险提醒", *(f"- {item}" for item in report.warnings or ["无"])])
        lines.append("")
        lines.append("## 检查项")
        for finding in report.findings:
            lines.extend(
                [
                    f"### {finding.check_id} {finding.title}",
                    f"- 状态：`{finding.status}`",
                    f"- 严重级别：`{finding.severity}`",
                    *(f"- 证据：{value}" for value in finding.evidence or ["无"]),
                    f"- 建议动作：{finding.action or '无'}",
                    "",
                ]
            )
        lines.extend(["## 下一步", *(f"- {item}" for item in report.next_actions)])
        return "\n".join(lines)

    def _items(
        self,
        assets: list[dict[str, Any]],
        creative_pack: CreativePack | None,
        candidate_review: dict[str, Any] | None,
    ) -> list[CandidateStyleDriftItem]:
        review_by_variant = {
            str(item.get("variant_id", "")).upper(): item
            for item in (candidate_review or {}).get("items", [])
            if isinstance(item, dict)
        }
        do_not = list(creative_pack.style_card.do_not if creative_pack else [])
        result: list[CandidateStyleDriftItem] = []
        for asset in assets:
            variant_id = str(asset.get("variant_id") or "").upper()
            notes = [str(item) for item in asset.get("notes", [])]
            review = review_by_variant.get(variant_id, {})
            evidence = list(notes)
            evidence.extend(str(item) for item in review.get("issues", [])[:3])
            evidence.extend(str(item) for item in review.get("revision_notes", [])[:3])
            matched_forbidden = [rule for rule in do_not if self._contains_any(evidence, rule)]
            drift_text_hits = [text for text in evidence if any(token in text for token in self.DRIFT_TOKENS)]
            style_fit = self._style_fit(review)
            if matched_forbidden:
                drift_level = "blocker"
                status = "forbidden_style_hit"
                action = f"{variant_id or asset.get('asset_id', '候选图')} 命中项目禁忌项：{'; '.join(matched_forbidden[:3])}，不要直接进入 PSD/交付。"
            elif style_fit is not None and style_fit < 3:
                drift_level = "blocker"
                status = "low_style_fit"
                action = f"{variant_id} 风格贴合评分低于 3，请先重出或明确作为废案学习。"
            elif variant_id == "V03" and self._has_k3(creative_pack):
                drift_level = "warning"
                status = "k3_exploration"
                action = "V03 是构图突破/探索方案，且当前存在 K3 假设；只能作为探索候选，不能默认交付。"
            elif drift_text_hits:
                drift_level = "warning"
                status = "drift_note_hit"
                action = f"{variant_id or asset.get('asset_id', '候选图')} 备注或评审中出现偏移词，请设计师复核。"
            else:
                drift_level = "info"
                status = "no_obvious_drift"
                action = "进入人工视觉评审，确认后再采纳。"
            result.append(
                CandidateStyleDriftItem(
                    asset_id=str(asset.get("asset_id") or asset.get("uri") or ""),
                    variant_id=variant_id,
                    uri=str(asset.get("uri") or ""),
                    status=status,
                    drift_level=drift_level,
                    evidence=evidence[:8],
                    recommended_action=action,
                )
            )
        return result

    @staticmethod
    def _generation_results_check(generation_results: dict[str, Any] | None) -> CandidateStyleDriftFinding:
        if not generation_results:
            return CandidateStyleDriftFinding(
                "RESULTS",
                "生成结果登记",
                "missing",
                "blocker",
                action="缺少 image_generation_results，无法检查候选图风格偏移。",
            )
        assets = generation_results.get("assets", [])
        missing = generation_results.get("missing_assets", [])
        delivery_candidates = generation_results.get("delivery_candidates", [])
        evidence = [f"资产数：{len(assets)}", f"缺失资产：{len(missing)}", f"交付候选：{len(delivery_candidates)}"]
        if missing:
            return CandidateStyleDriftFinding("RESULTS", "生成结果登记", "missing_assets", "blocker", evidence + missing[:3], "先修复缺失本地图片路径。")
        if not delivery_candidates:
            return CandidateStyleDriftFinding("RESULTS", "生成结果登记", "no_delivery_candidates", "warning", evidence, "请先标记候选图或确认全部生成图都需要评审。")
        return CandidateStyleDriftFinding("RESULTS", "生成结果登记", "pass", "info", evidence)

    @staticmethod
    def _style_gate_check(
        style_transfer: dict[str, Any] | None,
        style_alignment: dict[str, Any] | None,
    ) -> CandidateStyleDriftFinding:
        transfer_status = str((style_transfer or {}).get("status", "missing"))
        alignment_status = str((style_alignment or {}).get("status", "missing"))
        blockers = list((style_transfer or {}).get("blockers", [])) + list((style_alignment or {}).get("blockers", []))
        warnings = list((style_transfer or {}).get("warnings", [])) + list((style_alignment or {}).get("warnings", []))
        evidence = [f"风格迁移：{transfer_status}", f"风格一致性：{alignment_status}", f"阻塞项：{len(blockers)}"]
        if blockers or "blocked" in {transfer_status, alignment_status}:
            return CandidateStyleDriftFinding("STYLE_GATE", "风格门控", "blocked", "blocker", evidence + blockers[:3], "先处理风格门控阻塞项，再判断候选图。")
        if warnings or "missing" in {transfer_status, alignment_status} or "needs_designer_review" in {transfer_status, alignment_status}:
            return CandidateStyleDriftFinding("STYLE_GATE", "风格门控", "needs_review", "warning", evidence + warnings[:3], "候选图评审前建议补齐或确认风格门控风险。")
        return CandidateStyleDriftFinding("STYLE_GATE", "风格门控", "pass", "info", evidence)

    @staticmethod
    def _forbidden_notes_check(
        items: list[CandidateStyleDriftItem],
        creative_pack: CreativePack | None,
    ) -> CandidateStyleDriftFinding:
        do_not = list(creative_pack.style_card.do_not if creative_pack else [])
        hits = [item.asset_id for item in items if item.status == "forbidden_style_hit"]
        evidence = [f"禁忌项：{len(do_not)}", f"命中候选：{len(hits)}"] + hits[:5]
        if hits:
            return CandidateStyleDriftFinding("FORBIDDEN", "禁忌项命中", "failed", "blocker", evidence, "命中禁忌项的候选图不得直接进入交付。")
        return CandidateStyleDriftFinding("FORBIDDEN", "禁忌项命中", "pass", "info", evidence)

    @staticmethod
    def _review_score_check(candidate_review: dict[str, Any] | None) -> CandidateStyleDriftFinding:
        if not candidate_review:
            return CandidateStyleDriftFinding("REVIEW", "候选图评审", "missing", "warning", action="尚未回写 candidate_review，当前只能做生成结果备注级预警。")
        low_scores: list[str] = []
        for item in candidate_review.get("items", []):
            if str(item.get("decision", "")).lower() == "rejected":
                continue
            style_fit = CandidateStyleDriftAuditor._style_fit(item)
            if style_fit is not None and style_fit < 3:
                low_scores.append(f"{item.get('variant_id')}: style_fit={style_fit:g}")
        evidence = [f"评审项：{len(candidate_review.get('items', []))}", f"低风格分：{len(low_scores)}"] + low_scores[:5]
        if low_scores:
            return CandidateStyleDriftFinding("REVIEW", "候选图评审", "low_style_fit", "blocker", evidence, "先处理低风格贴合评分的候选图，不要直接交付。")
        return CandidateStyleDriftFinding("REVIEW", "候选图评审", "pass", "info", evidence)

    @staticmethod
    def _k3_variant_check(
        items: list[CandidateStyleDriftItem],
        creative_pack: CreativePack | None,
    ) -> CandidateStyleDriftFinding:
        has_k3 = CandidateStyleDriftAuditor._has_k3(creative_pack)
        exploratory = [item.variant_id for item in items if item.variant_id == "V03"]
        evidence = [f"K3 假设：{'有' if has_k3 else '无'}", f"探索候选：{len(exploratory)}"]
        if has_k3 and exploratory:
            return CandidateStyleDriftFinding("K3", "探索方案边界", "needs_review", "warning", evidence, "V03/K3 探索候选必须由设计师确认后才能升级为项目规则或交付方向。")
        return CandidateStyleDriftFinding("K3", "探索方案边界", "pass", "info", evidence)

    @staticmethod
    def _safety_check() -> CandidateStyleDriftFinding:
        return CandidateStyleDriftFinding(
            "SAFETY",
            "安全门控",
            "pass",
            "info",
            ["本报告只读取本地 JSON/Markdown 元数据，不调用出图工具、不发布、不覆盖文件。"],
            "最终审美判断仍由设计师确认。",
        )

    @staticmethod
    def _next_actions(status: str, candidate_review: dict[str, Any] | None) -> list[str]:
        if status == "blocked":
            return [
                "先处理阻塞候选：低风格分、命中禁忌项或风格门控阻塞。",
                "修正后重新登记结果或重新运行候选图风格偏移预警。",
            ]
        actions = [
            "打开 generated_gallery.md 对照实际图片进行人工视觉评审。",
            "把采纳/驳回/待修正原因写入 candidate_review，再回写风格记忆。",
        ]
        if candidate_review:
            actions.append("结合 candidate_review 结论选择进入 PSD 精修或重出图的候选。")
        return actions

    @staticmethod
    def _style_fit(review: dict[str, Any]) -> float | None:
        scores = review.get("scores") if isinstance(review, dict) else None
        if not isinstance(scores, dict):
            return None
        value = scores.get("style_fit") or scores.get("style") or scores.get("风格贴合")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _has_k3(creative_pack: CreativePack | None) -> bool:
        return bool(creative_pack and any(str(rule.level) == "K3" for rule in creative_pack.style_card.rules))

    @staticmethod
    def _contains_any(values: list[str], needle: str) -> bool:
        needle_norm = CandidateStyleDriftAuditor._norm(needle)
        if not needle_norm:
            return False
        return any(needle_norm in CandidateStyleDriftAuditor._norm(value) for value in values)

    @staticmethod
    def _norm(value: str) -> str:
        return "".join(str(value).lower().split())

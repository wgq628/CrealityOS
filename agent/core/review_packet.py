from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agent.models import DesignerReviewPacket, SessionSnapshot


class DesignerReviewPacketBuilder:
    IMPORTANT_FILES = (
        "design_brief.md",
        "requirement_clarification_report.md",
        "requirement_clarification_comment.md",
        "requirement_change_report.md",
        "creative_pack.md",
        "style_transfer_report.md",
        "style_alignment_report.md",
        "design_decision_record.md",
        "style_card.md",
        "image_generation_batch.md",
        "candidate_evaluation.md",
        "image_execution_package.md",
        "pixpark_execution_runbook.md",
        "generated_gallery.md",
        "delivery_candidates.md",
        "candidate_style_drift_report.md",
        "candidate_comparison_matrix.md",
        "candidate_review.md",
        "psd_handoff_plan.md",
        "layer_map.md",
        "slice_checklist.md",
        "psd_handoff_package.md",
        "psd_slice_spec_report.md",
        "delivery_readiness_report.md",
        "design_workflow_plan.md",
        "latest_learning_digest.md",
        "latest_audit.md",
    )

    def build(
        self,
        project_key: str,
        work_item_id: str,
        snapshot: SessionSnapshot | None,
        output_dir: Path | None,
        readiness_payload: dict[str, Any] | None,
        candidate_review_payload: dict[str, Any] | None,
    ) -> DesignerReviewPacket:
        title = snapshot.title if snapshot else work_item_id
        artifact_index = self._collect_artifacts(snapshot, output_dir)
        warnings = self._warnings(artifact_index, readiness_payload, candidate_review_payload)
        return DesignerReviewPacket(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            created_at=datetime.now().isoformat(timespec="seconds"),
            status=self._status(artifact_index, readiness_payload),
            artifact_index=artifact_index,
            decision_points=self._decision_points(readiness_payload, candidate_review_payload),
            review_steps=self._review_steps(artifact_index),
            warnings=warnings,
            next_actions=self._next_actions(artifact_index, readiness_payload),
            approval_checklist=self._approval_checklist(),
        )

    @staticmethod
    def render_markdown(packet: DesignerReviewPacket) -> str:
        lines = [
            f"# 设计师评审包 - {packet.title}",
            "",
            f"- 项目：`{packet.project_key}`",
            f"- 工作项：`{packet.work_item_id}`",
            f"- 创建时间：`{packet.created_at}`",
            f"- 当前状态：`{packet.status}`",
            "",
            "## 先看结论",
            *(f"- {item}" for item in packet.decision_points or ["暂无明确决策点，请先生成创作包或质量门。"]),
            "",
            "## 产物索引",
        ]
        for key, value in packet.artifact_index.items():
            lines.append(f"- {key}: `{value or '缺失'}`")
        lines.extend(["", "## 推荐评审顺序", *(f"- [ ] {item}" for item in packet.review_steps)])
        lines.extend(["", "## 风险提醒", *(f"- {item}" for item in packet.warnings or ["无"])])
        lines.extend(["", "## 下一步", *(f"- {item}" for item in packet.next_actions)])
        lines.extend(["", "## 人工确认清单", *(f"- [ ] {item}" for item in packet.approval_checklist)])
        return "\n".join(lines)

    def _collect_artifacts(self, snapshot: SessionSnapshot | None, output_dir: Path | None) -> dict[str, str | None]:
        artifacts: dict[str, str | None] = {Path(name).stem: None for name in self.IMPORTANT_FILES}
        candidates: list[Path] = []
        if output_dir and output_dir.exists():
            candidates.extend(
                path
                for path in output_dir.rglob("*")
                if self._artifact_key(path) and path.suffix.lower() in {".md", ".json"}
            )
        if snapshot:
            for raw in snapshot.last_artifacts:
                path = Path(raw)
                if path.suffix.lower() in {".md", ".json"} and self._artifact_key(path) and path.exists():
                    candidates.append(path)
            # Learning/audit reports live in memory, so snapshot paths are the most reliable source.
        for path in candidates:
            key = self._artifact_key(path)
            if key:
                current = artifacts.get(key)
                if not current or (Path(current).suffix.lower() != ".md" and path.suffix.lower() == ".md"):
                    artifacts[key] = str(path)
        return artifacts

    @classmethod
    def _artifact_key(cls, path: Path) -> str | None:
        important_stems = {Path(name).stem for name in cls.IMPORTANT_FILES}
        if path.stem in important_stems:
            return path.stem
        for stem in important_stems:
            if path.stem.endswith(f"-{stem}"):
                return stem
        return None

    @staticmethod
    def _status(artifact_index: dict[str, str | None], readiness_payload: dict[str, Any] | None) -> str:
        if readiness_payload and readiness_payload.get("status"):
            return str(readiness_payload["status"])
        if artifact_index.get("psd_handoff_package"):
            return "ready_for_psd_review"
        if artifact_index.get("candidate_review"):
            return "candidate_reviewed"
        if artifact_index.get("generated_gallery"):
            return "generated_assets_registered"
        if artifact_index.get("creative_pack"):
            return "creative_pack_ready"
        return "draft"

    @staticmethod
    def _decision_points(readiness_payload: dict[str, Any] | None, candidate_review_payload: dict[str, Any] | None) -> list[str]:
        points: list[str] = []
        if readiness_payload:
            for item in readiness_payload.get("blocking_items", [])[:4]:
                points.append(f"先处理阻塞项：{item}")
            for item in readiness_payload.get("warnings", [])[:4]:
                points.append(f"风险需确认：{item}")
            status = readiness_payload.get("status")
            if status and not points:
                points.append(f"质量门状态为 `{status}`，可进入人工确认。")
        if candidate_review_payload:
            accepted = candidate_review_payload.get("accepted_variant_ids", [])
            pending = candidate_review_payload.get("pending_variant_ids", [])
            if accepted:
                points.append("已采纳方向：" + "、".join(accepted))
            if pending:
                points.append("仍待验证方向：" + "、".join(pending))
        return list(dict.fromkeys(points))

    @staticmethod
    def _review_steps(artifact_index: dict[str, str | None]) -> list[str]:
        steps = [
            "先看 design_brief，确认目标、尺寸、平台、交付物没有误解。",
            "再看 design_decision_record，理解本轮判断依据、证据和临时假设。",
            "再看 style_transfer_report，确认同品类底座哪些可迁移、哪些被项目覆盖。",
            "再看 style_alignment_report，确认 K1/K2、禁忌项和 K3 边界没有偏移。",
            "再看 creative_pack，确认风格判断、提示词、构图和 PSD 建议。",
            "如已有 generated_gallery，挑选候选图并补候选图评审。",
            "如已有 candidate_style_drift_report，先确认候选图是否偏离项目风格。",
            "如已有 candidate_comparison_matrix，对比 V01/V02/V03/V04 的采纳、修正或驳回建议。",
            "如已有 psd_handoff_plan，检查图层、切图和命名是否能执行。",
            "如已有 psd_slice_spec_report，先处理图层/切图/命名核对项，再进入 Photoshop。",
            "最后看 delivery_readiness_report，确认是否能进入交付或 Meegle 回写。",
            "如已有 design_workflow_plan，按步骤看板推进下一条最小安全动作。",
        ]
        if not artifact_index.get("generated_gallery"):
            steps.append("当前未登记生成图，可先评审 image_generation_batch 并决定是否执行出图。")
        if not artifact_index.get("candidate_review"):
            steps.append("当前未发现候选图评审回写，若已有候选图请先沉淀采纳/驳回原因。")
        return steps

    @staticmethod
    def _warnings(
        artifact_index: dict[str, str | None],
        readiness_payload: dict[str, Any] | None,
        candidate_review_payload: dict[str, Any] | None,
    ) -> list[str]:
        warnings: list[str] = []
        if not artifact_index.get("creative_pack"):
            warnings.append("缺少创作包，评审包只能作为空框架。")
        if artifact_index.get("creative_pack") and not artifact_index.get("style_alignment_report"):
            warnings.append("缺少风格一致性报告，出图前建议先检查 K1/K2、禁忌项和 K3 边界。")
        if artifact_index.get("creative_pack") and not artifact_index.get("style_transfer_report"):
            warnings.append("缺少风格迁移报告，跨同品类复用时建议先确认项目覆盖层。")
        if artifact_index.get("creative_pack") and not artifact_index.get("design_decision_record"):
            warnings.append("缺少设计决策记录，新会话恢复时可能丢失本轮判断依据。")
        if readiness_payload and readiness_payload.get("blocking_items"):
            warnings.append("交付质量门存在阻塞项，不能直接进入正式交付。")
        if artifact_index.get("generated_gallery") and not candidate_review_payload:
            warnings.append("已有生成图索引但缺少候选图评审回写，学习闭环尚未闭合。")
        if artifact_index.get("generated_gallery") and not artifact_index.get("candidate_style_drift_report"):
            warnings.append("已有生成图索引但缺少候选图风格偏移预警，采纳前建议补齐。")
        if artifact_index.get("generated_gallery") and not artifact_index.get("candidate_comparison_matrix"):
            warnings.append("已有生成图索引但缺少候选方案对比矩阵，进入 PSD 前建议先明确采纳/修正/驳回方向。")
        if artifact_index.get("psd_handoff_plan") and not artifact_index.get("psd_slice_spec_report"):
            warnings.append("已有 PSD 交接计划但缺少 PSD/切图规格核对报告，进入 Photoshop 前建议补齐。")
        if not artifact_index.get("delivery_readiness_report"):
            warnings.append("缺少交付质量门报告，正式交付前建议先生成。")
        if not artifact_index.get("design_workflow_plan"):
            warnings.append("缺少设计工作流计划，继续推进前建议生成步骤看板。")
        return warnings

    @staticmethod
    def _next_actions(artifact_index: dict[str, str | None], readiness_payload: dict[str, Any] | None) -> list[str]:
        actions: list[str] = []
        if not artifact_index.get("creative_pack"):
            actions.append("先生成 build-creative-pack 或 run-local-design-cycle。")
        if artifact_index.get("creative_pack") and not artifact_index.get("style_alignment_report"):
            actions.append("先运行 create-style-alignment-report，确认风格约束再执行出图。")
        if artifact_index.get("creative_pack") and not artifact_index.get("style_transfer_report"):
            actions.append("先运行 create-style-transfer-report，确认同品类底座与项目覆盖层没有冲突。")
        if artifact_index.get("creative_pack") and not artifact_index.get("design_decision_record"):
            actions.append("先运行 create-design-decision-record，记录本轮判断依据。")
        if artifact_index.get("image_generation_batch") and not artifact_index.get("generated_gallery"):
            if not artifact_index.get("image_execution_package"):
                actions.append("确认要执行的出图方案后，先运行 prepare-image-execution-package 准备执行交接包。")
            actions.append("生成后登记结果并生成 generated_gallery。")
        if artifact_index.get("generated_gallery") and not artifact_index.get("candidate_review"):
            actions.append("填写 candidate_review.json 并运行 ingest-candidate-review。")
        if artifact_index.get("generated_gallery") and not artifact_index.get("candidate_style_drift_report"):
            actions.append("运行 create-candidate-style-drift-report，先做候选图风格偏移预警。")
        if artifact_index.get("generated_gallery") and not artifact_index.get("candidate_comparison_matrix"):
            actions.append("运行 create-candidate-comparison-matrix，对 V01/V02/V03/V04 做采纳、修正或驳回判断。")
        if artifact_index.get("psd_handoff_plan") and not artifact_index.get("psd_slice_spec_report"):
            actions.append("进入 Photoshop 前运行 create-psd-slice-spec-report，核对图层、切图任务和命名样例。")
        if readiness_payload and readiness_payload.get("status") == "ready_for_designer_confirmation":
            actions.append("设计师确认后，可创建 Meegle 回写草稿或进入正式交付 staging。")
        if not artifact_index.get("design_workflow_plan"):
            actions.append("运行 create-design-workflow-plan，生成当前需求的步骤看板和下一步命令。")
        actions.append("所有对外发送、Meegle 发布、工作流流转和文件覆盖仍需显式确认。")
        return list(dict.fromkeys(actions))

    @staticmethod
    def _approval_checklist() -> list[str]:
        return [
            "我已确认本评审包只用于本地决策，不自动对外发布。",
            "我已复核 K3 假设没有被写成确定结论。",
            "我已确认进入下一步的候选图、PSD/切图计划或交付包。",
            "如需 Meegle 回写或工作流流转，将单独走确认门控。",
        ]

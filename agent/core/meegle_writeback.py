from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent.models import MeegleWritebackDraft, SessionSnapshot
from agent.utils import load_json


class MeegleWritebackDraftBuilder:
    IMPORTANT_ARTIFACTS = (
        "creative_pack.md",
        "requirement_clarification_report.md",
        "requirement_clarification_comment.md",
        "style_transfer_report.md",
        "style_alignment_report.md",
        "design_decision_record.md",
        "image_generation_batch.md",
        "image_execution_package.md",
        "pixpark_execution_runbook.md",
        "generated_gallery.md",
        "candidate_style_drift_report.md",
        "candidate_comparison_matrix.md",
        "candidate_review.md",
        "latest_learning_digest.md",
        "psd_handoff_plan.md",
        "psd_handoff_package.md",
        "psd_handoff_approval_ticket.md",
        "psd_slice_spec_report.md",
        "design_workflow_plan.md",
        "design_cycle_report.md",
    )

    def build(
        self,
        project_key: str,
        work_item_id: str,
        snapshot: SessionSnapshot | None,
        output_dir: Path | None,
    ) -> MeegleWritebackDraft:
        artifacts = self._collect_artifacts(snapshot, output_dir)
        title = snapshot.title if snapshot else work_item_id
        status = self._status(artifacts)
        comment = self._comment_markdown(project_key, work_item_id, title, status, artifacts, snapshot)
        return MeegleWritebackDraft(
            project_key=project_key,
            work_item_id=work_item_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            title=title,
            status=status,
            comment_markdown=comment,
            source_artifacts=artifacts,
            publish_command_preview=[
                "meegle",
                "comment",
                "add",
                "--project-key",
                project_key,
                "--work-item-id",
                work_item_id,
                "--content",
                "<review meegle_writeback_comment.md first>",
                "--format",
                "json",
            ],
            warnings=self._warnings(artifacts),
            approval_checklist=self._approval_checklist(),
        )

    @staticmethod
    def render_markdown(draft: MeegleWritebackDraft) -> str:
        lines = [
            f"# Meegle 回写草稿 - {draft.work_item_id}",
            "",
            f"- 项目：`{draft.project_key}`",
            f"- 创建时间：`{draft.created_at}`",
            f"- 状态：`{draft.status}`",
            "",
            "## 待发布评论",
            draft.comment_markdown,
            "",
            "## 来源产物",
            *(f"- {key}: `{value}`" for key, value in draft.source_artifacts.items()),
            "",
            "## 发布命令预览",
            "```bash",
            " ".join(draft.publish_command_preview),
            "```",
            "",
            "## 警告",
            *(f"- {item}" for item in draft.warnings or ["无"]),
            "",
            "## 发布前确认",
            *(f"- [ ] {item}" for item in draft.approval_checklist),
        ]
        return "\n".join(lines)

    @staticmethod
    def render_approval_ticket(draft: MeegleWritebackDraft) -> str:
        return "\n".join(
            [
                f"# Meegle 评论发布确认单 - {draft.work_item_id}",
                "",
                f"- 项目：`{draft.project_key}`",
                f"- 状态：`{draft.status}`",
                "",
                "## 安全说明",
                "- 当前只生成回写草稿，未调用 Meegle 评论接口。",
                "- 发布前必须人工检查评论内容、附件/路径、敏感信息和结论准确性。",
                "- 正式评论应只在设计师确认后执行。",
                "",
                "## 确认项",
                *(f"- [ ] {item}" for item in draft.approval_checklist),
                "",
                "## 结果",
                "- [ ] 允许发布到 Meegle 评论",
                "- [ ] 暂不发布，继续修改草稿",
            ]
        )

    def _collect_artifacts(self, snapshot: SessionSnapshot | None, output_dir: Path | None) -> dict[str, str]:
        artifacts: dict[str, str] = {}
        for raw_path in snapshot.last_artifacts if snapshot else []:
            path = Path(raw_path)
            if path.name in self.IMPORTANT_ARTIFACTS or path.suffix.lower() == ".md":
                artifacts[path.stem] = str(path)
        if output_dir and output_dir.exists():
            for path in output_dir.rglob("*.md"):
                if path.name in self.IMPORTANT_ARTIFACTS:
                    artifacts.setdefault(path.stem, str(path))
        return dict(sorted(artifacts.items()))

    def _comment_markdown(
        self,
        project_key: str,
        work_item_id: str,
        title: str,
        status: str,
        artifacts: dict[str, str],
        snapshot: SessionSnapshot | None,
    ) -> str:
        lines = [
            f"## 设计副驾进度回写：{title}",
            "",
            f"- 项目：`{project_key}`",
            f"- 工作项：`{work_item_id}`",
            f"- 当前状态：`{status}`",
            "",
            "### 本轮已产出",
        ]
        labels = {
            "creative_pack": "创作包",
            "requirement_clarification_report": "需求澄清清单",
            "requirement_clarification_comment": "需求澄清评论草稿",
            "style_transfer_report": "风格迁移与项目覆盖报告",
            "style_alignment_report": "风格一致性报告",
            "design_decision_record": "设计决策记录",
            "image_generation_batch": "多方案出图批次",
            "image_execution_package": "图像生成执行交接包",
            "pixpark_execution_runbook": "Pixpark 执行说明",
            "generated_gallery": "生成图索引",
            "candidate_style_drift_report": "候选图风格偏移预警",
            "candidate_comparison_matrix": "候选方案对比矩阵",
            "candidate_review": "候选图评审回写",
            "latest_learning_digest": "学习复盘",
            "psd_handoff_plan": "PSD 交接计划",
            "psd_handoff_package": "PSD 交接 staging 包",
            "psd_handoff_approval_ticket": "PSD 交接确认单",
            "psd_slice_spec_report": "PSD/切图规格核对报告",
            "design_workflow_plan": "设计工作流计划",
            "design_cycle_report": "设计闭环报告",
        }
        if not artifacts:
            lines.append("- 暂无可回写产物，请先生成创作包或设计闭环报告。")
        for key, path in artifacts.items():
            label = labels.get(key, key)
            lines.append(f"- {label}：`{path}`")
        if snapshot and snapshot.unresolved_questions:
            lines.extend(["", "### 仍需确认", *(f"- {item}" for item in snapshot.unresolved_questions[:6])])
        lines.extend(
            [
                "",
                "### 建议下一步",
                "- 设计师确认创作包和候选方向。",
                "- 若已确认候选图，进入 PSD 精修/切图 staging 包复核。",
                "- 所有正式交付或覆盖文件前，需要人工确认。",
                "",
                "_注：本评论由本地 design-copilot 生成，发布前已要求人工复核。_",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _status(artifacts: dict[str, str]) -> str:
        if "psd_slice_spec_report" in artifacts:
            return "psd_slice_spec_checked"
        if "psd_handoff_package" in artifacts:
            return "ready_for_psd_refine_or_slicing_review"
        if "psd_handoff_plan" in artifacts:
            return "psd_handoff_planned"
        if "candidate_comparison_matrix" in artifacts:
            return "candidate_compared"
        if "candidate_review" in artifacts:
            return "candidate_reviewed"
        if "generated_gallery" in artifacts:
            return "generated_assets_registered"
        if "image_generation_batch" in artifacts:
            return "creative_directions_ready"
        if "creative_pack" in artifacts:
            return "creative_pack_ready"
        return "draft"

    @staticmethod
    def _warnings(artifacts: dict[str, str]) -> list[str]:
        warnings: list[str] = []
        if not artifacts:
            warnings.append("没有找到可回写的产物路径。")
        if "creative_pack" not in artifacts:
            warnings.append("缺少创作包，建议先补齐再回写。")
        if "psd_handoff_approval_ticket" in artifacts:
            ticket = Path(artifacts["psd_handoff_approval_ticket"])
            if ticket.exists() and "[ ]" in ticket.read_text(encoding="utf-8"):
                warnings.append("PSD 交接确认单仍有未勾选项，发布时请说明仍待人工确认。")
        return warnings

    @staticmethod
    def _approval_checklist() -> list[str]:
        return [
            "确认评论内容不会误导需求方，以“本地副驾产物”身份表达。",
            "确认所有路径/URL 可以被相关协作者访问，或已说明是本地路径。",
            "确认未包含不应公开的内部实验提示词、敏感账号或未授权素材。",
            "确认不把 K3 待验证假设写成已定论。",
            "确认发布评论前由设计师人工批准。",
        ]

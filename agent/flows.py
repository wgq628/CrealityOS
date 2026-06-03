from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agent.models import to_plain_data
from agent.utils import dump_json, load_json, slugify

if TYPE_CHECKING:
    from agent.app import DesignCopilotApp


class FlowBase:
    def __init__(self, app: DesignCopilotApp) -> None:
        self.app = app


class RequirementFlow(FlowBase):
    _NO_ASSET_ROOT_SKIPS = (
        "未提供 asset_root，已跳过资产索引",
        "未提供 asset_root，已跳过交付 staging",
        "未提供 asset_root，已跳过自动化计划",
    )

    def run_feishu_design_cycle(
        self,
        project_key: str,
        work_item_id: str,
        asset_root: str | None = None,
        full: bool = False,
    ) -> dict:
        app = self.app
        context = app.meegle.fetch_workitem_context(project_key, work_item_id)
        context.docs = app.lark_docs.fetch_docs(context.doc_links)
        creative_pack_result = app._build_creative_pack_from_context(context)
        return self._run_cycle(
            project_key=project_key,
            work_item_id=work_item_id,
            title=context.title,
            creative_pack_result=creative_pack_result,
            asset_root=asset_root,
            full=full,
            source_mode_prefix="feishu",
            rerun_command="run-feishu-design-cycle",
        )

    def run_local_design_cycle(
        self,
        project_key: str,
        work_item_id: str,
        title: str,
        requirement_file: str,
        same_category: str | None = None,
        doc_files: list[str] | None = None,
        asset_root: str | None = None,
        full: bool = False,
    ) -> dict:
        app = self.app
        creative_pack_result = app.build_local_creative_pack(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            requirement_file=requirement_file,
            same_category=same_category,
            doc_files=doc_files,
        )
        return self._run_cycle(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            creative_pack_result=creative_pack_result,
            asset_root=asset_root,
            full=full,
            source_mode_prefix="local",
            rerun_command="run-local-design-cycle",
        )

    def _run_cycle(
        self,
        project_key: str,
        work_item_id: str,
        title: str,
        creative_pack_result: dict,
        asset_root: str | None,
        full: bool,
        source_mode_prefix: str,
        rerun_command: str,
    ) -> dict:
        app = self.app
        output_dir = Path(creative_pack_result["output_dir"])
        artifacts = self._collect_creative_pack_artifacts(creative_pack_result)
        skipped_steps: list[str] = []
        if asset_root:
            self._append_asset_pipeline_artifacts(
                artifacts=artifacts,
                project_key=project_key,
                work_item_id=work_item_id,
                asset_root=asset_root,
            )
        else:
            skipped_steps.extend(self._NO_ASSET_ROOT_SKIPS)
        next_actions = self._append_full_or_lean_artifacts(
            artifacts=artifacts,
            project_key=project_key,
            work_item_id=work_item_id,
            output_dir=output_dir,
            full=full,
            skipped_steps=skipped_steps,
            rerun_command=rerun_command,
        )
        report = app.cycle_reporter.build(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            source_mode=f"{source_mode_prefix}-full" if full else f"{source_mode_prefix}-lean",
            artifacts=artifacts,
            skipped_steps=skipped_steps,
            next_actions=list(dict.fromkeys(next_actions)),
        )
        report_dir = output_dir / "cycle"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "design_cycle_report.json"
        md_path = report_dir / "design_cycle_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(app.cycle_reporter.render_markdown(report), encoding="utf-8")
        return {
            "cycle_report": str(json_path),
            "cycle_report_md": str(md_path),
            "artifacts": artifacts,
            "skipped_steps": skipped_steps,
        }

    def _collect_creative_pack_artifacts(self, creative_pack_result: dict) -> dict[str, str]:
        artifacts: dict[str, str] = {"creative_pack_dir": creative_pack_result["output_dir"]}
        for path in creative_pack_result.get("artifacts") or []:
            artifacts[Path(path).stem] = path
        return artifacts

    def _append_asset_pipeline_artifacts(
        self,
        artifacts: dict[str, str],
        project_key: str,
        work_item_id: str,
        asset_root: str,
    ) -> None:
        app = self.app
        asset_result = app.scan_assets(project_key=project_key, asset_root=asset_root)
        artifacts["asset_index"] = asset_result["asset_index"]
        delivery_result = app.prepare_delivery_package(
            project_key=project_key,
            work_item_id=work_item_id,
            source_root=asset_root,
            include_extensions=None,
        )
        artifacts["delivery_package"] = delivery_result["artifacts"][0]
        automation_result = app.plan_automation(
            project_key=project_key,
            work_item_id=work_item_id,
            asset_root=asset_root,
        )
        app._merge_artifact_paths(
            artifacts,
            automation_result,
            [
                "automation_plan",
                "automation_plan_md",
                "automation_stub_ps1",
                "photoshop_jsx",
                "photoshop_script_readme",
                "photoshop_script_manifest",
            ],
        )

    def _append_full_or_lean_artifacts(
        self,
        artifacts: dict[str, str],
        project_key: str,
        work_item_id: str,
        output_dir: Path,
        full: bool,
        skipped_steps: list[str],
        rerun_command: str,
    ) -> list[str]:
        app = self.app
        if full:
            audit_result = app.metacognition_audit(project_key=project_key)
            transition_result = app.create_transition_summary(project_key=project_key)
            learning_result = app.create_learning_digest(project_key=project_key)
            artifacts["metacognition_audit"] = audit_result["metacognition_audit"]
            artifacts["transition_summary"] = transition_result["transition_summary"]
            artifacts["learning_digest"] = learning_result["learning_digest"]
            readiness_result = app.create_delivery_readiness_report(project_key=project_key, work_item_id=work_item_id)
            artifacts["delivery_readiness_report"] = readiness_result["delivery_readiness_report"]
            workflow_plan_result = app.create_design_workflow_plan(project_key=project_key, work_item_id=work_item_id)
            artifacts["design_workflow_plan"] = workflow_plan_result["design_workflow_plan"]
            review_packet_result = app.create_designer_review_packet(project_key=project_key, work_item_id=work_item_id)
            artifacts["designer_review_packet"] = review_packet_result["designer_review_packet"]
            return list(audit_result["actions"]) + list(transition_result["restart_instructions"][:2])
        cleaned = app._cleanup_lean_cycle_artifacts(output_dir)
        skipped_steps.extend(
            [
                "默认轻量流程已跳过元认知审计、学习复盘、交付质量门、工作流计划和评审包。",
                f"如需完整闭环，请重新运行 {rerun_command} --full。",
            ]
        )
        if cleaned:
            skipped_steps.append(f"默认轻量流程已清理历史完整流程产物目录：{', '.join(cleaned)}。")
        return [
            f"python -m agent.cli create-image-generation-jobs --project-key {project_key} --work-item-id {work_item_id} --variant V01",
            f"python -m agent.cli create-design-workflow-plan --project-key {project_key} --work-item-id {work_item_id}",
        ]


class ImageFlow(FlowBase):
    """Boundary for image production, generation, and candidate review orchestration."""

    def prepare_image_direction(self, project_key: str, work_item_id: str | None = None) -> dict:
        app = self.app
        snapshot = app.store.load_session_snapshot(project_key)
        if not snapshot:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")
        if work_item_id and snapshot.active_work_item_id != work_item_id:
            raise ValueError(
                f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
            )
        output_dir = Path(snapshot.output_dir)
        creative_pack = app._load_creative_pack_from_output_dir(output_dir)
        profile_key = snapshot.memory_project_key or app._resolve_memory_project_key(project_key, snapshot.active_work_item_id)
        profile = app.store.load_project_profile(profile_key)
        image_batch_paths = app._write_image_production_batch(output_dir, creative_pack, profile, write_markdown=False)
        image_batch = load_json(Path(image_batch_paths[0]), {})
        state_path = app._designer_workpack_state_path(snapshot)
        state_payload = load_json(state_path, {}) if state_path else {}
        prompt_path = app._designer_visible_path(state_payload, "prompt_sheet") or (output_dir / "中文提示词.md")
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(app._render_designer_prompt_sheet(creative_pack, image_batch), encoding="utf-8")
        if state_path:
            state_payload.setdefault("visible_files", {})["prompt_sheet"] = str(prompt_path)
            state_payload.setdefault("system_artifacts", {})["image_generation_batch"] = image_batch_paths[0]
            dump_json(state_path, state_payload)
        artifacts = image_batch_paths + [str(prompt_path)]
        if state_path:
            artifacts.append(str(state_path))
        snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
        app.store.save_session_snapshot(snapshot)
        return {
            "image_generation_batch": image_batch_paths[0],
            "prompt_sheet": str(prompt_path),
            "variant_count": len(image_batch.get("variants", [])) if isinstance(image_batch, dict) else 0,
            "artifacts": artifacts,
        }


class DeliveryFlow(FlowBase):
    """Boundary for PSD, delivery readiness, review packet, and writeback orchestration."""

    def create_delivery_readiness_report(
        self,
        project_key: str,
        work_item_id: str | None = None,
        write_markdown: bool = True,
    ) -> dict:
        app = self.app
        snapshot = app.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")

        output_dir = Path(snapshot.output_dir) if snapshot else app.paths.workspace / slugify(project_key, fallback="project") / f"{effective_work_item_id}-delivery-readiness"
        creative_pack_path = output_dir / "creative_pack.json"
        creative_pack = app._load_creative_pack_from_output_dir(output_dir) if creative_pack_path.exists() else None
        style_transfer_path = output_dir / "style_transfer_report.json"
        style_alignment_path = output_dir / "style_alignment_report.json"
        generation_results_path = app._generation_results_path(snapshot, project_key, effective_work_item_id)
        candidate_style_drift_path = app._candidate_style_drift_report_path(snapshot)
        candidate_comparison_path = app._candidate_comparison_matrix_path(snapshot)
        psd_plan_path = app._psd_handoff_plan_path(snapshot, project_key, effective_work_item_id)
        candidate_review_path = app._candidate_review_path(project_key, effective_work_item_id)
        psd_package_path = app._latest_snapshot_artifact(snapshot, "psd_handoff_package.json")
        psd_slice_spec_path = app._psd_slice_spec_report_path(snapshot)
        delivery_package = app.store.load_delivery_preparation(project_key)

        report = app.delivery_readiness.build(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            creative_pack=creative_pack,
            style_transfer=load_json(style_transfer_path, None) if style_transfer_path.exists() else None,
            style_alignment=load_json(style_alignment_path, None) if style_alignment_path.exists() else None,
            generation_results=load_json(generation_results_path, None) if generation_results_path else None,
            candidate_style_drift=load_json(candidate_style_drift_path, None) if candidate_style_drift_path else None,
            candidate_comparison=load_json(candidate_comparison_path, None) if candidate_comparison_path else None,
            candidate_review=load_json(candidate_review_path, None) if candidate_review_path else None,
            psd_handoff_plan=load_json(psd_plan_path, None) if psd_plan_path else None,
            psd_handoff_package=load_json(psd_package_path, None) if psd_package_path else None,
            psd_slice_spec_report=load_json(psd_slice_spec_path, None) if psd_slice_spec_path else None,
            delivery_package=delivery_package,
            source_artifacts={
                "creative_pack": str(creative_pack_path) if creative_pack_path.exists() else None,
                "style_transfer": str(style_transfer_path) if style_transfer_path.exists() else None,
                "style_alignment": str(style_alignment_path) if style_alignment_path.exists() else None,
                "generation_results": str(generation_results_path) if generation_results_path else None,
                "candidate_style_drift": str(candidate_style_drift_path) if candidate_style_drift_path else None,
                "candidate_comparison_matrix": str(candidate_comparison_path) if candidate_comparison_path else None,
                "candidate_review": str(candidate_review_path) if candidate_review_path else None,
                "psd_handoff_plan": str(psd_plan_path) if psd_plan_path else None,
                "psd_handoff_package": str(psd_package_path) if psd_package_path else None,
                "psd_slice_spec_report": str(psd_slice_spec_path) if psd_slice_spec_path else None,
                "delivery_package": delivery_package.staged_root if delivery_package else None,
            },
        )

        report_dir = output_dir / "delivery_readiness"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "delivery_readiness_report.json"
        md_path = report_dir / "delivery_readiness_report.md"
        dump_json(json_path, to_plain_data(report))
        artifacts = [str(json_path)]
        if write_markdown:
            md_path.write_text(app.delivery_readiness.render_markdown(report), encoding="utf-8")
            artifacts.append(str(md_path))
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            app.store.save_session_snapshot(snapshot)
        result = {
            "delivery_readiness_report": str(json_path),
            "status": report.status,
            "blocking_items": report.blocking_items,
            "warnings": report.warnings,
            "approval_checklist": report.approval_checklist,
        }
        if write_markdown:
            result["delivery_readiness_report_md"] = str(md_path)
        return result

    def prepare_delivery_review(self, project_key: str, work_item_id: str | None = None) -> dict:
        app = self.app
        snapshot = app.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        readiness = app.create_delivery_readiness_report(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            write_markdown=False,
        )
        output_dir = Path(snapshot.output_dir) if snapshot else app.paths.workspace / slugify(project_key, fallback="project") / f"{effective_work_item_id}-delivery-readiness"
        readiness_payload = load_json(Path(readiness["delivery_readiness_report"]), {})
        state_path = app._designer_workpack_state_path(snapshot) if snapshot else None
        state_payload = load_json(state_path, {}) if state_path else {}
        review_path = app._designer_visible_path(state_payload, "delivery_review_sheet") or (
            (state_path.parent.parent / "交付检查.md") if state_path else (output_dir / "交付检查.md")
        )
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(app._render_delivery_review_sheet(readiness_payload), encoding="utf-8")
        if state_path:
            state_payload.setdefault("visible_files", {})["delivery_review_sheet"] = str(review_path)
            state_payload.setdefault("system_artifacts", {})["delivery_readiness_report"] = readiness["delivery_readiness_report"]
            dump_json(state_path, state_payload)
        if snapshot:
            artifacts_to_add = [str(review_path)]
            if state_path:
                artifacts_to_add.append(str(state_path))
            snapshot.last_artifacts.extend(path for path in artifacts_to_add if path not in snapshot.last_artifacts)
            app.store.save_session_snapshot(snapshot)
        artifacts = [readiness["delivery_readiness_report"], str(review_path)]
        if state_path:
            artifacts.append(str(state_path))
        return {
            "delivery_readiness_report": readiness["delivery_readiness_report"],
            "delivery_review_sheet": str(review_path),
            "status": readiness["status"],
            "blocking_items": readiness["blocking_items"],
            "warnings": readiness["warnings"],
            "artifacts": artifacts,
        }

    def create_designer_review_packet(self, project_key: str, work_item_id: str | None = None) -> dict:
        app = self.app
        snapshot = app.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        output_dir = Path(snapshot.output_dir) if snapshot else app.paths.workspace / slugify(project_key, fallback="project") / f"{effective_work_item_id}-review-packet"
        readiness_path = output_dir / "delivery_readiness" / "delivery_readiness_report.json"
        candidate_review_path = app._candidate_review_path(project_key, effective_work_item_id)
        packet = app.review_packet_builder.build(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            snapshot=snapshot,
            output_dir=output_dir,
            readiness_payload=load_json(readiness_path, None) if readiness_path.exists() else None,
            candidate_review_payload=load_json(candidate_review_path, None) if candidate_review_path else None,
        )
        packet_dir = output_dir / "review_packet"
        packet_dir.mkdir(parents=True, exist_ok=True)
        json_path = packet_dir / "designer_review_packet.json"
        md_path = packet_dir / "designer_review_packet.md"
        dump_json(json_path, to_plain_data(packet))
        md_path.write_text(app.review_packet_builder.render_markdown(packet), encoding="utf-8")
        artifacts = [str(json_path), str(md_path)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            app.store.save_session_snapshot(snapshot)
        return {
            "designer_review_packet": str(json_path),
            "designer_review_packet_md": str(md_path),
            "status": packet.status,
            "decision_points": packet.decision_points,
            "warnings": packet.warnings,
            "next_actions": packet.next_actions,
        }

    def create_design_workflow_plan(self, project_key: str, work_item_id: str | None = None) -> dict:
        app = self.app
        snapshot = app.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        output_dir = Path(snapshot.output_dir) if snapshot else app.paths.workspace / slugify(project_key, fallback="project") / f"{effective_work_item_id}-workflow"
        title = snapshot.title if snapshot else effective_work_item_id
        extra_artifacts = list(snapshot.last_artifacts) if snapshot else []
        candidate_review_path = app._candidate_review_path(project_key, effective_work_item_id)
        if candidate_review_path:
            extra_artifacts.append(str(candidate_review_path))
        artifact_index = app.artifact_resolver.collect_artifacts(output_dir, extra_artifacts, include_missing=False)
        payloads = {
            key: load_json(Path(value), None) if value else None
            for key, value in artifact_index.items()
            if value and Path(value).suffix.lower() == ".json"
        }
        plan = app.workflow_planner.build(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            title=title,
            output_dir=output_dir,
            artifact_index=artifact_index,
            payloads=payloads,
        )
        plan_dir = output_dir / "workflow"
        plan_dir.mkdir(parents=True, exist_ok=True)
        json_path = plan_dir / "design_workflow_plan.json"
        md_path = plan_dir / "design_workflow_plan.md"
        dump_json(json_path, to_plain_data(plan))
        md_path.write_text(app.workflow_planner.render_markdown(plan), encoding="utf-8")
        artifacts = [str(json_path), str(md_path)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            app.store.save_session_snapshot(snapshot)
        return {
            "design_workflow_plan": str(json_path),
            "design_workflow_plan_md": str(md_path),
            "status": plan.status,
            "blockers": plan.blockers,
            "next_commands": plan.next_commands,
            "artifacts": artifacts,
        }


class MemoryFlow(FlowBase):
    """Boundary for learning, metacognition, style memory, and session recovery orchestration."""

    def metacognition_audit(self, project_key: str) -> dict:
        app = self.app
        style_card = app.store.load_style_card(project_key)
        profile = app.store.load_project_profile(project_key)
        snapshot = app.store.load_session_snapshot(project_key)
        asset_index = app.store.load_asset_index(project_key)
        delivery = app.store.load_delivery_preparation(project_key)
        recent_reports = app.store.list_review_reports(project_key, limit=5)
        recent_review_notes = [report.name for report in recent_reports]
        audit = app.metacognition.build(
            project_key=project_key,
            style_card=style_card,
            profile=profile,
            snapshot=snapshot,
            asset_index=asset_index,
            delivery=delivery,
            recent_review_notes=recent_review_notes,
        )
        audit_path = app.store.save_metacognition_audit(project_key, audit)
        markdown_path = audit_path.with_suffix(".md")
        markdown_path.write_text(app.metacognition.render_markdown(audit), encoding="utf-8")
        return {
            "metacognition_audit": str(audit_path),
            "metacognition_audit_md": str(markdown_path),
            "actions": audit.actions,
        }

    def create_transition_summary(self, project_key: str) -> dict:
        app = self.app
        snapshot = app.store.load_session_snapshot(project_key)
        style_card = app.store.load_style_card(project_key)
        profile = app.store.load_project_profile(project_key)
        recent_reports = app.store.list_review_reports(project_key, limit=5)
        recent_review_notes = [report.name for report in recent_reports]
        capability_delta = app.metacognition._capability_delta(style_card, recent_review_notes)
        summary = app.transition_builder.build(
            project_key=project_key,
            snapshot=snapshot,
            style_card=style_card,
            profile=profile,
            capability_delta=capability_delta,
            recent_review_notes=recent_review_notes,
        )
        summary_path = app.store.save_transition_summary(project_key, summary)
        markdown_path = summary_path.with_suffix(".md")
        markdown_path.write_text(app.transition_builder.render_markdown(summary), encoding="utf-8")
        return {
            "transition_summary": str(summary_path),
            "transition_summary_md": str(markdown_path),
            "restart_instructions": summary.restart_instructions,
        }

    def create_learning_digest(self, project_key: str) -> dict:
        app = self.app
        style_card = app.store.load_style_card(project_key)
        profile = app.store.load_project_profile(project_key)
        snapshot = app.store.load_session_snapshot(project_key)
        recent_reports = [app.store.load_review_report(path) for path in app.store.list_review_reports(project_key, limit=5)]
        digest = app.learning_digest_builder.build(
            project_key=project_key,
            style_card=style_card,
            profile=profile,
            snapshot=snapshot,
            recent_reviews=recent_reports,
        )
        digest_path = app.store.save_learning_digest(project_key, digest)
        markdown_path = digest_path.with_suffix(".md")
        markdown_path.write_text(app.learning_digest_builder.render_markdown(digest), encoding="utf-8")
        return {
            "learning_digest": str(digest_path),
            "learning_digest_md": str(markdown_path),
            "next_time_checklist": digest.next_time_checklist,
            "recommended_commands": digest.recommended_commands,
        }

    def curate_style_memory(self, project_key: str, apply: bool = False) -> dict:
        app = self.app
        style_card = app.store.load_style_card(project_key)
        updated_card, report = app.style_memory_curator.build_report(style_card, apply=apply)
        if apply and updated_card:
            app.store.save_style_card(updated_card)
        report_path = app.store.save_style_memory_curation_report(project_key, report)
        markdown_path = report_path.with_suffix(".md")
        markdown_path.write_text(app.style_memory_curator.render_markdown(report), encoding="utf-8")
        return {
            "style_memory_curation_report": str(report_path),
            "style_memory_curation_report_md": str(markdown_path),
            "mode": report.mode,
            "action_count": len(report.actions),
            "applied_count": sum(1 for action in report.actions if action.applied),
            "warnings": report.warnings,
            "next_actions": report.next_actions,
        }

    def ingest_feedback(
        self,
        project_key: str,
        same_category: str,
        feedback: str,
        decision: str,
        work_item_id: str | None = None,
        share_to_base: bool = False,
    ) -> dict:
        app = self.app
        report = app.style_learner.ingest_feedback(
            project_key=project_key,
            same_category=same_category,
            work_item_id=work_item_id,
            feedback=feedback,
            decision=decision,
            share_to_base=share_to_base,
        )
        report_path = app.store.save_review_report(project_key, report)
        markdown_path = report_path.with_suffix(".md")
        markdown_path.write_text(app._render_review_report(report), encoding="utf-8")
        return {"review_report": str(report_path), "review_report_md": str(markdown_path)}

    def ingest_style_reference(
        self,
        project_key: str,
        same_category: str,
        reference_file: str,
        share_to_base: bool = False,
    ) -> dict:
        app = self.app
        report = app.style_reference_ingestor.ingest(
            project_key=project_key,
            same_category=same_category,
            reference_file=reference_file,
            share_to_base=share_to_base,
        )
        report_path = app.store.save_style_reference_report(project_key, report)
        markdown_path = report_path.with_suffix(".md")
        markdown_path.write_text(app.style_reference_ingestor.render_markdown(report), encoding="utf-8")
        return {
            "style_reference_report": str(report_path),
            "style_reference_report_md": str(markdown_path),
            "reference_count": len(report.references),
            "accepted_rule_count": len(report.accepted_rules),
            "rejected_rule_count": len(report.rejected_rules),
            "pending_rule_count": len(report.pending_rules),
            "warnings": report.warnings,
            "next_actions": report.next_actions,
        }

    def resume_session(self, project_key: str) -> dict:
        app = self.app
        snapshot = app.store.load_session_snapshot(project_key)
        if not snapshot:
            return {"project_key": project_key, "message": "No session snapshot found."}
        output_dir = Path(snapshot.output_dir)
        decision_payload = load_json(output_dir / "design_decision_record.json", None)
        style_alignment_payload = load_json(output_dir / "style_alignment_report.json", None)
        recent_reports = app.store.list_review_reports(project_key, limit=5)
        recent_review_notes = [report.name for report in recent_reports]
        report = app.session_resume_builder.build(
            project_key=project_key,
            snapshot=snapshot,
            style_card=app.store.load_style_card(project_key),
            profile=app.store.load_project_profile(project_key),
            recent_review_notes=recent_review_notes,
            decision_payload=decision_payload,
            style_alignment_payload=style_alignment_payload,
        )
        report_path = app.store.save_session_resume_report(project_key, report)
        report_md = report_path.with_suffix(".md")
        report_md.write_text(app.session_resume_builder.render_markdown(report), encoding="utf-8")
        return {
            "snapshot": to_plain_data(snapshot),
            "session_resume": str(report_path),
            "session_resume_md": str(report_md),
            "status": report.status,
            "active_work_item_id": report.active_work_item_id,
            "unresolved_questions": report.unresolved_questions,
            "next_commands": report.next_commands,
        }

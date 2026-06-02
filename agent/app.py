from __future__ import annotations

from pathlib import Path
import json

from agent.adapters.lark_doc import LarkDocAdapter
from agent.adapters.local_files import LocalFileAdapter
from agent.adapters.meegle import MeegleAdapter
from agent.artifact_resolver import ArtifactResolver
from agent.core.creative_pack import CreativePackBuilder
from agent.core.automation_planner import AutomationPlanner
from agent.core.candidate_comparison import CandidateComparisonMatrixBuilder
from agent.core.candidate_review import CandidateReviewIngestor
from agent.core.candidate_style_drift import CandidateStyleDriftAuditor
from agent.core.cycle_report import DesignCycleReporter
from agent.core.decision_recorder import DesignDecisionRecorder
from agent.core.delivery_readiness import DeliveryReadinessAuditor
from agent.core.designer_cockpit import DesignerCockpitBuilder
from agent.core.designer_dashboard import DesignerDashboardBuilder
from agent.core.doctor import Doctor
from agent.core.field_calibration import FieldCalibrator
from agent.core.generation_queue import ImageGenerationQueueBuilder
from agent.core.generation_results import ImageGenerationResultRegistrar
from agent.core.image_execution_package import ImageExecutionPackager
from agent.core.image_production import ImageProductionPlanner
from agent.core.learning_digest import LearningDigestBuilder
from agent.core.meegle_writeback import MeegleWritebackDraftBuilder
from agent.core.meegle_publish import CONFIRM_TOKEN, MeeglePublishGate
from agent.core.meegle_transition import TRANSITION_CONFIRM_TOKEN, MeegleTransitionGate
from agent.core.metacognition import MetacognitionAuditor
from agent.core.psd_handoff import PsdHandoffPlanner
from agent.core.psd_handoff_package import PsdHandoffPackager
from agent.core.psd_slice_spec import PsdSliceSpecAuditor
from agent.core.project_profiles import ProjectProfileManager
from agent.core.project_skill import ProjectSkillBuilder
from agent.core.requirement_change import RequirementChangeAnalyzer
from agent.core.requirement_clarifier import RequirementClarifier
from agent.core.requirement_interpreter import RequirementInterpreter
from agent.core.requirement_memory import RequirementMemoryEngine
from agent.core.risk_detector import RiskDetector
from agent.core.review_packet import DesignerReviewPacketBuilder
from agent.core.session import SessionManager
from agent.core.session_resume import SessionResumeBuilder
from agent.core.style_alignment import StyleAlignmentAuditor
from agent.core.style_learner import StyleLearner
from agent.core.style_memory_curator import StyleMemoryCurator
from agent.core.style_references import StyleReferenceIngestor
from agent.core.style_transfer import StyleTransferAuditor
from agent.core.transition_summary import TransitionSummaryBuilder
from agent.core.todo_screener import TodoScreener
from agent.core.workflow_plan import DesignWorkflowPlanner
from agent.core.workitem_intake import WorkItemIntakeDiagnostician
from agent.memory.store import MemoryStore
from agent.models import CreativePack, DeliveryItem, DeliveryManifest, DesignBrief, ProjectProfile, PromptPack, RequirementDoc, RequirementMemoryReport, ReviewReport, StyleCard, StyleRule, WorkItemContext, to_plain_data
from agent.settings import AppPaths
from agent.shell import ShellRunner
from agent.utils import dump_json, load_json, slugify


class DesignCopilotApp:
    def __init__(self, root: Path) -> None:
        self.paths = AppPaths.from_root(root)
        runner = ShellRunner(cwd=root)
        self.local_files = LocalFileAdapter(self.paths)
        self.local_files.ensure_runtime_directories()
        self.meegle = MeegleAdapter(runner)
        self.lark_docs = LarkDocAdapter(runner)
        self.store = MemoryStore(self.paths)
        self.interpreter = RequirementInterpreter()
        self.requirement_change = RequirementChangeAnalyzer()
        self.requirement_clarifier = RequirementClarifier()
        self.requirement_memory = RequirementMemoryEngine(self.store)
        self.risk_detector = RiskDetector()
        self.style_learner = StyleLearner(self.store)
        self.style_memory_curator = StyleMemoryCurator()
        self.style_reference_ingestor = StyleReferenceIngestor(self.store)
        self.pack_builder = CreativePackBuilder()
        self.decision_recorder = DesignDecisionRecorder()
        self.image_production_planner = ImageProductionPlanner()
        self.generation_queue_builder = ImageGenerationQueueBuilder()
        self.image_execution_packager = ImageExecutionPackager()
        self.generation_result_registrar = ImageGenerationResultRegistrar()
        self.candidate_comparison_builder = CandidateComparisonMatrixBuilder()
        self.candidate_review_ingestor = CandidateReviewIngestor()
        self.candidate_style_drift = CandidateStyleDriftAuditor()
        self.session_manager = SessionManager()
        self.session_resume_builder = SessionResumeBuilder()
        self.style_alignment = StyleAlignmentAuditor()
        self.style_transfer = StyleTransferAuditor()
        self.profile_manager = ProjectProfileManager(self.store)
        self.project_skill_builder = ProjectSkillBuilder()
        self.automation_planner = AutomationPlanner()
        self.metacognition = MetacognitionAuditor()
        self.psd_handoff_planner = PsdHandoffPlanner()
        self.psd_handoff_packager = PsdHandoffPackager()
        self.psd_slice_spec_auditor = PsdSliceSpecAuditor()
        self.transition_builder = TransitionSummaryBuilder()
        self.learning_digest_builder = LearningDigestBuilder()
        self.meegle_writeback_builder = MeegleWritebackDraftBuilder()
        self.meegle_publish_gate = MeeglePublishGate()
        self.meegle_transition_gate = MeegleTransitionGate()
        self.cycle_reporter = DesignCycleReporter()
        self.field_calibrator = FieldCalibrator()
        self.todo_screener = TodoScreener()
        self.delivery_readiness = DeliveryReadinessAuditor()
        self.review_packet_builder = DesignerReviewPacketBuilder()
        self.workflow_planner = DesignWorkflowPlanner()
        self.artifact_resolver = ArtifactResolver(self.paths)
        self.workitem_intake = WorkItemIntakeDiagnostician()
        self.designer_cockpit_builder = DesignerCockpitBuilder()
        self.designer_dashboard_builder = DesignerDashboardBuilder()
        self.doctor_builder = Doctor()

    def init_workspace(self) -> dict:
        self.local_files.ensure_runtime_directories()
        return {
            "memory": str(self.paths.memory),
            "workspace": str(self.paths.workspace),
            "templates": str(self.paths.templates),
        }

    def fetch_todos(self, action: str = "todo", asset_key: str | None = None, max_pages: int = 1) -> list[dict]:
        return self.meegle.fetch_todos(action=action, asset_key=asset_key, max_pages=max_pages)

    def screen_todos(self, action: str = "todo", asset_key: str | None = None, max_pages: int = 1) -> dict:
        todos = self.fetch_todos(action=action, asset_key=asset_key, max_pages=max_pages)
        report = self.todo_screener.screen(todos, action=action)
        report_dir = self.paths.workspace / "todo-screening"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / f"{action}_screening.json"
        md_path = report_dir / f"{action}_screening.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.todo_screener.render_markdown(report), encoding="utf-8")
        return {
            "todo_screening": str(json_path),
            "todo_screening_md": str(md_path),
            "total_count": report.total_count,
            "design_count": report.design_count,
            "warnings": report.warnings,
        }

    def fetch_workitem_context(self, project_key: str, work_item_id: str) -> dict:
        context = self.meegle.fetch_workitem_context(project_key, work_item_id)
        return to_plain_data(context)

    def fetch_requirement_docs(self, project_key: str, work_item_id: str) -> list[dict]:
        context = self.meegle.fetch_workitem_context(project_key, work_item_id)
        context.docs = self.lark_docs.fetch_docs(context.doc_links)
        return [to_plain_data(doc) for doc in context.docs]

    def init_project_profile(self, project_key: str, same_category: str, display_name: str | None = None) -> dict:
        profile = self.profile_manager.ensure_profile(project_key, same_category, title=display_name or project_key)
        profile_path = self.store.save_project_profile(profile)
        markdown_path = profile_path.with_suffix(".md")
        markdown_path.write_text(self.profile_manager.render_markdown(profile), encoding="utf-8")
        return {"project_profile": str(profile_path), "project_profile_md": str(markdown_path)}

    def update_project_profile(
        self,
        project_key: str,
        same_category: str,
        profile_file: str,
        replace: bool = False,
    ) -> dict:
        profile, report = self.profile_manager.update_profile_from_file(
            project_key=project_key,
            same_category=same_category,
            profile_file=profile_file,
            replace=replace,
        )
        profile_path = self.store.save_project_profile(profile)
        profile_md = profile_path.with_suffix(".md")
        profile_md.write_text(self.profile_manager.render_markdown(profile), encoding="utf-8")
        report_path = self.store.save_project_profile_update_report(project_key, report)
        report_md = report_path.with_suffix(".md")
        report_md.write_text(self.profile_manager.render_update_report(report), encoding="utf-8")
        return {
            "project_profile": str(profile_path),
            "project_profile_md": str(profile_md),
            "project_profile_update_report": str(report_path),
            "project_profile_update_report_md": str(report_md),
            "changed_fields": report.changed_fields,
            "warnings": report.warnings,
            "next_actions": report.next_actions,
        }

    def generate_project_skill(self, project_key: str, output_dir: str | None = None) -> dict:
        memory_project_key = self._resolve_memory_project_key(project_key)
        report = self.project_skill_builder.build(
            project_key=memory_project_key,
            memory_root=self.paths.memory,
            profile=self.store.load_project_profile(memory_project_key),
            style_card=self.store.load_style_card(memory_project_key),
            output_dir=output_dir,
        )
        return to_plain_data(report)

    def calibrate_field_mapping(self, project_key: str, sample_file: str) -> dict:
        sample_path = Path(sample_file)
        payload = self._read_requirement_payload(sample_path, fallback_title=sample_path.stem)
        report = self.field_calibrator.build_report(project_key, sample_file, payload)
        mapping_path = self.store.save_field_mapping(report.mapping)
        report_path = self.store.save_field_calibration_report(project_key, report)
        report_md = report_path.with_suffix(".md")
        report_md.write_text(self.field_calibrator.render_markdown(report), encoding="utf-8")
        return {
            "field_mapping": str(mapping_path),
            "field_calibration_report": str(report_path),
            "field_calibration_report_md": str(report_md),
            "warnings": report.warnings,
        }

    def diagnose_workitem_intake(
        self,
        project_key: str,
        work_item_id: str | None = None,
        sample_file: str | None = None,
        title: str | None = None,
    ) -> dict:
        if not work_item_id and not sample_file:
            raise ValueError("Either work_item_id or sample_file is required.")
        if sample_file:
            sample_path = Path(sample_file)
            raw_item = self._read_requirement_payload(sample_path, fallback_title=title or sample_path.stem)
            context = WorkItemContext(
                project_key=project_key,
                work_item_id=work_item_id or sample_path.stem,
                title=title or str(raw_item.get("title") or raw_item.get("name") or sample_path.stem),
                raw_item=raw_item,
                comments=[],
                doc_links=[],
                docs=[],
            )
            source_mode = "local-sample"
            source_artifacts = {"sample_file": str(sample_path)}
        else:
            context = self.meegle.fetch_workitem_context(project_key, work_item_id or "")
            source_mode = "meegle-workitem"
            source_artifacts = {"meegle_workitem": f"{project_key}/{work_item_id}"}
        report = self.workitem_intake.build(
            context=context,
            source_mode=source_mode,
            source_artifacts=source_artifacts,
            existing_mapping=self.store.load_field_mapping(project_key),
        )
        safe_project = slugify(project_key, fallback="project")
        safe_item = slugify(context.work_item_id, fallback="item")
        report_dir = self.paths.workspace / "intake" / safe_project / safe_item
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "workitem_intake_diagnostics.json"
        md_path = report_dir / "workitem_intake_diagnostics.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.workitem_intake.render_markdown(report), encoding="utf-8")
        return {
            "workitem_intake_diagnostics": str(json_path),
            "workitem_intake_diagnostics_md": str(md_path),
            "status": report.status,
            "blockers": report.blockers,
            "warnings": report.warnings,
            "missing_information": report.parsed_brief.missing_information,
            "next_actions": report.next_actions,
        }

    def scan_assets(self, project_key: str, asset_root: str) -> dict:
        asset_index = self.local_files.scan_assets(project_key, Path(asset_root))
        report_path = self.store.save_asset_index(project_key, asset_index)
        markdown_path = report_path.with_suffix(".md")
        markdown_path.write_text(self._render_asset_index(asset_index), encoding="utf-8")
        return {
            "asset_index": str(report_path),
            "asset_index_md": str(markdown_path),
            "asset_count": len(asset_index.asset_cards),
            "warnings": asset_index.warnings,
        }

    def build_creative_pack(self, project_key: str, work_item_id: str) -> dict:
        context = self.meegle.fetch_workitem_context(project_key, work_item_id)
        context.docs = self.lark_docs.fetch_docs(context.doc_links)
        return self._build_creative_pack_from_context(context)

    def create_requirement_clarification_report(
        self,
        project_key: str,
        work_item_id: str | None = None,
        output_dir: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        if output_dir:
            target_dir = Path(output_dir)
        elif snapshot:
            if work_item_id and snapshot.active_work_item_id != work_item_id:
                raise ValueError(
                    f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
                )
            target_dir = Path(snapshot.output_dir)
        else:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")

        brief_path = target_dir / "design_brief.json"
        brief_payload = load_json(brief_path, None)
        if not brief_payload:
            raise FileNotFoundError(f"design_brief.json does not exist: {brief_path}")
        brief = DesignBrief(**brief_payload)
        artifacts = self._write_requirement_clarification(target_dir, brief)
        if snapshot and Path(snapshot.output_dir).resolve() == target_dir.resolve():
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        report_payload = load_json(target_dir / "requirement_clarification_report.json", {})
        questions = report_payload.get("questions", [])
        return {
            "requirement_clarification_report": artifacts[0],
            "requirement_clarification_report_md": artifacts[1],
            "requirement_clarification_comment": artifacts[2],
            "safe_to_continue": report_payload.get("safe_to_continue", False),
            "question_count": len(questions),
            "blocker_count": sum(1 for question in questions if question.get("severity") == "blocker"),
            "artifacts": artifacts,
        }

    def create_requirement_change_report(
        self,
        project_key: str,
        work_item_id: str | None = None,
        requirement_file: str | None = None,
        same_category: str | None = None,
        title: str | None = None,
        doc_files: list[str] | None = None,
        output_dir: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        if output_dir:
            target_dir = Path(output_dir)
        elif snapshot:
            if work_item_id and snapshot.active_work_item_id != work_item_id:
                raise ValueError(
                    f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
                )
            target_dir = Path(snapshot.output_dir)
        else:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")

        old_brief_path = target_dir / "design_brief.json"
        old_brief_payload = load_json(old_brief_path, None)
        if not old_brief_payload:
            raise FileNotFoundError(f"design_brief.json does not exist: {old_brief_path}")
        old_brief = DesignBrief(**old_brief_payload)
        effective_work_item_id = work_item_id or old_brief.work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no design brief work item exists.")

        source_artifacts: dict[str, str | None] = {
            "old_design_brief": str(old_brief_path),
            "output_dir": str(target_dir),
        }
        if requirement_file:
            context = self._load_local_context(
                project_key=project_key,
                work_item_id=effective_work_item_id,
                title=title or old_brief.title,
                requirement_file=requirement_file,
                doc_files=doc_files,
            )
            field_mapping = self.store.load_field_mapping(project_key)
            source_mode = "local"
            source_artifacts["new_requirement_file"] = str(Path(requirement_file))
            if doc_files:
                source_artifacts["new_doc_files"] = "; ".join(doc_files)
        else:
            context = self.meegle.fetch_workitem_context(project_key, effective_work_item_id)
            context.docs = self.lark_docs.fetch_docs(context.doc_links)
            field_mapping = self.store.load_field_mapping(project_key)
            source_mode = "feishu"
            source_artifacts["work_item_id"] = effective_work_item_id

        new_brief = self.interpreter.build(context, field_mapping=field_mapping)
        if same_category:
            new_brief.same_category = same_category
        new_brief.risk_points = self.risk_detector.detect(new_brief, context)
        report = self.requirement_change.build(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            old_brief=old_brief,
            new_brief=new_brief,
            source_mode=source_mode,
            source_artifacts=source_artifacts,
        )
        json_path = target_dir / "requirement_change_report.json"
        md_path = target_dir / "requirement_change_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.requirement_change.render_markdown(report), encoding="utf-8")
        artifacts = [str(json_path), str(md_path)]
        if snapshot and Path(snapshot.output_dir).resolve() == target_dir.resolve():
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "requirement_change_report": str(json_path),
            "requirement_change_report_md": str(md_path),
            "status": report.status,
            "change_count": len(report.change_items),
            "blockers": report.blockers,
            "warnings": report.warnings,
            "impacted_artifacts": report.impacted_artifacts,
            "next_actions": report.next_actions,
            "artifacts": artifacts,
        }

    def create_style_alignment_report(
        self,
        project_key: str,
        work_item_id: str | None = None,
        output_dir: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        if output_dir:
            target_dir = Path(output_dir)
        elif snapshot:
            if work_item_id and snapshot.active_work_item_id != work_item_id:
                raise ValueError(
                    f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
                )
            target_dir = Path(snapshot.output_dir)
        else:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")

        creative_pack = self._load_creative_pack_from_output_dir(target_dir)
        artifacts = self._write_style_alignment_report(target_dir, creative_pack)
        if snapshot and Path(snapshot.output_dir).resolve() == target_dir.resolve():
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        report_payload = load_json(target_dir / "style_alignment_report.json", {})
        return {
            "style_alignment_report": artifacts[0],
            "style_alignment_report_md": artifacts[1],
            "status": report_payload.get("status"),
            "blockers": report_payload.get("blockers", []),
            "warnings": report_payload.get("warnings", []),
            "artifacts": artifacts,
        }

    def create_design_decision_record(
        self,
        project_key: str,
        work_item_id: str | None = None,
        output_dir: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        if output_dir:
            target_dir = Path(output_dir)
        elif snapshot:
            if work_item_id and snapshot.active_work_item_id != work_item_id:
                raise ValueError(
                    f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
                )
            target_dir = Path(snapshot.output_dir)
        else:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")

        creative_pack = self._load_creative_pack_from_output_dir(target_dir)
        artifacts = self._write_design_decision_record(target_dir, creative_pack)
        if snapshot and Path(snapshot.output_dir).resolve() == target_dir.resolve():
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        record_payload = load_json(target_dir / "design_decision_record.json", {})
        return {
            "design_decision_record": artifacts[0],
            "design_decision_record_md": artifacts[1],
            "decision_count": len(record_payload.get("decisions", [])),
            "open_question_count": len(record_payload.get("open_questions", [])),
            "artifacts": artifacts,
        }

    def create_style_transfer_report(
        self,
        project_key: str,
        work_item_id: str | None = None,
        output_dir: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        if output_dir:
            target_dir = Path(output_dir)
        elif snapshot:
            if work_item_id and snapshot.active_work_item_id != work_item_id:
                raise ValueError(
                    f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
                )
            target_dir = Path(snapshot.output_dir)
        else:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")

        creative_pack_path = target_dir / "creative_pack.json"
        creative_pack = self._load_creative_pack_from_output_dir(target_dir) if creative_pack_path.exists() else None
        effective_work_item_id = work_item_id or (creative_pack.brief.work_item_id if creative_pack else snapshot.active_work_item_id if snapshot else "general")
        profile = self.store.load_project_profile(project_key)
        effective_style = creative_pack.style_card if creative_pack else self.store.load_style_card(project_key)
        same_category = (
            creative_pack.brief.same_category
            if creative_pack
            else profile.same_category
            if profile
            else effective_style.same_category
            if effective_style
            else "unknown"
        )
        artifacts = self._write_style_transfer_report(
            output_dir=target_dir,
            project_key=project_key,
            work_item_id=effective_work_item_id,
            same_category=same_category,
            effective_style=effective_style,
            profile=profile,
            creative_pack_path=creative_pack_path if creative_pack_path.exists() else None,
        )
        if snapshot and Path(snapshot.output_dir).resolve() == target_dir.resolve():
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        report_payload = load_json(target_dir / "style_transfer_report.json", {})
        return {
            "style_transfer_report": artifacts[0],
            "style_transfer_report_md": artifacts[1],
            "status": report_payload.get("status"),
            "blockers": report_payload.get("blockers", []),
            "warnings": report_payload.get("warnings", []),
            "artifacts": artifacts,
        }

    def run_feishu_design_cycle(
        self,
        project_key: str,
        work_item_id: str,
        asset_root: str | None = None,
    ) -> dict:
        context = self.meegle.fetch_workitem_context(project_key, work_item_id)
        context.docs = self.lark_docs.fetch_docs(context.doc_links)
        artifacts: dict[str, str] = {}
        skipped_steps: list[str] = []
        creative_pack_result = self._build_creative_pack_from_context(context)
        artifacts["creative_pack_dir"] = creative_pack_result["output_dir"]
        for path in creative_pack_result["artifacts"]:
            artifacts[Path(path).stem] = path

        if asset_root:
            asset_result = self.scan_assets(project_key=project_key, asset_root=asset_root)
            artifacts["asset_index"] = asset_result["asset_index"]
            delivery_result = self.prepare_delivery_package(
                project_key=project_key,
                work_item_id=work_item_id,
                source_root=asset_root,
                include_extensions=None,
            )
            artifacts["delivery_package"] = delivery_result["artifacts"][0]
            automation_result = self.plan_automation(
                project_key=project_key,
                work_item_id=work_item_id,
                asset_root=asset_root,
            )
            self._merge_artifact_paths(
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
        else:
            skipped_steps.extend(
                [
                    "未提供 asset_root，已跳过资产索引",
                    "未提供 asset_root，已跳过交付 staging",
                    "未提供 asset_root，已跳过自动化计划",
                ]
            )

        audit_result = self.metacognition_audit(project_key=project_key)
        transition_result = self.create_transition_summary(project_key=project_key)
        learning_result = self.create_learning_digest(project_key=project_key)
        artifacts["metacognition_audit"] = audit_result["metacognition_audit"]
        artifacts["transition_summary"] = transition_result["transition_summary"]
        artifacts["learning_digest"] = learning_result["learning_digest"]
        readiness_result = self.create_delivery_readiness_report(project_key=project_key, work_item_id=work_item_id)
        artifacts["delivery_readiness_report"] = readiness_result["delivery_readiness_report"]
        workflow_plan_result = self.create_design_workflow_plan(project_key=project_key, work_item_id=work_item_id)
        artifacts["design_workflow_plan"] = workflow_plan_result["design_workflow_plan"]
        review_packet_result = self.create_designer_review_packet(project_key=project_key, work_item_id=work_item_id)
        artifacts["designer_review_packet"] = review_packet_result["designer_review_packet"]
        report = self.cycle_reporter.build(
            project_key=project_key,
            work_item_id=work_item_id,
            title=context.title,
            source_mode="feishu",
            artifacts=artifacts,
            skipped_steps=skipped_steps,
            next_actions=list(dict.fromkeys(list(audit_result["actions"]) + list(transition_result["restart_instructions"][:2]))),
        )
        report_dir = Path(creative_pack_result["output_dir"]) / "cycle"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "design_cycle_report.json"
        md_path = report_dir / "design_cycle_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.cycle_reporter.render_markdown(report), encoding="utf-8")
        return {
            "cycle_report": str(json_path),
            "cycle_report_md": str(md_path),
            "artifacts": artifacts,
            "skipped_steps": skipped_steps,
        }

    def build_local_creative_pack(
        self,
        project_key: str,
        work_item_id: str,
        title: str,
        requirement_file: str,
        same_category: str | None = None,
        doc_files: list[str] | None = None,
    ) -> dict:
        context = self._load_local_context(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            requirement_file=requirement_file,
            doc_files=doc_files,
        )
        return self._build_creative_pack_from_context(context, same_category_override=same_category)

    def run_local_design_cycle(
        self,
        project_key: str,
        work_item_id: str,
        title: str,
        requirement_file: str,
        same_category: str | None = None,
        doc_files: list[str] | None = None,
        asset_root: str | None = None,
    ) -> dict:
        artifacts: dict[str, str] = {}
        skipped_steps: list[str] = []
        creative_pack_result = self.build_local_creative_pack(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            requirement_file=requirement_file,
            same_category=same_category,
            doc_files=doc_files,
        )
        artifacts["creative_pack_dir"] = creative_pack_result["output_dir"]
        for path in creative_pack_result["artifacts"]:
            key = Path(path).stem
            artifacts[key] = path

        if asset_root:
            asset_result = self.scan_assets(project_key=project_key, asset_root=asset_root)
            artifacts["asset_index"] = asset_result["asset_index"]
            delivery_result = self.prepare_delivery_package(
                project_key=project_key,
                work_item_id=work_item_id,
                source_root=asset_root,
                include_extensions=None,
            )
            artifacts["delivery_package"] = delivery_result["artifacts"][0]
            automation_result = self.plan_automation(
                project_key=project_key,
                work_item_id=work_item_id,
                asset_root=asset_root,
            )
            self._merge_artifact_paths(
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
        else:
            skipped_steps.extend(
                [
                    "未提供 asset_root，已跳过资产索引",
                    "未提供 asset_root，已跳过交付 staging",
                    "未提供 asset_root，已跳过自动化计划",
                ]
            )

        audit_result = self.metacognition_audit(project_key=project_key)
        transition_result = self.create_transition_summary(project_key=project_key)
        learning_result = self.create_learning_digest(project_key=project_key)
        artifacts["metacognition_audit"] = audit_result["metacognition_audit"]
        artifacts["transition_summary"] = transition_result["transition_summary"]
        artifacts["learning_digest"] = learning_result["learning_digest"]
        readiness_result = self.create_delivery_readiness_report(project_key=project_key, work_item_id=work_item_id)
        artifacts["delivery_readiness_report"] = readiness_result["delivery_readiness_report"]
        workflow_plan_result = self.create_design_workflow_plan(project_key=project_key, work_item_id=work_item_id)
        artifacts["design_workflow_plan"] = workflow_plan_result["design_workflow_plan"]
        review_packet_result = self.create_designer_review_packet(project_key=project_key, work_item_id=work_item_id)
        artifacts["designer_review_packet"] = review_packet_result["designer_review_packet"]

        next_actions = list(audit_result["actions"]) + list(transition_result["restart_instructions"][:2])
        report = self.cycle_reporter.build(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            source_mode="local",
            artifacts=artifacts,
            skipped_steps=skipped_steps,
            next_actions=list(dict.fromkeys(next_actions)),
        )
        report_dir = Path(creative_pack_result["output_dir"]) / "cycle"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "design_cycle_report.json"
        md_path = report_dir / "design_cycle_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.cycle_reporter.render_markdown(report), encoding="utf-8")
        return {
            "cycle_report": str(json_path),
            "cycle_report_md": str(md_path),
            "artifacts": artifacts,
            "skipped_steps": skipped_steps,
        }

    def _build_creative_pack_from_context(
        self,
        context: WorkItemContext,
        same_category_override: str | None = None,
    ) -> dict:
        project_key = context.project_key or "unknown-project"
        work_item_id = context.work_item_id
        field_mapping = self.store.load_field_mapping(project_key)
        brief = self.interpreter.build(context, field_mapping=field_mapping)
        if same_category_override:
            brief.same_category = same_category_override
        brief.risk_points = self.risk_detector.detect(brief, context)
        memory_project_key = self._memory_project_key_from_brief(brief, project_key)
        self.store.save_project_memory_binding(
            meego_project_key=project_key,
            work_item_id=work_item_id,
            memory_project_key=memory_project_key,
            game_name=brief.game_name,
            game_project_id=brief.game_project_id,
        )
        profile = self.profile_manager.ensure_profile(memory_project_key, brief.same_category, title=brief.game_name if brief.game_name != "待确认" else context.title)
        memory_report = self.requirement_memory.learn(brief, profile)
        memory_report_path = self.store.save_requirement_memory_report(memory_project_key, memory_report)
        memory_report.memory_paths["requirement_memory_report"] = str(memory_report_path)
        self.store.save_requirement_memory_report(memory_project_key, memory_report)
        style_card = self.style_learner.synthesize(memory_project_key, brief.same_category, brief.raw_signals, brief.missing_information)
        style_card = self.profile_manager.apply_profile_to_style_card(style_card, profile)
        style_card.project_key = memory_project_key
        creative_pack = self.pack_builder.build(brief, style_card, profile)

        output_dir = self.local_files.prepare_run_directory(project_key, work_item_id, context.title)
        self._write_brief(output_dir, brief)
        memory_paths = self._write_requirement_memory_report(output_dir, memory_report)
        clarification_paths = self._write_requirement_clarification(output_dir, brief)
        self._write_style_card(output_dir, style_card)
        self._write_creative_pack(output_dir, creative_pack)
        style_transfer_paths = self._write_style_transfer_report(
            output_dir=output_dir,
            project_key=project_key,
            work_item_id=work_item_id,
            same_category=brief.same_category,
            effective_style=style_card,
            profile=profile,
            creative_pack_path=output_dir / "creative_pack.json",
        )
        style_alignment_paths = self._write_style_alignment_report(output_dir, creative_pack)
        decision_record_paths = self._write_design_decision_record(output_dir, creative_pack)
        self._write_delivery_manifest(output_dir, creative_pack)
        image_batch_paths = self._write_image_production_batch(output_dir, creative_pack, profile)

        self.store.save_style_card(style_card)
        snapshot = self.session_manager.build_snapshot(creative_pack, output_dir)
        snapshot.last_artifacts.extend(memory_paths + clarification_paths + style_transfer_paths + style_alignment_paths + decision_record_paths + image_batch_paths)
        snapshot.memory_project_key = memory_project_key
        self.store.save_session_snapshot(snapshot)

        return {
            "output_dir": str(output_dir),
            "artifacts": snapshot.last_artifacts,
            "same_category": brief.same_category,
            "uncertainties": creative_pack.uncertainties,
        }

    def create_image_production_batch(self, project_key: str, work_item_id: str | None = None) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        if not snapshot:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")
        if work_item_id and snapshot.active_work_item_id != work_item_id:
            raise ValueError(
                f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
            )
        output_dir = Path(snapshot.output_dir)
        creative_pack = self._load_creative_pack_from_output_dir(output_dir)
        profile = self.store.load_project_profile(project_key)
        artifacts = self._write_image_production_batch(output_dir, creative_pack, profile)
        snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
        self.store.save_session_snapshot(snapshot)
        return {
            "image_generation_batch": artifacts[0],
            "image_generation_batch_md": artifacts[1],
            "candidate_evaluation_md": artifacts[2],
            "artifacts": artifacts,
        }

    def ingest_candidate_review(
        self,
        project_key: str,
        same_category: str,
        review_file: str,
        work_item_id: str | None = None,
        share_to_base: bool = False,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")

        batch_path = self._candidate_batch_path(snapshot)
        batch_payload = load_json(batch_path, {}) if batch_path and batch_path.exists() else None
        items = self.candidate_review_ingestor.load_items(review_file, batch_payload=batch_payload)
        generated_review_reports: list[str] = []
        for item in items:
            feedback = self.candidate_review_ingestor.feedback_for_item(item)
            review = self.style_learner.ingest_feedback(
                project_key=project_key,
                same_category=same_category,
                work_item_id=f"{effective_work_item_id}-{item.variant_id}",
                feedback=feedback,
                decision=item.decision,
                share_to_base=share_to_base and item.decision == "approved",
            )
            review_path = self.store.save_review_report(project_key, review)
            review_md = review_path.with_suffix(".md")
            review_md.write_text(self._render_review_report(review), encoding="utf-8")
            generated_review_reports.extend([str(review_path), str(review_md)])

        report = self.candidate_review_ingestor.build_report(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            source_batch=str(batch_path) if batch_path else None,
            items=items,
            generated_review_reports=generated_review_reports,
        )
        report_path = self.store.save_candidate_review_report(project_key, report)
        report_md = report_path.with_suffix(".md")
        report_md.write_text(self.candidate_review_ingestor.render_markdown(report), encoding="utf-8")
        learning_result = self.create_learning_digest(project_key)
        drift_artifacts: list[str] = []
        comparison_artifacts: list[str] = []
        if snapshot:
            results_path = self._generation_results_path(snapshot, project_key, effective_work_item_id)
            if results_path:
                drift_artifacts = self._write_candidate_style_drift_report(
                    project_key=project_key,
                    work_item_id=effective_work_item_id,
                    output_dir=Path(snapshot.output_dir),
                    generation_results_path=results_path,
                    candidate_review_path=report_path,
                )
                comparison_artifacts = self._write_candidate_comparison_matrix(
                    project_key=project_key,
                    work_item_id=effective_work_item_id,
                    output_dir=Path(snapshot.output_dir),
                    generation_results_path=results_path,
                    candidate_style_drift_path=Path(drift_artifacts[0]),
                    candidate_review_path=report_path,
                )
                snapshot.last_artifacts.extend(path for path in drift_artifacts + comparison_artifacts if path not in snapshot.last_artifacts)
                self.store.save_session_snapshot(snapshot)
        return {
            "candidate_review": str(report_path),
            "candidate_review_md": str(report_md),
            "candidate_style_drift_report": drift_artifacts[0] if drift_artifacts else None,
            "candidate_style_drift_report_md": drift_artifacts[1] if drift_artifacts else None,
            "candidate_comparison_matrix": comparison_artifacts[0] if comparison_artifacts else None,
            "candidate_comparison_matrix_md": comparison_artifacts[1] if comparison_artifacts else None,
            "generated_review_reports": generated_review_reports,
            "learning_digest": learning_result["learning_digest"],
            "accepted_variant_ids": report.accepted_variant_ids,
            "rejected_variant_ids": report.rejected_variant_ids,
            "pending_variant_ids": report.pending_variant_ids,
            "next_actions": report.next_actions,
        }

    def create_image_generation_jobs(
        self,
        project_key: str,
        work_item_id: str | None = None,
        variants: list[str] | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        if not snapshot:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")
        if work_item_id and snapshot.active_work_item_id != work_item_id:
            raise ValueError(
                f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
            )
        batch_path = self._candidate_batch_path(snapshot)
        if not batch_path:
            raise FileNotFoundError(f"No image_generation_batch.json found for project: {project_key}")
        batch_payload = load_json(batch_path, {})
        queue_dir = Path(snapshot.output_dir) / "generation_jobs"
        queue = self.generation_queue_builder.build(
            batch_payload=batch_payload,
            source_batch=str(batch_path),
            selected_variants=variants,
            output_root=queue_dir / "outputs",
        )
        queue_dir.mkdir(parents=True, exist_ok=True)
        json_path = queue_dir / "image_generation_jobs.json"
        md_path = queue_dir / "image_generation_jobs.md"
        jsonl_path = queue_dir / "pixpark_requests.jsonl"
        approval_path = queue_dir / "generation_approval_ticket.md"
        dump_json(json_path, to_plain_data(queue))
        md_path.write_text(self.generation_queue_builder.render_markdown(queue), encoding="utf-8")
        jsonl_path.write_text(self.generation_queue_builder.render_pixpark_jsonl(queue), encoding="utf-8")
        approval_path.write_text(self._render_generation_approval_ticket(queue), encoding="utf-8")
        artifacts = [str(json_path), str(md_path), str(jsonl_path), str(approval_path)]
        snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
        self.store.save_session_snapshot(snapshot)
        return {
            "image_generation_jobs": str(json_path),
            "image_generation_jobs_md": str(md_path),
            "pixpark_requests_jsonl": str(jsonl_path),
            "generation_approval_ticket": str(approval_path),
            "job_count": len(queue.jobs),
            "warnings": queue.warnings,
            "next_actions": queue.next_actions,
        }

    def prepare_image_execution_package(self, project_key: str, work_item_id: str | None = None) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        if not snapshot:
            raise FileNotFoundError(f"No session snapshot found for project: {project_key}")
        if work_item_id and snapshot.active_work_item_id != work_item_id:
            raise ValueError(
                f"Latest snapshot is for work item {snapshot.active_work_item_id}, not requested work item {work_item_id}."
            )
        queue_path = self._generation_queue_path(snapshot)
        if not queue_path:
            raise FileNotFoundError(f"No image_generation_jobs.json found for project: {project_key}")
        queue_payload = load_json(queue_path, {})
        package_root = Path(snapshot.output_dir) / "generation_jobs" / "execution_package"
        payload_dir = package_root / "payloads"
        payload_dir.mkdir(parents=True, exist_ok=True)
        package = self.image_execution_packager.build(queue_payload, str(queue_path), package_root)
        jobs_by_id = {str(job.get("job_id")): job for job in queue_payload.get("jobs", []) if isinstance(job, dict)}
        for item in package.items:
            job = jobs_by_id.get(item.job_id, {})
            Path(item.payload_file).write_text(
                self.image_execution_packager.render_payload(dict(job.get("payload") or {})),
                encoding="utf-8",
            )
            Path(item.output_dir).mkdir(parents=True, exist_ok=True)
        json_path = package_root / "image_execution_package.json"
        md_path = package_root / "image_execution_package.md"
        runbook_path = package_root / "pixpark_execution_runbook.md"
        results_template_path = package_root / "generation_results_template.json"
        dump_json(json_path, to_plain_data(package))
        md_path.write_text(self.image_execution_packager.render_markdown(package), encoding="utf-8")
        runbook_path.write_text(self.image_execution_packager.render_runbook(package), encoding="utf-8")
        dump_json(results_template_path, package.result_template)
        artifacts = [str(json_path), str(md_path), str(runbook_path), str(results_template_path)] + [item.payload_file for item in package.items]
        snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
        self.store.save_session_snapshot(snapshot)
        return {
            "image_execution_package": str(json_path),
            "image_execution_package_md": str(md_path),
            "pixpark_execution_runbook": str(runbook_path),
            "generation_results_template": str(results_template_path),
            "item_count": len(package.items),
            "warnings": package.warnings,
            "next_actions": package.next_actions,
            "artifacts": artifacts,
        }

    def register_image_results(
        self,
        project_key: str,
        results_file: str,
        work_item_id: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        queue_path = self._generation_queue_path(snapshot)
        queue_payload = load_json(queue_path, {}) if queue_path and queue_path.exists() else None
        assets = self.generation_result_registrar.load_assets(results_file, queue_payload=queue_payload)
        index = self.generation_result_registrar.build_index(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            source_queue=str(queue_path) if queue_path else None,
            assets=assets,
        )
        result_dir = self._generation_result_dir(snapshot, project_key, effective_work_item_id)
        result_dir.mkdir(parents=True, exist_ok=True)
        json_path = result_dir / "image_generation_results.json"
        gallery_path = result_dir / "generated_gallery.md"
        candidates_path = result_dir / "delivery_candidates.md"
        dump_json(json_path, to_plain_data(index))
        gallery_path.write_text(self.generation_result_registrar.render_gallery(index), encoding="utf-8")
        candidates_path.write_text(self.generation_result_registrar.render_delivery_candidates(index), encoding="utf-8")
        artifacts = [str(json_path), str(gallery_path), str(candidates_path)]
        drift_artifacts = self._write_candidate_style_drift_report(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            output_dir=Path(snapshot.output_dir) if snapshot else result_dir,
            generation_results_path=json_path,
            candidate_review_path=self._candidate_review_path(project_key, effective_work_item_id),
        )
        comparison_artifacts = self._write_candidate_comparison_matrix(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            output_dir=Path(snapshot.output_dir) if snapshot else result_dir,
            generation_results_path=json_path,
            candidate_style_drift_path=Path(drift_artifacts[0]),
            candidate_review_path=self._candidate_review_path(project_key, effective_work_item_id),
        )
        artifacts.extend(drift_artifacts + comparison_artifacts)
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "image_generation_results": str(json_path),
            "generated_gallery": str(gallery_path),
            "delivery_candidates": str(candidates_path),
            "candidate_style_drift_report": drift_artifacts[0],
            "candidate_style_drift_report_md": drift_artifacts[1],
            "candidate_comparison_matrix": comparison_artifacts[0],
            "candidate_comparison_matrix_md": comparison_artifacts[1],
            "asset_count": len(index.assets),
            "missing_assets": index.missing_assets,
            "delivery_candidates_count": len(index.delivery_candidates),
            "next_actions": index.next_actions,
        }

    def create_candidate_style_drift_report(
        self,
        project_key: str,
        work_item_id: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        output_dir = Path(snapshot.output_dir) if snapshot else self.paths.workspace / slugify(project_key, fallback="project")
        results_path = self._generation_results_path(snapshot, project_key, effective_work_item_id)
        if not results_path:
            raise FileNotFoundError("No image_generation_results.json found. Run register-image-results first.")
        artifacts = self._write_candidate_style_drift_report(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            output_dir=output_dir,
            generation_results_path=results_path,
            candidate_review_path=self._candidate_review_path(project_key, effective_work_item_id),
        )
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        report_payload = load_json(Path(artifacts[0]), {})
        return {
            "candidate_style_drift_report": artifacts[0],
            "candidate_style_drift_report_md": artifacts[1],
            "status": report_payload.get("status"),
            "blockers": report_payload.get("blockers", []),
            "warnings": report_payload.get("warnings", []),
            "artifacts": artifacts,
        }

    def create_candidate_comparison_matrix(
        self,
        project_key: str,
        work_item_id: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        output_dir = Path(snapshot.output_dir) if snapshot else self.paths.workspace / slugify(project_key, fallback="project")
        artifacts = self._write_candidate_comparison_matrix(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            output_dir=output_dir,
            generation_results_path=self._generation_results_path(snapshot, project_key, effective_work_item_id),
            candidate_style_drift_path=self._candidate_style_drift_report_path(snapshot),
            candidate_review_path=self._candidate_review_path(project_key, effective_work_item_id),
        )
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        payload = load_json(Path(artifacts[0]), {})
        return {
            "candidate_comparison_matrix": artifacts[0],
            "candidate_comparison_matrix_md": artifacts[1],
            "status": payload.get("status"),
            "recommended_variant_ids": payload.get("recommended_variant_ids", []),
            "warnings": payload.get("warnings", []),
            "blockers": payload.get("blockers", []),
            "artifacts": artifacts,
        }

    def create_psd_handoff_plan(
        self,
        project_key: str,
        work_item_id: str | None = None,
        selected_assets: list[str] | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        results_path = self._generation_results_path(snapshot, project_key, effective_work_item_id)
        results_payload = load_json(results_path, {}) if results_path and results_path.exists() else None
        output_dir = Path(snapshot.output_dir) if snapshot else self.paths.workspace / slugify(project_key, fallback="project")
        creative_pack_path = output_dir / "creative_pack.json"
        creative_pack = self._load_creative_pack_from_output_dir(output_dir) if creative_pack_path.exists() else None
        plan = self.psd_handoff_planner.build(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            results_payload=results_payload,
            creative_pack=creative_pack,
            selected_assets=selected_assets,
            source_results=str(results_path) if results_path else None,
            source_creative_pack=str(creative_pack_path) if creative_pack_path.exists() else None,
        )
        plan_dir = output_dir / "psd_handoff"
        plan_dir.mkdir(parents=True, exist_ok=True)
        json_path = plan_dir / "psd_handoff_plan.json"
        md_path = plan_dir / "psd_handoff_plan.md"
        layer_map_path = plan_dir / "layer_map.md"
        slice_checklist_path = plan_dir / "slice_checklist.md"
        dump_json(json_path, to_plain_data(plan))
        md_path.write_text(self.psd_handoff_planner.render_markdown(plan), encoding="utf-8")
        layer_map_path.write_text(self.psd_handoff_planner.render_layer_map(plan), encoding="utf-8")
        slice_checklist_path.write_text(self.psd_handoff_planner.render_slice_checklist(plan), encoding="utf-8")
        artifacts = [str(json_path), str(md_path), str(layer_map_path), str(slice_checklist_path)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "psd_handoff_plan": str(json_path),
            "psd_handoff_plan_md": str(md_path),
            "layer_map": str(layer_map_path),
            "slice_checklist": str(slice_checklist_path),
            "asset_count": len(plan.assets),
            "warnings": plan.warnings,
            "approval_checklist": plan.approval_checklist,
        }

    def prepare_psd_handoff_package(
        self,
        project_key: str,
        work_item_id: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        plan_path = self._psd_handoff_plan_path(snapshot, project_key, effective_work_item_id)
        if not plan_path or not plan_path.exists():
            raise FileNotFoundError("No psd_handoff_plan.json found. Run create-psd-handoff-plan first.")
        plan_payload = load_json(plan_path, {})
        safe_project = slugify(project_key, fallback="project")
        safe_item = slugify(effective_work_item_id, fallback="item")
        stage_root = (
            self.paths.root
            / "workspace"
            / "deliveries"
            / safe_project
            / f"{safe_item}-psd-handoff-{self._timestamp_for_path()}"
        )
        package = self.psd_handoff_packager.build(
            plan_payload=plan_payload,
            source_plan=str(plan_path),
            staged_root=stage_root,
        )
        manifest_json = stage_root / "psd_handoff_package.json"
        manifest_md = stage_root / "psd_handoff_package.md"
        approval_ticket = stage_root / "psd_handoff_approval_ticket.md"
        dump_json(manifest_json, to_plain_data(package))
        manifest_md.write_text(self.psd_handoff_packager.render_markdown(package), encoding="utf-8")
        approval_ticket.write_text(self.psd_handoff_packager.render_approval_ticket(package), encoding="utf-8")
        artifacts = [str(manifest_json), str(manifest_md), str(approval_ticket)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "staged_root": package.staged_root,
            "psd_handoff_package": str(manifest_json),
            "psd_handoff_package_md": str(manifest_md),
            "psd_handoff_approval_ticket": str(approval_ticket),
            "item_count": len(package.items),
            "warnings": package.warnings,
            "confirmation_checklist": package.confirmation_checklist,
        }

    def create_psd_slice_spec_report(
        self,
        project_key: str,
        work_item_id: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        output_dir = Path(snapshot.output_dir) if snapshot else self.paths.workspace / slugify(project_key, fallback="project")
        plan_path = self._psd_handoff_plan_path(snapshot, project_key, effective_work_item_id)
        if not plan_path or not plan_path.exists():
            raise FileNotFoundError("No psd_handoff_plan.json found. Run create-psd-handoff-plan first.")
        package_path = self._latest_snapshot_artifact(snapshot, "psd_handoff_package.json")
        creative_pack_path = output_dir / "creative_pack.json"
        creative_pack = self._load_creative_pack_from_output_dir(output_dir) if creative_pack_path.exists() else None
        profile = self.store.load_project_profile(project_key)
        report = self.psd_slice_spec_auditor.build(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            psd_handoff_plan=load_json(plan_path, None),
            psd_handoff_package=load_json(package_path, None) if package_path else None,
            creative_pack=creative_pack,
            profile=profile,
            source_artifacts={
                "psd_handoff_plan": str(plan_path),
                "psd_handoff_package": str(package_path) if package_path else None,
                "creative_pack": str(creative_pack_path) if creative_pack_path.exists() else None,
                "project_profile": str(self.paths.memory / "projects" / project_key / "project_profile.json") if profile else None,
            },
        )
        report_dir = output_dir / "psd_handoff"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "psd_slice_spec_report.json"
        md_path = report_dir / "psd_slice_spec_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.psd_slice_spec_auditor.render_markdown(report), encoding="utf-8")
        artifacts = [str(json_path), str(md_path)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "psd_slice_spec_report": str(json_path),
            "psd_slice_spec_report_md": str(md_path),
            "status": report.status,
            "blockers": report.blockers,
            "warnings": report.warnings,
            "next_actions": report.next_actions,
            "artifacts": artifacts,
        }

    def create_meegle_writeback_draft(self, project_key: str, work_item_id: str | None = None) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        output_dir = Path(snapshot.output_dir) if snapshot else None
        draft = self.meegle_writeback_builder.build(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            snapshot=snapshot,
            output_dir=output_dir,
        )
        draft_dir = output_dir / "meegle_writeback" if output_dir else self.paths.workspace / slugify(project_key, fallback="project") / f"{effective_work_item_id}-meegle-writeback"
        draft_dir.mkdir(parents=True, exist_ok=True)
        json_path = draft_dir / "meegle_writeback_draft.json"
        md_path = draft_dir / "meegle_writeback_draft.md"
        comment_path = draft_dir / "meegle_writeback_comment.md"
        approval_path = draft_dir / "meegle_writeback_approval_ticket.md"
        dump_json(json_path, to_plain_data(draft))
        md_path.write_text(self.meegle_writeback_builder.render_markdown(draft), encoding="utf-8")
        comment_path.write_text(draft.comment_markdown, encoding="utf-8")
        approval_path.write_text(self.meegle_writeback_builder.render_approval_ticket(draft), encoding="utf-8")
        artifacts = [str(json_path), str(md_path), str(comment_path), str(approval_path)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "meegle_writeback_draft": str(json_path),
            "meegle_writeback_draft_md": str(md_path),
            "meegle_writeback_comment": str(comment_path),
            "meegle_writeback_approval_ticket": str(approval_path),
            "status": draft.status,
            "warnings": draft.warnings,
            "approval_checklist": draft.approval_checklist,
        }

    def create_delivery_readiness_report(self, project_key: str, work_item_id: str | None = None) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")

        output_dir = Path(snapshot.output_dir) if snapshot else self.paths.workspace / slugify(project_key, fallback="project") / f"{effective_work_item_id}-delivery-readiness"
        creative_pack_path = output_dir / "creative_pack.json"
        creative_pack = self._load_creative_pack_from_output_dir(output_dir) if creative_pack_path.exists() else None
        style_transfer_path = output_dir / "style_transfer_report.json"
        style_alignment_path = output_dir / "style_alignment_report.json"
        generation_results_path = self._generation_results_path(snapshot, project_key, effective_work_item_id)
        candidate_style_drift_path = self._candidate_style_drift_report_path(snapshot)
        candidate_comparison_path = self._candidate_comparison_matrix_path(snapshot)
        psd_plan_path = self._psd_handoff_plan_path(snapshot, project_key, effective_work_item_id)
        candidate_review_path = self._candidate_review_path(project_key, effective_work_item_id)
        psd_package_path = self._latest_snapshot_artifact(snapshot, "psd_handoff_package.json")
        psd_slice_spec_path = self._psd_slice_spec_report_path(snapshot)
        delivery_package = self.store.load_delivery_preparation(project_key)

        report = self.delivery_readiness.build(
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
        md_path.write_text(self.delivery_readiness.render_markdown(report), encoding="utf-8")
        artifacts = [str(json_path), str(md_path)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "delivery_readiness_report": str(json_path),
            "delivery_readiness_report_md": str(md_path),
            "status": report.status,
            "blocking_items": report.blocking_items,
            "warnings": report.warnings,
            "approval_checklist": report.approval_checklist,
        }

    def create_designer_review_packet(self, project_key: str, work_item_id: str | None = None) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        output_dir = Path(snapshot.output_dir) if snapshot else self.paths.workspace / slugify(project_key, fallback="project") / f"{effective_work_item_id}-review-packet"
        readiness_path = output_dir / "delivery_readiness" / "delivery_readiness_report.json"
        candidate_review_path = self._candidate_review_path(project_key, effective_work_item_id)
        packet = self.review_packet_builder.build(
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
        md_path.write_text(self.review_packet_builder.render_markdown(packet), encoding="utf-8")
        artifacts = [str(json_path), str(md_path)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "designer_review_packet": str(json_path),
            "designer_review_packet_md": str(md_path),
            "status": packet.status,
            "decision_points": packet.decision_points,
            "warnings": packet.warnings,
            "next_actions": packet.next_actions,
        }

    def create_design_workflow_plan(self, project_key: str, work_item_id: str | None = None) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        output_dir = Path(snapshot.output_dir) if snapshot else self.paths.workspace / slugify(project_key, fallback="project") / f"{effective_work_item_id}-workflow"
        title = snapshot.title if snapshot else effective_work_item_id
        extra_artifacts = list(snapshot.last_artifacts) if snapshot else []
        candidate_review_path = self._candidate_review_path(project_key, effective_work_item_id)
        if candidate_review_path:
            extra_artifacts.append(str(candidate_review_path))
        artifact_index = self.artifact_resolver.collect_artifacts(output_dir, extra_artifacts)
        payloads = {
            key: load_json(Path(value), None) if value else None
            for key, value in artifact_index.items()
            if value and Path(value).suffix.lower() == ".json"
        }
        plan = self.workflow_planner.build(
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
        md_path.write_text(self.workflow_planner.render_markdown(plan), encoding="utf-8")
        artifacts = [str(json_path), str(md_path)]
        if snapshot:
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "design_workflow_plan": str(json_path),
            "design_workflow_plan_md": str(md_path),
            "status": plan.status,
            "blockers": plan.blockers,
            "next_commands": plan.next_commands,
            "artifacts": artifacts,
        }

    def cockpit(
        self,
        project_key: str,
        work_item_id: str | None = None,
        output_dir: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if output_dir:
            target_dir = Path(output_dir)
        elif snapshot and (not work_item_id or work_item_id == snapshot.active_work_item_id):
            target_dir = Path(snapshot.output_dir)
        else:
            target_dir = self.paths.workspace / slugify(project_key, fallback="project") / "cockpit"
        extra_artifacts = list(snapshot.last_artifacts) if snapshot else []
        if effective_work_item_id:
            candidate_review_path = self._candidate_review_path(project_key, effective_work_item_id)
            if candidate_review_path:
                extra_artifacts.append(str(candidate_review_path))
        artifact_index = self.artifact_resolver.collect_artifacts(target_dir if target_dir.exists() else None, extra_artifacts)
        payloads = {
            key: load_json(Path(value), None) if value else None
            for key, value in artifact_index.items()
            if value and Path(value).suffix.lower() == ".json"
        }
        learning_digest_path = self.paths.memory / "projects" / project_key / "latest_learning_digest.json"
        report = self.designer_cockpit_builder.build(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            snapshot=snapshot,
            output_dir=target_dir,
            artifact_index=artifact_index,
            payloads=payloads,
            learning_digest=load_json(learning_digest_path, None) if learning_digest_path.exists() else None,
        )
        cockpit_dir = target_dir / "cockpit"
        cockpit_dir.mkdir(parents=True, exist_ok=True)
        json_path = cockpit_dir / "designer_cockpit.json"
        md_path = cockpit_dir / "designer_cockpit.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.designer_cockpit_builder.render_markdown(report), encoding="utf-8")
        artifacts = [str(json_path), str(md_path)]
        if snapshot and Path(snapshot.output_dir).resolve() == target_dir.resolve():
            snapshot.last_artifacts.extend(path for path in artifacts if path not in snapshot.last_artifacts)
            self.store.save_session_snapshot(snapshot)
        return {
            "designer_cockpit": str(json_path),
            "designer_cockpit_md": str(md_path),
            "status": report.status,
            "work_item_id": report.work_item_id,
            "blockers": report.blockers,
            "confirmations": report.confirmations,
            "next_commands": report.next_commands,
            "artifacts": artifacts,
        }

    def dashboard(
        self,
        project_key: str,
        work_item_id: str | None = None,
        output_dir: str | None = None,
    ) -> dict:
        cockpit_result = self.cockpit(project_key=project_key, work_item_id=work_item_id, output_dir=output_dir)
        cockpit_payload = load_json(Path(cockpit_result["designer_cockpit"]), {})
        target_dir = Path(cockpit_payload.get("output_dir") or output_dir or self.paths.workspace / slugify(project_key, fallback="project") / "dashboard")
        artifact_index = cockpit_payload.get("artifact_index") or {}

        def artifact_payload(key: str) -> dict | None:
            value = artifact_index.get(key)
            return load_json(Path(value), None) if value else None

        requirement_memory_path = target_dir / "requirement_memory_report.json"
        payload = self.designer_dashboard_builder.build_payload(
            cockpit=cockpit_payload,
            design_brief=artifact_payload("design_brief"),
            creative_pack=artifact_payload("creative_pack"),
            requirement_memory=load_json(requirement_memory_path, None)
            if requirement_memory_path.exists()
            else load_json(self.paths.memory / "projects" / project_key / "latest_requirement_memory_report.json", None),
            learning_digest=load_json(self.paths.memory / "projects" / project_key / "latest_learning_digest.json", None),
            project_profile=load_json(self.paths.memory / "projects" / project_key / "project_profile.json", None),
            workflow_plan=artifact_payload("design_workflow_plan"),
            delivery_readiness=artifact_payload("delivery_readiness_report"),
        )
        dashboard_dir = target_dir / "dashboard"
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        data_path = dashboard_dir / "dashboard_data.json"
        html_path = dashboard_dir / "dashboard.html"
        dump_json(data_path, payload)
        html_path.write_text(self.designer_dashboard_builder.render_html(payload), encoding="utf-8")
        return {
            "dashboard": str(html_path),
            "dashboard_data": str(data_path),
            "designer_cockpit": cockpit_result["designer_cockpit"],
            "status": cockpit_payload.get("status", "draft"),
            "work_item_id": cockpit_payload.get("work_item_id"),
            "artifacts": [str(html_path), str(data_path)],
        }

    def doctor(self, project_key: str | None = None) -> dict:
        snapshot = self.store.load_session_snapshot(project_key) if project_key else None
        report = self.doctor_builder.build(self.paths, project_key=project_key, snapshot=snapshot)
        report_dir = self.paths.workspace / "diagnostics"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "doctor_report.json"
        md_path = report_dir / "doctor_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.doctor_builder.render_markdown(report), encoding="utf-8")
        return {
            "doctor_report": str(json_path),
            "doctor_report_md": str(md_path),
            "status": report.status,
            "warnings": report.warnings,
            "blockers": report.blockers,
            "recommended_commands": report.recommended_commands,
        }

    def publish_meegle_writeback(
        self,
        project_key: str,
        work_item_id: str | None = None,
        execute: bool = False,
        confirm_token: str | None = None,
        approval_file: str | None = None,
        draft_dir: str | None = None,
    ) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        effective_work_item_id = work_item_id or (snapshot.active_work_item_id if snapshot else None)
        if not effective_work_item_id:
            raise ValueError("work_item_id is required when no session snapshot exists.")
        writeback_dir = self._meegle_writeback_dir(snapshot, project_key, effective_work_item_id, draft_dir)
        comment_path = writeback_dir / "meegle_writeback_comment.md"
        if not comment_path.exists():
            raise FileNotFoundError("No meegle_writeback_comment.md found. Run create-meegle-writeback-draft first.")
        allowed, confirmation_method, warnings = self.meegle_publish_gate.validate_confirmation(
            execute=execute,
            confirm_token=confirm_token,
            approval_file=approval_file,
        )
        content = comment_path.read_text(encoding="utf-8")
        command_preview = [
            "meegle",
            "comment",
            "add",
            "--project-key",
            project_key,
            "--work-item-id",
            effective_work_item_id,
            "--content",
            str(comment_path),
            "--format",
            "json",
        ]
        response: dict = {}
        if execute and allowed:
            response = self.meegle.add_comment(project_key=project_key, work_item_id=effective_work_item_id, content=content)
        receipt = self.meegle_publish_gate.build_receipt(
            project_key=project_key,
            work_item_id=effective_work_item_id,
            comment_path=str(comment_path),
            command_preview=command_preview,
            executed=execute and allowed,
            confirmation_method=confirmation_method,
            response=response,
            warnings=warnings,
        )
        receipt_path = writeback_dir / "meegle_publish_receipt.json"
        receipt_md = writeback_dir / "meegle_publish_receipt.md"
        dump_json(receipt_path, to_plain_data(receipt))
        receipt_md.write_text(self.meegle_publish_gate.render_markdown(receipt), encoding="utf-8")
        if snapshot:
            for path in (str(receipt_path), str(receipt_md)):
                if path not in snapshot.last_artifacts:
                    snapshot.last_artifacts.append(path)
            self.store.save_session_snapshot(snapshot)
        return {
            "meegle_publish_receipt": str(receipt_path),
            "meegle_publish_receipt_md": str(receipt_md),
            "executed": receipt.executed,
            "confirmation_method": receipt.confirmation_method,
            "warnings": receipt.warnings,
            "confirm_token_hint": CONFIRM_TOKEN,
        }

    def create_meegle_transition_draft(
        self,
        project_key: str,
        work_item_id: str,
        action: str = "confirm",
        node_id: str | None = None,
        node_names: list[str] | None = None,
        rollback_reason: str | None = None,
    ) -> dict:
        draft = self.meegle_transition_gate.build_draft(
            project_key=project_key,
            work_item_id=work_item_id,
            action=action,
            node_id=node_id,
            node_names=node_names,
            rollback_reason=rollback_reason,
        )
        draft_dir = self.paths.workspace / slugify(project_key, fallback="project") / f"{work_item_id}-meegle-transition"
        draft_dir.mkdir(parents=True, exist_ok=True)
        json_path = draft_dir / "meegle_transition_draft.json"
        md_path = draft_dir / "meegle_transition_draft.md"
        approval_path = draft_dir / "meegle_transition_approval_ticket.md"
        dump_json(json_path, to_plain_data(draft))
        md_path.write_text(self.meegle_transition_gate.render_draft_markdown(draft), encoding="utf-8")
        approval_path.write_text(self.meegle_transition_gate.render_approval_ticket(draft), encoding="utf-8")
        return {
            "meegle_transition_draft": str(json_path),
            "meegle_transition_draft_md": str(md_path),
            "meegle_transition_approval_ticket": str(approval_path),
            "warnings": draft.warnings,
            "approval_checklist": draft.approval_checklist,
            "confirm_token_hint": TRANSITION_CONFIRM_TOKEN,
        }

    def publish_meegle_transition(
        self,
        project_key: str,
        work_item_id: str,
        execute: bool = False,
        confirm_token: str | None = None,
        approval_file: str | None = None,
        draft_dir: str | None = None,
    ) -> dict:
        transition_dir = Path(draft_dir) if draft_dir else self.paths.workspace / slugify(project_key, fallback="project") / f"{work_item_id}-meegle-transition"
        draft_path = transition_dir / "meegle_transition_draft.json"
        if not draft_path.exists():
            raise FileNotFoundError("No meegle_transition_draft.json found. Run create-meegle-transition-draft first.")
        payload = load_json(draft_path, {})
        draft = self.meegle_transition_gate.build_draft(
            project_key=payload["project_key"],
            work_item_id=payload["work_item_id"],
            action=payload["action"],
            node_id=payload.get("node_id"),
            node_names=payload.get("node_names") or [],
            rollback_reason=payload.get("rollback_reason"),
        )
        allowed, confirmation_method, warnings = self.meegle_transition_gate.validate_confirmation(
            execute=execute,
            confirm_token=confirm_token,
            approval_file=approval_file,
        )
        response: dict = {}
        if execute and allowed:
            response = self.meegle.transition_workflow(
                project_key=draft.project_key,
                work_item_id=draft.work_item_id,
                action=draft.action,
                node_id=draft.node_id,
                node_names=draft.node_names,
                rollback_reason=draft.rollback_reason,
            )
        receipt = self.meegle_transition_gate.build_receipt(
            draft=draft,
            executed=execute and allowed,
            confirmation_method=confirmation_method,
            response=response,
            warnings=warnings,
        )
        receipt_path = transition_dir / "meegle_transition_receipt.json"
        receipt_md = transition_dir / "meegle_transition_receipt.md"
        dump_json(receipt_path, to_plain_data(receipt))
        receipt_md.write_text(self.meegle_transition_gate.render_receipt_markdown(receipt), encoding="utf-8")
        return {
            "meegle_transition_receipt": str(receipt_path),
            "meegle_transition_receipt_md": str(receipt_md),
            "executed": receipt.executed,
            "confirmation_method": receipt.confirmation_method,
            "warnings": receipt.warnings,
            "confirm_token_hint": TRANSITION_CONFIRM_TOKEN,
        }

    def _load_local_context(
        self,
        project_key: str,
        work_item_id: str,
        title: str,
        requirement_file: str,
        doc_files: list[str] | None = None,
    ) -> WorkItemContext:
        requirement_path = Path(requirement_file)
        raw_item = self._read_requirement_payload(requirement_path, fallback_title=title)
        docs: list[RequirementDoc] = []
        for file_path in doc_files or []:
            path = Path(file_path)
            docs.append(
                RequirementDoc(
                    source="local-doc",
                    token_or_url=str(path),
                    title=path.stem,
                    content=path.read_text(encoding="utf-8"),
                )
            )
        return WorkItemContext(
            project_key=project_key,
            work_item_id=work_item_id,
            title=title,
            raw_item=raw_item,
            comments=[],
            doc_links=[],
            docs=docs,
        )

    def _resolve_memory_project_key(self, project_key: str, work_item_id: str | None = None) -> str:
        binding = self.store.load_project_memory_binding(project_key, work_item_id)
        if binding and binding.get("memory_project_key"):
            return str(binding["memory_project_key"])
        snapshot = self.store.load_session_snapshot(project_key)
        if snapshot and snapshot.memory_project_key:
            return snapshot.memory_project_key
        return project_key

    @staticmethod
    def _memory_project_key_from_brief(brief: DesignBrief, fallback_project_key: str) -> str:
        if brief.game_project_id and brief.game_project_id != "待确认":
            return str(brief.game_project_id)
        if brief.game_name and brief.game_name != "待确认":
            return slugify(brief.game_name, fallback=fallback_project_key)
        return fallback_project_key

    @staticmethod
    def _merge_artifact_paths(target: dict[str, str], source: dict, keys: list[str]) -> None:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str):
                target[key] = value

    @staticmethod
    def _read_requirement_payload(path: Path, fallback_title: str) -> dict:
        content = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
            return {"title": fallback_title, "description": content}
        return {"title": fallback_title, "description": content}

    def prepare_delivery_package(
        self,
        project_key: str,
        work_item_id: str,
        source_root: str,
        include_extensions: list[str] | None = None,
    ) -> dict:
        extensions = {item if item.startswith(".") else f".{item}" for item in include_extensions} if include_extensions else None
        package = self.local_files.prepare_delivery_package(
            project_key=project_key,
            work_item_id=work_item_id,
            source_root=Path(source_root),
            include_extensions=extensions,
        )
        self.store.save_delivery_preparation(project_key, package)
        stage_root = Path(package.staged_root)
        manifest_json = stage_root / "delivery_package.json"
        manifest_md = stage_root / "delivery_package.md"
        approval_ticket = stage_root / "approval_ticket.md"
        dump_json(manifest_json, to_plain_data(package))
        manifest_md.write_text(self._render_delivery_package(package), encoding="utf-8")
        approval_ticket.write_text(self._render_approval_ticket(package), encoding="utf-8")
        return {
            "staged_root": package.staged_root,
            "file_count": len(package.files),
            "warnings": package.warnings,
            "artifacts": [str(manifest_json), str(manifest_md), str(approval_ticket)],
        }

    def plan_automation(
        self,
        project_key: str,
        work_item_id: str,
        asset_root: str | None = None,
    ) -> dict:
        profile = self.store.load_project_profile(project_key)
        if not profile:
            profile = self.profile_manager.ensure_profile(project_key, same_category="general-game-design", title=project_key)
            self.store.save_project_profile(profile)
        asset_index = self.local_files.scan_assets(project_key, Path(asset_root)) if asset_root else self.store.load_asset_index(project_key)
        if asset_index and asset_root:
            self.store.save_asset_index(project_key, asset_index)
        delivery_package = self.store.load_delivery_preparation(project_key)
        plan = self.automation_planner.build_plan(project_key, work_item_id, profile, asset_index, delivery_package)
        plan_dir = self.paths.workspace / slugify(project_key, fallback="project") / f"{work_item_id}-automation"
        plan_dir.mkdir(parents=True, exist_ok=True)
        json_path = plan_dir / "automation_plan.json"
        md_path = plan_dir / "automation_plan.md"
        ps1_path = plan_dir / "automation_stub.ps1"
        jsx_path = plan_dir / "photoshop_export_dry_run.jsx"
        jsx_readme_path = plan_dir / "photoshop_script_readme.md"
        script_manifest_path = plan_dir / "photoshop_script_manifest.json"
        dump_json(json_path, to_plain_data(plan))
        md_path.write_text(self.automation_planner.render_markdown(plan), encoding="utf-8")
        ps1_path.write_text(self.automation_planner.render_powershell_stub(plan), encoding="utf-8")
        jsx_path.write_text(self.automation_planner.render_photoshop_jsx(plan), encoding="utf-8")
        jsx_readme_path.write_text(self.automation_planner.render_photoshop_readme(plan), encoding="utf-8")
        dump_json(
            script_manifest_path,
            {
                "project_key": project_key,
                "work_item_id": work_item_id,
                "source_psd": plan.source_psd,
                "stage_root": plan.stage_root,
                "default_mode": "dry-run",
                "requires_manual_photoshop_execution": True,
                "requires_designer_confirmation_before_export": True,
                "artifacts": {
                    "jsx": str(jsx_path),
                    "readme": str(jsx_readme_path),
                    "expected_layer_report": str(Path(plan.stage_root) / "photoshop_layer_report.md") if plan.stage_root else None,
                    "expected_slice_checklist": str(Path(plan.stage_root) / "photoshop_slice_checklist.md") if plan.stage_root else None,
                },
            },
        )
        return {
            "automation_plan": str(json_path),
            "automation_plan_md": str(md_path),
            "automation_stub_ps1": str(ps1_path),
            "photoshop_jsx": str(jsx_path),
            "photoshop_script_readme": str(jsx_readme_path),
            "photoshop_script_manifest": str(script_manifest_path),
            "warnings": plan.warnings,
        }

    def metacognition_audit(self, project_key: str) -> dict:
        style_card = self.store.load_style_card(project_key)
        profile = self.store.load_project_profile(project_key)
        snapshot = self.store.load_session_snapshot(project_key)
        asset_index = self.store.load_asset_index(project_key)
        delivery = self.store.load_delivery_preparation(project_key)
        recent_reports = self.store.list_review_reports(project_key, limit=5)
        recent_review_notes = [report.name for report in recent_reports]
        audit = self.metacognition.build(
            project_key=project_key,
            style_card=style_card,
            profile=profile,
            snapshot=snapshot,
            asset_index=asset_index,
            delivery=delivery,
            recent_review_notes=recent_review_notes,
        )
        audit_path = self.store.save_metacognition_audit(project_key, audit)
        markdown_path = audit_path.with_suffix(".md")
        markdown_path.write_text(self.metacognition.render_markdown(audit), encoding="utf-8")
        return {
            "metacognition_audit": str(audit_path),
            "metacognition_audit_md": str(markdown_path),
            "actions": audit.actions,
        }

    def create_transition_summary(self, project_key: str) -> dict:
        snapshot = self.store.load_session_snapshot(project_key)
        style_card = self.store.load_style_card(project_key)
        profile = self.store.load_project_profile(project_key)
        recent_reports = self.store.list_review_reports(project_key, limit=5)
        recent_review_notes = [report.name for report in recent_reports]
        capability_delta = self.metacognition._capability_delta(style_card, recent_review_notes)
        summary = self.transition_builder.build(
            project_key=project_key,
            snapshot=snapshot,
            style_card=style_card,
            profile=profile,
            capability_delta=capability_delta,
            recent_review_notes=recent_review_notes,
        )
        summary_path = self.store.save_transition_summary(project_key, summary)
        markdown_path = summary_path.with_suffix(".md")
        markdown_path.write_text(self.transition_builder.render_markdown(summary), encoding="utf-8")
        return {
            "transition_summary": str(summary_path),
            "transition_summary_md": str(markdown_path),
            "restart_instructions": summary.restart_instructions,
        }

    def create_learning_digest(self, project_key: str) -> dict:
        style_card = self.store.load_style_card(project_key)
        profile = self.store.load_project_profile(project_key)
        snapshot = self.store.load_session_snapshot(project_key)
        recent_reports = [self.store.load_review_report(path) for path in self.store.list_review_reports(project_key, limit=5)]
        digest = self.learning_digest_builder.build(
            project_key=project_key,
            style_card=style_card,
            profile=profile,
            snapshot=snapshot,
            recent_reviews=recent_reports,
        )
        digest_path = self.store.save_learning_digest(project_key, digest)
        markdown_path = digest_path.with_suffix(".md")
        markdown_path.write_text(self.learning_digest_builder.render_markdown(digest), encoding="utf-8")
        return {
            "learning_digest": str(digest_path),
            "learning_digest_md": str(markdown_path),
            "next_time_checklist": digest.next_time_checklist,
            "recommended_commands": digest.recommended_commands,
        }

    def curate_style_memory(self, project_key: str, apply: bool = False) -> dict:
        style_card = self.store.load_style_card(project_key)
        updated_card, report = self.style_memory_curator.build_report(style_card, apply=apply)
        if apply and updated_card:
            self.store.save_style_card(updated_card)
        report_path = self.store.save_style_memory_curation_report(project_key, report)
        markdown_path = report_path.with_suffix(".md")
        markdown_path.write_text(self.style_memory_curator.render_markdown(report), encoding="utf-8")
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
        report = self.style_learner.ingest_feedback(
            project_key=project_key,
            same_category=same_category,
            work_item_id=work_item_id,
            feedback=feedback,
            decision=decision,
            share_to_base=share_to_base,
        )
        report_path = self.store.save_review_report(project_key, report)
        markdown_path = report_path.with_suffix(".md")
        markdown_path.write_text(self._render_review_report(report), encoding="utf-8")
        return {"review_report": str(report_path), "review_report_md": str(markdown_path)}

    def ingest_style_reference(
        self,
        project_key: str,
        same_category: str,
        reference_file: str,
        share_to_base: bool = False,
    ) -> dict:
        report = self.style_reference_ingestor.ingest(
            project_key=project_key,
            same_category=same_category,
            reference_file=reference_file,
            share_to_base=share_to_base,
        )
        report_path = self.store.save_style_reference_report(project_key, report)
        markdown_path = report_path.with_suffix(".md")
        markdown_path.write_text(self.style_reference_ingestor.render_markdown(report), encoding="utf-8")
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
        snapshot = self.store.load_session_snapshot(project_key)
        if not snapshot:
            return {"project_key": project_key, "message": "No session snapshot found."}
        output_dir = Path(snapshot.output_dir)
        decision_payload = load_json(output_dir / "design_decision_record.json", None)
        style_alignment_payload = load_json(output_dir / "style_alignment_report.json", None)
        recent_reports = self.store.list_review_reports(project_key, limit=5)
        recent_review_notes = [report.name for report in recent_reports]
        report = self.session_resume_builder.build(
            project_key=project_key,
            snapshot=snapshot,
            style_card=self.store.load_style_card(project_key),
            profile=self.store.load_project_profile(project_key),
            recent_review_notes=recent_review_notes,
            decision_payload=decision_payload,
            style_alignment_payload=style_alignment_payload,
        )
        report_path = self.store.save_session_resume_report(project_key, report)
        report_md = report_path.with_suffix(".md")
        report_md.write_text(self.session_resume_builder.render_markdown(report), encoding="utf-8")
        return {
            "snapshot": to_plain_data(snapshot),
            "session_resume": str(report_path),
            "session_resume_md": str(report_md),
            "status": report.status,
            "active_work_item_id": report.active_work_item_id,
            "unresolved_questions": report.unresolved_questions,
            "next_commands": report.next_commands,
        }

    def _write_brief(self, output_dir: Path, brief: DesignBrief) -> None:
        dump_json(output_dir / "design_brief.json", to_plain_data(brief))
        markdown = "\n".join(
            [
                f"# 设计需求卡 - {brief.title}",
                "",
                f"- 工作项：`{brief.work_item_id}`",
                f"- 项目：`{brief.project_key or 'unknown'}`",
                f"- 游戏：{brief.game_name}",
                f"- 玩法理解：{brief.gameplay_summary}",
                f"- 风格方向：{brief.style_direction}",
                f"- 同品类底座：`{brief.same_category}`",
                f"- 目标：{brief.objective}",
                f"- 受众：{brief.target_audience}",
                f"- 平台：{brief.platform}",
                f"- 截止时间：{brief.deadline}",
                f"- 尺寸：{', '.join(brief.sizes) if brief.sizes else '待确认'}",
                f"- 交付物：{', '.join(brief.deliverables) if brief.deliverables else '待确认'}",
                "",
                "## 摘要",
                brief.summary,
                "",
                "## 平面需求汇总",
                brief.source_requirement_summary,
                "",
                "## 任务拆解",
                *(f"- {item}" for item in brief.task_breakdown or ["待确认"]),
                "",
                "## 参考图与素材线索",
                *(f"- {item}" for item in brief.reference_assets or ["待确认"]),
                "",
                "## 风险点",
                *(f"- {item}" for item in brief.risk_points),
                "",
                "## 待确认项",
                *(f"- {item}" for item in brief.missing_information),
            ]
        )
        (output_dir / "design_brief.md").write_text(markdown, encoding="utf-8")

    def _write_requirement_memory_report(self, output_dir: Path, report: RequirementMemoryReport) -> list[str]:
        json_path = output_dir / "requirement_memory_report.json"
        md_path = output_dir / "requirement_memory_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.requirement_memory.render_markdown(report), encoding="utf-8")
        return [str(json_path), str(md_path)]

    def _write_requirement_clarification(self, output_dir: Path, brief: DesignBrief) -> list[str]:
        report = self.requirement_clarifier.build(brief, brief.risk_points)
        json_path = output_dir / "requirement_clarification_report.json"
        md_path = output_dir / "requirement_clarification_report.md"
        comment_path = output_dir / "requirement_clarification_comment.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.requirement_clarifier.render_markdown(report), encoding="utf-8")
        comment_path.write_text(report.comment_draft, encoding="utf-8")
        return [str(json_path), str(md_path), str(comment_path)]

    def _write_style_card(self, output_dir: Path, style_card: StyleCard) -> None:
        dump_json(output_dir / "style_card.json", to_plain_data(style_card))
        rules = [f"- [{rule.level}] {rule.statement} | {rule.rationale}" for rule in style_card.rules] or ["- 暂无已沉淀规则"]
        markdown = "\n".join(
            [
                f"# 风格卡 - {style_card.project_key}",
                "",
                f"- 同品类底座：`{style_card.same_category}`",
                f"- 视觉关键词：{', '.join(style_card.visual_keywords) if style_card.visual_keywords else '待沉淀'}",
                "",
                "## 规则",
                *rules,
                "",
                "## 待确认项",
                *(f"- {item}" for item in style_card.open_questions),
            ]
        )
        (output_dir / "style_card.md").write_text(markdown, encoding="utf-8")

    def _write_creative_pack(self, output_dir: Path, creative_pack: CreativePack) -> None:
        dump_json(output_dir / "creative_pack.json", to_plain_data(creative_pack))
        prompt_positive = "\n".join(f"- {item}" for item in creative_pack.prompt_pack.positive)
        prompt_negative = "\n".join(f"- {item}" for item in creative_pack.prompt_pack.negative)
        references = "\n".join(f"- {item}" for item in creative_pack.references)
        composition = "\n".join(f"- {item}" for item in creative_pack.composition_suggestions)
        psd_guidance = "\n".join(f"- {item}" for item in creative_pack.psd_guidance)
        guidance_title = "## 横竖适配 / 剧情向交付建议" if "剧情向" in psd_guidance else "## PSD / 图层建议"
        uncertainties = "\n".join(f"- {item}" for item in creative_pack.uncertainties)
        markdown = "\n".join(
            [
                f"# 创作包 - {creative_pack.brief.title}",
                "",
                "## 需求摘要",
                creative_pack.brief.summary,
                "",
                "## 风格判断",
                references,
                "",
                "## 参考方向",
                "\n".join(f"- {item}" for item in creative_pack.references[:3]),
                "",
                "## 提示词包",
                "### Positive",
                prompt_positive,
                "### Negative",
                prompt_negative,
                "### Reference Groups",
                "\n".join(f"- {item}" for item in creative_pack.prompt_pack.reference_groups),
                "",
                "## 构图建议",
                composition,
                "",
                guidance_title,
                psd_guidance,
                "",
                "## 不确定项",
                uncertainties,
            ]
        )
        (output_dir / "creative_pack.md").write_text(markdown, encoding="utf-8")

    def _write_style_alignment_report(self, output_dir: Path, creative_pack: CreativePack) -> list[str]:
        source_artifacts = {
            "design_brief": str(output_dir / "design_brief.json") if (output_dir / "design_brief.json").exists() else None,
            "style_card": str(output_dir / "style_card.json") if (output_dir / "style_card.json").exists() else None,
            "creative_pack": str(output_dir / "creative_pack.json") if (output_dir / "creative_pack.json").exists() else None,
        }
        report = self.style_alignment.build(creative_pack, source_artifacts=source_artifacts)
        json_path = output_dir / "style_alignment_report.json"
        md_path = output_dir / "style_alignment_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.style_alignment.render_markdown(report), encoding="utf-8")
        return [str(json_path), str(md_path)]

    def _write_style_transfer_report(
        self,
        output_dir: Path,
        project_key: str,
        work_item_id: str,
        same_category: str,
        effective_style: StyleCard | None,
        profile: ProjectProfile | None,
        creative_pack_path: Path | None,
    ) -> list[str]:
        style_card_path = output_dir / "style_card.json"
        profile_path = self.paths.memory / "projects" / project_key / "project_profile.json"
        shared_base_path = self.paths.memory / "style_bases" / f"{same_category}.json"
        report = self.style_transfer.build(
            project_key=project_key,
            work_item_id=work_item_id,
            same_category=same_category,
            shared_base=self.store.load_style_base(same_category),
            effective_style=effective_style,
            profile=profile,
            source_artifacts={
                "style_base": str(shared_base_path) if shared_base_path.exists() else None,
                "style_card": str(style_card_path) if style_card_path.exists() else None,
                "project_profile": str(profile_path) if profile_path.exists() else None,
                "creative_pack": str(creative_pack_path) if creative_pack_path and creative_pack_path.exists() else None,
            },
        )
        json_path = output_dir / "style_transfer_report.json"
        md_path = output_dir / "style_transfer_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.style_transfer.render_markdown(report), encoding="utf-8")
        return [str(json_path), str(md_path)]

    def _write_design_decision_record(self, output_dir: Path, creative_pack: CreativePack) -> list[str]:
        source_artifacts = {
            "design_brief": str(output_dir / "design_brief.json") if (output_dir / "design_brief.json").exists() else None,
            "requirement_clarification": str(output_dir / "requirement_clarification_report.json") if (output_dir / "requirement_clarification_report.json").exists() else None,
            "style_card": str(output_dir / "style_card.json") if (output_dir / "style_card.json").exists() else None,
            "creative_pack": str(output_dir / "creative_pack.json") if (output_dir / "creative_pack.json").exists() else None,
            "style_alignment": str(output_dir / "style_alignment_report.json") if (output_dir / "style_alignment_report.json").exists() else None,
        }
        record = self.decision_recorder.build(
            creative_pack=creative_pack,
            clarification_payload=load_json(output_dir / "requirement_clarification_report.json", None),
            style_alignment_payload=load_json(output_dir / "style_alignment_report.json", None),
            source_artifacts=source_artifacts,
        )
        json_path = output_dir / "design_decision_record.json"
        md_path = output_dir / "design_decision_record.md"
        dump_json(json_path, to_plain_data(record))
        md_path.write_text(self.decision_recorder.render_markdown(record), encoding="utf-8")
        return [str(json_path), str(md_path)]

    def _write_image_production_batch(self, output_dir: Path, creative_pack: CreativePack, profile: ProjectProfile | None) -> list[str]:
        batch = self.image_production_planner.build(creative_pack, profile, str(output_dir))
        json_path = output_dir / "image_generation_batch.json"
        md_path = output_dir / "image_generation_batch.md"
        evaluation_path = output_dir / "candidate_evaluation.md"
        dump_json(json_path, to_plain_data(batch))
        md_path.write_text(self.image_production_planner.render_markdown(batch), encoding="utf-8")
        evaluation_path.write_text(self.image_production_planner.render_evaluation_sheet(batch), encoding="utf-8")
        return [str(json_path), str(md_path), str(evaluation_path)]

    def _write_candidate_style_drift_report(
        self,
        project_key: str,
        work_item_id: str,
        output_dir: Path,
        generation_results_path: Path,
        candidate_review_path: Path | None,
    ) -> list[str]:
        creative_pack_path = output_dir / "creative_pack.json"
        style_transfer_path = output_dir / "style_transfer_report.json"
        style_alignment_path = output_dir / "style_alignment_report.json"
        creative_pack = self._load_creative_pack_from_output_dir(output_dir) if creative_pack_path.exists() else None
        report = self.candidate_style_drift.build(
            project_key=project_key,
            work_item_id=work_item_id,
            generation_results=load_json(generation_results_path, None) if generation_results_path.exists() else None,
            creative_pack=creative_pack,
            style_transfer=load_json(style_transfer_path, None) if style_transfer_path.exists() else None,
            style_alignment=load_json(style_alignment_path, None) if style_alignment_path.exists() else None,
            candidate_review=load_json(candidate_review_path, None) if candidate_review_path and candidate_review_path.exists() else None,
            source_artifacts={
                "image_generation_results": str(generation_results_path) if generation_results_path.exists() else None,
                "creative_pack": str(creative_pack_path) if creative_pack_path.exists() else None,
                "style_transfer": str(style_transfer_path) if style_transfer_path.exists() else None,
                "style_alignment": str(style_alignment_path) if style_alignment_path.exists() else None,
                "candidate_review": str(candidate_review_path) if candidate_review_path and candidate_review_path.exists() else None,
            },
        )
        report_dir = output_dir / "generation_results"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "candidate_style_drift_report.json"
        md_path = report_dir / "candidate_style_drift_report.md"
        dump_json(json_path, to_plain_data(report))
        md_path.write_text(self.candidate_style_drift.render_markdown(report), encoding="utf-8")
        return [str(json_path), str(md_path)]

    def _write_candidate_comparison_matrix(
        self,
        project_key: str,
        work_item_id: str,
        output_dir: Path,
        generation_results_path: Path | None,
        candidate_style_drift_path: Path | None,
        candidate_review_path: Path | None,
    ) -> list[str]:
        image_batch_path = output_dir / "image_generation_batch.json"
        matrix = self.candidate_comparison_builder.build(
            project_key=project_key,
            work_item_id=work_item_id,
            image_batch=load_json(image_batch_path, None) if image_batch_path.exists() else None,
            generation_results=load_json(generation_results_path, None) if generation_results_path and generation_results_path.exists() else None,
            candidate_style_drift=load_json(candidate_style_drift_path, None) if candidate_style_drift_path and candidate_style_drift_path.exists() else None,
            candidate_review=load_json(candidate_review_path, None) if candidate_review_path and candidate_review_path.exists() else None,
            source_artifacts={
                "image_generation_batch": str(image_batch_path) if image_batch_path.exists() else None,
                "image_generation_results": str(generation_results_path) if generation_results_path and generation_results_path.exists() else None,
                "candidate_style_drift": str(candidate_style_drift_path) if candidate_style_drift_path and candidate_style_drift_path.exists() else None,
                "candidate_review": str(candidate_review_path) if candidate_review_path and candidate_review_path.exists() else None,
            },
        )
        report_dir = output_dir / "candidate_comparison"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "candidate_comparison_matrix.json"
        md_path = report_dir / "candidate_comparison_matrix.md"
        dump_json(json_path, to_plain_data(matrix))
        md_path.write_text(self.candidate_comparison_builder.render_markdown(matrix), encoding="utf-8")
        return [str(json_path), str(md_path)]

    def _write_delivery_manifest(self, output_dir: Path, creative_pack: CreativePack) -> None:
        manifest = creative_pack.delivery_manifest
        dump_json(output_dir / "delivery_manifest.json", to_plain_data(manifest))
        items = "\n".join(
            f"- {item.name} | {item.size} | {item.format_hint} | {item.notes}"
            for item in manifest.export_items
        )
        markdown = "\n".join(
            [
                f"# 交付清单 - {manifest.work_item_id}",
                "",
                "## 命名规则",
                *(f"- {item}" for item in manifest.naming_rules),
                "",
                "## 导出项",
                items,
                "",
                "## 切图说明",
                *(f"- {item}" for item in manifest.slicing_notes),
                "",
                f"## 确认要求\n- 正式导出前需要人工确认：{'是' if manifest.requires_confirmation else '否'}",
            ]
        )
        (output_dir / "delivery_manifest.md").write_text(markdown, encoding="utf-8")

    def _load_creative_pack_from_output_dir(self, output_dir: Path) -> CreativePack:
        creative_pack_path = output_dir / "creative_pack.json"
        if creative_pack_path.exists():
            return self._decode_creative_pack(load_json(creative_pack_path, {}))
        brief_payload = load_json(output_dir / "design_brief.json", None)
        style_payload = load_json(output_dir / "style_card.json", None)
        if not brief_payload or not style_payload:
            raise FileNotFoundError(f"Cannot rebuild creative pack from output dir: {output_dir}")
        brief = DesignBrief(**brief_payload)
        style_card = self._decode_style_card(style_payload)
        profile = self.store.load_project_profile(brief.project_key or "unknown-project")
        return self.pack_builder.build(brief, style_card, profile)

    def _decode_creative_pack(self, payload: dict) -> CreativePack:
        brief = DesignBrief(**payload["brief"])
        style_card = self._decode_style_card(payload["style_card"])
        manifest_payload = payload["delivery_manifest"]
        manifest = DeliveryManifest(
            project_key=manifest_payload["project_key"],
            work_item_id=manifest_payload["work_item_id"],
            naming_rules=manifest_payload.get("naming_rules", []),
            export_items=[DeliveryItem(**item) for item in manifest_payload.get("export_items", [])],
            slicing_notes=manifest_payload.get("slicing_notes", []),
            requires_confirmation=manifest_payload.get("requires_confirmation", True),
        )
        return CreativePack(
            brief=brief,
            style_card=style_card,
            references=payload.get("references", []),
            prompt_pack=PromptPack(**payload.get("prompt_pack", {"positive": [], "negative": [], "reference_groups": []})),
            composition_suggestions=payload.get("composition_suggestions", []),
            psd_guidance=payload.get("psd_guidance", []),
            uncertainties=payload.get("uncertainties", []),
            delivery_manifest=manifest,
        )

    @staticmethod
    def _decode_style_card(payload: dict) -> StyleCard:
        data = dict(payload)
        data["rules"] = [StyleRule(**rule) for rule in payload.get("rules", [])]
        return StyleCard(**data)

    @staticmethod
    def _candidate_batch_path(snapshot) -> Path | None:
        if not snapshot:
            return None
        output_dir = Path(snapshot.output_dir)
        path = output_dir / "image_generation_batch.json"
        return path if path.exists() else None

    @staticmethod
    def _generation_queue_path(snapshot) -> Path | None:
        if not snapshot:
            return None
        path = Path(snapshot.output_dir) / "generation_jobs" / "image_generation_jobs.json"
        return path if path.exists() else None

    def _generation_result_dir(self, snapshot, project_key: str, work_item_id: str) -> Path:
        if snapshot:
            return Path(snapshot.output_dir) / "generation_results"
        return self.paths.workspace / slugify(project_key, fallback="project") / f"{work_item_id}-generation-results"

    def _generation_results_path(self, snapshot, project_key: str, work_item_id: str) -> Path | None:
        result_dir = self._generation_result_dir(snapshot, project_key, work_item_id)
        path = result_dir / "image_generation_results.json"
        return path if path.exists() else None

    def _psd_handoff_plan_path(self, snapshot, project_key: str, work_item_id: str) -> Path | None:
        if snapshot:
            path = Path(snapshot.output_dir) / "psd_handoff" / "psd_handoff_plan.json"
        else:
            path = self.paths.workspace / slugify(project_key, fallback="project") / f"{work_item_id}-psd_handoff" / "psd_handoff_plan.json"
        return path if path.exists() else None

    def _psd_slice_spec_report_path(self, snapshot) -> Path | None:
        if not snapshot:
            return None
        path = Path(snapshot.output_dir) / "psd_handoff" / "psd_slice_spec_report.json"
        if path.exists():
            return path
        return self._latest_snapshot_artifact(snapshot, "psd_slice_spec_report.json")

    def _candidate_style_drift_report_path(self, snapshot) -> Path | None:
        if not snapshot:
            return None
        path = Path(snapshot.output_dir) / "generation_results" / "candidate_style_drift_report.json"
        if path.exists():
            return path
        return self._latest_snapshot_artifact(snapshot, "candidate_style_drift_report.json")

    def _candidate_comparison_matrix_path(self, snapshot) -> Path | None:
        if not snapshot:
            return None
        path = Path(snapshot.output_dir) / "candidate_comparison" / "candidate_comparison_matrix.json"
        if path.exists():
            return path
        return self._latest_snapshot_artifact(snapshot, "candidate_comparison_matrix.json")

    def _candidate_review_path(self, project_key: str, work_item_id: str) -> Path | None:
        path = self.paths.memory / "reviews" / project_key / f"{work_item_id}-candidate_review.json"
        return path if path.exists() else None

    @staticmethod
    def _latest_snapshot_artifact(snapshot, filename: str) -> Path | None:
        if not snapshot:
            return None
        for artifact in reversed(snapshot.last_artifacts):
            path = Path(artifact)
            if path.name == filename and path.exists():
                return path
        return None

    def _meegle_writeback_dir(self, snapshot, project_key: str, work_item_id: str, draft_dir: str | None) -> Path:
        if draft_dir:
            return Path(draft_dir)
        if snapshot:
            return Path(snapshot.output_dir) / "meegle_writeback"
        return self.paths.workspace / slugify(project_key, fallback="project") / f"{work_item_id}-meegle-writeback"

    @staticmethod
    def _timestamp_for_path() -> str:
        from datetime import datetime

        return datetime.now().strftime("%Y%m%d-%H%M%S")

    @staticmethod
    def _render_review_report(report: ReviewReport) -> str:
        def render_section(title: str, items: list) -> list[str]:
            lines = [f"## {title}"]
            if not items:
                lines.append("- 无")
                return lines
            lines.extend(f"- [{item.level}] {item.statement} | {item.rationale}" for item in items)
            return lines

        lines = [
            f"# 评审回写 - {report.project_key}",
            "",
            f"- 工作项：`{report.work_item_id or 'general'}`",
            f"- 决策：`{report.decision}`",
            "",
            "## 原始反馈",
            report.feedback,
            "",
        ]
        lines.extend(render_section("采纳", report.accepted))
        lines.append("")
        lines.extend(render_section("驳回", report.rejected))
        lines.append("")
        lines.extend(render_section("待验证", report.pending))
        lines.append("")
        lines.append("## 下一步")
        lines.extend(f"- {item}" for item in report.next_actions)
        return "\n".join(lines)

    @staticmethod
    def _render_asset_index(asset_index) -> str:
        lines = [
            f"# 资产索引 - {asset_index.project_key}",
            "",
            f"- 资产根目录：`{asset_index.source_root}`",
            f"- 扫描时间：`{asset_index.scanned_at}`",
            f"- 资产数量：`{len(asset_index.asset_cards)}`",
            "",
            "## 资产卡",
        ]
        if not asset_index.asset_cards:
            lines.append("- 未扫描到资产")
        else:
            for card in asset_index.asset_cards:
                lines.append(
                    f"- `{card.relative_path}` | {card.extension} | role={card.role_guess} | tags={', '.join(card.tags)} | size={card.size_bytes}"
                )
        lines.extend(["", "## 警告", *(f"- {item}" for item in asset_index.warnings or ["无"])])
        return "\n".join(lines)

    @staticmethod
    def _render_delivery_package(package) -> str:
        lines = [
            f"# 交付 staging 包 - {package.work_item_id}",
            "",
            f"- 项目：`{package.project_key}`",
            f"- 来源目录：`{package.source_root}`",
            f"- staging 目录：`{package.staged_root}`",
            f"- 创建时间：`{package.created_at}`",
            f"- 文件数量：`{len(package.files)}`",
            "",
            "## 已暂存文件",
        ]
        if not package.files:
            lines.append("- 无")
        else:
            lines.extend(
                f"- `{item.source_relative_path}` -> `{item.staged_relative_path}` | role={item.role_guess} | size={item.size_bytes}"
                for item in package.files
            )
        lines.extend(["", "## 风险与提醒", *(f"- {item}" for item in package.warnings or ["无"])])
        lines.extend(["", "## 确认清单", *(f"- {item}" for item in package.confirmation_checklist)])
        return "\n".join(lines)

    @staticmethod
    def _render_approval_ticket(package) -> str:
        return "\n".join(
            [
                f"# 交付确认单 - {package.work_item_id}",
                "",
                f"- 项目：`{package.project_key}`",
                f"- staging 目录：`{package.staged_root}`",
                f"- 文件数量：`{len(package.files)}`",
                "",
                "## 说明",
                "- 本次仅生成预交付 staging 包，未覆盖任何正式文件。",
                "- 对外发送、正式交付、覆盖已有文件前，必须由设计师人工确认。",
                "",
                "## 需确认项目",
                *(f"- [ ] {item}" for item in package.confirmation_checklist),
                "",
                "## 结果",
                "- [ ] 允许正式交付",
                "- [ ] 退回继续修正",
            ]
        )

    @staticmethod
    def _render_generation_approval_ticket(queue) -> str:
        return "\n".join(
            [
                f"# 图像生成确认单 - {queue.work_item_id}",
                "",
                f"- 项目：`{queue.project_key}`",
                f"- 任务数：`{len(queue.jobs)}`",
                f"- 执行模式：`{queue.execution_mode}`",
                "",
                "## 安全说明",
                "- 当前仅生成待确认任务队列，未调用出图工具，未消耗算力。",
                "- 执行 Pixpark 或其他生成工具前，需要设计师确认。",
                "- 生成结果只能写入 workspace staging，不自动对外发送或覆盖正式文件。",
                "",
                "## 待确认任务",
                *(f"- [ ] {job.variant_id} {job.title} -> `{job.output_dir}`" for job in queue.jobs),
                "",
                "## 结果",
                "- [ ] 允许执行选中任务",
                "- [ ] 退回修改提示词或参考图",
            ]
        )

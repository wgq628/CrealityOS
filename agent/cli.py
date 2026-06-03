from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from agent.app import DesignCopilotApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="design-copilot", description="Designer copilot for Feishu project workflows.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize runtime directories.")

    doctor = subparsers.add_parser("doctor", help="Check local runtime, optional project session, and external CLI availability.")
    doctor.add_argument("--project-key")

    cockpit = subparsers.add_parser("cockpit", help="Create the designer cockpit status entrypoint from local artifacts.")
    cockpit.add_argument("--project-key", required=True)
    cockpit.add_argument("--work-item-id")
    cockpit.add_argument("--output-dir")

    dashboard = subparsers.add_parser("dashboard", help="Create a static HTML designer dashboard from local JSON artifacts.")
    dashboard.add_argument("--project-key", required=True)
    dashboard.add_argument("--work-item-id")
    dashboard.add_argument("--output-dir")

    serve = subparsers.add_parser("serve", help="Run the local CrealityOS visual console.")
    serve.add_argument("--project-key")
    serve.add_argument("--work-item-id")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)

    process_feishu = subparsers.add_parser(
        "process-feishu-requirement",
        help="Designer-first flow: read a Meegle work item and create a slim design workpack.",
    )
    process_feishu.add_argument("--project-key", required=True)
    process_feishu.add_argument("--work-item-id", required=True)
    process_feishu.add_argument("--asset-root")
    process_feishu.add_argument("--output-mode", choices=("designer", "debug"), default="designer")

    process_local = subparsers.add_parser(
        "process-local-requirement",
        help="Designer-first flow: read a local requirement and create a slim design workpack.",
    )
    process_local.add_argument("--project-key", required=True)
    process_local.add_argument("--work-item-id", required=True)
    process_local.add_argument("--title", required=True)
    process_local.add_argument("--requirement-file", required=True)
    process_local.add_argument("--category")
    process_local.add_argument("--doc-file", action="append", dest="doc_files")
    process_local.add_argument("--asset-root")
    process_local.add_argument("--output-mode", choices=("designer", "debug"), default="designer")

    image_direction = subparsers.add_parser(
        "prepare-image-direction",
        help="Create or refresh the designer-facing Chinese prompt sheet for first full-image generation.",
    )
    image_direction.add_argument("--project-key", required=True)
    image_direction.add_argument("--work-item-id")

    delivery_review = subparsers.add_parser(
        "prepare-delivery-review",
        help="Create a slim designer-facing delivery checklist without a long debug report.",
    )
    delivery_review.add_argument("--project-key", required=True)
    delivery_review.add_argument("--work-item-id")

    fetch_todos = subparsers.add_parser("fetch-todos", help="Fetch Meegle todos.")
    fetch_todos.add_argument("--action", default="todo")
    fetch_todos.add_argument("--asset-key")
    fetch_todos.add_argument("--max-pages", type=int, default=1)

    screen_todos = subparsers.add_parser("screen-todos", help="Screen Meegle todos for likely design requirements.")
    screen_todos.add_argument("--action", default="todo")
    screen_todos.add_argument("--asset-key")
    screen_todos.add_argument("--max-pages", type=int, default=1)

    workitem = subparsers.add_parser("fetch-workitem-context", help="Fetch a work item with doc links.")
    workitem.add_argument("--project-key", required=True)
    workitem.add_argument("--work-item-id", required=True)

    docs = subparsers.add_parser("fetch-requirement-docs", help="Fetch linked Feishu docs for a work item.")
    docs.add_argument("--project-key", required=True)
    docs.add_argument("--work-item-id", required=True)

    init_profile = subparsers.add_parser("init-project-profile", help="Create or refresh a project profile scaffold.")
    init_profile.add_argument("--project-key", required=True)
    init_profile.add_argument("--category", required=True)
    init_profile.add_argument("--display-name")

    update_profile = subparsers.add_parser(
        "update-project-profile",
        help="Merge or replace a project profile from JSON/text calibration data.",
    )
    update_profile.add_argument("--project-key", required=True)
    update_profile.add_argument("--category", required=True)
    update_profile.add_argument("--profile-file", required=True)
    update_profile.add_argument("--replace", action="store_true")

    project_skill = subparsers.add_parser(
        "generate-project-skill",
        help="Generate a local Codex SKILL.md from learned project style memory.",
    )
    project_skill.add_argument("--project-key", required=True)
    project_skill.add_argument("--output-dir")

    calibrate_fields = subparsers.add_parser(
        "calibrate-field-mapping",
        help="Infer and persist project-specific work item field mappings from a sample JSON/Markdown export.",
    )
    calibrate_fields.add_argument("--project-key", required=True)
    calibrate_fields.add_argument("--sample-file", required=True)

    diagnose_intake = subparsers.add_parser(
        "diagnose-workitem-intake",
        help="Diagnose Meegle/local work item fields before building a creative pack.",
    )
    diagnose_intake.add_argument("--project-key", required=True)
    diagnose_intake.add_argument("--work-item-id")
    diagnose_intake.add_argument("--sample-file")
    diagnose_intake.add_argument("--title")

    scan_assets = subparsers.add_parser("scan-assets", help="Index local PSD and export assets for a project.")
    scan_assets.add_argument("--project-key", required=True)
    scan_assets.add_argument("--asset-root", required=True)

    build_pack = subparsers.add_parser("build-creative-pack", help="Build the main creative pack artifacts.")
    build_pack.add_argument("--project-key", required=True)
    build_pack.add_argument("--work-item-id", required=True)
    build_pack.add_argument("--output-mode", choices=("designer", "debug"), default="designer")

    clarification = subparsers.add_parser(
        "create-requirement-clarification-report",
        help="Regenerate the local requirement clarification report and Feishu comment draft from a design brief.",
    )
    clarification.add_argument("--project-key", required=True)
    clarification.add_argument("--work-item-id")
    clarification.add_argument("--output-dir", help="Run output directory containing design_brief.json. Defaults to latest session.")

    requirement_change = subparsers.add_parser(
        "create-requirement-change-report",
        help="Compare a refreshed requirement against the current design brief without rebuilding artifacts.",
    )
    requirement_change.add_argument("--project-key", required=True)
    requirement_change.add_argument("--work-item-id")
    requirement_change.add_argument("--requirement-file", help="Local refreshed requirement file. If omitted, fetches the live work item.")
    requirement_change.add_argument("--category", help="Override same-category base for the refreshed requirement.")
    requirement_change.add_argument("--title", help="Title to use when reading a local refreshed requirement file.")
    requirement_change.add_argument("--doc-file", action="append", dest="doc_files")
    requirement_change.add_argument("--output-dir", help="Run output directory containing the old design_brief.json. Defaults to latest session.")

    style_alignment = subparsers.add_parser(
        "create-style-alignment-report",
        help="Regenerate the local style alignment gate from a creative pack.",
    )
    style_alignment.add_argument("--project-key", required=True)
    style_alignment.add_argument("--work-item-id")
    style_alignment.add_argument("--output-dir", help="Run output directory containing creative_pack.json. Defaults to latest session.")

    style_transfer = subparsers.add_parser(
        "create-style-transfer-report",
        help="Explain which same-category style rules can transfer and which project overrides block them.",
    )
    style_transfer.add_argument("--project-key", required=True)
    style_transfer.add_argument("--work-item-id")
    style_transfer.add_argument("--output-dir", help="Run output directory containing creative_pack.json. Defaults to latest session.")

    decision_record = subparsers.add_parser(
        "create-design-decision-record",
        help="Regenerate the local decision ledger explaining why the creative pack made its choices.",
    )
    decision_record.add_argument("--project-key", required=True)
    decision_record.add_argument("--work-item-id")
    decision_record.add_argument("--output-dir", help="Run output directory containing creative_pack.json. Defaults to latest session.")

    image_batch = subparsers.add_parser(
        "create-image-production-batch",
        help="Create multi-variant image generation prompts and a candidate evaluation sheet from the latest creative pack.",
    )
    image_batch.add_argument("--project-key", required=True)
    image_batch.add_argument("--work-item-id")

    candidate_review = subparsers.add_parser(
        "ingest-candidate-review",
        help="Ingest V01/V02/V03 candidate image review scores and turn them into reusable style learning.",
    )
    candidate_review.add_argument("--project-key", required=True)
    candidate_review.add_argument("--category", required=True)
    candidate_review.add_argument("--review-file", required=True)
    candidate_review.add_argument("--work-item-id")
    candidate_review.add_argument("--share-to-base", action="store_true")

    style_reference = subparsers.add_parser(
        "ingest-style-reference",
        help="Ingest local reference images or URLs into project style memory.",
    )
    style_reference.add_argument("--project-key", required=True)
    style_reference.add_argument("--category", required=True)
    style_reference.add_argument("--reference-file", required=True)
    style_reference.add_argument("--share-to-base", action="store_true")

    generation_jobs = subparsers.add_parser(
        "create-image-generation-jobs",
        help="Create confirmed-before-execution Pixpark job payloads from image production variants.",
    )
    generation_jobs.add_argument("--project-key", required=True)
    generation_jobs.add_argument("--work-item-id")
    generation_jobs.add_argument("--variant", action="append", dest="variants", help="Variant id such as V01. Repeat to select multiple.")

    execution_package = subparsers.add_parser(
        "prepare-image-execution-package",
        help="Prepare per-job Pixpark payload files, a runbook, and a results template without executing generation.",
    )
    execution_package.add_argument("--project-key", required=True)
    execution_package.add_argument("--work-item-id")

    register_results = subparsers.add_parser(
        "register-image-results",
        help="Register generated image paths or URLs back to generation jobs and create gallery/review artifacts.",
    )
    register_results.add_argument("--project-key", required=True)
    register_results.add_argument("--results-file", required=True)
    register_results.add_argument("--work-item-id")

    drift_report = subparsers.add_parser(
        "create-candidate-style-drift-report",
        help="Create a local style drift warning report for registered generated candidates.",
    )
    drift_report.add_argument("--project-key", required=True)
    drift_report.add_argument("--work-item-id")

    comparison_matrix = subparsers.add_parser(
        "create-candidate-comparison-matrix",
        help="Create a local comparison matrix across generated candidate variants.",
    )
    comparison_matrix.add_argument("--project-key", required=True)
    comparison_matrix.add_argument("--work-item-id")

    psd_handoff = subparsers.add_parser(
        "create-psd-handoff-plan",
        help="Create PSD reconstruction, layer map, and slicing checklist from registered delivery candidates.",
    )
    psd_handoff.add_argument("--project-key", required=True)
    psd_handoff.add_argument("--work-item-id")
    psd_handoff.add_argument("--asset", action="append", dest="selected_assets", help="Asset id, variant id, or URI to include. Repeat to select multiple.")

    psd_handoff_package = subparsers.add_parser(
        "prepare-psd-handoff-package",
        help="Stage PSD handoff candidate assets and confirmation docs into a safe workspace delivery folder.",
    )
    psd_handoff_package.add_argument("--project-key", required=True)
    psd_handoff_package.add_argument("--work-item-id")

    psd_slice_spec = subparsers.add_parser(
        "create-psd-slice-spec-report",
        help="Create a local PSD layer, slicing, naming, and staging spec check without opening Photoshop.",
    )
    psd_slice_spec.add_argument("--project-key", required=True)
    psd_slice_spec.add_argument("--work-item-id")

    delivery_readiness = subparsers.add_parser(
        "create-delivery-readiness-report",
        help="Create a pre-delivery quality gate report without publishing or overwriting files.",
    )
    delivery_readiness.add_argument("--project-key", required=True)
    delivery_readiness.add_argument("--work-item-id")

    review_packet = subparsers.add_parser(
        "create-designer-review-packet",
        help="Create one designer-facing review packet that links creative, image, PSD, delivery, and learning artifacts.",
    )
    review_packet.add_argument("--project-key", required=True)
    review_packet.add_argument("--work-item-id")

    workflow_plan = subparsers.add_parser(
        "create-design-workflow-plan",
        help="Create a local step-by-step workflow plan from current design artifacts.",
    )
    workflow_plan.add_argument("--project-key", required=True)
    workflow_plan.add_argument("--work-item-id")

    writeback_draft = subparsers.add_parser(
        "create-meegle-writeback-draft",
        help="Create a reviewable Meegle comment draft and approval ticket from the latest design artifacts.",
    )
    writeback_draft.add_argument("--project-key", required=True)
    writeback_draft.add_argument("--work-item-id")

    publish_writeback = subparsers.add_parser(
        "publish-meegle-writeback",
        help="Publish a reviewed Meegle writeback comment only with explicit confirmation; dry-run by default.",
    )
    publish_writeback.add_argument("--project-key", required=True)
    publish_writeback.add_argument("--work-item-id")
    publish_writeback.add_argument("--draft-dir")
    publish_writeback.add_argument("--execute", action="store_true")
    publish_writeback.add_argument("--confirm-token")
    publish_writeback.add_argument("--approval-file")

    transition_draft = subparsers.add_parser(
        "create-meegle-transition-draft",
        help="Create a reviewable Meegle workflow transition draft and approval ticket.",
    )
    transition_draft.add_argument("--project-key", required=True)
    transition_draft.add_argument("--work-item-id", required=True)
    transition_draft.add_argument("--action", choices=("confirm", "rollback"), default="confirm")
    transition_draft.add_argument("--node-id")
    transition_draft.add_argument("--node", action="append", dest="node_names")
    transition_draft.add_argument("--rollback-reason")

    publish_transition = subparsers.add_parser(
        "publish-meegle-transition",
        help="Execute a reviewed Meegle workflow transition only with explicit confirmation; dry-run by default.",
    )
    publish_transition.add_argument("--project-key", required=True)
    publish_transition.add_argument("--work-item-id", required=True)
    publish_transition.add_argument("--draft-dir")
    publish_transition.add_argument("--execute", action="store_true")
    publish_transition.add_argument("--confirm-token")
    publish_transition.add_argument("--approval-file")

    feishu_cycle = subparsers.add_parser(
        "run-feishu-design-cycle",
        help="Run the live Feishu work item -> pack -> audit -> transition loop, with optional asset steps.",
    )
    feishu_cycle.add_argument("--project-key", required=True)
    feishu_cycle.add_argument("--work-item-id", required=True)
    feishu_cycle.add_argument("--asset-root")
    feishu_cycle.add_argument("--full", action="store_true", help="Run the full audit/learning/readiness/review loop.")

    build_local_pack = subparsers.add_parser(
        "build-local-creative-pack",
        help="Build a creative pack from a local requirement file without live Feishu access.",
    )
    build_local_pack.add_argument("--project-key", required=True)
    build_local_pack.add_argument("--work-item-id", required=True)
    build_local_pack.add_argument("--title", required=True)
    build_local_pack.add_argument("--requirement-file", required=True)
    build_local_pack.add_argument("--category")
    build_local_pack.add_argument("--doc-file", action="append", dest="doc_files")
    build_local_pack.add_argument("--output-mode", choices=("designer", "debug"), default="designer")

    prepare_delivery = subparsers.add_parser(
        "prepare-delivery-package",
        help="Stage delivery files into a safe workspace folder without overwriting formal files.",
    )
    prepare_delivery.add_argument("--project-key", required=True)
    prepare_delivery.add_argument("--work-item-id", required=True)
    prepare_delivery.add_argument("--source-root", required=True)
    prepare_delivery.add_argument("--include-ext", action="append", dest="include_ext")

    plan_automation = subparsers.add_parser(
        "plan-automation",
        help="Generate a safe Photoshop/export automation action plan and PowerShell dry-run stub.",
    )
    plan_automation.add_argument("--project-key", required=True)
    plan_automation.add_argument("--work-item-id", required=True)
    plan_automation.add_argument("--asset-root")

    audit = subparsers.add_parser(
        "metacognition-audit",
        help="Audit project memory, style certainty, and delivery readiness.",
    )
    audit.add_argument("--project-key", required=True)

    transition = subparsers.add_parser(
        "create-transition-summary",
        help="Generate a cross-session recovery summary for the project.",
    )
    transition.add_argument("--project-key", required=True)

    learning_digest = subparsers.add_parser(
        "create-learning-digest",
        help="Summarize reusable project learning into next-time defaults, avoid rules, and K3 checks.",
    )
    learning_digest.add_argument("--project-key", required=True)

    curate_style = subparsers.add_parser(
        "curate-style-memory",
        help="Create style memory governance suggestions; use --apply to safely promote repeated K3 evidence.",
    )
    curate_style.add_argument("--project-key", required=True)
    curate_style.add_argument("--apply", action="store_true")

    local_cycle = subparsers.add_parser(
        "run-local-design-cycle",
        help="Run the local requirement -> pack -> audit -> transition loop, with optional asset steps.",
    )
    local_cycle.add_argument("--project-key", required=True)
    local_cycle.add_argument("--work-item-id", required=True)
    local_cycle.add_argument("--title", required=True)
    local_cycle.add_argument("--requirement-file", required=True)
    local_cycle.add_argument("--category")
    local_cycle.add_argument("--doc-file", action="append", dest="doc_files")
    local_cycle.add_argument("--asset-root")
    local_cycle.add_argument("--full", action="store_true", help="Run the full audit/learning/readiness/review loop.")

    ingest = subparsers.add_parser("ingest-feedback", help="Write designer feedback back into style memory.")
    ingest.add_argument("--project-key", required=True)
    ingest.add_argument("--category", required=True)
    ingest.add_argument("--decision", choices=("approved", "rejected", "revise"), required=True)
    ingest.add_argument("--work-item-id")
    ingest.add_argument("--feedback")
    ingest.add_argument("--feedback-file")
    ingest.add_argument("--share-to-base", action="store_true")

    resume = subparsers.add_parser("resume-session", help="Resume latest session snapshot for a project.")
    resume.add_argument("--project-key", required=True)

    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args()
    app = DesignCopilotApp(Path(args.root).resolve())

    if args.command == "init":
        output = app.init_workspace()
    elif args.command == "doctor":
        output = app.doctor(project_key=args.project_key)
    elif args.command == "cockpit":
        output = app.cockpit(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            output_dir=args.output_dir,
        )
    elif args.command == "dashboard":
        output = app.dashboard(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            output_dir=args.output_dir,
        )
    elif args.command == "serve":
        from agent.console_server import run_console_server

        run_console_server(
            root=Path(args.root).resolve(),
            host=args.host,
            port=args.port,
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
        return
    elif args.command == "fetch-todos":
        output = app.fetch_todos(action=args.action, asset_key=args.asset_key, max_pages=args.max_pages)
    elif args.command == "screen-todos":
        output = app.screen_todos(action=args.action, asset_key=args.asset_key, max_pages=args.max_pages)
    elif args.command == "fetch-workitem-context":
        output = app.fetch_workitem_context(project_key=args.project_key, work_item_id=args.work_item_id)
    elif args.command == "fetch-requirement-docs":
        output = app.fetch_requirement_docs(project_key=args.project_key, work_item_id=args.work_item_id)
    elif args.command == "init-project-profile":
        output = app.init_project_profile(
            project_key=args.project_key,
            same_category=args.category,
            display_name=args.display_name,
        )
    elif args.command == "update-project-profile":
        output = app.update_project_profile(
            project_key=args.project_key,
            same_category=args.category,
            profile_file=args.profile_file,
            replace=args.replace,
        )
    elif args.command == "generate-project-skill":
        output = app.generate_project_skill(project_key=args.project_key, output_dir=args.output_dir)
    elif args.command == "calibrate-field-mapping":
        output = app.calibrate_field_mapping(project_key=args.project_key, sample_file=args.sample_file)
    elif args.command == "diagnose-workitem-intake":
        output = app.diagnose_workitem_intake(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            sample_file=args.sample_file,
            title=args.title,
        )
    elif args.command == "scan-assets":
        output = app.scan_assets(project_key=args.project_key, asset_root=args.asset_root)
    elif args.command == "process-feishu-requirement":
        output = app.process_feishu_requirement(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            asset_root=args.asset_root,
            output_mode=args.output_mode,
        )
    elif args.command == "process-local-requirement":
        output = app.process_local_requirement(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            title=args.title,
            requirement_file=args.requirement_file,
            same_category=args.category,
            doc_files=args.doc_files,
            asset_root=args.asset_root,
            output_mode=args.output_mode,
        )
    elif args.command == "prepare-image-direction":
        output = app.prepare_image_direction(project_key=args.project_key, work_item_id=args.work_item_id)
    elif args.command == "prepare-delivery-review":
        output = app.prepare_delivery_review(project_key=args.project_key, work_item_id=args.work_item_id)
    elif args.command == "build-creative-pack":
        output = app.build_creative_pack(project_key=args.project_key, work_item_id=args.work_item_id, output_mode=args.output_mode)
    elif args.command == "create-requirement-clarification-report":
        output = app.create_requirement_clarification_report(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            output_dir=args.output_dir,
        )
    elif args.command == "create-requirement-change-report":
        output = app.create_requirement_change_report(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            requirement_file=args.requirement_file,
            same_category=args.category,
            title=args.title,
            doc_files=args.doc_files,
            output_dir=args.output_dir,
        )
    elif args.command == "create-style-alignment-report":
        output = app.create_style_alignment_report(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            output_dir=args.output_dir,
        )
    elif args.command == "create-style-transfer-report":
        output = app.create_style_transfer_report(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            output_dir=args.output_dir,
        )
    elif args.command == "create-design-decision-record":
        output = app.create_design_decision_record(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            output_dir=args.output_dir,
        )
    elif args.command == "create-image-production-batch":
        output = app.create_image_production_batch(project_key=args.project_key, work_item_id=args.work_item_id)
    elif args.command == "ingest-candidate-review":
        output = app.ingest_candidate_review(
            project_key=args.project_key,
            same_category=args.category,
            review_file=args.review_file,
            work_item_id=args.work_item_id,
            share_to_base=args.share_to_base,
        )
    elif args.command == "ingest-style-reference":
        output = app.ingest_style_reference(
            project_key=args.project_key,
            same_category=args.category,
            reference_file=args.reference_file,
            share_to_base=args.share_to_base,
        )
    elif args.command == "create-image-generation-jobs":
        output = app.create_image_generation_jobs(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            variants=args.variants,
        )
    elif args.command == "prepare-image-execution-package":
        output = app.prepare_image_execution_package(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "register-image-results":
        output = app.register_image_results(
            project_key=args.project_key,
            results_file=args.results_file,
            work_item_id=args.work_item_id,
        )
    elif args.command == "create-candidate-style-drift-report":
        output = app.create_candidate_style_drift_report(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "create-candidate-comparison-matrix":
        output = app.create_candidate_comparison_matrix(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "create-psd-handoff-plan":
        output = app.create_psd_handoff_plan(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            selected_assets=args.selected_assets,
        )
    elif args.command == "prepare-psd-handoff-package":
        output = app.prepare_psd_handoff_package(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "create-psd-slice-spec-report":
        output = app.create_psd_slice_spec_report(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "create-delivery-readiness-report":
        output = app.create_delivery_readiness_report(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "create-designer-review-packet":
        output = app.create_designer_review_packet(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "create-design-workflow-plan":
        output = app.create_design_workflow_plan(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "create-meegle-writeback-draft":
        output = app.create_meegle_writeback_draft(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
        )
    elif args.command == "publish-meegle-writeback":
        output = app.publish_meegle_writeback(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            execute=args.execute,
            confirm_token=args.confirm_token,
            approval_file=args.approval_file,
            draft_dir=args.draft_dir,
        )
    elif args.command == "create-meegle-transition-draft":
        output = app.create_meegle_transition_draft(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            action=args.action,
            node_id=args.node_id,
            node_names=args.node_names,
            rollback_reason=args.rollback_reason,
        )
    elif args.command == "publish-meegle-transition":
        output = app.publish_meegle_transition(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            execute=args.execute,
            confirm_token=args.confirm_token,
            approval_file=args.approval_file,
            draft_dir=args.draft_dir,
        )
    elif args.command == "run-feishu-design-cycle":
        output = app.run_feishu_design_cycle(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            asset_root=args.asset_root,
            full=args.full,
        )
    elif args.command == "build-local-creative-pack":
        output = app.build_local_creative_pack(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            title=args.title,
            requirement_file=args.requirement_file,
            same_category=args.category,
            doc_files=args.doc_files,
            output_mode=args.output_mode,
        )
    elif args.command == "prepare-delivery-package":
        output = app.prepare_delivery_package(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            source_root=args.source_root,
            include_extensions=args.include_ext,
        )
    elif args.command == "plan-automation":
        output = app.plan_automation(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            asset_root=args.asset_root,
        )
    elif args.command == "metacognition-audit":
        output = app.metacognition_audit(project_key=args.project_key)
    elif args.command == "create-transition-summary":
        output = app.create_transition_summary(project_key=args.project_key)
    elif args.command == "create-learning-digest":
        output = app.create_learning_digest(project_key=args.project_key)
    elif args.command == "curate-style-memory":
        output = app.curate_style_memory(project_key=args.project_key, apply=args.apply)
    elif args.command == "run-local-design-cycle":
        output = app.run_local_design_cycle(
            project_key=args.project_key,
            work_item_id=args.work_item_id,
            title=args.title,
            requirement_file=args.requirement_file,
            same_category=args.category,
            doc_files=args.doc_files,
            asset_root=args.asset_root,
            full=args.full,
        )
    elif args.command == "ingest-feedback":
        feedback = _load_feedback(args.feedback, args.feedback_file)
        output = app.ingest_feedback(
            project_key=args.project_key,
            same_category=args.category,
            feedback=feedback,
            decision=args.decision,
            work_item_id=args.work_item_id,
            share_to_base=args.share_to_base,
        )
    elif args.command == "resume-session":
        output = app.resume_session(project_key=args.project_key)
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")

    print(json.dumps(output, ensure_ascii=False, indent=2))


def _load_feedback(feedback: str | None, feedback_file: str | None) -> str:
    if feedback:
        return feedback
    if feedback_file:
        return Path(feedback_file).read_text(encoding="utf-8")
    raise SystemExit("Either --feedback or --feedback-file is required.")


if __name__ == "__main__":
    main()

# Module Map

This file maps current source files to architecture domains. It documents the intended blueprint without requiring any import changes.

## Entry And Orchestration

| File | Domain | Responsibility |
|---|---|---|
| `agent/cli.py` | CLI | Defines all `design-copilot` commands, parses arguments, calls `DesignCopilotApp`, and prints JSON output. |
| `agent/app.py` | Application orchestration | Wires adapters, memory, builders, auditors, packagers, and publish gates into complete use cases. |
| `agent/models.py` | Data contracts | Defines dataclasses and enums for every persisted artifact and in-memory workflow object. |
| `agent/settings.py` | Infrastructure | Resolves repository, memory, workspace, and template paths. |
| `agent/shell.py` | Infrastructure | Runs external CLI commands and wraps command results or errors. |
| `agent/utils.py` | Infrastructure | Shared helpers for slugs, JSON IO, text extraction, size extraction, and flattening data. |

## Adapters

| File | Domain | Responsibility |
|---|---|---|
| `agent/adapters/meegle.py` | External boundary | Reads Meegle todos, work items, comments, and performs gated comments/transitions. |
| `agent/adapters/lark_doc.py` | External boundary | Reads linked Lark/Feishu docs through `lark-cli` and returns requirement docs. |
| `agent/adapters/local_files.py` | Local boundary | Creates runtime folders, scans assets, guesses asset roles/tags, and stages delivery files. |

## Memory

| File | Domain | Responsibility |
|---|---|---|
| `agent/memory/store.py` | Persistence | Reads and writes project profiles, style cards, session snapshots, reviews, learning digests, asset indexes, delivery packages, and related JSON artifacts. |

## Requirement Domain

| File | Responsibility |
|---|---|
| `agent/core/requirement_interpreter.py` | Converts raw work item/local requirement evidence into a `DesignBrief`. |
| `agent/core/requirement_clarifier.py` | Builds clarification questions, assumptions, comment drafts, and next actions. |
| `agent/core/requirement_change.py` | Compares refreshed requirements against existing briefs and reports impact. |
| `agent/core/requirement_memory.py` | Learns reusable project defaults from requirement patterns. |
| `agent/core/risk_detector.py` | Detects requirement risks and missing information. |
| `agent/core/field_calibration.py` | Infers project-specific work item field mappings. |
| `agent/core/workitem_intake.py` | Diagnoses work item intake quality, mapping confidence, and source evidence. |
| `agent/core/todo_screener.py` | Scores Meegle todos for likely design requirement relevance. |

## Style Domain

| File | Responsibility |
|---|---|
| `agent/core/project_profiles.py` | Creates and updates project profiles and applies profile rules to style cards. |
| `agent/core/project_skill.py` | Generates a reusable Codex skill from project memory. |
| `agent/core/style_alignment.py` | Checks style rule coverage, forbidden rule coverage, and K3 leakage. |
| `agent/core/style_transfer.py` | Explains same-category reuse, project overrides, conflicts, and K3 boundaries. |

## Creative Domain

| File | Responsibility |
|---|---|
| `agent/core/creative_pack.py` | Builds the central `CreativePack` from brief, style card, and project profile. |
| `agent/core/decision_recorder.py` | Records design decisions, rationale, assumptions, safety notes, and next actions. |
| `agent/core/workflow_plan.py` | Builds a step-by-step workflow board from current artifacts. |
| `agent/core/cycle_report.py` | Summarizes a completed local or live design cycle. |

## Generation Domain

| File | Responsibility |
|---|---|
| `agent/core/image_production.py` | Creates image production variants and candidate evaluation sheets. |
| `agent/core/generation_queue.py` | Converts selected variants into pending generation jobs and Pixpark JSONL payloads. |
| `agent/core/image_execution_package.py` | Prepares manual execution payloads, runbooks, and result templates. |
| `agent/core/generation_results.py` | Registers generated assets and creates gallery/delivery candidate indexes. |
| `agent/core/candidate_review.py` | Reads candidate decisions and review scores from designer feedback files. |
| `agent/core/candidate_style_drift.py` | Audits generated candidates for metadata-based style drift risk. |
| `agent/core/candidate_comparison.py` | Builds a candidate comparison matrix and recommended actions. |

## PSD Domain

| File | Responsibility |
|---|---|
| `agent/core/psd_handoff.py` | Creates PSD reconstruction plans, layer maps, and slice checklists. |
| `agent/core/psd_handoff_package.py` | Stages selected candidate assets for PSD handoff review. |
| `agent/core/psd_slice_spec.py` | Checks PSD layer, slicing, naming, staging, and safety requirements. |
| `agent/core/automation_planner.py` | Generates safe Photoshop/export automation plans, scripts, and dry-run stubs. |

## Delivery Domain

| File | Responsibility |
|---|---|
| `agent/core/delivery_readiness.py` | Runs the final local readiness gate across creative, style, generation, PSD, and staging artifacts. |
| `agent/core/review_packet.py` | Collects scattered artifacts into one designer review packet. |
| `agent/core/designer_cockpit.py` | Builds a readable local cockpit with status, blockers, confirmations, and commands. |
| `agent/core/designer_dashboard.py` | Builds a static HTML dashboard and JSON data snapshot from local artifacts. |

## Collaboration Domain

| File | Responsibility |
|---|---|
| `agent/core/meegle_writeback.py` | Creates Meegle comment drafts and approval tickets. |
| `agent/core/meegle_publish.py` | Validates explicit publish confirmation and builds publish receipts. |
| `agent/core/meegle_transition.py` | Creates and validates workflow transition drafts, tickets, previews, and receipts. |

## Session Domain

| File | Responsibility |
|---|---|
| `agent/core/session.py` | Builds session snapshots for latest active work item recovery. |
| `agent/core/session_resume.py` | Creates actionable resume briefs from snapshots and memory. |
| `agent/core/transition_summary.py` | Creates cross-session transition summaries. |
| `agent/core/doctor.py` | Checks runtime paths, optional CLIs, sessions, tests, and artifacts. |

## Evolution Domain

| File | Responsibility |
|---|---|
| `agent/core/style_learner.py` | Learns accepted, rejected, and pending style insights from feedback. |
| `agent/core/style_references.py` | Turns positive, negative, and exploratory references into graded memory. |
| `agent/core/style_memory_curator.py` | Suggests and optionally applies safe memory governance actions. |
| `agent/core/learning_digest.py` | Compresses memory into next-time defaults, avoid rules, hypotheses, and checklists. |
| `agent/core/metacognition.py` | Audits uncertainty, memory health, blind spots, and capability deltas. |
| `agent/core/requirement_memory.py` | Also participates here by learning recurring project defaults from briefs. |
| `agent/core/candidate_review.py` | Also participates here as a source of learning signals. |

## Tests And Tools

| File | Responsibility |
|---|---|
| `tests/test_core_logic.py` | Unit-level coverage for core parsing, style, creative, candidate, and automation logic. |
| `tests/test_workflow.py` | Workflow-level coverage for memory, feedback, local cycles, delivery staging, and sessions. |
| `tests/test_cli_entrypoints.py` | CLI smoke and user-facing artifact tests. |
| `tools/create_psd_handoff_demo.py` | Generates PSD handoff demo assets, PSD files, preview images, docs, and JSX scripts. |

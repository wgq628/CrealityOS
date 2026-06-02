# Artifact Map

This document records the main persisted artifacts, their producers, and their downstream consumers. It focuses on stable artifact roles rather than every runtime path instance.

## Core Requirement Artifacts

| Artifact | Producer | Main Consumers | Role |
|---|---|---|---|
| `design_brief.json` | `RequirementInterpreter` through `DesignCopilotApp` | `CreativePackBuilder`, change reports, workflow plans, dashboards | Structured requirement contract for a work item. |
| `design_brief.md` | `DesignCopilotApp` | Designers | Human-readable requirement card. |
| `requirement_clarification_report.json` | `RequirementClarifier` | Decision recorder, cockpit, review packet | Open questions, assumptions, and safety state. |
| `requirement_clarification_comment.md` | `RequirementClarifier` | Meegle writeback draft | Reviewable clarification comment draft. |
| `requirement_change_report.json` | `RequirementChangeAnalyzer` | Designer, workflow plan | Impact report when requirements change. |
| `workitem_intake_diagnostics.json` | `WorkItemIntakeDiagnostician` | Designer, field calibration | Field mapping and intake quality report. |
| `field_calibration_report.json` | `FieldCalibrator` | `MemoryStore`, requirement interpreter | Mapping confidence and recommended field bindings. |

## Style And Memory Artifacts

| Artifact | Producer | Main Consumers | Role |
|---|---|---|---|
| `project_profile.json` | `ProjectProfileManager`, `RequirementMemoryEngine` | `CreativePackBuilder`, `StyleTransferAuditor`, automation planner | Project-level defaults and hard rules. |
| `style_card.json` | `StyleLearner`, `StyleReferenceIngestor`, `ProjectProfileManager` | `CreativePackBuilder`, style auditors | Graded style rules and memory. |
| `style_transfer_report.json` | `StyleTransferAuditor` | Delivery readiness, candidate drift, review packet | Explains reusable, blocked, and exploratory style rules. |
| `style_alignment_report.json` | `StyleAlignmentAuditor` | Delivery readiness, candidate drift, decision record | Checks style prompt coverage and K3 boundaries. |
| `latest_style_reference_report.json` | `StyleReferenceIngestor` | Learning digest, review packet | Records ingested reference examples and memory effects. |
| `style_memory_curation_report.json` | `StyleMemoryCurator` | Designers, learning digest | Reports proposed or applied memory governance actions. |
| `review_report.json` | `StyleLearner` | Learning digest, future style cards | Captures accepted/rejected/pending designer feedback. |
| `latest_learning_digest.json` | `LearningDigestBuilder` | Session resume, future project skill generation | Compresses reusable learning into next-time guidance. |
| `latest_audit.json` | `MetacognitionAuditor` | Transition summary, cockpit | Audits uncertainty, blind spots, memory health, and capability gaps. |

## Creative Artifacts

| Artifact | Producer | Main Consumers | Role |
|---|---|---|---|
| `creative_pack.json` | `CreativePackBuilder` | Image production, PSD handoff, style auditors, delivery readiness | Central execution package for the current task. |
| `creative_pack.md` | `CreativePackBuilder` through `DesignCopilotApp` | Designers | Human-readable creative execution package. |
| `delivery_manifest.json` | `CreativePackBuilder` | Delivery staging, PSD/spec checks, readiness | Expected exports, naming, slicing, and confirmation policy. |
| `delivery_manifest.md` | `DesignCopilotApp` | Designers | Human-readable delivery checklist. |
| `design_decision_record.json` | `DesignDecisionRecorder` | Review packet, session resume | Rationale and safety notes behind the creative pack. |
| `design_workflow_plan.json` | `DesignWorkflowPlanner` | Cockpit, designers | Current step board with ready/waiting/blocked status. |
| `design_cycle_report.json` | `DesignCycleReporter` | Cockpit, transition summary | Summary of a full local or live cycle. |

## Generation And Candidate Artifacts

| Artifact | Producer | Main Consumers | Role |
|---|---|---|---|
| `image_generation_batch.json` | `ImageProductionPlanner` | Generation queue, candidate comparison, review packet | Multi-variant image production plan. |
| `candidate_evaluation.md` | `ImageProductionPlanner` | Designers | Review sheet for comparing generated directions. |
| `image_generation_jobs.json` | `ImageGenerationQueueBuilder` | Execution packager | Pending generation jobs selected from variants. |
| `pixpark_requests.jsonl` | `ImageGenerationQueueBuilder` | Manual Pixpark execution | Per-job request payloads. |
| `generation_approval_ticket.md` | `ImageGenerationQueueBuilder` | Designer confirmation | Confirms generation before execution. |
| `image_execution_package.json` | `ImageExecutionPackager` | Manual execution, result registration | Payload package for confirmed jobs. |
| `generation_results_template.json` | `ImageExecutionPackager` | Result registration | Template for recording generated paths or URLs. |
| `image_generation_results.json` | `ImageGenerationResultRegistrar` | Drift report, comparison matrix, PSD handoff | Registered generated image index. |
| `generated_gallery.md` | `ImageGenerationResultRegistrar` | Designers | Human-readable generated asset gallery. |
| `delivery_candidates.md` | `ImageGenerationResultRegistrar` | PSD handoff, delivery review | Candidate assets that can move toward delivery. |
| `candidate_style_drift_report.json` | `CandidateStyleDriftAuditor` | Comparison matrix, delivery readiness | Metadata/feedback-based style drift warnings. |
| `candidate_comparison_matrix.json` | `CandidateComparisonMatrixBuilder` | PSD handoff, delivery readiness | Variant scoring, risks, and recommended actions. |
| `*-candidate_review.json` | `CandidateReviewIngestor` | Style learner, delivery readiness, digest | Designer decisions and scores for generated variants. |

## PSD And Delivery Artifacts

| Artifact | Producer | Main Consumers | Role |
|---|---|---|---|
| `psd_handoff_plan.json` | `PsdHandoffPlanner` | PSD package, slice spec, readiness | PSD reconstruction and slicing plan. |
| `layer_map.md` | `PsdHandoffPlanner` | Designer, Photoshop work | Layer grouping and reconstruction notes. |
| `slice_checklist.md` | `PsdHandoffPlanner` | Designer, delivery review | Slice task checklist. |
| `psd_handoff_package.json` | `PsdHandoffPackager` | Slice spec, delivery readiness | Staged candidate assets for PSD work. |
| `psd_handoff_approval_ticket.md` | `PsdHandoffPackager` | Designer confirmation | Review ticket before PSD handoff. |
| `psd_slice_spec_report.json` | `PsdSliceSpecAuditor` | Delivery readiness | Checks PSD layer, slicing, naming, staging, and safety gates. |
| `automation_plan.json` | `AutomationPlanner` | Designer review | Safe Photoshop/export automation action plan. |
| `photoshop_export_dry_run.jsx` | `AutomationPlanner` | Manual Photoshop review | Dry-run JSX script for layer/slice inspection. |
| `asset_index.json` | `LocalFileAdapter` | Automation planner, delivery staging | Indexed local PSD/render assets. |
| `delivery_package.json` | `LocalFileAdapter` | Delivery readiness | Staged delivery files copied into a safe workspace package. |
| `approval_ticket.md` | `LocalFileAdapter` | Designer confirmation | Confirmation checklist before formal delivery. |
| `delivery_readiness_report.json` | `DeliveryReadinessAuditor` | Review packet, cockpit, writeback | Final local quality gate. |

## Review, Dashboard, Collaboration, And Session Artifacts

| Artifact | Producer | Main Consumers | Role |
|---|---|---|---|
| `designer_review_packet.json` | `DesignerReviewPacketBuilder` | Designers | One decision page linking creative, generation, PSD, delivery, and learning artifacts. |
| `designer_cockpit.json` | `DesignerCockpitBuilder` | Designers, session resume | Local status entrypoint with blockers and next commands. |
| `dashboard.html` | `DesignerDashboardBuilder` | Designers | Static HTML view of local artifacts. |
| `dashboard_data.json` | `DesignerDashboardBuilder` | Dashboard | Data snapshot used by the static dashboard. |
| `meegle_writeback_draft.json` | `MeegleWritebackDraftBuilder` | Publish gate | Structured writeback draft. |
| `meegle_writeback_comment.md` | `MeegleWritebackDraftBuilder` | Designer, Meegle publish | Human-reviewable comment body. |
| `meegle_writeback_approval_ticket.md` | `MeegleWritebackDraftBuilder` | Publish gate | Approval checklist before posting. |
| `meegle_transition_draft.json` | `MeegleTransitionGate` | Transition publish gate | Structured workflow transition draft. |
| `session_resume.json` | `SessionResumeBuilder` | Future runs | Actionable state recovery report. |
| `latest_transition.json` | `TransitionSummaryBuilder` | Future sessions | Cross-session handoff summary. |
| `doctor_report.json` | `Doctor` | Developers, designers | Local runtime and artifact health check. |


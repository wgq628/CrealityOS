from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class KnowledgeLevel(StrEnum):
    K1 = "K1"
    K2 = "K2"
    K3 = "K3"
    K4 = "K4"


@dataclass(slots=True)
class RequirementDoc:
    source: str
    token_or_url: str
    title: str | None
    content: str


@dataclass(slots=True)
class WorkItemContext:
    project_key: str | None
    work_item_id: str
    title: str
    raw_item: dict[str, Any]
    comments: list[dict[str, Any]] = field(default_factory=list)
    doc_links: list[str] = field(default_factory=list)
    docs: list[RequirementDoc] = field(default_factory=list)


@dataclass(slots=True)
class DesignBrief:
    project_key: str | None
    work_item_id: str
    title: str
    objective: str
    target_audience: str
    platform: str
    sizes: list[str]
    deliverables: list[str]
    deadline: str
    summary: str
    same_category: str
    source_links: list[str]
    missing_information: list[str]
    risk_points: list[str]
    raw_signals: list[str]
    game_name: str = "待确认"
    game_project_id: str = "待确认"
    gameplay_summary: str = "待确认"
    reference_assets: list[str] = field(default_factory=list)
    source_requirement_summary: str = "待确认"
    task_breakdown: list[str] = field(default_factory=list)
    style_direction: str = "待确认"


@dataclass(slots=True)
class ClarificationQuestion:
    question_id: str
    topic: str
    question: str
    reason: str
    severity: str
    suggested_default: str


@dataclass(slots=True)
class RequirementClarificationReport:
    project_key: str
    work_item_id: str
    title: str
    created_at: str
    safe_to_continue: bool
    questions: list[ClarificationQuestion]
    assumptions: list[str]
    comment_draft: str
    next_actions: list[str]


@dataclass(slots=True)
class RequirementChangeItem:
    field: str
    old_value: Any
    new_value: Any
    severity: str
    impact: str


@dataclass(slots=True)
class RequirementChangeReport:
    project_key: str
    work_item_id: str
    title: str
    created_at: str
    status: str
    source_mode: str
    change_items: list[RequirementChangeItem]
    unchanged_fields: list[str]
    impacted_artifacts: list[str]
    blockers: list[str]
    warnings: list[str]
    next_actions: list[str]
    source_artifacts: dict[str, str | None]


@dataclass(slots=True)
class StyleRule:
    statement: str
    level: KnowledgeLevel
    rationale: str
    source_refs: list[str] = field(default_factory=list)
    evidence_count: int = 1
    scope: str = "project"


@dataclass(slots=True)
class StyleCard:
    project_key: str
    same_category: str
    visual_keywords: list[str]
    composition_preferences: list[str]
    color_rules: list[str]
    material_rules: list[str]
    typography_rules: list[str]
    ui_mood: list[str]
    do_not: list[str]
    rules: list[StyleRule] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    evidence_summary: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StyleReferenceItem:
    reference_id: str
    uri: str
    kind: str
    role: str
    level: KnowledgeLevel
    keywords: list[str]
    notes: list[str]
    rules: list[str]
    exists: bool


@dataclass(slots=True)
class StyleReferenceReport:
    project_key: str
    same_category: str
    created_at: str
    source_file: str
    references: list[StyleReferenceItem]
    accepted_rules: list[StyleRule]
    rejected_rules: list[StyleRule]
    pending_rules: list[StyleRule]
    warnings: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class StyleMemoryCurationAction:
    action_id: str
    kind: str
    statement: str
    current_level: str | None
    proposed_level: str | None
    reason: str
    applied: bool = False
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StyleMemoryCurationReport:
    project_key: str
    same_category: str
    created_at: str
    mode: str
    actions: list[StyleMemoryCurationAction]
    warnings: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class ReviewInsight:
    statement: str
    level: KnowledgeLevel
    rationale: str
    applies_to_shared_base: bool = False


@dataclass(slots=True)
class ReviewReport:
    project_key: str
    work_item_id: str | None
    decision: str
    feedback: str
    accepted: list[ReviewInsight]
    rejected: list[ReviewInsight]
    pending: list[ReviewInsight]
    next_actions: list[str]


@dataclass(slots=True)
class PromptPack:
    positive: list[str]
    negative: list[str]
    reference_groups: list[str]


@dataclass(slots=True)
class DeliveryItem:
    name: str
    size: str
    format_hint: str
    notes: str


@dataclass(slots=True)
class DeliveryManifest:
    project_key: str
    work_item_id: str
    naming_rules: list[str]
    export_items: list[DeliveryItem]
    slicing_notes: list[str]
    requires_confirmation: bool = True


@dataclass(slots=True)
class CreativePack:
    brief: DesignBrief
    style_card: StyleCard
    references: list[str]
    prompt_pack: PromptPack
    composition_suggestions: list[str]
    psd_guidance: list[str]
    uncertainties: list[str]
    delivery_manifest: DeliveryManifest


@dataclass(slots=True)
class StyleAlignmentFinding:
    check_id: str
    title: str
    status: str
    severity: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""


@dataclass(slots=True)
class StyleAlignmentReport:
    project_key: str
    work_item_id: str
    title: str
    created_at: str
    status: str
    findings: list[StyleAlignmentFinding]
    confirmed_rule_count: int
    k3_hypothesis_count: int
    blockers: list[str]
    warnings: list[str]
    next_actions: list[str]
    source_artifacts: dict[str, str | None]


@dataclass(slots=True)
class StyleTransferFinding:
    check_id: str
    title: str
    status: str
    severity: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""


@dataclass(slots=True)
class StyleTransferReport:
    project_key: str
    work_item_id: str
    same_category: str
    created_at: str
    status: str
    transferable_rules: list[str]
    project_overrides: list[str]
    blocked_shared_rules: list[str]
    k3_hypotheses: list[str]
    findings: list[StyleTransferFinding]
    warnings: list[str]
    blockers: list[str]
    next_actions: list[str]
    source_artifacts: dict[str, str | None]


@dataclass(slots=True)
class DesignDecisionItem:
    decision_id: str
    category: str
    statement: str
    rationale: str
    evidence: list[str]
    level: str
    requires_designer_confirmation: bool = False


@dataclass(slots=True)
class DesignDecisionRecord:
    project_key: str
    work_item_id: str
    title: str
    created_at: str
    decisions: list[DesignDecisionItem]
    assumptions: list[str]
    open_questions: list[str]
    safety_notes: list[str]
    source_artifacts: dict[str, str | None]
    next_actions: list[str]


@dataclass(slots=True)
class ImageVariant:
    variant_id: str
    title: str
    intent: str
    positive_prompt: str
    negative_prompt: str
    target_sizes: list[str]
    reference_policy: list[str]
    review_rubric: list[str]
    psd_notes: list[str]
    tool_payloads: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ImageProductionBatch:
    project_key: str
    work_item_id: str
    created_at: str
    source_output_dir: str
    variants: list[ImageVariant]
    shared_negative_prompt: list[str]
    acceptance_checklist: list[str]
    feedback_questions: list[str]
    warnings: list[str]


@dataclass(slots=True)
class CandidateReviewItem:
    variant_id: str
    title: str
    decision: str
    scores: dict[str, float]
    strengths: list[str]
    issues: list[str]
    revision_notes: list[str]
    learning_statement: str
    generated_assets: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CandidateReviewReport:
    project_key: str
    work_item_id: str
    created_at: str
    source_batch: str | None
    items: list[CandidateReviewItem]
    accepted_variant_ids: list[str]
    rejected_variant_ids: list[str]
    pending_variant_ids: list[str]
    generated_review_reports: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class ImageGenerationJob:
    job_id: str
    variant_id: str
    title: str
    provider: str
    status: str
    payload: dict[str, Any]
    output_dir: str
    safety_notes: list[str]
    expected_outputs: list[str]


@dataclass(slots=True)
class ImageGenerationQueue:
    project_key: str
    work_item_id: str
    created_at: str
    source_batch: str
    execution_mode: str
    requires_designer_confirmation: bool
    jobs: list[ImageGenerationJob]
    warnings: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class ImageExecutionPackageItem:
    job_id: str
    variant_id: str
    provider: str
    title: str
    payload_file: str
    output_dir: str
    result_placeholder: str
    safety_notes: list[str]


@dataclass(slots=True)
class ImageExecutionPackage:
    project_key: str
    work_item_id: str
    created_at: str
    source_queue: str
    package_root: str
    execution_mode: str
    requires_designer_confirmation: bool
    items: list[ImageExecutionPackageItem]
    runbook: list[str]
    result_template: dict[str, Any]
    warnings: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class GeneratedAssetResult:
    asset_id: str
    job_id: str
    variant_id: str
    uri: str
    kind: str
    exists: bool
    width: int | None = None
    height: int | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ImageGenerationResultIndex:
    project_key: str
    work_item_id: str
    created_at: str
    source_queue: str | None
    assets: list[GeneratedAssetResult]
    missing_assets: list[str]
    delivery_candidates: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class CandidateStyleDriftItem:
    asset_id: str
    variant_id: str
    uri: str
    status: str
    drift_level: str
    evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""


@dataclass(slots=True)
class CandidateStyleDriftFinding:
    check_id: str
    title: str
    status: str
    severity: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""


@dataclass(slots=True)
class CandidateStyleDriftReport:
    project_key: str
    work_item_id: str
    created_at: str
    status: str
    items: list[CandidateStyleDriftItem]
    findings: list[CandidateStyleDriftFinding]
    blockers: list[str]
    warnings: list[str]
    next_actions: list[str]
    source_artifacts: dict[str, str | None]


@dataclass(slots=True)
class CandidateComparisonRow:
    variant_id: str
    title: str
    intent: str
    asset_count: int
    drift_level: str
    review_decision: str
    style_fit: float | None
    conversion_score: float | None
    psd_ready_score: float | None
    recommendation: str
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CandidateComparisonMatrix:
    project_key: str
    work_item_id: str
    created_at: str
    status: str
    rows: list[CandidateComparisonRow]
    recommended_variant_ids: list[str]
    rejected_variant_ids: list[str]
    revise_variant_ids: list[str]
    blockers: list[str]
    warnings: list[str]
    next_actions: list[str]
    source_artifacts: dict[str, str | None]


@dataclass(slots=True)
class PsdHandoffAsset:
    asset_id: str
    variant_id: str
    uri: str
    role: str
    recommended_layers: list[str]
    slicing_notes: list[str]


@dataclass(slots=True)
class PsdHandoffPlan:
    project_key: str
    work_item_id: str
    created_at: str
    source_results: str | None
    source_creative_pack: str | None
    assets: list[PsdHandoffAsset]
    layer_groups: list[str]
    reconstruction_steps: list[str]
    slicing_tasks: list[str]
    naming_rules: list[str]
    warnings: list[str]
    approval_checklist: list[str]


@dataclass(slots=True)
class PsdHandoffStageItem:
    asset_id: str
    variant_id: str
    source_uri: str
    staged_relative_path: str | None
    status: str
    role: str
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PsdHandoffPackage:
    project_key: str
    work_item_id: str
    created_at: str
    source_plan: str
    staged_root: str
    items: list[PsdHandoffStageItem]
    warnings: list[str]
    confirmation_checklist: list[str]


@dataclass(slots=True)
class PsdSliceSpecFinding:
    check_id: str
    title: str
    status: str
    severity: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""


@dataclass(slots=True)
class PsdSliceSpecReport:
    project_key: str
    work_item_id: str
    created_at: str
    status: str
    required_layer_groups: list[str]
    slicing_tasks: list[str]
    naming_examples: list[str]
    findings: list[PsdSliceSpecFinding]
    blockers: list[str]
    warnings: list[str]
    source_artifacts: dict[str, str | None]
    next_actions: list[str]


@dataclass(slots=True)
class MeegleWritebackDraft:
    project_key: str
    work_item_id: str
    created_at: str
    title: str
    status: str
    comment_markdown: str
    source_artifacts: dict[str, str]
    publish_command_preview: list[str]
    warnings: list[str]
    approval_checklist: list[str]


@dataclass(slots=True)
class MeeglePublishReceipt:
    project_key: str
    work_item_id: str
    created_at: str
    mode: str
    executed: bool
    confirmation_method: str
    comment_path: str
    command_preview: list[str]
    response: dict[str, Any]
    warnings: list[str]


@dataclass(slots=True)
class MeegleTransitionDraft:
    project_key: str
    work_item_id: str
    created_at: str
    action: str
    node_id: str | None
    node_names: list[str]
    rollback_reason: str | None
    command_preview: list[str]
    warnings: list[str]
    approval_checklist: list[str]


@dataclass(slots=True)
class MeegleTransitionReceipt:
    project_key: str
    work_item_id: str
    created_at: str
    action: str
    mode: str
    executed: bool
    confirmation_method: str
    command_preview: list[str]
    response: dict[str, Any]
    warnings: list[str]


@dataclass(slots=True)
class SessionSnapshot:
    project_key: str
    same_category: str
    active_work_item_id: str
    title: str
    output_dir: str
    key_decisions: list[str]
    unresolved_questions: list[str]
    last_artifacts: list[str]
    memory_project_key: str | None = None


@dataclass(slots=True)
class ProjectProfile:
    project_key: str
    same_category: str
    display_name: str
    gameplay_tags: list[str]
    visual_keywords: list[str]
    must_have_rules: list[str]
    forbidden_rules: list[str]
    delivery_naming_template: str
    required_deliverables: list[str]
    export_formats: list[str]
    default_sizes: list[str]
    slice_requirements: list[str]
    automation_preferences: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectProfileUpdateReport:
    project_key: str
    same_category: str
    created_at: str
    source_file: str
    mode: str
    changed_fields: list[str]
    warnings: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class RequirementMemoryReport:
    project_key: str
    work_item_id: str
    created_at: str
    game_name: str
    same_category: str
    learned_audience: str
    learned_gameplay_tags: list[str]
    learned_visual_keywords: list[str]
    learned_default_sizes: list[str]
    learned_deliverables: list[str]
    learned_style_rules: list[str]
    learned_slice_requirements: list[str]
    source_requirement_summary: str
    task_breakdown: list[str]
    memory_paths: dict[str, str]
    warnings: list[str]
    next_time_defaults: list[str]


@dataclass(slots=True)
class AssetCard:
    project_key: str
    source_root: str
    relative_path: str
    file_name: str
    extension: str
    role_guess: str
    tags: list[str]
    size_bytes: int
    modified_at: str
    level: KnowledgeLevel = KnowledgeLevel.K4
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AssetIndex:
    project_key: str
    source_root: str
    scanned_at: str
    asset_cards: list[AssetCard]
    warnings: list[str]


@dataclass(slots=True)
class DeliveryStageItem:
    source_relative_path: str
    staged_relative_path: str
    role_guess: str
    size_bytes: int
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DeliveryPreparation:
    project_key: str
    work_item_id: str
    source_root: str
    staged_root: str
    created_at: str
    files: list[DeliveryStageItem]
    warnings: list[str]
    confirmation_checklist: list[str]


@dataclass(slots=True)
class DeliveryReadinessFinding:
    check_id: str
    title: str
    status: str
    severity: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""


@dataclass(slots=True)
class DeliveryReadinessReport:
    project_key: str
    work_item_id: str
    created_at: str
    status: str
    requires_designer_confirmation: bool
    findings: list[DeliveryReadinessFinding]
    blocking_items: list[str]
    warnings: list[str]
    approval_checklist: list[str]
    source_artifacts: dict[str, str | None]


@dataclass(slots=True)
class AutomationAction:
    step_id: str
    title: str
    tool: str
    mode: str
    instruction: str
    depends_on: list[str] = field(default_factory=list)
    requires_confirmation: bool = True


@dataclass(slots=True)
class AutomationPlan:
    project_key: str
    work_item_id: str
    created_at: str
    source_psd: str | None
    stage_root: str | None
    actions: list[AutomationAction]
    checks: list[str]
    warnings: list[str]


@dataclass(slots=True)
class AuditFinding:
    category: str
    status: str
    summary: str
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MetacognitionAudit:
    project_key: str
    created_at: str
    consistency: AuditFinding
    validity: AuditFinding
    blind_spots: AuditFinding
    memory_health: AuditFinding
    actions: list[str]
    capability_delta: list[str]


@dataclass(slots=True)
class TransitionSummary:
    project_key: str
    created_at: str
    active_work_item_id: str | None
    active_title: str
    progress_summary: str
    key_decisions: list[str]
    unresolved_questions: list[str]
    recent_artifacts: list[str]
    capability_delta: list[str]
    restart_instructions: list[str]


@dataclass(slots=True)
class SessionResumeReport:
    project_key: str
    created_at: str
    status: str
    active_work_item_id: str | None
    active_title: str
    same_category: str
    output_dir: str | None
    key_decisions: list[str]
    unresolved_questions: list[str]
    artifact_index: dict[str, str | None]
    style_gate_status: str
    decision_summary: list[str]
    recent_feedback: list[str]
    next_commands: list[str]
    safety_notes: list[str]


@dataclass(slots=True)
class DesignCycleReport:
    project_key: str
    work_item_id: str
    title: str
    source_mode: str
    created_at: str
    artifacts: dict[str, str]
    skipped_steps: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class DesignWorkflowStep:
    step_id: str
    phase: str
    title: str
    status: str
    command: str
    depends_on: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    requires_designer_confirmation: bool = False


@dataclass(slots=True)
class DesignWorkflowPlan:
    project_key: str
    work_item_id: str
    title: str
    created_at: str
    status: str
    output_dir: str | None
    steps: list[DesignWorkflowStep]
    blockers: list[str]
    next_commands: list[str]
    safety_notes: list[str]
    artifact_index: dict[str, str | None]


@dataclass(slots=True)
class DesignerReviewPacket:
    project_key: str
    work_item_id: str
    title: str
    created_at: str
    status: str
    artifact_index: dict[str, str | None]
    decision_points: list[str]
    review_steps: list[str]
    warnings: list[str]
    next_actions: list[str]
    approval_checklist: list[str]


@dataclass(slots=True)
class DesignerCockpitReport:
    project_key: str
    work_item_id: str | None
    title: str
    created_at: str
    status: str
    summary: str
    output_dir: str | None
    blockers: list[str]
    confirmations: list[str]
    artifact_index: dict[str, str | None]
    next_commands: list[str]
    safety_notes: list[str]


@dataclass(slots=True)
class DoctorCheck:
    check_id: str
    title: str
    status: str
    detail: str


@dataclass(slots=True)
class DoctorReport:
    project_key: str | None
    created_at: str
    status: str
    checks: list[DoctorCheck]
    warnings: list[str]
    blockers: list[str]
    recommended_commands: list[str]


@dataclass(slots=True)
class LearningDigest:
    project_key: str
    created_at: str
    active_work_item_id: str | None
    same_category: str
    confirmed_defaults: list[str]
    avoid_next_time: list[str]
    hypotheses_to_verify: list[str]
    open_questions: list[str]
    recent_feedback: list[str]
    next_time_checklist: list[str]
    recommended_commands: list[str]


@dataclass(slots=True)
class ProjectStyleSkillReport:
    project_key: str
    skill_name: str
    display_name: str
    created_at: str
    status: str
    skill_dir: str
    skill_file: str
    manifest_file: str
    source_artifacts: dict[str, str | None]
    warnings: list[str]
    next_actions: list[str]


@dataclass(slots=True)
class FieldMapping:
    project_key: str
    fields: dict[str, str]
    confidence: dict[str, float]
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FieldCalibrationReport:
    project_key: str
    sample_file: str
    created_at: str
    mapping: FieldMapping
    candidates: dict[str, list[str]]
    warnings: list[str]


@dataclass(slots=True)
class WorkItemIntakeFinding:
    check_id: str
    title: str
    status: str
    severity: str
    evidence: list[str] = field(default_factory=list)
    action: str = ""


@dataclass(slots=True)
class WorkItemIntakeDiagnosticsReport:
    project_key: str
    work_item_id: str
    title: str
    created_at: str
    source_mode: str
    status: str
    field_mapping: FieldMapping
    mapping_candidates: dict[str, list[str]]
    parsed_brief: DesignBrief
    findings: list[WorkItemIntakeFinding]
    warnings: list[str]
    blockers: list[str]
    next_actions: list[str]
    source_artifacts: dict[str, str | None]


@dataclass(slots=True)
class TodoScreenItem:
    rank: int
    work_item_id: str | None
    project_key: str | None
    title: str
    score: float
    reasons: list[str]
    suggested_action: str
    raw: dict[str, Any]


@dataclass(slots=True)
class TodoScreeningReport:
    created_at: str
    action: str
    total_count: int
    design_count: int
    items: list[TodoScreenItem]
    warnings: list[str]


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_plain_data(item) for key, item in asdict(value).items()}
    if isinstance(value, EnumLikeTuple):
        return [to_plain_data(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


EnumLikeTuple = (list, tuple)

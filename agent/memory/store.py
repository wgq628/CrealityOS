from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Iterable

from agent.models import (
    AssetCard,
    AssetIndex,
    CandidateReviewReport,
    DeliveryPreparation,
    FieldCalibrationReport,
    FieldMapping,
    LearningDigest,
    MetacognitionAudit,
    ProjectProfile,
    ProjectProfileUpdateReport,
    RequirementMemoryReport,
    ReviewInsight,
    ReviewReport,
    SessionResumeReport,
    SessionSnapshot,
    StyleCard,
    StyleMemoryCurationReport,
    StyleReferenceReport,
    StyleRule,
    TransitionSummary,
    to_plain_data,
)
from agent.settings import AppPaths
from agent.utils import dump_json, ensure_directory, load_json


class MemoryStore:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load_style_card(self, project_key: str) -> StyleCard | None:
        path = self._project_dir(project_key) / "style_card.json"
        payload = load_json(path, None)
        return self._decode_style_card(payload) if payload else None

    def load_project_profile(self, project_key: str) -> ProjectProfile | None:
        path = self._project_dir(project_key) / "project_profile.json"
        payload = load_json(path, None)
        return ProjectProfile(**payload) if payload else None

    def save_project_profile(self, profile: ProjectProfile) -> Path:
        path = self._project_dir(profile.project_key) / "project_profile.json"
        dump_json(path, to_plain_data(profile))
        return path

    def save_project_profile_update_report(self, project_key: str, report: ProjectProfileUpdateReport) -> Path:
        path = self._project_dir(project_key) / "project_profile_update_report.json"
        dump_json(path, to_plain_data(report))
        return path

    def save_requirement_memory_report(self, project_key: str, report: RequirementMemoryReport) -> Path:
        path = self._project_dir(project_key) / "latest_requirement_memory_report.json"
        dump_json(path, to_plain_data(report))
        return path

    def save_project_memory_binding(
        self,
        meego_project_key: str,
        work_item_id: str,
        memory_project_key: str,
        game_name: str,
        game_project_id: str,
    ) -> Path:
        binding = {
            "meego_project_key": meego_project_key,
            "work_item_id": work_item_id,
            "memory_project_key": memory_project_key,
            "game_name": game_name,
            "game_project_id": game_project_id,
        }
        binding_dir = self.paths.memory / "project_bindings" / meego_project_key
        work_item_path = binding_dir / f"{work_item_id}.json"
        dump_json(work_item_path, binding)
        dump_json(binding_dir / "latest.json", binding)
        return work_item_path

    def load_project_memory_binding(self, meego_project_key: str, work_item_id: str | None = None) -> dict | None:
        binding_dir = self.paths.memory / "project_bindings" / meego_project_key
        path = binding_dir / f"{work_item_id}.json" if work_item_id else binding_dir / "latest.json"
        payload = load_json(path, None)
        return payload if isinstance(payload, dict) else None

    def save_field_mapping(self, mapping: FieldMapping) -> Path:
        path = self._project_dir(mapping.project_key) / "field_mapping.json"
        dump_json(path, to_plain_data(mapping))
        return path

    def load_field_mapping(self, project_key: str) -> FieldMapping | None:
        path = self._project_dir(project_key) / "field_mapping.json"
        payload = load_json(path, None)
        return FieldMapping(**payload) if payload else None

    def save_field_calibration_report(self, project_key: str, report: FieldCalibrationReport) -> Path:
        path = self._project_dir(project_key) / "field_calibration_report.json"
        dump_json(path, to_plain_data(report))
        return path

    def save_style_card(self, style_card: StyleCard) -> Path:
        path = self._project_dir(style_card.project_key) / "style_card.json"
        dump_json(path, to_plain_data(style_card))
        return path

    def save_style_memory_curation_report(self, project_key: str, report: StyleMemoryCurationReport) -> Path:
        path = self._project_dir(project_key) / "style_memory_curation_report.json"
        dump_json(path, to_plain_data(report))
        return path

    def load_style_base(self, same_category: str) -> StyleCard | None:
        path = self.paths.memory / "style_bases" / f"{same_category}.json"
        payload = load_json(path, None)
        return self._decode_style_card(payload) if payload else None

    def save_style_base(self, style_card: StyleCard) -> Path:
        path = self.paths.memory / "style_bases" / f"{style_card.same_category}.json"
        dump_json(path, to_plain_data(style_card))
        return path

    def save_review_report(self, project_key: str, report: ReviewReport) -> Path:
        review_dir = self.paths.memory / "reviews" / project_key
        ensure_directory(review_dir)
        suffix = report.work_item_id or "general"
        path = review_dir / f"{suffix}-review_report.json"
        dump_json(path, to_plain_data(report))
        return path

    def load_review_report(self, path: Path) -> ReviewReport:
        payload = load_json(path, None)
        if not payload:
            raise FileNotFoundError(f"Review report does not exist: {path}")
        return self._decode_review_report(payload)

    def save_asset_index(self, project_key: str, asset_index: AssetIndex) -> Path:
        path = self._project_dir(project_key) / "asset_index.json"
        dump_json(path, to_plain_data(asset_index))
        return path

    def load_asset_index(self, project_key: str) -> AssetIndex | None:
        path = self._project_dir(project_key) / "asset_index.json"
        payload = load_json(path, None)
        return self._decode_asset_index(payload) if payload else None

    def save_delivery_preparation(self, project_key: str, delivery: DeliveryPreparation) -> Path:
        path = self._project_dir(project_key) / "latest_delivery_package.json"
        dump_json(path, to_plain_data(delivery))
        return path

    def load_delivery_preparation(self, project_key: str) -> DeliveryPreparation | None:
        path = self._project_dir(project_key) / "latest_delivery_package.json"
        payload = load_json(path, None)
        return DeliveryPreparation(**payload) if payload else None

    def save_session_snapshot(self, snapshot: SessionSnapshot) -> Path:
        session_dir = self.paths.memory / "sessions" / snapshot.project_key
        ensure_directory(session_dir)
        path = session_dir / "latest.json"
        dump_json(path, to_plain_data(snapshot))
        return path

    def load_session_snapshot(self, project_key: str) -> SessionSnapshot | None:
        path = self.paths.memory / "sessions" / project_key / "latest.json"
        payload = load_json(path, None)
        if not payload:
            return None
        snapshot = SessionSnapshot(**payload)
        self._relocate_snapshot(snapshot)
        return snapshot

    def save_session_resume_report(self, project_key: str, report: SessionResumeReport) -> Path:
        session_dir = self.paths.memory / "sessions" / project_key
        ensure_directory(session_dir)
        path = session_dir / "session_resume.json"
        dump_json(path, to_plain_data(report))
        return path

    def save_metacognition_audit(self, project_key: str, audit: MetacognitionAudit) -> Path:
        audit_dir = self.paths.memory / "audits" / project_key
        ensure_directory(audit_dir)
        path = audit_dir / "latest_audit.json"
        dump_json(path, to_plain_data(audit))
        return path

    def save_transition_summary(self, project_key: str, summary: TransitionSummary) -> Path:
        transition_dir = self.paths.memory / "session-transition" / project_key
        ensure_directory(transition_dir)
        path = transition_dir / "latest_transition.json"
        dump_json(path, to_plain_data(summary))
        return path

    def save_learning_digest(self, project_key: str, digest: LearningDigest) -> Path:
        path = self._project_dir(project_key) / "latest_learning_digest.json"
        dump_json(path, to_plain_data(digest))
        return path

    def save_candidate_review_report(self, project_key: str, report: CandidateReviewReport) -> Path:
        review_dir = self.paths.memory / "reviews" / project_key
        ensure_directory(review_dir)
        path = review_dir / f"{report.work_item_id}-candidate_review.json"
        dump_json(path, to_plain_data(report))
        return path

    def save_style_reference_report(self, project_key: str, report: StyleReferenceReport) -> Path:
        reference_dir = self.paths.memory / "style_references" / project_key
        ensure_directory(reference_dir)
        path = reference_dir / "latest_style_reference_report.json"
        dump_json(path, to_plain_data(report))
        return path

    def list_review_reports(self, project_key: str, limit: int = 5) -> list[Path]:
        review_dir = self.paths.memory / "reviews" / project_key
        if not review_dir.exists():
            return []
        candidates = sorted(review_dir.glob("*-review_report.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[:limit]

    def _project_dir(self, project_key: str) -> Path:
        path = self.paths.memory / "projects" / project_key
        ensure_directory(path)
        return path

    def _relocate_snapshot(self, snapshot: SessionSnapshot) -> bool:
        changed = False
        output_dir = self._relocate_known_path(snapshot.output_dir)
        if output_dir != snapshot.output_dir:
            snapshot.output_dir = output_dir
            changed = True
        relocated_artifacts = [self._relocate_known_path(path) for path in snapshot.last_artifacts]
        if relocated_artifacts != snapshot.last_artifacts:
            snapshot.last_artifacts = relocated_artifacts
            changed = True
        return changed

    def _relocate_known_path(self, raw_path: str) -> str:
        path = Path(raw_path)
        if path.exists():
            return str(path)

        normalized = str(raw_path).replace("\\", "/")
        lower = normalized.lower()
        known_roots = (
            ("/workspace/runs/", self.paths.workspace),
            ("/workspace/deliveries/", self.paths.root / "workspace" / "deliveries"),
            ("/memory/", self.paths.memory),
        )
        for marker, base in known_roots:
            index = lower.find(marker)
            if index == -1:
                continue
            suffix = normalized[index + len(marker) :].strip("/")
            relocated = base.joinpath(*suffix.split("/")) if suffix else base
            if relocated.exists():
                return str(relocated)
        return raw_path

    @staticmethod
    def _decode_style_card(payload: dict) -> StyleCard:
        rules = [StyleRule(**rule) for rule in payload.get("rules", [])]
        card_fields = {field.name for field in fields(StyleCard)}
        data = {key: value for key, value in payload.items() if key in card_fields and key != "rules"}
        data["rules"] = rules
        return StyleCard(**data)

    @staticmethod
    def _decode_asset_index(payload: dict) -> AssetIndex:
        cards = [AssetCard(**card) for card in payload.get("asset_cards", [])]
        data = dict(payload)
        data["asset_cards"] = cards
        return AssetIndex(**data)

    @staticmethod
    def _decode_review_report(payload: dict) -> ReviewReport:
        data = dict(payload)
        for key in ("accepted", "rejected", "pending"):
            data[key] = [ReviewInsight(**item) for item in payload.get(key, [])]
        return ReviewReport(**data)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agent.settings import AppPaths
from agent.utils import load_json, slugify


IMPORTANT_ARTIFACT_FILES = (
    "design_brief.json",
    "requirement_clarification_report.json",
    "requirement_change_report.json",
    "creative_pack.json",
    "style_transfer_report.json",
    "style_alignment_report.json",
    "design_decision_record.json",
    "image_generation_batch.json",
    "image_generation_jobs.json",
    "image_execution_package.json",
    "image_generation_results.json",
    "candidate_style_drift_report.json",
    "candidate_comparison_matrix.json",
    "candidate_review.json",
    "psd_handoff_plan.json",
    "psd_handoff_package.json",
    "psd_slice_spec_report.json",
    "delivery_readiness_report.json",
    "design_workflow_plan.json",
    "designer_review_packet.json",
    "designer_cockpit.json",
    "meegle_writeback_draft.json",
)


@dataclass(slots=True)
class ResolvedRunContext:
    project_key: str
    work_item_id: str | None = None
    output_dir: Path | None = None
    title: str | None = None
    requested_project_key: str | None = None
    requested_work_item_id: str | None = None
    notices: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def corrected(self) -> bool:
        return bool(
            (self.requested_project_key and self.requested_project_key != self.project_key)
            or (self.requested_work_item_id and self.requested_work_item_id != self.work_item_id)
        )


class ArtifactResolver:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def resolve(
        self,
        project_key: str | None = None,
        work_item_id: str | None = None,
        output_dir: str | Path | None = None,
    ) -> ResolvedRunContext:
        if output_dir:
            target_dir = Path(output_dir)
            project = project_key or self._project_from_output_dir(target_dir) or "EMPTY"
            parsed_item, parsed_title = parse_run_name(target_dir.name)
            brief = load_json(target_dir / "design_brief.json", {})
            return ResolvedRunContext(
                project_key=brief.get("project_key") or project,
                work_item_id=work_item_id or brief.get("work_item_id") or parsed_item,
                output_dir=target_dir if target_dir.exists() else None,
                title=brief.get("title") or parsed_title,
                requested_project_key=project_key,
                requested_work_item_id=work_item_id,
                warnings=[] if target_dir.exists() else [f"Requested output directory does not exist: {target_dir}"],
            )

        projects = discover_projects(self.paths)
        selected_project = project_key or (projects[0]["project_key"] if projects else "EMPTY")
        snapshot = self._load_snapshot(selected_project)
        selected_work_item = work_item_id or (snapshot or {}).get("active_work_item_id")

        if selected_work_item:
            run_dir = find_run_dir(self.paths, selected_project, selected_work_item)
            if run_dir:
                title = self._title_for_run(run_dir)
                return ResolvedRunContext(
                    project_key=selected_project,
                    work_item_id=selected_work_item,
                    output_dir=run_dir,
                    title=title,
                    requested_project_key=project_key,
                    requested_work_item_id=work_item_id,
                )

            owner = self.find_work_item(selected_work_item)
            if owner:
                actual_project, actual_dir = owner
                notice = (
                    f"Requested project `{selected_project}` does not contain work item `{selected_work_item}`; "
                    f"using `{actual_project}` instead."
                )
                return ResolvedRunContext(
                    project_key=actual_project,
                    work_item_id=selected_work_item,
                    output_dir=actual_dir,
                    title=self._title_for_run(actual_dir),
                    requested_project_key=project_key,
                    requested_work_item_id=work_item_id,
                    notices=[notice],
                )

            return ResolvedRunContext(
                project_key=selected_project,
                work_item_id=selected_work_item,
                requested_project_key=project_key,
                requested_work_item_id=work_item_id,
                warnings=[f"No local run directory found for {selected_project}/{selected_work_item}."],
            )

        work_items = discover_work_items(self.paths, selected_project)
        if work_items:
            latest = work_items[0]
            return ResolvedRunContext(
                project_key=selected_project,
                work_item_id=latest["work_item_id"],
                output_dir=Path(latest["output_dir"]) if latest.get("output_dir") else None,
                title=latest.get("title"),
                requested_project_key=project_key,
                requested_work_item_id=work_item_id,
            )

        if snapshot and snapshot.get("output_dir"):
            candidate = Path(snapshot["output_dir"])
            return ResolvedRunContext(
                project_key=selected_project,
                work_item_id=snapshot.get("active_work_item_id"),
                output_dir=candidate if candidate.exists() else None,
                title=snapshot.get("title"),
                requested_project_key=project_key,
                requested_work_item_id=work_item_id,
                warnings=[] if candidate.exists() else [f"Snapshot output directory does not exist: {candidate}"],
            )

        return ResolvedRunContext(
            project_key=selected_project,
            requested_project_key=project_key,
            requested_work_item_id=work_item_id,
            warnings=[f"No local project context found for {selected_project}."],
        )

    def collect_artifacts(self, output_dir: Path | None, extra_artifacts: list[str] | None = None) -> dict[str, str | None]:
        return collect_artifacts(output_dir, extra_artifacts)

    def find_work_item(self, work_item_id: str) -> tuple[str, Path] | None:
        matches: list[tuple[str, Path]] = []
        for project in discover_projects(self.paths):
            project_key = project["project_key"]
            run_dir = find_run_dir(self.paths, project_key, work_item_id)
            if run_dir:
                matches.append((project_key, run_dir))
        if not matches:
            return None
        return sorted(matches, key=lambda item: modified_time(item[1]), reverse=True)[0]

    def _load_snapshot(self, project_key: str) -> dict | None:
        return load_json(self.paths.memory / "sessions" / project_key / "latest.json", None)

    def _project_from_output_dir(self, output_dir: Path) -> str | None:
        try:
            relative = output_dir.resolve().relative_to(self.paths.workspace.resolve())
        except ValueError:
            return None
        return relative.parts[0] if relative.parts else None

    @staticmethod
    def _title_for_run(run_dir: Path) -> str | None:
        brief = load_json(run_dir / "design_brief.json", {})
        if brief.get("title"):
            return brief["title"]
        return parse_run_name(run_dir.name)[1]


def discover_projects(paths: AppPaths) -> list[dict]:
    seen: dict[str, dict] = {}

    def touch(project_key: str, source: str, path: Path) -> None:
        if not project_key or project_key.startswith("."):
            return
        modified = modified_time(path)
        current = seen.get(project_key)
        if not current or modified > current["modified_ts"]:
            seen[project_key] = {
                "project_key": project_key,
                "source": source,
                "path": str(path),
                "modified_ts": modified,
                "modified_at": _iso_time(modified),
            }

    for base, source in (
        (paths.memory / "sessions", "session"),
        (paths.memory / "projects", "memory"),
        (paths.workspace, "run"),
    ):
        if not base.exists():
            continue
        for child in base.iterdir():
            if child.is_dir():
                touch(child.name, source, child)

    return sorted(seen.values(), key=lambda item: item["modified_ts"], reverse=True)


def discover_work_items(paths: AppPaths, project_key: str) -> list[dict]:
    runs_dir = paths.workspace / slugify(project_key, fallback=project_key)
    if not runs_dir.exists():
        runs_dir = paths.workspace / project_key
    items: list[dict] = []
    if runs_dir.exists():
        for child in runs_dir.iterdir():
            if not child.is_dir():
                continue
            parsed_id, parsed_title = parse_run_name(child.name)
            brief = load_json(child / "design_brief.json", {})
            modified = modified_time(child)
            items.append(
                {
                    "work_item_id": str(brief.get("work_item_id") or parsed_id),
                    "title": brief.get("title") or parsed_title or child.name,
                    "output_dir": str(child),
                    "modified_ts": modified,
                    "modified_at": _iso_time(modified),
                }
            )
    snapshot = load_json(paths.memory / "sessions" / project_key / "latest.json", None)
    if snapshot and snapshot.get("active_work_item_id"):
        existing = {item["work_item_id"] for item in items}
        if snapshot["active_work_item_id"] not in existing:
            output_dir = snapshot.get("output_dir")
            modified = modified_time(Path(output_dir)) if output_dir else 0.0
            items.append(
                {
                    "work_item_id": snapshot["active_work_item_id"],
                    "title": snapshot.get("title") or snapshot["active_work_item_id"],
                    "output_dir": output_dir,
                    "modified_ts": modified,
                    "modified_at": _iso_time(modified),
                }
            )
    return sorted(items, key=lambda item: item["modified_ts"], reverse=True)


def find_run_dir(paths: AppPaths, project_key: str, work_item_id: str) -> Path | None:
    for base in (paths.workspace / project_key, paths.workspace / slugify(project_key, fallback=project_key)):
        if not base.exists():
            continue
        matches = [child for child in base.iterdir() if child.is_dir() and child.name.startswith(f"{work_item_id}-")]
        if matches:
            return sorted(matches, key=modified_time, reverse=True)[0]
    return None


def collect_artifacts(output_dir: Path | None, extra_artifacts: list[str] | None = None) -> dict[str, str | None]:
    artifact_index: dict[str, str | None] = {Path(name).stem: None for name in IMPORTANT_ARTIFACT_FILES}
    candidates: list[Path] = []
    if output_dir and output_dir.exists():
        candidates.extend(path for path in output_dir.rglob("*") if path.name in IMPORTANT_ARTIFACT_FILES)
    for raw in extra_artifacts or []:
        path = Path(raw)
        if path.exists() and path.name in IMPORTANT_ARTIFACT_FILES:
            candidates.append(path)
    for path in sorted(candidates, key=modified_time):
        artifact_index[path.stem] = str(path)
    return artifact_index


def parse_run_name(name: str) -> tuple[str, str | None]:
    if "-" not in name:
        return name, None
    work_item_id, title = name.split("-", 1)
    return work_item_id, title or None


def modified_time(path: Path) -> float:
    if not path.exists():
        return 0.0
    if path.is_file():
        return path.stat().st_mtime
    latest = path.stat().st_mtime
    try:
        for child in path.rglob("*"):
            if child.exists():
                latest = max(latest, child.stat().st_mtime)
    except OSError:
        pass
    return latest


def _iso_time(timestamp: float) -> str | None:
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds") if timestamp else None

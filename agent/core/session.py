from __future__ import annotations

from pathlib import Path

from agent.models import CreativePack, SessionSnapshot


class SessionManager:
    def build_snapshot(self, creative_pack: CreativePack, output_dir: Path) -> SessionSnapshot:
        brief = creative_pack.brief
        decisions = [item for item in creative_pack.references[:4]]
        unresolved = list(dict.fromkeys(creative_pack.uncertainties or ["等待设计师确认风格方向"]))
        artifacts = [
            str(output_dir / "design_brief.md"),
            str(output_dir / "style_card.md"),
            str(output_dir / "creative_pack.md"),
            str(output_dir / "delivery_manifest.md"),
        ]
        return SessionSnapshot(
            project_key=brief.project_key or "unknown-project",
            same_category=brief.same_category,
            active_work_item_id=brief.work_item_id,
            title=brief.title,
            output_dir=str(output_dir),
            key_decisions=decisions,
            unresolved_questions=unresolved,
            last_artifacts=artifacts,
            memory_project_key=creative_pack.style_card.project_key,
        )

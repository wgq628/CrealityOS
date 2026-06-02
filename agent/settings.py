from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppPaths:
    root: Path
    memory: Path
    workspace: Path
    templates: Path

    @classmethod
    def from_root(cls, root: Path) -> "AppPaths":
        return cls(
            root=root,
            memory=root / "memory",
            workspace=root / "workspace" / "runs",
            templates=root / "templates",
        )

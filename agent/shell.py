from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class CommandError(RuntimeError):
    """Raised when an external command fails."""


@dataclass(slots=True)
class ShellResult:
    command: list[str]
    stdout: str
    stderr: str
    returncode: int

    def json(self):
        return json.loads(self.stdout or "{}")


class ShellRunner:
    def __init__(self, cwd: Path | None = None) -> None:
        self.cwd = cwd

    def run(self, command: Sequence[str]) -> ShellResult:
        resolved_command = list(command)
        executable = shutil.which(resolved_command[0])
        if executable:
            resolved_command[0] = executable
        completed = subprocess.run(
            resolved_command,
            cwd=self.cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        result = ShellResult(
            command=resolved_command,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            returncode=completed.returncode,
        )
        if completed.returncode != 0:
            message = result.stderr or result.stdout or f"Command failed: {' '.join(command)}"
            raise CommandError(message)
        return result

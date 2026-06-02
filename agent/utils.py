from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any


DOC_URL_PATTERN = re.compile(
    r"https?://[^\s]+/(?:docx|wiki)/([A-Za-z0-9]+)[^\s]*",
    re.IGNORECASE,
)
SIZE_PATTERN = re.compile(r"\b\d{2,5}\s*[xX*]\s*\d{2,5}\b|\b\d{1,2}:\d{1,2}\b")


def slugify(value: str, fallback: str = "item") -> str:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip()).strip("-")
    return text or fallback


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    for attempt in range(8):
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    for attempt in range(8):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (PermissionError, json.JSONDecodeError):
            if attempt == 7:
                raise
            time.sleep(0.05)
    return default


def find_doc_links(value: Any) -> list[str]:
    text = stringify(value)
    return list(dict.fromkeys(match.group(0) for match in DOC_URL_PATTERN.finditer(text)))


def find_sizes(text: str) -> list[str]:
    sizes = [re.sub(r"\s+", "", match.group(0)).replace("*", "x") for match in SIZE_PATTERN.finditer(text)]
    return list(dict.fromkeys(sizes))


def stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return str(value)
    if isinstance(value, dict):
        return "\n".join(f"{key}: {stringify(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(stringify(item) for item in value)
    return str(value)


def flatten_pairs(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            pairs.extend(flatten_pairs(item, next_prefix))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            next_prefix = f"{prefix}[{index}]"
            pairs.extend(flatten_pairs(item, next_prefix))
    else:
        pairs.append((prefix, stringify(value)))
    return pairs


def first_non_empty(candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip()
    return ""

"""Helpers for optional speaker manifest files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


def load_speaker_manifest(path: Optional[str]) -> Dict[str, Any]:
    """Load speaker metadata from JSON when provided."""
    if not path:
        return {}

    manifest_path = Path(path).expanduser().resolve()
    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Speaker manifest must be a JSON object.")
    return payload


def speaker_hint_to_manifest(speaker_hint: Optional[str]) -> Dict[str, Any]:
    """Convert a free-form participant hint into an expected speaker manifest."""
    if not speaker_hint or not speaker_hint.strip():
        return {}
    normalized = speaker_hint.strip()
    capitalized_names = [
        name for name in re.findall(r"\b[А-ЯЁA-Z][а-яёa-z]+\b", normalized) if _looks_like_name(name)
    ]
    names = capitalized_names or [
        item.strip(" .,;:!?()[]{}\"'")
        for item in re.split(r"\s*(?:,|;|/|\\|\+|\s+и\s+|\s+and\s+)\s*", normalized, flags=re.I)
    ]
    names = [name for name in names if _looks_like_name(name)]
    if not names:
        return {}
    deduped: list[str] = []
    for name in names:
        if name not in deduped:
            deduped.append(name)
    return {
        "source": "freeform_speaker_hint",
        "raw_hint": normalized,
        "expected_speakers": [{"name": name} for name in deduped],
    }


def _looks_like_name(value: str) -> bool:
    if not value or len(value) > 40:
        return False
    stop_words = {
        "был",
        "была",
        "были",
        "вот",
        "на",
        "встреча",
        "встрече",
        "созвоне",
        "звонке",
        "meeting",
        "call",
    }
    words = value.split()
    if len(words) > 3:
        return False
    return not all(word.lower() in stop_words for word in words)

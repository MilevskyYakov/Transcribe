"""Conservative transcript cleanup helpers."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable, List

from mnema.app.models import TranscriptSegment

_SPACE_BEFORE_PUNCTUATION_RE = re.compile(r"\s+([,.!?;:])")
_SPACE_AFTER_PUNCTUATION_RE = re.compile(r"([,.!?;:])(?=\S)")
_REPEATED_WORD_RE = re.compile(r"\b([A-Za-zА-Яа-яЁё]+)\b\s+\b\1\b", re.IGNORECASE)
_TERMINAL_PUNCTUATION = (".", "!", "?", "…")


def clean_text_conservatively(text: str) -> str:
    """Apply editor-safe cleanup while preserving raw transcript separately."""
    cleaned = " ".join(text.split())
    cleaned = _SPACE_BEFORE_PUNCTUATION_RE.sub(r"\1", cleaned)
    cleaned = _SPACE_AFTER_PUNCTUATION_RE.sub(r"\1 ", cleaned)
    while True:
        next_cleaned = _REPEATED_WORD_RE.sub(r"\1", cleaned)
        if next_cleaned == cleaned:
            break
        cleaned = next_cleaned
    cleaned = cleaned.strip()
    if not cleaned:
        return cleaned
    cleaned = cleaned[0].upper() + cleaned[1:]
    if not cleaned.endswith(_TERMINAL_PUNCTUATION):
        cleaned += "."
    return cleaned


def apply_conservative_cleanup(segments: Iterable[TranscriptSegment]) -> List[TranscriptSegment]:
    """Return segments with normalized `text_clean` while preserving `text_raw`."""
    cleaned_segments = []
    for segment in segments:
        cleaned_segments.append(
            replace(segment, text_clean=clean_text_conservatively(segment.text_clean))
        )
    return cleaned_segments

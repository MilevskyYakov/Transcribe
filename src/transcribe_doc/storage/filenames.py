"""Safe user-facing artifact filename helpers."""

from __future__ import annotations

from pathlib import Path
import re


FORBIDDEN_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
WHITESPACE = re.compile(r"\s+")
TRIM_CHARS = " .-_"
DEFAULT_MARKDOWN_STEM = "transcription"
MAX_MARKDOWN_STEM_LENGTH = 120


def safe_markdown_filename(
    title: str | None,
    *,
    source_path: str | Path | None = None,
    fallback: str = DEFAULT_MARKDOWN_STEM,
    max_stem_length: int = MAX_MARKDOWN_STEM_LENGTH,
) -> str:
    """Return a safe Markdown filename derived from a title with source fallback."""
    stem = _safe_filename_stem(title, max_stem_length=max_stem_length)
    if not stem and source_path is not None:
        source = Path(source_path)
        stem = _safe_filename_stem(source.stem or source.name, max_stem_length=max_stem_length)
    if not stem:
        stem = _safe_filename_stem(fallback, max_stem_length=max_stem_length) or DEFAULT_MARKDOWN_STEM
    return f"{stem}.md"


def _safe_filename_stem(value: str | None, *, max_stem_length: int) -> str:
    if not value:
        return ""
    cleaned = FORBIDDEN_FILENAME_CHARS.sub(" ", value)
    cleaned = WHITESPACE.sub(" ", cleaned).strip(TRIM_CHARS)
    if len(cleaned) > max_stem_length:
        cleaned = cleaned[:max_stem_length].rstrip(TRIM_CHARS)
    return cleaned
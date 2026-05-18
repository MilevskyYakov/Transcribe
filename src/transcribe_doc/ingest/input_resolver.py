"""Input validation and normalization for media sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transcribe_doc.app.constants import (
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
)


class InputResolutionError(ValueError):
    """Raised when the requested media input cannot be accepted."""


@dataclass(frozen=True)
class ResolvedInput:
    """Normalized input description used by the pipeline."""

    path: Path
    extension: str
    media_kind: str


def resolve_single_input(path: Path | str) -> ResolvedInput:
    """Validate a single file path and classify it as audio or video."""
    resolved_path = Path(path).expanduser().resolve()
    if not resolved_path.exists() or not resolved_path.is_file():
        raise InputResolutionError(f"Input file not found: {resolved_path}")

    extension = resolved_path.suffix.lower().lstrip(".")
    if extension in SUPPORTED_AUDIO_EXTENSIONS:
        return ResolvedInput(path=resolved_path, extension=extension, media_kind="audio")
    if extension in SUPPORTED_VIDEO_EXTENSIONS:
        return ResolvedInput(path=resolved_path, extension=extension, media_kind="video")

    raise InputResolutionError(f"Unsupported media format: .{extension}")

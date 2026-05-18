"""Factory helpers for alignment backends."""

from __future__ import annotations

from transcribe_doc.alignment.base import AlignmentBackend
from transcribe_doc.alignment.passthrough_backend import PassthroughAlignmentBackend
from transcribe_doc.app.config import AppConfig


def build_alignment_backend(config: AppConfig) -> AlignmentBackend | None:
    """Construct the configured alignment backend, if enabled."""
    if not config.alignment.enabled:
        return None
    return PassthroughAlignmentBackend()

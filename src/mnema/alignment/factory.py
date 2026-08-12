"""Factory helpers for alignment backends."""

from __future__ import annotations

from mnema.alignment.base import AlignmentBackend
from mnema.alignment.passthrough_backend import PassthroughAlignmentBackend
from mnema.app.config import AppConfig


def build_alignment_backend(config: AppConfig) -> AlignmentBackend | None:
    """Construct the configured alignment backend, if enabled."""
    if not config.alignment.enabled:
        return None
    return PassthroughAlignmentBackend()

"""Baseline alignment backend that preserves existing timing information."""

from __future__ import annotations

from typing import List

from mnema.alignment.base import AlignmentBackend
from mnema.app.models import TranscriptSegment


class PassthroughAlignmentBackend(AlignmentBackend):
    """Use ASR-provided timestamps as the alignment result."""

    def align(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        return list(segments)

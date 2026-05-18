"""Baseline alignment backend that preserves existing timing information."""

from __future__ import annotations

from typing import List

from transcribe_doc.alignment.base import AlignmentBackend
from transcribe_doc.app.models import TranscriptSegment


class PassthroughAlignmentBackend(AlignmentBackend):
    """Use ASR-provided timestamps as the alignment result."""

    def align(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        return list(segments)

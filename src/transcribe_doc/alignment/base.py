"""Base contracts for timestamp alignment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from transcribe_doc.app.models import TranscriptSegment


class AlignmentBackend(ABC):
    """Contract for refining transcript timestamps."""

    @abstractmethod
    def align(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        """Return timestamp-refined transcript segments."""

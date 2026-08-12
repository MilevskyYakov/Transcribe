"""Base contracts for speaker diarization."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from mnema.app.models import TranscriptSegment


class DiarizationBackend(ABC):
    """Contract for assigning speaker labels to transcript segments."""

    @abstractmethod
    def diarize(self, media_path: str, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        """Return speaker-labeled transcript segments."""

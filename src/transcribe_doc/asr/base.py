"""Base contracts for transcription backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from transcribe_doc.app.models import TranscriptSegment


@dataclass(frozen=True)
class AsrTranscription:
    """Raw ASR output before alignment/diarization cleanup."""

    segments: List[TranscriptSegment]
    detected_language: Optional[str] = None


class AsrBackend(ABC):
    """Contract for any transcription backend."""

    name: str

    @abstractmethod
    def transcribe(self, media_path: str) -> AsrTranscription:
        """Return raw transcript data for a media file."""

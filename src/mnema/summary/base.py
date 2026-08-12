"""Base contracts for transcript summarization."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from mnema.app.models import TranscriptSegment


class SummaryBackend(ABC):
    """Contract for generating summary artifacts."""

    @abstractmethod
    def summarize(self, segments: List[TranscriptSegment]) -> str:
        """Return a summary string for the transcript."""

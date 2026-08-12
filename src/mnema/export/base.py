"""Base contracts for transcript exporters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from mnema.app.models import TranscriptSegment


class Exporter(ABC):
    """Contract for writing transcript artifacts to disk."""

    format_name: str

    @abstractmethod
    def export(self, output_path: Path, segments: Iterable[TranscriptSegment]) -> Path:
        """Write the artifact and return its path."""

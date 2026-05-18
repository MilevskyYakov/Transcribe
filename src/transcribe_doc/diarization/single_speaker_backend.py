"""Fallback diarization backend for single-speaker labeling."""

from __future__ import annotations

from dataclasses import replace
from typing import List

from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment
from transcribe_doc.diarization.base import DiarizationBackend


class SingleSpeakerDiarizationBackend(DiarizationBackend):
    """Assign all segments to a single stable speaker label."""

    def diarize(self, media_path: str, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        machine_label = "SPEAKER_00"
        mapping = SpeakerMapping(
            machine_label=machine_label,
            display_label=machine_label,
            confidence=1.0,
            metadata={
                "backend": "single_speaker",
                "strategy": "uniform_label",
            },
        )
        return [
            replace(segment, speaker_label=machine_label, mapping=mapping)
            for segment in segments
        ]

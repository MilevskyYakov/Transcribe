"""Heuristic fallback diarization for multi-segment conversations."""

from __future__ import annotations

from dataclasses import replace
from typing import List

from mnema.app.models import SpeakerMapping, TranscriptSegment
from mnema.diarization.base import DiarizationBackend


class HeuristicMultiSpeakerDiarizationBackend(DiarizationBackend):
    """Alternate speaker labels across segments as a lightweight fallback."""

    def __init__(self, num_speakers: int = 2) -> None:
        self._num_speakers = max(2, num_speakers)

    def diarize(self, media_path: str, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        diarized_segments: List[TranscriptSegment] = []
        for index, segment in enumerate(segments):
            machine_label = f"SPEAKER_{index % self._num_speakers:02d}"
            diarized_segments.append(
                replace(
                    segment,
                    speaker_label=machine_label,
                    mapping=SpeakerMapping(
                        machine_label=machine_label,
                        display_label=machine_label,
                        confidence=0.6,
                        metadata={
                            "backend": "heuristic_multi_speaker",
                            "strategy": "alternating_index",
                            "speaker_index": index % self._num_speakers,
                        },
                    ),
                )
            )
        return diarized_segments

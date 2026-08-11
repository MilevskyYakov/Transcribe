"""Orchestration service for ASR, alignment, diarization, and cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from transcribe_doc.alignment.base import AlignmentBackend
from transcribe_doc.app.models import TranscriptSegment
from transcribe_doc.asr.base import AsrBackend
from transcribe_doc.diarization.base import DiarizationBackend
from transcribe_doc.postprocess.segmenter import split_segments_on_long_pauses
from transcribe_doc.postprocess.transcript_cleaner import apply_conservative_cleanup
from transcribe_doc.postprocess.word_quality import apply_word_quality_checks


@dataclass(frozen=True)
class TranscriptionResult:
    """Transcript segments plus non-fatal pipeline warnings."""

    segments: List[TranscriptSegment]
    warnings: List[str]
    detected_language: Optional[str] = None


class TranscriptionService:
    """Run the current transcript pipeline with graceful degradation."""

    def __init__(
        self,
        asr_backend: AsrBackend,
        alignment_backend: Optional[AlignmentBackend] = None,
        diarization_backend: Optional[DiarizationBackend] = None,
    ) -> None:
        self._asr_backend = asr_backend
        self._alignment_backend = alignment_backend
        self._diarization_backend = diarization_backend

    def transcribe(self, media_path: str) -> TranscriptionResult:
        warnings: List[str] = []
        asr_result = self._asr_backend.transcribe(media_path)
        segments = asr_result.segments

        if self._alignment_backend is not None:
            try:
                segments = self._alignment_backend.align(segments)
            except Exception as error:  # noqa: BLE001
                warnings.append(f"Alignment fallback activated: {error}")

        segments = split_segments_on_long_pauses(segments)

        if self._diarization_backend is not None:
            try:
                segments = self._diarization_backend.diarize(media_path, segments)
            except Exception as error:  # noqa: BLE001
                warnings.append(f"Diarization fallback activated: {error}")

        segments = apply_word_quality_checks(segments)
        cleaned_segments = apply_conservative_cleanup(segments)
        return TranscriptionResult(
            segments=cleaned_segments,
            warnings=warnings,
            detected_language=asr_result.detected_language,
        )

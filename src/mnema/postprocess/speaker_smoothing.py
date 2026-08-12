"""Safe speaker-turn smoothing for obvious diarization glitches."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, List

from mnema.app.models import SpeakerMapping, TranscriptSegment

_MAX_SHORT_TURN_SECONDS = 0.9
_LOW_MARGIN_THRESHOLD = 0.10


def smooth_speaker_turns(
    segments: Iterable[TranscriptSegment],
) -> List[TranscriptSegment]:
    """Repair short low-confidence A-B-A speaker flips."""
    smoothed = list(segments)
    for index in range(1, len(smoothed) - 1):
        previous = smoothed[index - 1]
        current = smoothed[index]
        following = smoothed[index + 1]
        if not _is_safe_aba_repair(previous, current, following):
            continue

        target_label = previous.speaker_label
        if not target_label:
            continue

        smoothed[index] = replace(
            current,
            speaker_label=target_label,
            mapping=_smoothed_mapping(current.mapping, target_label),
        )
    return smoothed


def _is_safe_aba_repair(
    previous: TranscriptSegment,
    current: TranscriptSegment,
    following: TranscriptSegment,
) -> bool:
    if not previous.speaker_label or not current.speaker_label or not following.speaker_label:
        return False
    if previous.speaker_label != following.speaker_label:
        return False
    if current.speaker_label == previous.speaker_label:
        return False
    duration = current.end_seconds - current.start_seconds
    return duration <= _MAX_SHORT_TURN_SECONDS and _margin(current) < _LOW_MARGIN_THRESHOLD


def _margin(segment: TranscriptSegment) -> float:
    value = None
    if segment.mapping is not None:
        value = segment.mapping.metadata.get("centroid_similarity_margin")
    return value if isinstance(value, (int, float)) else 1.0


def _smoothed_mapping(
    mapping: SpeakerMapping | None,
    display_label: str,
) -> SpeakerMapping:
    metadata = dict(mapping.metadata) if mapping is not None else {}
    metadata["speaker_smoothing_reason"] = "short_low_confidence_aba"
    metadata["speaker_smoothing_target"] = display_label
    if mapping is None:
        return SpeakerMapping(
            machine_label=display_label,
            display_label=display_label,
            confidence=None,
            metadata=metadata,
        )
    return replace(mapping, display_label=display_label, metadata=metadata)

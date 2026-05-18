"""Helpers for manifest-driven speaker label mapping."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List

from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment


def apply_expected_speaker_mapping(
    segments: List[TranscriptSegment],
    manifest: Dict[str, Any],
) -> List[TranscriptSegment]:
    """Map machine labels to expected speaker names when confidence is unambiguous."""
    expected_speakers = manifest.get("expected_speakers", [])
    if not isinstance(expected_speakers, list) or not expected_speakers:
        return list(segments)

    if len(expected_speakers) == 1:
        expected_speaker = expected_speakers[0]
        if not isinstance(expected_speaker, dict):
            return list(segments)

        display_label = expected_speaker.get("name")
        if not isinstance(display_label, str) or not display_label.strip():
            return list(segments)

        mapped_segments: List[TranscriptSegment] = []
        for segment in segments:
            machine_label = (
                segment.mapping.machine_label
                if segment.mapping is not None
                else segment.speaker_label or "SPEAKER_00"
            )
            mapped_segments.append(
                replace(
                    segment,
                    speaker_label=display_label,
                    mapping=SpeakerMapping(
                        machine_label=machine_label,
                        display_label=display_label,
                        confidence=1.0,
                        metadata=_mapped_metadata(segment.mapping),
                    ),
                )
            )
        return mapped_segments

    normalized_names: List[str] = []
    for speaker in expected_speakers:
        if not isinstance(speaker, dict):
            return list(segments)
        name = speaker.get("name")
        if not isinstance(name, str) or not name.strip():
            return list(segments)
        normalized_names.append(name)

    machine_labels_in_order: List[str] = []
    for segment in segments:
        machine_label_optional = (
            segment.mapping.machine_label
            if segment.mapping is not None
            else segment.speaker_label
        )
        if machine_label_optional is None:
            return list(segments)
        if machine_label_optional not in machine_labels_in_order:
            machine_labels_in_order.append(machine_label_optional)

    if len(machine_labels_in_order) != len(normalized_names):
        return list(segments)

    label_mapping = dict(zip(machine_labels_in_order, normalized_names))
    mapped_segments_multi: List[TranscriptSegment] = []
    for segment in segments:
        machine_label = (
            segment.mapping.machine_label
            if segment.mapping is not None
            else segment.speaker_label or "SPEAKER_00"
        )
        display_label = label_mapping[machine_label]
        mapped_segments_multi.append(
            replace(
                segment,
                speaker_label=display_label,
                mapping=SpeakerMapping(
                    machine_label=machine_label,
                    display_label=display_label,
                    confidence=1.0,
                    metadata=_mapped_metadata(segment.mapping),
                ),
            )
        )
    return mapped_segments_multi


def _mapped_metadata(mapping: SpeakerMapping | None) -> Dict[str, Any]:
    metadata = dict(mapping.metadata) if mapping is not None else {}
    metadata["display_label_source"] = "expected_speaker_manifest"
    return metadata

"""Speaker review helpers for manual display-name assignment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mnema.app.models import SpeakerMapping, TranscriptSegment
from mnema.service.types import JsonObject


@dataclass(frozen=True)
class SpeakerReviewGroup:
    machine_label: str
    fallback_label: str
    display_label: str
    example: str
    suggestions: list[str]

    def to_payload(self) -> JsonObject:
        return {
            "machine_label": self.machine_label,
            "fallback_label": self.fallback_label,
            "display_label": self.display_label,
            "example": self.example,
            "suggestions": self.suggestions,
        }


def build_speaker_review_payload(job: JsonObject, segments: list[JsonObject]) -> JsonObject:
    metadata = _metadata(job)
    confidence = metadata.get("diarization_confidence")
    if isinstance(confidence, dict) and confidence.get("mode") == "transcript_without_labels":
        return {"status": "not_required", "groups": [], "suggestions": []}
    groups = build_speaker_groups(job, segments)
    raw_review = metadata.get("speaker_review")
    review = raw_review if isinstance(raw_review, dict) else {}
    status = str(review.get("status") or ("pending" if groups else "not_required"))
    return {
        "status": status,
        "groups": [group.to_payload() for group in groups],
        "suggestions": _speaker_suggestions(job),
    }


def build_speaker_groups(job: JsonObject, segments: list[JsonObject]) -> list[SpeakerReviewGroup]:
    confidence = _metadata(job).get("diarization_confidence")
    if isinstance(confidence, dict) and confidence.get("mode") == "transcript_without_labels":
        return []
    assignments = speaker_assignments(job)
    suggestions = _speaker_suggestions(job)
    ordered_labels: list[str] = []
    examples: dict[str, str] = {}
    existing_display_labels: dict[str, str] = {}
    for segment in segments:
        label = _machine_label_from_segment_payload(segment)
        if not label:
            continue
        if label not in ordered_labels:
            ordered_labels.append(label)
        existing_display_label = _display_label_from_segment_payload(segment)
        if existing_display_label and not _is_machine_label(existing_display_label):
            existing_display_labels.setdefault(label, existing_display_label)
        if label not in examples:
            text = _segment_text(segment)
            if text:
                examples[label] = text
    return [
        SpeakerReviewGroup(
            machine_label=label,
            fallback_label=fallback_speaker_label(index),
            display_label=assignments.get(label)
            or existing_display_labels.get(label)
            or fallback_speaker_label(index),
            example=examples.get(label, ""),
            suggestions=suggestions,
        )
        for index, label in enumerate(ordered_labels, start=1)
    ]


def update_speaker_assignments(
    job: JsonObject,
    segments: list[JsonObject],
    assignments: dict[str, str],
    *,
    skipped: bool = False,
) -> JsonObject:
    groups = build_speaker_groups(job, segments)
    allowed_labels = {group.machine_label for group in groups}
    clean_assignments = {
        str(machine_label): str(display_label).strip()
        for machine_label, display_label in assignments.items()
        if str(machine_label) in allowed_labels and str(display_label).strip()
    }
    metadata = _metadata(job)
    metadata["speaker_assignments"] = clean_assignments
    metadata["speaker_review"] = {
        "status": "skipped" if skipped else "confirmed",
        "required": bool(groups),
    }
    job["metadata"] = metadata
    return build_speaker_review_payload(job, segments)


def speaker_assignments(job: JsonObject) -> dict[str, str]:
    metadata = _metadata(job)
    raw = metadata.get("speaker_assignments")
    if not isinstance(raw, dict):
        return {}
    return {
        str(machine_label): str(display_label).strip()
        for machine_label, display_label in raw.items()
        if str(machine_label).strip() and str(display_label).strip()
    }


def apply_speaker_assignments_to_segment_payloads(
    job: JsonObject,
    segments: list[JsonObject],
) -> list[JsonObject]:
    groups = build_speaker_groups(job, segments)
    display_by_machine = {group.machine_label: group.display_label for group in groups}
    result: list[JsonObject] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        item = dict(segment)
        machine_label = _machine_label_from_segment_payload(item)
        if machine_label and machine_label in display_by_machine:
            item["speaker_label"] = display_by_machine[machine_label]
            raw_mapping = item.get("mapping")
            mapping = raw_mapping if isinstance(raw_mapping, dict) else {}
            item["mapping"] = {
                **mapping,
                "machine_label": machine_label,
                "display_label": display_by_machine[machine_label],
            }
        result.append(item)
    return result


def apply_speaker_assignments_to_segments(
    job: JsonObject,
    segments: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    payloads = [_segment_to_minimal_payload(segment) for segment in segments]
    groups = build_speaker_groups(job, payloads)
    display_by_machine = {group.machine_label: group.display_label for group in groups}
    result: list[TranscriptSegment] = []
    for segment in segments:
        machine_label = segment.mapping.machine_label if segment.mapping else segment.speaker_label
        if machine_label and machine_label in display_by_machine:
            display_label = display_by_machine[machine_label]
            result.append(
                TranscriptSegment(
                    segment_id=segment.segment_id,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    text_raw=segment.text_raw,
                    text_clean=segment.text_clean,
                    speaker_label=display_label,
                    words=segment.words,
                    mapping=SpeakerMapping(machine_label=machine_label, display_label=display_label),
                )
            )
        else:
            result.append(segment)
    return result


def fallback_speaker_label(index: int) -> str:
    return f"Спикер {index}"


def _speaker_suggestions(job: JsonObject) -> list[str]:
    metadata = _metadata(job)
    manifest = metadata.get("speaker_manifest")
    if not isinstance(manifest, dict):
        return []
    speakers = manifest.get("expected_speakers")
    if not isinstance(speakers, list):
        return []
    suggestions: list[str] = []
    for speaker in speakers:
        if not isinstance(speaker, dict):
            continue
        name = speaker.get("name")
        if isinstance(name, str) and name.strip() and name.strip() not in suggestions:
            suggestions.append(name.strip())
    return suggestions


def _machine_label_from_segment_payload(segment: JsonObject) -> str | None:
    mapping = segment.get("mapping")
    if isinstance(mapping, dict):
        machine_label = _string_or_none(mapping.get("machine_label"))
        if machine_label:
            return machine_label
    return _string_or_none(segment.get("speaker_label"))


def _display_label_from_segment_payload(segment: JsonObject) -> str | None:
    mapping = segment.get("mapping")
    if isinstance(mapping, dict):
        display_label = _string_or_none(mapping.get("display_label"))
        if display_label:
            return display_label
    return _string_or_none(segment.get("speaker_label"))


def _is_machine_label(label: str) -> bool:
    return label.startswith("SPEAKER_")


def _segment_text(segment: JsonObject) -> str:
    return _string_or_none(segment.get("text_clean")) or _string_or_none(segment.get("text_raw")) or ""


def _segment_to_minimal_payload(segment: TranscriptSegment) -> JsonObject:
    payload: JsonObject = {
        "segment_id": segment.segment_id,
        "start_seconds": segment.start_seconds,
        "end_seconds": segment.end_seconds,
        "text_raw": segment.text_raw,
        "text_clean": segment.text_clean,
        "speaker_label": segment.speaker_label,
    }
    if segment.mapping is not None:
        payload["mapping"] = {
            "machine_label": segment.mapping.machine_label,
            "display_label": segment.mapping.display_label,
        }
    return payload


def _metadata(job: JsonObject) -> JsonObject:
    metadata = job.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _string_or_none(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None

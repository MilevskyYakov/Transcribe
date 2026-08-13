"""Persistence helpers for job metadata and artifact snapshots."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TypeGuard, cast
from uuid import uuid4

from mnema.app.config import AppConfig
from mnema.app.models import Job, TranscriptSegment
from mnema.asr.transcription_service import TranscriptionResult

JsonObject = dict[str, Any]
JOB_STATE_LOCK = threading.RLock()


def save_job(job: Job, destination: Path) -> None:
    """Persist job metadata to JSON."""
    write_job_payload(destination, _normalize(asdict(job)))


def mutate_job_payload(
    destination: Path,
    mutation: Callable[[JsonObject], None],
) -> JsonObject | None:
    """Apply one serialized read-modify-write operation to job metadata."""
    with JOB_STATE_LOCK:
        try:
            payload = json.loads(destination.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        mutation(payload)
        _write_json(destination, payload)
        return payload


def write_job_payload(destination: Path, payload: JsonObject) -> None:
    """Atomically replace job metadata under the shared job-state lock."""
    with JOB_STATE_LOCK:
        _write_json(destination, payload)


def save_config_snapshot(config: AppConfig, destination: Path) -> None:
    """Persist the resolved config to JSON for later inspection."""
    _write_json(destination, config.to_dict())


def save_transcription_result(result: TranscriptionResult, destination: Path) -> None:
    """Persist raw transcription result for later stages and debugging."""
    _write_json(
        destination,
        {
            "segments": _normalize(result.segments),
            "warnings": _normalize(result.warnings),
            "detected_language": _normalize(result.detected_language),
        },
    )


def save_segments(segments: list[TranscriptSegment], destination: Path) -> None:
    """Persist normalized segments as a standalone artifact."""
    _write_json(destination, _normalize(segments))


def save_words(segments: list[TranscriptSegment], destination: Path) -> None:
    """Persist flattened word-level timestamps for downstream tooling."""
    words_payload = []
    for segment in segments:
        for word in segment.words:
            words_payload.append(
                {
                    "segment_id": segment.segment_id,
                    "speaker_label": segment.speaker_label,
                    "text": word.text,
                    "text_clean": word.text_clean,
                    "confidence": word.confidence,
                    "issues": _normalize(word.issues),
                    "start_seconds": word.start_seconds,
                    "end_seconds": word.end_seconds,
                }
            )
    _write_json(destination, words_payload)


def _write_json(destination: Path, payload: Any) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f".{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(destination)


def _normalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if _is_dataclass_instance(value):
        return _normalize(asdict(cast(Any, value)))
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def _is_dataclass_instance(value: Any) -> TypeGuard[object]:
    return is_dataclass(value) and not isinstance(value, type)

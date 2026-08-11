"""Canonical local API response contracts.

This module is the single Python boundary for JSON payloads returned by the
local desktop API. Route handlers and persistence helpers should construct
responses through these models/helpers instead of assembling endpoint-specific
ad-hoc dictionaries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, Literal

from transcribe_doc.app.models import ArtifactManifest, Job
from transcribe_doc.service.types import JsonObject

ModelStatusValue = Literal[
    "unknown", "missing", "queued", "downloading", "ready", "corrupt", "error"
]
EventStatusValue = Literal["ok", "warning", "error"]


def dataclass_payload(value: Any) -> JsonObject:
    """Serialize a dataclass contract while omitting optional ``None`` fields."""
    if not is_dataclass(value):
        raise TypeError(f"Expected dataclass contract, got {type(value).__name__}")
    payload: JsonObject = {}
    for contract_field in fields(value):
        field_value = getattr(value, contract_field.name)
        if field_value is None:
            continue
        payload[contract_field.name] = json_value(field_value)
    return payload


def json_value(value: Any) -> Any:
    if is_dataclass(value):
        return dataclass_payload(value)
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class MediaToolStatusResponse:
    available: bool
    path: str | None = None


@dataclass(frozen=True)
class AppPathsResponse:
    output_dir: str
    temp_dir: str
    cache_dir: str
    model_dir: str | None = None


@dataclass(frozen=True)
class MediaToolsResponse:
    ffmpeg: MediaToolStatusResponse
    ffprobe: MediaToolStatusResponse


@dataclass(frozen=True)
class HealthResponse:
    status: str
    app: AppPathsResponse
    media_tools: MediaToolsResponse


@dataclass(frozen=True)
class DiarizationQualityResponse:
    detected_cluster_count_max: int | None = None
    min_centroid_similarity_margin: float | None = None
    dominant_cluster_share: float | None = None
    unmapped_segment_count: int | None = None
    speaker_switch_count: int | None = None
    total_segment_count: int | None = None


@dataclass(frozen=True)
class DiarizationConfidenceResponse:
    version: int
    mode: str
    reason_codes: list[str]
    metrics: JsonObject
    thresholds: JsonObject


@dataclass(frozen=True)
class JobMetadataResponse:
    display_title: str | None = None
    title: str | None = None
    source_filename: str | None = None
    execution: str | None = None
    current_stage: str | None = None
    last_message: str | None = None
    progress: int | float | None = None
    events: list[JsonObject] | None = None
    diarization_quality: DiarizationQualityResponse | None = None
    diarization_confidence: DiarizationConfidenceResponse | None = None
    extra: JsonObject = field(default_factory=dict)

    def to_payload(self) -> JsonObject:
        payload = dataclass_payload(self)
        extra = payload.pop("extra", {})
        if isinstance(extra, dict):
            payload.update(extra)
        return payload


@dataclass(frozen=True)
class JobResponse:
    job_id: str
    source_paths: list[str]
    status: str
    detected_language: str | None
    artifacts: JsonObject
    metadata: JobMetadataResponse
    warnings: list[str]

    def to_payload(self) -> JsonObject:
        payload = dataclass_payload(self)
        payload["metadata"] = self.metadata.to_payload()
        return payload


@dataclass(frozen=True)
class TranscriptResponse:
    job: JsonObject | None
    segments: list[JsonObject]
    words: list[JsonObject]


@dataclass(frozen=True)
class ArtifactResponse:
    name: str
    filename: str
    size_bytes: int
    download_url: str


@dataclass(frozen=True)
class ArtifactsResponse:
    artifacts: list[JsonObject]


@dataclass(frozen=True)
class JobEventResponse:
    timestamp: str
    stage: str
    status: EventStatusValue | str
    message: str
    progress: int | float


@dataclass(frozen=True)
class EventsResponse:
    events: list[JsonObject]


@dataclass(frozen=True)
class ModelStatusResponse:
    name: str
    status: ModelStatusValue | str
    label: str | None = None
    backend: str | None = None
    language: str | None = None
    description: str | None = None
    path: str | None = None
    size_bytes: int | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    progress: int | float | None = None
    message: str | None = None
    updated_at: str | None = None
    stale_download: bool | None = None
    runtime_name: str | None = None
    queue_position: int | None = None


@dataclass(frozen=True)
class ModelsResponse:
    current_model: str
    models: list[ModelStatusResponse]


def metadata_from_payload(payload: JsonObject) -> JobMetadataResponse:
    known_keys = {field.name for field in fields(JobMetadataResponse)} - {"extra"}
    quality = payload.get("diarization_quality")
    confidence = payload.get("diarization_confidence")
    extra = {key: value for key, value in payload.items() if key not in known_keys}
    return JobMetadataResponse(
        display_title=string_or_none(payload.get("display_title")),
        title=string_or_none(payload.get("title")),
        source_filename=string_or_none(payload.get("source_filename")),
        execution=string_or_none(payload.get("execution")),
        current_stage=string_or_none(payload.get("current_stage")),
        last_message=string_or_none(payload.get("last_message")),
        progress=number_or_none(payload.get("progress")),
        events=payload.get("events") if isinstance(payload.get("events"), list) else None,
        diarization_quality=diarization_quality_from_payload(quality)
        if isinstance(quality, dict)
        else None,
        diarization_confidence=diarization_confidence_from_payload(confidence)
        if isinstance(confidence, dict)
        else None,
        extra=extra,
    )


def diarization_quality_from_payload(payload: JsonObject) -> DiarizationQualityResponse:
    return DiarizationQualityResponse(
        detected_cluster_count_max=int_or_none(payload.get("detected_cluster_count_max")),
        min_centroid_similarity_margin=float_or_none(payload.get("min_centroid_similarity_margin")),
        dominant_cluster_share=float_or_none(payload.get("dominant_cluster_share")),
        unmapped_segment_count=int_or_none(payload.get("unmapped_segment_count")),
        speaker_switch_count=int_or_none(payload.get("speaker_switch_count")),
        total_segment_count=int_or_none(payload.get("total_segment_count")),
    )


def diarization_confidence_from_payload(payload: JsonObject) -> DiarizationConfidenceResponse:
    metrics = payload.get("metrics")
    thresholds = payload.get("thresholds")
    reason_codes = payload.get("reason_codes")
    return DiarizationConfidenceResponse(
        version=int(payload.get("version") or 1),
        mode=str(payload.get("mode") or "transcript_without_labels"),
        reason_codes=[str(code) for code in reason_codes] if isinstance(reason_codes, list) else [],
        metrics=metrics if isinstance(metrics, dict) else {},
        thresholds=thresholds if isinstance(thresholds, dict) else {},
    )


def job_response(job: Job | JsonObject) -> JobResponse:
    if isinstance(job, dict):
        raw_metadata = job.get("metadata")
        metadata: JsonObject = raw_metadata if isinstance(raw_metadata, dict) else {}
        raw_artifacts = job.get("artifacts")
        artifacts: JsonObject = raw_artifacts if isinstance(raw_artifacts, dict) else {}
        return JobResponse(
            job_id=str(job.get("job_id") or ""),
            source_paths=[str(path) for path in job.get("source_paths", [])]
            if isinstance(job.get("source_paths"), list)
            else [],
            status=str(job.get("status") or "queued"),
            detected_language=string_or_none(job.get("detected_language")),
            artifacts=artifacts,
            metadata=metadata_from_payload(metadata),
            warnings=[str(warning) for warning in job.get("warnings", [])]
            if isinstance(job.get("warnings"), list)
            else [],
        )
    artifacts = (
        asdict(job.artifacts)
        if isinstance(job.artifacts, ArtifactManifest)
        else json_value(job.artifacts)
    )
    return JobResponse(
        job_id=job.job_id,
        source_paths=job.source_paths,
        status=job.status.value,
        detected_language=job.detected_language,
        artifacts=artifacts,
        metadata=metadata_from_payload(job.metadata),
        warnings=job.warnings,
    )


def model_status_response(payload: JsonObject) -> ModelStatusResponse:
    return ModelStatusResponse(
        name=str(payload.get("name") or ""),
        status=str(payload.get("status") or "unknown"),
        label=string_or_none(payload.get("label")),
        backend=string_or_none(payload.get("backend")),
        language=string_or_none(payload.get("language")),
        description=string_or_none(payload.get("description")),
        path=string_or_none(payload.get("path")),
        size_bytes=int_or_none(payload.get("size_bytes")),
        downloaded_bytes=int_or_none(payload.get("downloaded_bytes")),
        total_bytes=int_or_none(payload.get("total_bytes")),
        progress=number_or_none(payload.get("progress")),
        message=string_or_none(payload.get("message")),
        updated_at=string_or_none(payload.get("updated_at")),
        stale_download=bool_or_none(payload.get("stale_download")),
        runtime_name=string_or_none(payload.get("runtime_name")),
        queue_position=int_or_none(payload.get("queue_position")),
    )


def event_response(payload: JsonObject) -> JobEventResponse:
    return JobEventResponse(
        timestamp=str(payload.get("timestamp") or ""),
        stage=str(payload.get("stage") or ""),
        status=str(payload.get("status") or "ok"),
        message=str(payload.get("message") or ""),
        progress=number_or_none(payload.get("progress")) or 0,
    )


def string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def number_or_none(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def float_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

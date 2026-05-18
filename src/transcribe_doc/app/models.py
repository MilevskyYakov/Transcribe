"""Core runtime data contracts for jobs and transcripts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class JobStatus(str, Enum):
    """Lifecycle states supported by the MVP design."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED_PARTIAL = "failed_partial"
    FAILED = "failed"


@dataclass(frozen=True)
class WordToken:
    """Word-level timing token."""

    text: str
    start_seconds: float
    end_seconds: float
    text_clean: Optional[str] = None
    confidence: Optional[float] = None
    issues: List[Dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class SpeakerMapping:
    """Mapping from machine label to display label."""

    machine_label: str
    display_label: str
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TranscriptSegment:
    """Normalized transcript segment shared by exporters and services."""

    segment_id: str
    start_seconds: float
    end_seconds: float
    text_raw: str
    text_clean: str
    speaker_label: Optional[str] = None
    words: List[WordToken] = field(default_factory=list)
    mapping: Optional[SpeakerMapping] = None


@dataclass(frozen=True)
class ArtifactManifest:
    """Filesystem pointers to generated outputs and intermediate artifacts."""

    extracted_audio: Optional[str] = None
    normalized_audio: Optional[str] = None
    raw_transcript: Optional[str] = None
    segments_json: Optional[str] = None
    words_json: Optional[str] = None
    transcript_clean_txt: Optional[str] = None
    transcript_clean_md: Optional[str] = None
    final_speech_text_md: Optional[str] = None
    transcript_clean_docx: Optional[str] = None
    transcript_clean_pdf: Optional[str] = None
    subtitles_srt: Optional[str] = None
    summary_md: Optional[str] = None
    summary_json: Optional[str] = None
    aligned_transcript: Optional[str] = None
    diarization_dump: Optional[str] = None
    events_jsonl: Optional[str] = None
    merged_transcript: Optional[str] = None
    log_file: Optional[str] = None
    config_snapshot: Optional[str] = None


@dataclass
class Job:
    """Persistent job metadata shared across CLI and service layers."""

    job_id: str
    source_paths: List[str]
    status: JobStatus = JobStatus.QUEUED
    detected_language: Optional[str] = None
    artifacts: ArtifactManifest = field(default_factory=ArtifactManifest)
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

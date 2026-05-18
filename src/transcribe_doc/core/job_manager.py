"""Create and update job metadata for local processing."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from transcribe_doc.app.config import AppConfig
from transcribe_doc.app.models import ArtifactManifest, Job, JobStatus
from transcribe_doc.storage.artifact_store import save_config_snapshot, save_job
from transcribe_doc.storage.paths import JobPaths, build_job_paths


def create_job(
    source_path: Path | str,
    output_root: Path | str,
    config: AppConfig,
    job_id: str | None = None,
    display_title: str | None = None,
) -> tuple[Job, JobPaths]:
    """Create a new job workspace and persist initial metadata."""
    resolved_job_id = job_id or _generate_job_id()
    resolved_source = Path(source_path).expanduser().resolve()
    source_filename = resolved_source.name
    title = _resolve_display_title(resolved_source, display_title)
    job_paths = build_job_paths(output_root, resolved_job_id)
    job_paths.log_file.touch(exist_ok=True)
    save_config_snapshot(config, job_paths.config_snapshot)

    job = Job(
        job_id=resolved_job_id,
        source_paths=[str(resolved_source)],
        status=JobStatus.QUEUED,
        artifacts=ArtifactManifest(
            extracted_audio=str(job_paths.extracted_audio),
            normalized_audio=str(job_paths.normalized_audio),
            raw_transcript=str(job_paths.transcript_raw_json),
            segments_json=str(job_paths.segments_json),
            words_json=str(job_paths.words_json),
            transcript_clean_txt=str(job_paths.transcript_clean_txt),
            transcript_clean_md=str(job_paths.transcript_clean_md),
            final_speech_text_md=str(job_paths.final_speech_text_md),
            transcript_clean_docx=str(job_paths.transcript_clean_docx),
            transcript_clean_pdf=str(job_paths.transcript_clean_pdf),
            subtitles_srt=str(job_paths.subtitles_srt),
            summary_md=str(job_paths.summary_md),
            summary_json=str(job_paths.summary_json),
            diarization_dump=str(job_paths.diarization_dump),
            events_jsonl=str(job_paths.events_jsonl),
            log_file=str(job_paths.log_file),
            config_snapshot=str(job_paths.config_snapshot),
        ),
        metadata={
            "display_title": title,
            "source_filename": source_filename,
        },
    )
    save_job(job, job_paths.job_json)
    return job, job_paths


def persist_job(job: Job, job_paths: JobPaths) -> None:
    """Write the latest job state to disk."""
    save_job(job, job_paths.job_json)


def append_job_event(
    job: Job,
    job_paths: JobPaths,
    *,
    stage: str,
    status: str,
    message: str,
    progress: int,
) -> None:
    """Append a structured event and mirror latest progress into job metadata."""
    event = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "stage": stage,
        "status": status,
        "message": message,
        "progress": progress,
    }
    events = job.metadata.setdefault("events", [])
    if isinstance(events, list):
        events.append(event)
        job.metadata["events"] = events[-80:]
    job.metadata["current_stage"] = stage
    job.metadata["progress"] = progress
    job.metadata["last_message"] = message
    job_paths.events_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with job_paths.events_jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    with job_paths.log_file.open("a", encoding="utf-8") as handle:
        handle.write(
            f"{event['timestamp']} [{status}] {stage} {progress}% - {message}\n"
        )
    persist_job(job, job_paths)


def _generate_job_id() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"job-{timestamp}-{uuid4().hex[:8]}"


def _resolve_display_title(source_path: Path, display_title: str | None) -> str:
    title = display_title.strip() if display_title else ""
    if title:
        return title
    return source_path.stem or source_path.name

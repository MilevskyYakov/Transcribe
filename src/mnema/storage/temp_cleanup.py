"""Safe cleanup for temporary media managed by the local service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from mnema.service.types import JsonObject
from mnema.storage.artifact_store import mutate_job_payload

DEFAULT_TEMP_RETENTION_DAYS = 7

# Compact durable artifacts are required for app history, transcript viewing, and
# re-saving user-visible outputs. Everything else below is a job/session
# intermediate or diagnostic snapshot that can be removed after a successful job.
DURABLE_USER_ARTIFACTS = frozenset(
    {
        "segments_json",
        "words_json",
        "transcript_clean_txt",
        "transcript_clean_md",
        "final_speech_text_md",
        "transcript_clean_docx",
        "transcript_clean_pdf",
        "subtitles_srt",
        "summary_md",
        "summary_json",
    }
)
SUCCESS_INTERNAL_ARTIFACTS = frozenset(
    {
        "extracted_audio",
        "normalized_audio",
        "raw_transcript",
        "diarization_dump",
        "events_jsonl",
        "log_file",
        "config_snapshot",
    }
)
MANAGED_MEDIA_ARTIFACTS = ("extracted_audio", "normalized_audio")
STALE_JOB_STATUSES = {"failed", "failed_partial"}


@dataclass
class CleanupReport:
    """Summary of managed temporary files removed by cleanup."""

    removed_files: list[str] = field(default_factory=list)
    freed_bytes: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def removed_count(self) -> int:
        return len(self.removed_files)

    def merge(self, other: "CleanupReport") -> None:
        self.removed_files.extend(other.removed_files)
        self.freed_bytes += other.freed_bytes
        self.errors.extend(other.errors)

    def to_payload(self) -> JsonObject:
        return {
            "removed_files": self.removed_files,
            "removed_count": self.removed_count,
            "freed_bytes": self.freed_bytes,
            "errors": self.errors,
        }


def cleanup_successful_job_media(
    job: JsonObject,
    *,
    output_root: Path,
    job_id: str,
    temp_root: Path,
) -> CleanupReport:
    """Delete job/session intermediates after durable successful outputs exist."""
    job_dir = output_root / job_id
    report = CleanupReport()
    deleted_artifact_fields: list[str] = []
    for field_name, path in _successful_job_cleanup_candidates(job):
        if not _is_managed_temporary_path(path, job_dir=job_dir, temp_root=temp_root):
            continue
        before = report.removed_count
        existed_as_file = path.exists() and path.is_file()
        _delete_file(path, report)
        deleted = report.removed_count > before
        missing_internal_file = not existed_as_file and not path.exists()
        if field_name in SUCCESS_INTERNAL_ARTIFACTS and (deleted or missing_internal_file):
            deleted_artifact_fields.append(field_name)

    artifacts = job.get("artifacts")
    if isinstance(artifacts, dict):
        for field_name in deleted_artifact_fields:
            artifacts[field_name] = None
        job["artifacts"] = artifacts
    _record_cleanup_metadata(job, report, reason="job_success")
    return report


def cleanup_stale_temporary_media(
    *,
    output_root: Path,
    temp_root: Path,
    retention_days: int = DEFAULT_TEMP_RETENTION_DAYS,
) -> CleanupReport:
    """Delete managed failed-job and orphan upload media older than the retention period."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    report = CleanupReport()
    if output_root.exists():
        for job_json in output_root.glob("*/job.json"):
            current_job_json = job_json
            job_report = CleanupReport()

            def cleanup(
                job: JsonObject,
                job_json: Path = current_job_json,
            ) -> None:
                nonlocal job_report
                if str(job.get("status") or "") not in STALE_JOB_STATUSES:
                    return
                job_report = _cleanup_stale_job_media(
                    job,
                    job_json.parent,
                    temp_root,
                    cutoff,
                )
                if job_report.removed_count or job_report.errors:
                    _record_cleanup_metadata(job, job_report, reason="stale_retention")

            mutate_job_payload(current_job_json, cleanup)
            report.merge(job_report)
    report.merge(_cleanup_orphan_uploads(temp_root / "uploads", cutoff))
    return report


def _cleanup_stale_job_media(
    job: JsonObject,
    job_dir: Path,
    temp_root: Path,
    cutoff: datetime,
) -> CleanupReport:
    report = CleanupReport()
    deleted_artifact_fields: list[str] = []
    for field_name, path in _job_media_candidates(job):
        if not _is_managed_temporary_path(path, job_dir=job_dir, temp_root=temp_root):
            continue
        if not _is_older_than(path, cutoff):
            continue
        before = report.removed_count
        _delete_file(path, report)
        if report.removed_count > before and field_name in MANAGED_MEDIA_ARTIFACTS:
            deleted_artifact_fields.append(field_name)
    artifacts = job.get("artifacts")
    if isinstance(artifacts, dict):
        for field_name in deleted_artifact_fields:
            artifacts[field_name] = None
        job["artifacts"] = artifacts
    return report


def _cleanup_orphan_uploads(upload_root: Path, cutoff: datetime) -> CleanupReport:
    report = CleanupReport()
    if not upload_root.exists():
        return report
    for path in upload_root.rglob("*"):
        if path.is_file() and _is_older_than(path, cutoff):
            _delete_file(path, report)
    return report


def _job_media_candidates(job: JsonObject) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    artifacts = job.get("artifacts")
    if isinstance(artifacts, dict):
        for field_name in MANAGED_MEDIA_ARTIFACTS:
            value = artifacts.get(field_name)
            if isinstance(value, str) and value.strip():
                candidates.append((field_name, Path(value)))
    source_paths = job.get("source_paths")
    if isinstance(source_paths, list):
        for value in source_paths:
            if isinstance(value, str) and value.strip():
                candidates.append(("source_paths", Path(value)))
    return candidates


def _successful_job_cleanup_candidates(job: JsonObject) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    artifacts = job.get("artifacts")
    if isinstance(artifacts, dict):
        for field_name in sorted(SUCCESS_INTERNAL_ARTIFACTS):
            value = artifacts.get(field_name)
            if isinstance(value, str) and value.strip():
                candidates.append((field_name, Path(value)))
    source_paths = job.get("source_paths")
    if isinstance(source_paths, list):
        for value in source_paths:
            if isinstance(value, str) and value.strip():
                candidates.append(("source_paths", Path(value)))
    return candidates


def _is_managed_temporary_path(path: Path, *, job_dir: Path, temp_root: Path) -> bool:
    try:
        resolved = path.expanduser().resolve(strict=False)
        resolved_job_dir = job_dir.expanduser().resolve(strict=False)
        resolved_temp_root = temp_root.expanduser().resolve(strict=False)
    except OSError:
        return False
    return _is_relative_to(resolved, resolved_job_dir) or _is_relative_to(resolved, resolved_temp_root)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_older_than(path: Path, cutoff: datetime) -> bool:
    try:
        return datetime.utcfromtimestamp(path.stat().st_mtime) < cutoff
    except OSError:
        return False


def _delete_file(path: Path, report: CleanupReport) -> None:
    try:
        if not path.exists() or not path.is_file():
            return
        size = path.stat().st_size
        path.unlink()
    except OSError as error:
        report.errors.append(f"{path}: {error}")
        return
    report.removed_files.append(str(path))
    report.freed_bytes += size


def _record_cleanup_metadata(job: JsonObject, report: CleanupReport, *, reason: str) -> None:
    metadata = job.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["temp_cleanup"] = {
        "reason": reason,
        "removed_count": report.removed_count,
        "freed_bytes": report.freed_bytes,
        "cleaned_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    if report.errors:
        metadata["temp_cleanup"]["errors"] = report.errors
    job["metadata"] = metadata

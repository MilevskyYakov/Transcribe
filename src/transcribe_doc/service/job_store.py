"""Job persistence, events, and artifact lookup helpers for the local API."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from transcribe_doc.app.models import JobStatus

from .contracts import ArtifactResponse, dataclass_payload, event_response
from .responses import job_to_response
from .types import JsonObject


def list_jobs(output_root: Path) -> list[JsonObject]:
    """Return known jobs in newest-first directory order."""
    if not output_root.exists():
        return []
    jobs = []
    for job_json in sorted(output_root.glob("*/job.json"), reverse=True):
        payload = read_json_file(job_json, None)
        if isinstance(payload, dict):
            jobs.append(job_to_response(payload))
    return jobs


def mark_interrupted_jobs(output_root: Path) -> None:
    """Mark previously active jobs as interrupted when the local service restarts."""
    if not output_root.exists():
        return
    for job_json in output_root.glob("*/job.json"):
        payload = read_json_file(job_json, None)
        if not isinstance(payload, dict) or payload.get("status") not in {"queued", "processing"}:
            continue
        job_id = str(payload.get("job_id") or job_json.parent.name)
        message = "Обработка была прервана перезапуском сервера. Запустите файл заново"
        progress = int(metadata_value(payload, "progress", 0))
        payload["status"] = JobStatus.FAILED.value
        warnings_list = payload.get("warnings")
        if not isinstance(warnings_list, list):
            warnings_list = []
        if message not in warnings_list:
            warnings_list.append(message)
        payload["warnings"] = warnings_list
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        event = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "stage": "interrupted",
            "status": "error",
            "message": message,
            "progress": progress,
        }
        events = metadata.get("events")
        if not isinstance(events, list):
            events = []
        events.append(event)
        metadata["events"] = events[-80:]
        metadata["current_stage"] = "interrupted"
        metadata["last_message"] = message
        metadata["progress"] = progress
        payload["metadata"] = metadata
        write_job_payload(job_json, payload)
        append_event_files(output_root / job_id, event)


def load_job(output_root: Path, job_id: str) -> JsonObject | None:
    """Load one persisted job payload."""
    job_path = output_root / job_id / "job.json"
    payload = read_json_file(job_path, None)
    return payload if isinstance(payload, dict) else None


def metadata_value(payload: JsonObject, key: str, fallback: Any) -> Any:
    metadata = payload.get("metadata")
    return metadata.get(key, fallback) if isinstance(metadata, dict) else fallback


def write_job_payload(job_json: Path, payload: JsonObject) -> None:
    job_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_failed_job_payload(
    output_root: Path,
    job_id: str,
    *,
    input_path: str,
    message: str,
    display_title: str | None = None,
) -> None:
    """Persist a failed job payload through the service persistence helper."""
    job_dir = output_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    payload: JsonObject = {
        "job_id": job_id,
        "source_paths": [input_path],
        "status": JobStatus.FAILED.value,
        "detected_language": None,
        "artifacts": {},
        "metadata": {"display_title": display_title or Path(input_path).stem},
        "warnings": [message],
    }
    write_job_payload(job_dir / "job.json", payload)


def append_event_files(job_dir: Path, event: JsonObject) -> None:
    artifacts_dir = job_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    with (artifacts_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    with (artifacts_dir / "job.log").open("a", encoding="utf-8") as handle:
        handle.write(
            f"{event['timestamp']} [{event['status']}] {event['stage']} {event['progress']}% - {event['message']}\n"
        )


def list_artifacts(output_root: Path, job_id: str) -> list[JsonObject]:
    """List existing artifacts for a job."""
    job = load_job(output_root, job_id)
    if job is None:
        return []
    artifacts = job.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return []
    existing = []
    for label, value in artifacts.items():
        if not value:
            continue
        path = Path(str(value))
        if path.exists() and path.is_file():
            existing.append(
                dataclass_payload(
                    ArtifactResponse(
                        name=label,
                        filename=path.name,
                        size_bytes=path.stat().st_size,
                        download_url=f"/jobs/{job_id}/artifacts/{label}",
                    )
                )
            )
    return existing


def list_events(output_root: Path, job_id: str) -> list[JsonObject]:
    """Load structured job events from events.jsonl with job metadata fallback."""
    events_path = output_root / job_id / "artifacts" / "events.jsonl"
    events: list[JsonObject] = []
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(dataclass_payload(event_response(payload)))
        return events
    job = load_job(output_root, job_id)
    metadata = job.get("metadata", {}) if job else {}
    fallback = metadata.get("events") if isinstance(metadata, dict) else None
    if not isinstance(fallback, list):
        return []
    return [
        dataclass_payload(event_response(event)) for event in fallback if isinstance(event, dict)
    ]


def artifact_by_name(output_root: Path, job_id: str, artifact_name: str) -> Path | None:
    """Resolve an artifact label to a file inside the job workspace."""
    job = load_job(output_root, job_id)
    if job is None:
        return None
    artifacts = job.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return None
    value = artifacts.get(artifact_name)
    if not value:
        return None
    path = Path(str(value)).resolve()
    job_dir = (output_root / job_id).resolve()
    if job_dir not in path.parents and path != job_dir:
        return None
    return path if path.exists() and path.is_file() else None


def read_json_file(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback

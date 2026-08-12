"""Durable batch-session metadata layered over canonical jobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from mnema.ingest.input_resolver import resolve_single_input

from .job_store import list_jobs, load_job
from .types import JsonObject

_ACTIVE_JOB_STATUSES = {"queued", "processing"}
_READY_JOB_STATUSES = {"completed", "completed_with_warnings"}
# ponytail: global lock fits one local user; use per-session locks if throughput matters.
BATCH_SESSION_LOCK = RLock()


def create_batch_session(
    output_root: Path,
    items: list[JsonObject],
    *,
    common_output_dir: str | None,
) -> JsonObject:
    """Persist ordered batch items before any canonical job starts."""
    session_id = _generate_session_id()
    session_items: list[JsonObject] = []
    for position, item in enumerate(items, start=1):
        raw_path = item.get("input_path")
        input_path = None
        if isinstance(raw_path, str) and raw_path.strip():
            input_path = str(resolve_single_input(raw_path).path)
        source_name = str(
            item.get("source_name") or (Path(input_path).name if input_path else "")
        ).strip()
        if not source_name:
            raise ValueError("Each batch item requires 'input_path' or 'source_name'.")
        session_items.append(
            {
                "item_id": f"item-{position}",
                "position": position,
                "input_path": input_path,
                "source_name": source_name,
                "display_title": Path(source_name).stem or source_name,
                "output_dir": None,
                "output_dir_override": None,
                "job_id": None,
                "attempt_job_ids": [],
            }
        )
    if not session_items:
        raise ValueError("'items' must be a non-empty list.")
    payload: JsonObject = {
        "session_id": session_id,
        "created_at": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "common_output_dir": common_output_dir,
        "items": session_items,
    }
    write_batch_session(output_root, payload)
    return batch_session_response(output_root, payload)


def list_batch_sessions(output_root: Path) -> list[JsonObject]:
    root = _sessions_root(output_root)
    if not root.exists():
        return []
    sessions = []
    for path in sorted(root.glob("batch-*.json"), reverse=True):
        payload = _read_session(path)
        if payload is not None:
            sessions.append(batch_session_response(output_root, payload))
    return sessions


def load_batch_session(output_root: Path, session_id: str) -> JsonObject | None:
    payload = _read_session(_session_path(output_root, session_id))
    return batch_session_response(output_root, payload) if payload is not None else None


def load_batch_session_payload(output_root: Path, session_id: str) -> JsonObject | None:
    return _read_session(_session_path(output_root, session_id))


def write_batch_session(output_root: Path, payload: JsonObject) -> None:
    path = _session_path(output_root, str(payload["session_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def reconcile_batch_session_jobs(output_root: Path) -> None:
    """Recover canonical jobs created before their batch link was persisted."""
    linked_jobs: dict[tuple[str, str], list[str]] = {}
    for job in reversed(list_jobs(output_root)):
        metadata = job.get("metadata")
        if not isinstance(metadata, dict):
            continue
        session_id = metadata.get("batch_session_id")
        item_id = metadata.get("batch_item_id")
        if session_id and item_id:
            linked_jobs.setdefault((str(session_id), str(item_id)), []).append(str(job["job_id"]))

    with BATCH_SESSION_LOCK:
        for path in _sessions_root(output_root).glob("*.json"):
            payload = _read_session(path)
            if payload is None:
                continue
            changed = False
            for item in payload.get("items", []):
                attempts = linked_jobs.get((str(payload["session_id"]), str(item["item_id"])), [])
                if attempts and attempts != item.get("attempt_job_ids"):
                    item["attempt_job_ids"] = attempts
                    item["job_id"] = attempts[-1]
                    changed = True
            if changed:
                write_batch_session(output_root, payload)


def batch_session_response(output_root: Path, payload: JsonObject) -> JsonObject:
    items = [_item_response(output_root, item, payload) for item in payload.get("items", [])]
    totals = {
        "total": len(items),
        "configure": sum(item["status"] == "configure" for item in items),
        "processing": sum(item["status"] == "processing" for item in items),
        "ready": sum(item["status"] == "ready" for item in items),
        "failed": sum(item["status"] == "failed" for item in items),
    }
    if totals["configure"] or totals["processing"]:
        status = "active"
    elif totals["failed"]:
        status = "completed_with_errors"
    else:
        status = "completed"
    return {
        "session_id": payload["session_id"],
        "created_at": payload["created_at"],
        "common_output_dir": payload.get("common_output_dir"),
        "status": status,
        "totals": totals,
        "items": items,
    }


def find_batch_item(payload: JsonObject, item_id: str) -> JsonObject | None:
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    return next(
        (item for item in items if isinstance(item, dict) and item.get("item_id") == item_id),
        None,
    )


def _item_response(output_root: Path, item: JsonObject, session: JsonObject) -> JsonObject:
    job_id = item.get("job_id")
    job = load_job(output_root, str(job_id)) if job_id else None
    job_status = str(job.get("status")) if job else None
    if job_status in _ACTIVE_JOB_STATUSES:
        status = "processing"
    elif job_status in _READY_JOB_STATUSES:
        status = "ready"
    elif job_id:
        status = "failed"
    else:
        status = "configure"
    return {
        **item,
        "output_dir_override": item.get("output_dir_override"),
        "output_dir": item.get("output_dir") or session.get("common_output_dir"),
        "status": status,
        "job_status": job_status,
    }


def _sessions_root(output_root: Path) -> Path:
    return output_root / "_batch_sessions"


def _session_path(output_root: Path, session_id: str) -> Path:
    if not session_id.startswith("batch-") or any(part in session_id for part in ("/", "\\", "..")):
        raise ValueError("Invalid batch session id.")
    return _sessions_root(output_root) / f"{session_id}.json"


def _read_session(path: Path) -> JsonObject | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _generate_session_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"batch-{timestamp}-{uuid4().hex[:8]}"

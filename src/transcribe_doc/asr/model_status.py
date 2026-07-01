"""Typed model download/status payloads and status-file persistence."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

ModelStatusValue = Literal["unknown", "missing", "queued", "downloading", "ready", "corrupt", "error"]


@dataclass(frozen=True)
class ModelStatus:
    name: str
    status: ModelStatusValue | str
    label: str | None = None
    backend: str | None = None
    path: str | None = None
    size_bytes: int | None = None
    message: str | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    progress: int | None = None
    updated_at: str | None = None
    runtime_name: str | None = None
    language: str | None = None
    description: str | None = None
    stale_download: bool | None = None
    queue_position: int | None = None

    def to_payload(self, **overrides: Any) -> dict[str, Any]:
        nullable_progress_fields = {"downloaded_bytes", "total_bytes"}
        payload = {
            key: value
            for key, value in asdict(self).items()
            if value is not None
            or (key in nullable_progress_fields and self.status in {"queued", "downloading", "error"})
        }
        for key, value in overrides.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        return payload


def utc_timestamp() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def whisper_cache_dir() -> Path:
    cache_root = os.getenv("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_root) / "whisper"


def transcribe_model_cache_dir() -> Path:
    cache_root = os.getenv("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_root) / "transcribe-doc" / "models"


def download_status_path(model_name: str) -> Path:
    return whisper_cache_dir() / f"{model_name}.download.json"


def read_download_status(model_name: str) -> dict[str, Any] | None:
    path = download_status_path(model_name)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def write_download_status(model_name: str, payload: dict[str, Any]) -> None:
    path = download_status_path(model_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def emit_download_status(
    model_name: str,
    status: ModelStatus,
    progress_callback: Any | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload = status.to_payload(updated_at=utc_timestamp(), **overrides)
    write_download_status(model_name, payload)
    if progress_callback is not None:
        progress_callback(payload)
    return payload

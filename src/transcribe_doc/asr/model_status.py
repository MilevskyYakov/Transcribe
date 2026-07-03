"""Typed model download/status payloads and status-file persistence."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

ModelStatusValue = Literal["unknown", "missing", "queued", "downloading", "ready", "corrupt", "error"]
MODEL_DIR_ENV = "TRANSCRIBE_DOC_MODEL_DIR"


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


def model_root_dir() -> Path | None:
    value = os.getenv(MODEL_DIR_ENV)
    if not value:
        return None
    return Path(value).expanduser()


def default_cache_root() -> Path:
    cache_root = os.getenv("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_root).expanduser()


def whisper_cache_dir() -> Path:
    model_root = model_root_dir()
    if model_root is not None:
        return model_root / "whisper"
    return default_cache_root() / "whisper"


def transcribe_model_cache_dir() -> Path:
    model_root = model_root_dir()
    if model_root is not None:
        return model_root / "external"
    return default_cache_root() / "transcribe-doc" / "models"


def legacy_whisper_cache_dirs() -> list[Path]:
    """Return old Whisper cache locations to search when a durable model dir is set."""
    if model_root_dir() is None:
        return []
    return _unique_existing_style_dirs([default_cache_root() / "whisper", Path.home() / ".cache" / "whisper"])


def legacy_transcribe_model_cache_dirs() -> list[Path]:
    """Return old external ASR cache locations to search when a durable model dir is set."""
    if model_root_dir() is None:
        return []
    return _unique_existing_style_dirs(
        [
            default_cache_root() / "transcribe-doc" / "models",
            Path.home() / ".cache" / "transcribe-doc" / "models",
        ]
    )


def _unique_existing_style_dirs(paths: list[Path]) -> list[Path]:
    canonical_dirs = {whisper_cache_dir().resolve(strict=False), transcribe_model_cache_dir().resolve(strict=False)}
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        expanded = path.expanduser()
        resolved = expanded.resolve(strict=False)
        if resolved in canonical_dirs or resolved in seen:
            continue
        seen.add(resolved)
        result.append(expanded)
    return result


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

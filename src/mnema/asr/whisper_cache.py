"""Whisper model cache inspection, validation, and downloads."""

from __future__ import annotations

import hashlib
import shutil
from importlib import import_module
from pathlib import Path
from typing import Any, Callable
import urllib.request

from mnema.app.exceptions import ExternalDependencyError
from mnema.asr.model_registry import DEFAULT_WHISPER_MODELS, EXTERNAL_MODELS, external_spec
from mnema.asr.model_status import (
    ModelStatus,
    emit_download_status,
    legacy_whisper_cache_dirs,
    read_download_status,
    transcribe_model_cache_dir,
    whisper_cache_dir,
)

ModelProgress = Callable[[dict[str, Any]], None]
_SHA_CACHE: dict[tuple[str, int, int], str] = {}


def inspect_whisper_models(model_names: list[str] | None = None) -> list[dict[str, Any]]:
    """Return cache status for known Whisper and external ASR models."""
    from mnema.asr.external_model_cache import inspect_external_model

    names = model_names or DEFAULT_WHISPER_MODELS
    models = [inspect_whisper_model(name) for name in names]
    models.extend(inspect_external_model(spec) for spec in EXTERNAL_MODELS)
    return models


def inspect_whisper_model(model_name: str) -> dict[str, Any]:
    """Return cache status for one Whisper model."""
    model_url = model_url_for(model_name)
    if model_url is None:
        return ModelStatus(
            name=model_name,
            status="unknown",
            message="Модель неизвестна",
        ).to_payload()

    model_path = model_path_for(model_name, model_url)
    download_status = read_download_status(model_name)
    if download_status and download_status.get("status") in {"queued", "downloading"}:
        return download_status

    if model_path.exists():
        size_bytes = model_path.stat().st_size
        status = "ready" if sha256(model_path) == expected_sha(model_url) else "corrupt"
        message = "Модель готова" if status == "ready" else "Файл модели повреждён или скачан не полностью"
        return ModelStatus(
            name=model_name,
            label=model_name,
            backend="whisper",
            status=status,
            path=str(model_path),
            size_bytes=size_bytes,
            message=message,
        ).to_payload()

    legacy_path = migrate_legacy_whisper_model(model_name, model_url, model_path)
    if legacy_path is not None:
        ready_path = model_path if model_path.exists() else legacy_path
        return ModelStatus(
            name=model_name,
            label=model_name,
            backend="whisper",
            status="ready",
            path=str(ready_path),
            size_bytes=ready_path.stat().st_size,
            message="Модель найдена в старом кэше и доступна без повторного скачивания",
        ).to_payload()

    corrupt_legacy_path = corrupt_legacy_whisper_model_path(model_url)
    if corrupt_legacy_path is not None:
        return ModelStatus(
            name=model_name,
            label=model_name,
            backend="whisper",
            status="corrupt",
            path=str(corrupt_legacy_path),
            size_bytes=corrupt_legacy_path.stat().st_size,
            message="Файл модели повреждён или скачан не полностью",
        ).to_payload()

    return ModelStatus(
        name=model_name,
        label=model_name,
        backend="whisper",
        status="missing",
        path=str(model_path),
        size_bytes=0,
        message="Модель ещё не скачана",
    ).to_payload()


def ensure_whisper_model_ready(model_name: str) -> None:
    """Raise a clear error unless the model exists locally and matches checksum."""
    if external_spec(model_name) is not None:
        from mnema.asr.external_model_cache import ensure_external_model_ready

        ensure_external_model_ready(model_name)
        return
    status = inspect_whisper_model(model_name)
    if status.get("status") == "ready":
        return
    raise ExternalDependencyError(str(status.get("message") or f"Модель Whisper '{model_name}' не готова"))


def download_whisper_model(model_name: str, progress_callback: ModelProgress | None = None) -> dict[str, Any]:
    """Download one Whisper model and validate it before exposing it as ready."""
    external = external_spec(model_name)
    if external is not None:
        from mnema.asr.external_model_cache import download_external_model

        return download_external_model(external, progress_callback)

    model_url = model_url_for(model_name)
    if model_url is None:
        raise ExternalDependencyError(f"Unknown Whisper model: {model_name}")

    final_path = model_path_for(model_name, model_url)
    temp_path = Path(str(final_path) + ".download")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    expected = expected_sha(model_url)

    def emit(**payload: Any) -> dict[str, Any]:
        return emit_download_status(
            model_name,
            ModelStatus(
                name=model_name,
                label=model_name,
                backend="whisper",
                status=payload.pop("status"),
                path=str(final_path),
                **payload,
            ),
            progress_callback,
        )

    emit(status="downloading", downloaded_bytes=0, total_bytes=None, progress=0)
    try:
        with urllib.request.urlopen(model_url, timeout=30) as response:
            total_bytes = _content_length(response)
            downloaded = 0
            with temp_path.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    emit(
                        status="downloading",
                        downloaded_bytes=downloaded,
                        total_bytes=total_bytes,
                        progress=progress_percent(downloaded, total_bytes),
                    )
        actual_sha = sha256(temp_path)
        if actual_sha != expected:
            raise ExternalDependencyError(
                f"Checksum mismatch for Whisper model '{model_name}': expected {expected}, got {actual_sha}"
            )
        temp_path.replace(final_path)
        size_bytes = final_path.stat().st_size
        emit(
            status="ready",
            downloaded_bytes=size_bytes,
            total_bytes=size_bytes,
            progress=100,
            message="Модель скачана и проверена",
        )
        return inspect_whisper_model(model_name)
    except Exception as error:
        emit(
            status="error",
            downloaded_bytes=temp_path.stat().st_size if temp_path.exists() else 0,
            total_bytes=None,
            progress=0,
            message=str(error),
        )
        raise


def model_url_for(model_name: str) -> str | None:
    try:
        whisper_module = import_module("whisper")
    except ModuleNotFoundError:
        return None
    model_urls = getattr(whisper_module, "_MODELS", {})
    if not isinstance(model_urls, dict):
        return None
    value = model_urls.get(model_name)
    return value if isinstance(value, str) else None


def model_path_for(model_name: str, model_url: str | None = None) -> Path:
    url = model_url or model_url_for(model_name) or f"/{model_name}.pt"
    return whisper_cache_dir() / url.split("/")[-1]


def migrate_legacy_whisper_model(model_name: str, model_url: str, target_path: Path) -> Path | None:
    """Copy a valid legacy Whisper model into the durable model directory if needed."""
    filename = model_url.split("/")[-1]
    expected = expected_sha(model_url)
    for legacy_dir in legacy_whisper_cache_dirs():
        legacy_path = legacy_dir / filename
        if not legacy_path.is_file() or sha256(legacy_path) != expected:
            continue
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if not target_path.exists():
                shutil.copy2(legacy_path, target_path)
        except OSError:
            return legacy_path
        return target_path
    return None


def corrupt_legacy_whisper_model_path(model_url: str) -> Path | None:
    filename = model_url.split("/")[-1]
    expected = expected_sha(model_url)
    for legacy_dir in legacy_whisper_cache_dirs():
        legacy_path = legacy_dir / filename
        if legacy_path.is_file() and sha256(legacy_path) != expected:
            return legacy_path
    return None


def legacy_external_model_path(filename: str) -> Path:
    return transcribe_model_cache_dir() / filename


def expected_sha(model_url: str) -> str:
    return model_url.split("/")[-2]


def progress_percent(downloaded: int, total: int | None) -> int:
    if not total:
        return 0
    return max(0, min(99, int(downloaded / total * 100)))


def sha256(path: Path) -> str:
    stat = path.stat()
    cache_key = (str(path), stat.st_size, stat.st_mtime_ns)
    cached = _SHA_CACHE.get(cache_key)
    if cached is not None:
        return cached
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    _SHA_CACHE[cache_key] = value
    return value


def _content_length(response: Any) -> int | None:
    value = response.headers.get("Content-Length")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None

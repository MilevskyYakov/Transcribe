"""External ONNX-ASR model cache inspection, validation, and downloads."""

from __future__ import annotations

import shutil
import threading
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

from transcribe_doc.app.exceptions import ExternalDependencyError
from transcribe_doc.asr.model_registry import ExternalModelSpec, external_spec
from transcribe_doc.asr.model_status import (
    ModelStatus,
    emit_download_status,
    legacy_transcribe_model_cache_dirs,
    read_download_status,
    transcribe_model_cache_dir,
    utc_timestamp,
    write_download_status,
)
from transcribe_doc.asr.whisper_cache import sha256

ModelProgress = Callable[[dict[str, Any]], None]


def inspect_external_model(spec: ExternalModelSpec) -> dict[str, Any]:
    runtime_dir = external_model_runtime_path(spec.name)
    source_path = external_model_source_path(spec)
    base = spec.metadata(runtime_dir)
    download_status = read_download_status(spec.name)

    if download_status and download_status.get("status") in {"queued", "downloading"}:
        return download_status
    if external_ready_path_exists(runtime_dir):
        return ModelStatus(
            **base,
            status="ready",
            size_bytes=path_size(runtime_dir),
            message="Модель готова",
        ).to_payload()
    if runtime_dir.exists():
        return ModelStatus(
            **base,
            status="corrupt",
            size_bytes=path_size(runtime_dir),
            message="Файлы модели повреждены или скачаны не полностью",
        ).to_payload()
    if download_status and download_status.get("status") == "error":
        return {**base, **download_status, "status": "error", "stale_download": True}
    if download_status and download_status.get("status") == "ready":
        status_path = Path(str(download_status.get("path") or ""))
        if external_ready_path_exists(status_path) or external_ready_path_exists(runtime_dir):
            return {**base, **download_status, "status": "ready"}
        return {
            **base,
            **download_status,
            "status": "error",
            "progress": 0,
            "stale_download": True,
            "message": "Файлы модели не найдены в кэше. Нажмите «Скачать заново».",
        }
    migrated_path = migrate_legacy_external_model(spec, runtime_dir, source_path)
    if migrated_path is not None:
        return ModelStatus(
            **spec.metadata(migrated_path),
            status="ready",
            size_bytes=path_size(migrated_path),
            message="Модель найдена в старом кэше и доступна без повторного скачивания",
        ).to_payload()
    corrupt_legacy_path = corrupt_legacy_external_model_path(spec)
    if corrupt_legacy_path is not None:
        return ModelStatus(
            **spec.metadata(corrupt_legacy_path),
            status="corrupt",
            size_bytes=path_size(corrupt_legacy_path),
            message="Файлы модели повреждены или скачаны не полностью",
        ).to_payload()
    if not source_path.exists():
        return ModelStatus(
            **base,
            status="missing",
            size_bytes=0,
            message="Модель ещё не скачана",
        ).to_payload()
    if spec.expected_sha256 and sha256(source_path) != spec.expected_sha256:
        return ModelStatus(
            **base,
            status="corrupt",
            size_bytes=source_path.stat().st_size,
            message="Файл модели повреждён или скачан не полностью",
        ).to_payload()
    return ModelStatus(
        **spec.metadata(source_path),
        status="ready",
        size_bytes=source_path.stat().st_size,
        message="Модель готова",
    ).to_payload()


def download_external_model(
    spec: ExternalModelSpec, progress_callback: ModelProgress | None = None
) -> dict[str, Any]:
    final_path = external_model_runtime_path(spec.name)
    if final_path.exists() and not external_ready_path_exists(final_path):
        shutil.rmtree(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(**payload: Any) -> dict[str, Any]:
        return emit_download_status(
            spec.name,
            ModelStatus(**spec.metadata(final_path), status=payload.pop("status"), **payload),
            progress_callback,
        )

    emit(
        status="downloading",
        downloaded_bytes=None,
        total_bytes=None,
        progress=0,
        message="Готовлю ONNX ASR модель",
    )
    try:
        onnx_asr = import_module("onnx_asr")
        stop_progress = threading.Event()
        progress_thread = threading.Thread(
            target=emit_external_download_progress,
            args=(spec, emit, stop_progress),
            daemon=True,
        )
        progress_thread.start()
        try:
            onnx_asr.load_model(
                spec.runtime_name,
                path=str(final_path),
                providers=["CPUExecutionProvider"],
            )
        finally:
            stop_progress.set()
            progress_thread.join(timeout=1.0)
        size_bytes = path_size(final_path)
        emit(
            status="ready",
            downloaded_bytes=size_bytes,
            total_bytes=size_bytes,
            progress=100,
            message="Модель скачана и проверена",
        )
        return inspect_external_model(spec)
    except Exception as error:
        emit(
            status="error",
            downloaded_bytes=None,
            total_bytes=None,
            progress=0,
            message=str(error),
        )
        raise


def ensure_external_model_ready(model_name: str) -> None:
    spec = external_spec(model_name)
    if spec is None:
        raise ExternalDependencyError(f"Unknown external ASR model: {model_name}")
    status = inspect_external_model(spec)
    if status.get("status") == "ready":
        return
    raise ExternalDependencyError(str(status.get("message") or f"Модель '{model_name}' не готова"))


def external_runtime_name(model_name: str) -> str:
    spec = external_spec(model_name)
    if spec is None:
        raise ExternalDependencyError(f"Unknown external ASR model: {model_name}")
    return spec.runtime_name


def external_model_runtime_path(model_name: str) -> Path:
    spec = external_spec(model_name)
    if spec is None:
        raise ExternalDependencyError(f"Unknown external ASR model: {model_name}")
    return transcribe_model_cache_dir() / spec.name


def external_model_source_path(spec: ExternalModelSpec) -> Path:
    return transcribe_model_cache_dir() / spec.filename


def migrate_legacy_external_model(
    spec: ExternalModelSpec, runtime_dir: Path, source_path: Path
) -> Path | None:
    """Copy a valid legacy external ASR model into the durable model directory if needed."""
    for legacy_dir in legacy_transcribe_model_cache_dirs():
        legacy_runtime_dir = legacy_dir / spec.name
        if external_ready_path_exists(legacy_runtime_dir):
            try:
                runtime_dir.parent.mkdir(parents=True, exist_ok=True)
                if not runtime_dir.exists():
                    shutil.copytree(legacy_runtime_dir, runtime_dir)
            except OSError:
                return legacy_runtime_dir
            return runtime_dir

        legacy_source_path = legacy_dir / spec.filename
        if not legacy_source_path.is_file():
            continue
        if spec.expected_sha256 and sha256(legacy_source_path) != spec.expected_sha256:
            continue
        try:
            source_path.parent.mkdir(parents=True, exist_ok=True)
            if not source_path.exists():
                shutil.copy2(legacy_source_path, source_path)
        except OSError:
            return legacy_source_path
        return source_path
    return None


def corrupt_legacy_external_model_path(spec: ExternalModelSpec) -> Path | None:
    for legacy_dir in legacy_transcribe_model_cache_dirs():
        legacy_runtime_dir = legacy_dir / spec.name
        if legacy_runtime_dir.exists() and not external_ready_path_exists(legacy_runtime_dir):
            return legacy_runtime_dir
        legacy_source_path = legacy_dir / spec.filename
        if spec.expected_sha256 and legacy_source_path.is_file():
            if sha256(legacy_source_path) != spec.expected_sha256:
                return legacy_source_path
    return None


def external_ready_path_exists(path: Path) -> bool:
    if path.is_dir():
        return (path / "config.json").exists() and any(path.rglob("*.onnx"))
    return path.is_file()


def path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if not path.is_dir():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def mark_model_download_error(model_name: str, message: str) -> None:
    spec = external_spec(model_name)
    status = ModelStatus(
        name=model_name,
        status="error",
        downloaded_bytes=None,
        total_bytes=None,
        progress=0,
        message=message,
        updated_at=utc_timestamp(),
        stale_download=True,
    )
    if spec is not None:
        status = ModelStatus(
            **spec.metadata(external_model_runtime_path(model_name)),
            status="error",
            progress=0,
            message=message,
            updated_at=utc_timestamp(),
            stale_download=True,
        )
    write_download_status(model_name, status.to_payload())


def mark_model_download_queued(model_name: str, position: int | None = None) -> None:
    spec = external_spec(model_name)
    if spec is None:
        from transcribe_doc.asr.whisper_cache import model_path_for, model_url_for

        model_url = model_url_for(model_name)
        status = ModelStatus(
            name=model_name,
            label=model_name,
            backend="whisper",
            path=str(model_path_for(model_name, model_url)),
            status="queued",
            downloaded_bytes=None,
            total_bytes=None,
            progress=0,
            message="Модель ожидает очереди на скачивание",
            updated_at=utc_timestamp(),
            queue_position=position,
        )
    else:
        status = ModelStatus(
            **spec.metadata(external_model_runtime_path(model_name)),
            status="queued",
            downloaded_bytes=None,
            total_bytes=None,
            progress=0,
            message="Модель ожидает очереди на скачивание",
            updated_at=utc_timestamp(),
            queue_position=position,
        )
    write_download_status(model_name, status.to_payload())


def external_download_progress_payload(spec: ExternalModelSpec) -> dict[str, Any]:
    downloaded_bytes = path_size(external_model_runtime_path(spec.name))
    return ModelStatus(
        name=spec.name,
        status="downloading",
        downloaded_bytes=downloaded_bytes,
        total_bytes=None,
        progress=1 if downloaded_bytes > 0 else 0,
        message="Скачиваю ONNX ASR модель",
    ).to_payload(name=None)


def emit_external_download_progress(
    spec: ExternalModelSpec,
    emit: Callable[..., dict[str, Any]],
    stop_event: threading.Event,
) -> None:
    last_downloaded = -1
    while not stop_event.wait(2.0):
        payload = external_download_progress_payload(spec)
        downloaded = payload["downloaded_bytes"]
        if downloaded != last_downloaded:
            emit(**payload)
            last_downloaded = downloaded

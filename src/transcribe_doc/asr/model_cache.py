"""Local Whisper model cache inspection and downloads."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Callable
import urllib.request

from transcribe_doc.app.exceptions import ExternalDependencyError


ModelProgress = Callable[[dict[str, Any]], None]
_SHA_CACHE: dict[tuple[str, int, int], str] = {}


@dataclass(frozen=True)
class ExternalModelSpec:
    name: str
    label: str
    backend: str
    runtime_name: str
    url: str
    filename: str
    expected_sha256: str | None
    language: str
    description: str


EXTERNAL_MODELS = [
    ExternalModelSpec(
        name="parakeet-v3",
        label="Parakeet V3",
        backend="onnx-asr",
        runtime_name="nemo-parakeet-tdt-0.6b-v3",
        url="https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/resolve/main/parakeet-tdt-0.6b-v3.nemo",
        filename="parakeet-tdt-0.6b-v3.nemo",
        expected_sha256=None,
        language="Многоязычная",
        description="NVIDIA Parakeet-TDT 0.6B v3 через ONNX ASR",
    ),
    ExternalModelSpec(
        name="gigaam-v3",
        label="GigaAM v3",
        backend="onnx-asr",
        runtime_name="gigaam-v3-e2e-ctc",
        url="https://huggingface.co/protocolvoice/asr-models/resolve/main/gigaam_v3_e2e_ctc_int8.onnx",
        filename="gigaam_v3_e2e_ctc_int8.onnx",
        expected_sha256="0aacb41f70f0f5aaac4b45dd430337b9e16b180f22c72af04db8516e7609c3c0",
        language="Только Russian",
        description="GigaAM v3 E2E CTC int8 ONNX с пунктуацией",
    ),
]


def inspect_whisper_models(model_names: list[str] | None = None) -> list[dict[str, Any]]:
    """Return cache status for known Whisper models."""
    names = model_names or ["tiny", "base", "small", "medium", "large-v3"]
    models = [inspect_whisper_model(name) for name in names]
    models.extend(inspect_external_model(spec) for spec in EXTERNAL_MODELS)
    return models


def inspect_whisper_model(model_name: str) -> dict[str, Any]:
    """Return cache status for one Whisper model."""
    model_url = _model_url(model_name)
    if model_url is None:
        return {"name": model_name, "status": "unknown", "message": "Модель неизвестна"}

    model_path = _model_path(model_name, model_url)
    download_status = _read_download_status(model_name)
    if download_status and download_status.get("status") in {"queued", "downloading"}:
        return download_status
    if model_path.exists():
        size_bytes = model_path.stat().st_size
        expected_sha = _expected_sha(model_url)
        status = "ready" if _sha256(model_path) == expected_sha else "corrupt"
        message = "Модель готова" if status == "ready" else "Файл модели повреждён или скачан не полностью"
        return {
            "name": model_name,
            "label": model_name,
            "backend": "whisper",
            "status": status,
            "path": str(model_path),
            "size_bytes": size_bytes,
            "message": message,
        }
    return {
        "name": model_name,
        "label": model_name,
        "backend": "whisper",
        "status": "missing",
        "path": str(model_path),
        "size_bytes": 0,
        "message": "Модель ещё не скачана",
    }


def ensure_whisper_model_ready(model_name: str) -> None:
    """Raise a clear error unless the model exists locally and matches checksum."""
    if _external_spec(model_name) is not None:
        ensure_external_model_ready(model_name)
        return
    status = inspect_whisper_model(model_name)
    if status.get("status") == "ready":
        return
    raise ExternalDependencyError(str(status.get("message") or f"Модель Whisper '{model_name}' не готова"))


def download_whisper_model(model_name: str, progress_callback: ModelProgress | None = None) -> dict[str, Any]:
    """Download one Whisper model and validate it before exposing it as ready."""
    external = _external_spec(model_name)
    if external is not None:
        return download_external_model(external, progress_callback)

    model_url = _model_url(model_name)
    if model_url is None:
        raise ExternalDependencyError(f"Unknown Whisper model: {model_name}")

    final_path = _model_path(model_name, model_url)
    temp_path = Path(str(final_path) + ".download")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    expected_sha = _expected_sha(model_url)

    def emit(payload: dict[str, Any]) -> None:
        payload = {
            "name": model_name,
            "path": str(final_path),
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            **payload,
        }
        _write_download_status(model_name, payload)
        if progress_callback is not None:
            progress_callback(payload)

    emit({"status": "downloading", "downloaded_bytes": 0, "total_bytes": None, "progress": 0})
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
                        {
                            "status": "downloading",
                            "downloaded_bytes": downloaded,
                            "total_bytes": total_bytes,
                            "progress": _progress(downloaded, total_bytes),
                        }
                    )
        actual_sha = _sha256(temp_path)
        if actual_sha != expected_sha:
            raise ExternalDependencyError(
                f"Checksum mismatch for Whisper model '{model_name}': expected {expected_sha}, got {actual_sha}"
            )
        temp_path.replace(final_path)
        payload = {
            "status": "ready",
            "downloaded_bytes": final_path.stat().st_size,
            "total_bytes": final_path.stat().st_size,
            "progress": 100,
            "message": "Модель скачана и проверена",
        }
        emit(payload)
        return inspect_whisper_model(model_name)
    except Exception as error:
        payload = {
            "status": "error",
            "downloaded_bytes": temp_path.stat().st_size if temp_path.exists() else 0,
            "total_bytes": None,
            "progress": 0,
            "message": str(error),
        }
        emit(payload)
        raise


def inspect_external_model(spec: ExternalModelSpec) -> dict[str, Any]:
    path = _external_model_path(spec)
    runtime_dir = external_model_runtime_path(spec.name)
    download_status = _read_download_status(spec.name)
    if download_status and download_status.get("status") in {"queued", "downloading"}:
        return download_status
    base = {
        "name": spec.name,
        "label": spec.label,
        "backend": spec.backend,
        "runtime_name": spec.runtime_name,
        "language": spec.language,
        "description": spec.description,
        "path": str(runtime_dir),
    }
    if _external_ready_path_exists(runtime_dir):
        return {
            **base,
            "status": "ready",
            "size_bytes": _path_size(runtime_dir),
            "message": "Модель готова",
        }
    if download_status and download_status.get("status") == "error":
        return {
            **base,
            **download_status,
            "status": "error",
            "stale_download": True,
        }
    if download_status and download_status.get("status") == "ready":
        status_path = Path(str(download_status.get("path") or ""))
        if _external_ready_path_exists(status_path) or _external_ready_path_exists(runtime_dir):
            return {**base, **download_status, "status": "ready"}
        return {
            **base,
            **download_status,
            "status": "error",
            "progress": 0,
            "stale_download": True,
            "message": "Файлы модели не найдены в кэше. Нажмите «Скачать заново».",
        }
    if not path.exists():
        return {**base, "status": "missing", "size_bytes": 0, "message": "Модель ещё не скачана"}
    if spec.expected_sha256 and _sha256(path) != spec.expected_sha256:
        return {
            **base,
            "status": "corrupt",
            "size_bytes": path.stat().st_size,
            "message": "Файл модели повреждён или скачан не полностью",
        }
    return {**base, "status": "ready", "size_bytes": path.stat().st_size, "message": "Модель готова"}


def download_external_model(
    spec: ExternalModelSpec, progress_callback: ModelProgress | None = None
) -> dict[str, Any]:
    final_path = external_model_runtime_path(spec.name)
    if final_path.exists() and not _external_ready_path_exists(final_path):
        shutil.rmtree(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(payload: dict[str, Any]) -> None:
        payload = {
            "name": spec.name,
            "label": spec.label,
            "backend": spec.backend,
            "runtime_name": spec.runtime_name,
            "language": spec.language,
            "description": spec.description,
            "path": str(final_path),
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            **payload,
        }
        _write_download_status(spec.name, payload)
        if progress_callback is not None:
            progress_callback(payload)

    emit(
        {
            "status": "downloading",
            "downloaded_bytes": None,
            "total_bytes": None,
            "progress": 0,
            "message": "Готовлю ONNX ASR модель",
        }
    )
    try:
        onnx_asr = import_module("onnx_asr")
        stop_progress = threading.Event()
        progress_thread = threading.Thread(
            target=_emit_external_download_progress,
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
        emit(
            {
                "status": "ready",
                "downloaded_bytes": _path_size(final_path),
                "total_bytes": _path_size(final_path),
                "progress": 100,
                "message": "Модель скачана и проверена",
                "runtime_name": spec.runtime_name,
            }
        )
        return inspect_external_model(spec)
    except Exception as error:
        emit(
            {
                "status": "error",
                "downloaded_bytes": None,
                "total_bytes": None,
                "progress": 0,
                "message": str(error),
            }
        )
        raise


def ensure_external_model_ready(model_name: str) -> None:
    spec = _external_spec(model_name)
    if spec is None:
        raise ExternalDependencyError(f"Unknown external ASR model: {model_name}")
    status = inspect_external_model(spec)
    if status.get("status") == "ready":
        return
    raise ExternalDependencyError(str(status.get("message") or f"Модель '{model_name}' не готова"))


def external_runtime_name(model_name: str) -> str:
    spec = _external_spec(model_name)
    if spec is None:
        raise ExternalDependencyError(f"Unknown external ASR model: {model_name}")
    return spec.runtime_name


def external_model_runtime_path(model_name: str) -> Path:
    spec = _external_spec(model_name)
    if spec is None:
        raise ExternalDependencyError(f"Unknown external ASR model: {model_name}")
    return _transcribe_cache_dir() / spec.name


def mark_model_download_error(model_name: str, message: str) -> None:
    spec = _external_spec(model_name)
    payload: dict[str, Any] = {
        "name": model_name,
        "status": "error",
        "downloaded_bytes": None,
        "total_bytes": None,
        "progress": 0,
        "message": message,
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "stale_download": True,
    }
    if spec is not None:
        payload.update(
            {
                "label": spec.label,
                "backend": spec.backend,
                "runtime_name": spec.runtime_name,
                "language": spec.language,
                "description": spec.description,
                "path": str(external_model_runtime_path(model_name)),
            }
        )
    _write_download_status(model_name, payload)


def external_download_progress_payload(spec: ExternalModelSpec) -> dict[str, Any]:
    downloaded_bytes = _path_size(external_model_runtime_path(spec.name))
    return {
        "status": "downloading",
        "downloaded_bytes": downloaded_bytes,
        "total_bytes": None,
        "progress": 1 if downloaded_bytes > 0 else 0,
        "message": "Скачиваю ONNX ASR модель",
    }


def mark_model_download_queued(model_name: str, position: int | None = None) -> None:
    spec = _external_spec(model_name)
    payload: dict[str, Any] = {
        "name": model_name,
        "status": "queued",
        "downloaded_bytes": None,
        "total_bytes": None,
        "progress": 0,
        "message": "Модель ожидает очереди на скачивание",
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    if position is not None:
        payload["queue_position"] = position
    if spec is not None:
        payload.update(
            {
                "label": spec.label,
                "backend": spec.backend,
                "runtime_name": spec.runtime_name,
                "language": spec.language,
                "description": spec.description,
                "path": str(external_model_runtime_path(model_name)),
            }
        )
    else:
        model_url = _model_url(model_name)
        payload.update(
            {
                "label": model_name,
                "backend": "whisper",
                "path": str(_model_path(model_name, model_url)),
            }
        )
    _write_download_status(model_name, payload)


def _model_url(model_name: str) -> str | None:
    try:
        whisper_module = import_module("whisper")
    except ModuleNotFoundError:
        return None
    model_urls = getattr(whisper_module, "_MODELS", {})
    if not isinstance(model_urls, dict):
        return None
    value = model_urls.get(model_name)
    return value if isinstance(value, str) else None


def _external_spec(model_name: str) -> ExternalModelSpec | None:
    return next((spec for spec in EXTERNAL_MODELS if spec.name == model_name), None)


def _model_path(model_name: str, model_url: str | None = None) -> Path:
    url = model_url or _model_url(model_name) or f"/{model_name}.pt"
    return _whisper_cache_dir() / url.split("/")[-1]


def _external_model_path(spec: ExternalModelSpec) -> Path:
    return _transcribe_cache_dir() / spec.filename


def _external_ready_path_exists(path: Path) -> bool:
    if path.is_dir():
        return (path / "config.json").exists() and any(path.rglob("*.onnx"))
    return path.is_file()


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if not path.is_dir():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _expected_sha(model_url: str) -> str:
    return model_url.split("/")[-2]


def _whisper_cache_dir() -> Path:
    cache_root = os.getenv("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_root) / "whisper"


def _transcribe_cache_dir() -> Path:
    cache_root = os.getenv("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_root) / "transcribe-doc" / "models"


def _download_status_path(model_name: str) -> Path:
    return _whisper_cache_dir() / f"{model_name}.download.json"


def _read_download_status(model_name: str) -> dict[str, Any] | None:
    path = _download_status_path(model_name)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _write_download_status(model_name: str, payload: dict[str, Any]) -> None:
    path = _download_status_path(model_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _emit_external_download_progress(
    spec: ExternalModelSpec,
    emit: ModelProgress,
    stop_event: threading.Event,
) -> None:
    last_downloaded = -1
    while not stop_event.wait(2.0):
        payload = external_download_progress_payload(spec)
        downloaded = payload["downloaded_bytes"]
        if downloaded != last_downloaded:
            emit(payload)
            last_downloaded = downloaded


def _content_length(response: Any) -> int | None:
    value = response.headers.get("Content-Length")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _progress(downloaded: int, total: int | None) -> int:
    if not total:
        return 0
    return max(0, min(99, int(downloaded / total * 100)))


def _sha256(path: Path) -> str:
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

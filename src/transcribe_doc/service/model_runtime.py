"""Model download state helpers for the local API."""

from __future__ import annotations

from typing import Any, Protocol

from transcribe_doc.asr.whisper_cache import download_whisper_model, inspect_whisper_models


class ModelRuntimeServer(Protocol):
    model_downloads: set[str]
    model_lock: Any


def run_model_download(server: ModelRuntimeServer, model_name: str) -> None:
    try:
        download_whisper_model(model_name)
    finally:
        with server.model_lock:
            server.model_downloads.discard(model_name)


def models_for_response(server: ModelRuntimeServer) -> list[dict[str, Any]]:
    with server.model_lock:
        active_downloads = set(server.model_downloads)
    return [model_download_state_for_response(model, active_downloads) for model in inspect_whisper_models()]


def model_download_state_for_response(model: dict[str, Any], active_downloads: set[str]) -> dict[str, Any]:
    model_name = model.get("name")
    if (
        isinstance(model_name, str)
        and model.get("status") in {"queued", "downloading"}
        and model_name not in active_downloads
    ):
        return {
            **model,
            "status": "error",
            "progress": 0,
            "stale_download": True,
            "message": "Загрузка была прервана. Нажмите «Скачать заново», чтобы восстановить модель.",
        }
    return model

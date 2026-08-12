"""Model-list and model-download endpoint functions."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from mnema.asr.external_model_cache import mark_model_download_queued
from mnema.asr.whisper_cache import inspect_whisper_models
from mnema.service.contracts import (
    ModelsResponse,
    dataclass_payload,
    model_status_response,
)
from mnema.service.http_response import ApiResponse, json_response
from mnema.service.model_runtime import (
    model_download_state_for_response,
    run_model_download,
)


def models_endpoint(ctx: Any) -> ApiResponse:
    return json_response(
        dataclass_payload(
            ModelsResponse(
                current_model=ctx.app_config.asr.model_name,
                models=[model_status_response(model) for model in models_for_response(ctx.server)],
            )
        )
    )


def download_model_endpoint(ctx: Any) -> ApiResponse:
    try:
        payload = ctx.read_json_object()
        model_name = payload.get("model_name") or ctx.app_config.asr.model_name
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("'model_name' is required.")
        model_name = model_name.strip()
        with ctx.server.model_lock:
            if model_name in ctx.server.model_downloads:
                return json_response(
                    {
                        "status": "already_running",
                        "message": f"Загрузка модели {model_name} уже идёт",
                        "model": model_name,
                    },
                    HTTPStatus.ACCEPTED,
                )
            ctx.server.model_downloads.add(model_name)
            mark_model_download_queued(model_name)
        ctx.model_executor.submit(run_model_download, ctx.server, model_name)
    except ValueError as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    return json_response(
        {
            "status": "started",
            "message": f"Загрузка модели {model_name} запущена",
            "model": model_name,
        },
        HTTPStatus.ACCEPTED,
    )


def download_all_models_endpoint(ctx: Any) -> ApiResponse:
    started: list[str] = []
    skipped: list[str] = []
    queue_position = 0
    for model in inspect_whisper_models():
        model_name = model.get("name")
        status = model.get("status")
        if not isinstance(model_name, str) or status == "ready":
            continue
        with ctx.server.model_lock:
            if model_name in ctx.server.model_downloads:
                skipped.append(model_name)
                continue
            ctx.server.model_downloads.add(model_name)
            queue_position += 1
            mark_model_download_queued(model_name, queue_position)
        ctx.model_executor.submit(run_model_download, ctx.server, model_name)
        started.append(model_name)
    return json_response(
        {
            "status": "started",
            "message": f"Запущено загрузок: {len(started)}",
            "started": started,
            "skipped": skipped,
        },
        HTTPStatus.ACCEPTED,
    )


def models_for_response(server: Any) -> list[dict[str, Any]]:
    with server.model_lock:
        active_downloads = set(server.model_downloads)
    return [
        model_download_state_for_response(model, active_downloads)
        for model in inspect_whisper_models()
    ]

"""Explicit route table for the local API."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Callable

from transcribe_doc.service.health import health_payload
from transcribe_doc.service.http_response import ApiResponse, json_response
from transcribe_doc.service.job_endpoints import (
    artifact_download_endpoint,
    artifacts_endpoint,
    cleanup_temp_endpoint,
    create_batch_endpoint,
    create_job_endpoint,
    events_endpoint,
    final_markdown_status_endpoint,
    get_job_endpoint,
    list_jobs_endpoint,
    save_final_markdown_endpoint,
    scan_watch_folder_endpoint,
    transcript_endpoint,
)
from transcribe_doc.service.model_endpoints import (
    download_all_models_endpoint,
    download_model_endpoint,
    models_endpoint,
)

Handler = Callable[..., ApiResponse]


@dataclass(frozen=True)
class Route:
    method: str
    pattern: tuple[str, ...]
    handler: Handler

    def match(self, method: str, path_parts: list[str]) -> dict[str, str] | None:
        if method != self.method or len(path_parts) != len(self.pattern):
            return None
        params: dict[str, str] = {}
        for expected, actual in zip(self.pattern, path_parts):
            if expected.startswith("{") and expected.endswith("}"):
                params[expected[1:-1]] = actual
            elif expected != actual:
                return None
        return params


ROUTES = [
    Route("GET", ("health",), lambda ctx: json_response(health_payload(ctx.app_config))),
    Route("GET", ("jobs",), list_jobs_endpoint),
    Route("GET", ("models",), models_endpoint),
    Route("GET", ("jobs", "{job_id}"), get_job_endpoint),
    Route("GET", ("jobs", "{job_id}", "transcript"), transcript_endpoint),
    Route("GET", ("jobs", "{job_id}", "final-markdown"), final_markdown_status_endpoint),
    Route("GET", ("jobs", "{job_id}", "artifacts"), artifacts_endpoint),
    Route("GET", ("jobs", "{job_id}", "events"), events_endpoint),
    Route("GET", ("jobs", "{job_id}", "artifacts", "{artifact_name}"), artifact_download_endpoint),
    Route("POST", ("cleanup", "temp"), cleanup_temp_endpoint),
    Route("POST", ("jobs",), create_job_endpoint),
    Route("POST", ("jobs", "{job_id}", "final-markdown"), save_final_markdown_endpoint),
    Route("POST", ("batch",), create_batch_endpoint),
    Route("POST", ("watch-folder", "scan"), scan_watch_folder_endpoint),
    Route("POST", ("models", "download"), download_model_endpoint),
    Route("POST", ("models", "download-all"), download_all_models_endpoint),
]


def dispatch(ctx: Any, method: str, path_parts: list[str]) -> ApiResponse:
    for route in ROUTES:
        params = route.match(method, path_parts)
        if params is not None:
            return route.handler(ctx, **params)
    return json_response({"error": "not_found"}, HTTPStatus.NOT_FOUND)

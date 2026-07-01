"""HTTP response shapes and sender helpers for the local API."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ApiResponse:
    status: HTTPStatus
    payload: Any = None
    file_path: Path | None = None
    download_name: str | None = None
    content_type: str = "application/json; charset=utf-8"


def json_response(payload: Any, status: HTTPStatus = HTTPStatus.OK) -> ApiResponse:
    return ApiResponse(status=status, payload=payload)


def empty_response(status: HTTPStatus) -> ApiResponse:
    return ApiResponse(status=status)


def file_response(path: Path, download_name: str | None = None) -> ApiResponse:
    return ApiResponse(
        status=HTTPStatus.OK,
        file_path=path,
        download_name=download_name or path.name,
        content_type="application/octet-stream",
    )


def send_api_response(handler: Any, response: ApiResponse) -> None:
    if response.file_path is not None:
        _send_file(handler, response)
        return
    if response.payload is None:
        _send_empty(handler, response.status)
        return
    _send_json(handler, response.payload, response.status)


def _send_json(handler: Any, payload: Any, status: HTTPStatus) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    _send_cors_headers(handler)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_empty(handler: Any, status: HTTPStatus) -> None:
    handler.send_response(status)
    _send_cors_headers(handler)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


def _send_file(handler: Any, response: ApiResponse) -> None:
    assert response.file_path is not None
    handler.send_response(response.status)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Type", response.content_type)
    handler.send_header("Content-Length", str(response.file_path.stat().st_size))
    handler.send_header("Content-Disposition", f'attachment; filename="{response.download_name}"')
    handler.end_headers()
    with response.file_path.open("rb") as handle:
        shutil.copyfileobj(handle, handler.wfile)


def _send_cors_headers(handler: Any) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")

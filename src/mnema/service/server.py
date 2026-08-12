"""Local HTTP API used by the web dashboard."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from mnema.app.config import AppConfig
from mnema.service.batch_session_store import reconcile_batch_session_jobs
from mnema.service.http_response import empty_response, send_api_response
from mnema.service.job_store import (
    list_artifacts,
    list_events,
    list_jobs,
    mark_interrupted_jobs,
)
from mnema.service.model_runtime import (
    model_download_state_for_response as _model_download_state_for_response,
)
from mnema.service.request_parsing import read_job_request, read_json_object
from mnema.service.router import dispatch
from mnema.service.types import JsonObject
from mnema.storage.temp_cleanup import cleanup_stale_temporary_media

__all__ = [
    "LocalApiServer",
    "_model_download_state_for_response",
    "build_server",
    "list_artifacts",
    "list_events",
    "list_jobs",
    "run_server",
]


class LocalApiServer(ThreadingHTTPServer):
    """HTTP server with a bounded local job executor."""

    app_config: AppConfig
    executor: ThreadPoolExecutor
    model_executor: ThreadPoolExecutor
    model_downloads: set[str]
    model_lock: threading.Lock

    def server_close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.model_executor.shutdown(wait=False, cancel_futures=True)
        super().server_close()


def run_server(config: AppConfig, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the local HTTP service."""
    server = build_server(config=config, host=host, port=port)
    print(f"Serving mnema on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping mnema service")
    finally:
        server.server_close()


def build_server(config: AppConfig, host: str = "127.0.0.1", port: int = 8765) -> LocalApiServer:
    """Build a configured HTTP server for CLI and tests."""
    mark_interrupted_jobs(Path(config.app.output_dir))
    reconcile_batch_session_jobs(Path(config.app.output_dir))
    cleanup_report = cleanup_stale_temporary_media(
        output_root=Path(config.app.output_dir),
        temp_root=Path(config.app.temp_dir),
    )
    if cleanup_report.removed_count:
        print(
            "Cleaned temporary media: "
            f"{cleanup_report.removed_count} files, {cleanup_report.freed_bytes} bytes"
        )
    server = LocalApiServer((host, port), LocalApiHandler)
    server.app_config = config
    server.executor = ThreadPoolExecutor(max_workers=max(1, config.runtime.max_parallel_jobs))
    server.model_executor = ThreadPoolExecutor(max_workers=1)
    server.model_downloads = set()
    server.model_lock = threading.Lock()
    return server


class LocalApiHandler(BaseHTTPRequestHandler):
    """Small local-only JSON API adapter for route dispatch."""

    server_version = "MnemaLocal/0.1"

    def do_OPTIONS(self) -> None:
        send_api_response(self, empty_response(HTTPStatus.NO_CONTENT))

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    @property
    def app_config(self) -> AppConfig:
        return cast(LocalApiServer, self.server).app_config

    @property
    def executor(self) -> ThreadPoolExecutor:
        return cast(LocalApiServer, self.server).executor

    @property
    def model_executor(self) -> ThreadPoolExecutor:
        return cast(LocalApiServer, self.server).model_executor

    @property
    def output_root(self) -> Path:
        return Path(self.app_config.app.output_dir)

    @property
    def upload_root(self) -> Path:
        return Path(self.app_config.app.temp_dir) / "uploads"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def read_json_object(self) -> JsonObject:
        return read_json_object(cast(Any, self.headers), cast(Any, self.rfile))

    def read_job_request(self) -> JsonObject:
        return read_job_request(cast(Any, self.headers), cast(Any, self.rfile), self.upload_root)

    def _dispatch(self, method: str) -> None:
        send_api_response(self, dispatch(self, method, self._path_parts()))

    def _path_parts(self) -> list[str]:
        parsed = urlparse(self.path)
        return [unquote(part) for part in parsed.path.split("/") if part]

"""Local HTTP API used by the web dashboard."""

from __future__ import annotations

import json
import shutil
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, IO, cast
from urllib.parse import unquote, urlparse

from transcribe_doc.app.config import AppConfig
from transcribe_doc.app.models import JobStatus
from transcribe_doc.asr.model_cache import inspect_whisper_models, mark_model_download_queued
from transcribe_doc.core.batch import process_batch, scan_watch_folder
from transcribe_doc.core.job_manager import create_job, persist_job
from transcribe_doc.core.processing import process_single_file
from transcribe_doc.ingest.input_resolver import InputResolutionError, resolve_single_input
from transcribe_doc.storage.paths import build_job_paths
from transcribe_doc.service.health import health_payload
from transcribe_doc.service.job_store import (
    artifact_by_name,
    list_artifacts,
    list_events,
    list_jobs,
    load_job,
    mark_interrupted_jobs,
    read_json_file,
)
from transcribe_doc.service.model_runtime import (
    model_download_state_for_response as _model_download_state_for_response,
    run_model_download,
)
from transcribe_doc.service.responses import (
    batch_to_response,
    config_for_payload,
    display_title_from_payload,
    job_to_response,
)
from transcribe_doc.service.types import JsonObject

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning, message="'cgi' is deprecated.*")
    import cgi


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
    print(f"Serving transcribe-doc on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping transcribe-doc service")
    finally:
        server.server_close()


def build_server(config: AppConfig, host: str = "127.0.0.1", port: int = 8765) -> LocalApiServer:
    """Build a configured HTTP server for CLI and tests."""
    mark_interrupted_jobs(Path(config.app.output_dir))
    server = LocalApiServer((host, port), LocalApiHandler)
    server.app_config = config
    server.executor = ThreadPoolExecutor(max_workers=max(1, config.runtime.max_parallel_jobs))
    server.model_executor = ThreadPoolExecutor(max_workers=1)
    server.model_downloads = set()
    server.model_lock = threading.Lock()
    return server


class LocalApiHandler(BaseHTTPRequestHandler):
    """Small local-only JSON API for jobs and artifacts."""

    server_version = "TranscribeDocLocal/0.1"

    def do_OPTIONS(self) -> None:
        self._send_empty(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        path_parts = self._path_parts()
        if path_parts == ["health"]:
            self._send_json(health_payload(self.app_config))
            return
        if path_parts == ["jobs"]:
            self._send_json({"jobs": list_jobs(self.output_root)})
            return
        if path_parts == ["models"]:
            self._send_json(
                {
                    "current_model": self.app_config.asr.model_name,
                    "models": _models_for_response(cast(LocalApiServer, self.server)),
                }
            )
            return
        if len(path_parts) == 2 and path_parts[0] == "jobs":
            self._send_job(path_parts[1])
            return
        if len(path_parts) == 3 and path_parts[0] == "jobs" and path_parts[2] == "transcript":
            self._send_transcript(path_parts[1])
            return
        if len(path_parts) == 3 and path_parts[0] == "jobs" and path_parts[2] == "artifacts":
            self._send_json({"artifacts": list_artifacts(self.output_root, path_parts[1])})
            return
        if len(path_parts) == 3 and path_parts[0] == "jobs" and path_parts[2] == "events":
            self._send_json({"events": list_events(self.output_root, path_parts[1])})
            return
        if len(path_parts) == 4 and path_parts[0] == "jobs" and path_parts[2] == "artifacts":
            self._send_artifact(path_parts[1], path_parts[3])
            return
        self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path_parts = self._path_parts()
        if path_parts == ["jobs"]:
            self._create_job()
            return
        if path_parts == ["batch"]:
            self._create_batch()
            return
        if path_parts == ["watch-folder", "scan"]:
            self._scan_watch_folder()
            return
        if path_parts == ["models", "download"]:
            self._download_model()
            return
        if path_parts == ["models", "download-all"]:
            self._download_all_models()
            return
        self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

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

    def _create_job(self) -> None:
        try:
            payload = self._read_job_request()
            job_config = config_for_payload(self.app_config, payload)
            resolved_input = resolve_single_input(payload["input_path"])
            output_root = Path(payload.get("output_dir") or self.output_root)
            display_title = display_title_from_payload(payload)
            job, _ = create_job(
                source_path=resolved_input.path,
                output_root=output_root,
                config=job_config,
                display_title=display_title,
            )
            job.metadata["execution"] = "background"
            persist_job(job, build_job_paths(output_root, job.job_id))
            self.executor.submit(
                _run_background_job,
                input_path=str(resolved_input.path),
                output_root=output_root,
                config=job_config,
                job_id=job.job_id,
                display_title=display_title,
                speaker_manifest_path=payload.get("speaker_manifest_path"),
                speaker_hint=payload.get("speaker_hint"),
                formats=payload.get("formats"),
            )
        except InputResolutionError as error:
            self._send_json({"error": str(error)}, HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        except (KeyError, ValueError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return

        body: JsonObject = {
            "exit_code": None,
            "message": f"Job {job.job_id} queued",
            "job": job_to_response(job),
        }
        self._send_json(body, HTTPStatus.ACCEPTED)

    def _create_batch(self) -> None:
        try:
            payload = self._read_json_object()
            input_paths = payload.get("input_paths")
            if not isinstance(input_paths, list) or not input_paths:
                raise ValueError("'input_paths' must be a non-empty list.")
            result = process_batch(
                input_paths,
                output_root=payload.get("output_dir") or self.output_root,
                config=config_for_payload(self.app_config, payload),
                speaker_manifest_path=payload.get("speaker_manifest_path"),
                speaker_hint=payload.get("speaker_hint"),
                formats=payload.get("formats"),
            )
        except ValueError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json(batch_to_response(result), HTTPStatus.CREATED)

    def _scan_watch_folder(self) -> None:
        try:
            payload = self._read_json_object()
            input_dir = payload.get("input_dir")
            if not isinstance(input_dir, str) or not input_dir:
                raise ValueError("'input_dir' is required.")
            result = scan_watch_folder(
                input_dir,
                output_root=payload.get("output_dir") or self.output_root,
                config=config_for_payload(self.app_config, payload),
                recursive=bool(payload.get("recursive", False)),
                stability_seconds=payload.get("stability_seconds"),
                speaker_manifest_path=payload.get("speaker_manifest_path"),
                speaker_hint=payload.get("speaker_hint"),
                formats=payload.get("formats"),
            )
        except ValueError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json(batch_to_response(result), HTTPStatus.CREATED)

    def _download_model(self) -> None:
        try:
            payload = self._read_json_object()
            model_name = payload.get("model_name") or self.app_config.asr.model_name
            if not isinstance(model_name, str) or not model_name.strip():
                raise ValueError("'model_name' is required.")
            model_name = model_name.strip()
            server = cast(LocalApiServer, self.server)
            with server.model_lock:
                if model_name in server.model_downloads:
                    self._send_json(
                        {
                            "status": "already_running",
                            "message": f"Загрузка модели {model_name} уже идёт",
                            "model": model_name,
                        },
                        HTTPStatus.ACCEPTED,
                    )
                    return
                server.model_downloads.add(model_name)
                mark_model_download_queued(model_name)
            self.model_executor.submit(run_model_download, server, model_name)
        except ValueError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json(
            {
                "status": "started",
                "message": f"Загрузка модели {model_name} запущена",
                "model": model_name,
            },
            HTTPStatus.ACCEPTED,
        )

    def _download_all_models(self) -> None:
        started: list[str] = []
        skipped: list[str] = []
        queue_position = 0
        for model in inspect_whisper_models():
            model_name = model.get("name")
            status = model.get("status")
            if not isinstance(model_name, str) or status == "ready":
                continue
            server = cast(LocalApiServer, self.server)
            with server.model_lock:
                if model_name in server.model_downloads:
                    skipped.append(model_name)
                    continue
                server.model_downloads.add(model_name)
                queue_position += 1
                mark_model_download_queued(model_name, queue_position)
            self.model_executor.submit(run_model_download, server, model_name)
            started.append(model_name)
        self._send_json(
            {
                "status": "started",
                "message": f"Запущено загрузок: {len(started)}",
                "started": started,
                "skipped": skipped,
            },
            HTTPStatus.ACCEPTED,
        )

    def _read_json_object(self) -> JsonObject:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def _read_job_request(self) -> JsonObject:
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            return self._read_multipart_job_request()
        payload = self._read_json_object()
        if not payload.get("input_path"):
            raise ValueError("'input_path' is required.")
        return payload

    def _read_multipart_job_request(self) -> JsonObject:
        form = cgi.FieldStorage(
            fp=cast(IO[Any], self.rfile),
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )
        media_item = form["media"] if "media" in form else None
        if media_item is None or not getattr(media_item, "filename", None):
            raise ValueError("multipart field 'media' is required.")

        self.upload_root.mkdir(parents=True, exist_ok=True)
        media_path = self.upload_root / Path(media_item.filename).name
        with media_path.open("wb") as handle:
            shutil.copyfileobj(media_item.file, handle)

        payload: JsonObject = {"input_path": str(media_path)}
        speaker_hint = _field_value(form, "speaker_hint")
        if speaker_hint:
            payload["speaker_hint"] = speaker_hint
        asr_backend = _field_value(form, "asr_backend")
        if asr_backend:
            payload["asr_backend"] = asr_backend
        asr_model = _field_value(form, "asr_model_name")
        if asr_model:
            payload["asr_model_name"] = asr_model
        display_title = _field_value(form, "display_title") or _field_value(form, "title")
        if display_title:
            payload["display_title"] = display_title
        speaker_item = form["speaker_manifest"] if "speaker_manifest" in form else None
        if speaker_item is not None and getattr(speaker_item, "filename", None):
            speaker_path = self.upload_root / Path(speaker_item.filename).name
            with speaker_path.open("wb") as handle:
                shutil.copyfileobj(speaker_item.file, handle)
            payload["speaker_manifest_path"] = str(speaker_path)
        return payload

    def _send_job(self, job_id: str) -> None:
        job = load_job(self.output_root, job_id)
        if job is None:
            self._send_json({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json({"job": job_to_response(job)})

    def _send_transcript(self, job_id: str) -> None:
        job_dir = self.output_root / job_id
        if not job_dir.exists():
            self._send_json({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json(
            {
                "job": load_job(self.output_root, job_id),
                "segments": read_json_file(job_dir / "segments.json", []),
                "words": read_json_file(job_dir / "words.json", []),
            }
        )

    def _send_artifact(self, job_id: str, artifact_name: str) -> None:
        artifact = artifact_by_name(self.output_root, job_id, artifact_name)
        if artifact is None:
            self._send_json({"error": "artifact_not_found"}, HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(artifact.stat().st_size))
        self.send_header("Content-Disposition", f'attachment; filename="{artifact.name}"')
        self.end_headers()
        with artifact.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def _path_parts(self) -> list[str]:
        parsed = urlparse(self.path)
        return [unquote(part) for part in parsed.path.split("/") if part]

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()


def _field_value(form: cgi.FieldStorage, name: str) -> str | None:
    if name not in form:
        return None
    item = form[name]
    value = getattr(item, "value", None)
    return value if isinstance(value, str) and value.strip() else None


def _run_background_job(
    *,
    input_path: str,
    output_root: Path,
    config: AppConfig,
    job_id: str,
    display_title: str | None,
    speaker_manifest_path: str | None,
    speaker_hint: str | None,
    formats: str | None,
) -> None:
    result = process_single_file(
        input_path,
        output_root=output_root,
        config=config,
        job_id=job_id,
        display_title=display_title,
        speaker_manifest_path=speaker_manifest_path,
        speaker_hint=speaker_hint,
        formats=formats,
    )
    if result.job is None:
        job_paths = build_job_paths(output_root, job_id)
        job_payload: JsonObject = {
            "job_id": job_id,
            "source_paths": [input_path],
            "status": JobStatus.FAILED.value,
            "detected_language": None,
            "artifacts": {},
            "metadata": {"display_title": display_title or Path(input_path).stem},
            "warnings": [result.message],
        }
        job_paths.job_json.write_text(json.dumps(job_payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _models_for_response(server: LocalApiServer) -> list[dict[str, Any]]:
    with server.model_lock:
        active_downloads = set(server.model_downloads)
    return [_model_download_state_for_response(model, active_downloads) for model in inspect_whisper_models()]

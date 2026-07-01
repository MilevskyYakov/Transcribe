"""Job, batch, watch-folder, and artifact endpoint functions."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from transcribe_doc.app.config import AppConfig
from transcribe_doc.core.batch import process_batch, scan_watch_folder
from transcribe_doc.core.job_manager import create_job, persist_job
from transcribe_doc.core.processing import process_single_file
from transcribe_doc.ingest.input_resolver import InputResolutionError, resolve_single_input
from transcribe_doc.storage.paths import build_job_paths
from transcribe_doc.service.contracts import (
    ArtifactsResponse,
    EventsResponse,
    TranscriptResponse,
    dataclass_payload,
)
from transcribe_doc.service.http_response import ApiResponse, file_response, json_response
from transcribe_doc.service.job_store import (
    artifact_by_name,
    list_artifacts,
    list_events,
    list_jobs,
    load_job,
    read_json_file,
    write_failed_job_payload,
)
from transcribe_doc.service.responses import (
    batch_to_response,
    config_for_payload,
    display_title_from_payload,
    job_to_response,
)
from transcribe_doc.service.types import JsonObject


def list_jobs_endpoint(ctx: Any) -> ApiResponse:
    return json_response({"jobs": list_jobs(ctx.output_root)})


def get_job_endpoint(ctx: Any, job_id: str) -> ApiResponse:
    job = load_job(ctx.output_root, job_id)
    if job is None:
        return json_response({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
    return json_response({"job": job_to_response(job)})


def transcript_endpoint(ctx: Any, job_id: str) -> ApiResponse:
    job_dir = ctx.output_root / job_id
    if not job_dir.exists():
        return json_response({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
    segments = read_json_file(job_dir / "segments.json", [])
    words = read_json_file(job_dir / "words.json", [])
    return json_response(
        dataclass_payload(
            TranscriptResponse(
                job=load_job(ctx.output_root, job_id),
                segments=segments if isinstance(segments, list) else [],
                words=words if isinstance(words, list) else [],
            )
        )
    )


def artifacts_endpoint(ctx: Any, job_id: str) -> ApiResponse:
    return json_response(
        dataclass_payload(ArtifactsResponse(artifacts=list_artifacts(ctx.output_root, job_id)))
    )


def events_endpoint(ctx: Any, job_id: str) -> ApiResponse:
    return json_response(
        dataclass_payload(EventsResponse(events=list_events(ctx.output_root, job_id)))
    )


def artifact_download_endpoint(ctx: Any, job_id: str, artifact_name: str) -> ApiResponse:
    artifact = artifact_by_name(ctx.output_root, job_id, artifact_name)
    if artifact is None:
        return json_response({"error": "artifact_not_found"}, HTTPStatus.NOT_FOUND)
    return file_response(artifact, artifact.name)


def create_job_endpoint(ctx: Any) -> ApiResponse:
    try:
        payload = ctx.read_job_request()
        job_config = config_for_payload(ctx.app_config, payload)
        resolved_input = resolve_single_input(payload["input_path"])
        output_root = Path(payload.get("output_dir") or ctx.output_root)
        display_title = display_title_from_payload(payload)
        job, _ = create_job(
            source_path=resolved_input.path,
            output_root=output_root,
            config=job_config,
            display_title=display_title,
        )
        job.metadata["execution"] = "background"
        persist_job(job, build_job_paths(output_root, job.job_id))
        ctx.executor.submit(
            run_background_job,
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
        return json_response({"error": str(error)}, HTTPStatus.UNPROCESSABLE_ENTITY)
    except (KeyError, ValueError) as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    body: JsonObject = {
        "exit_code": None,
        "message": f"Job {job.job_id} queued",
        "job": job_to_response(job),
    }
    return json_response(body, HTTPStatus.ACCEPTED)


def create_batch_endpoint(ctx: Any) -> ApiResponse:
    try:
        payload = ctx.read_json_object()
        input_paths = payload.get("input_paths")
        if not isinstance(input_paths, list) or not input_paths:
            raise ValueError("'input_paths' must be a non-empty list.")
        result = process_batch(
            input_paths,
            output_root=payload.get("output_dir") or ctx.output_root,
            config=config_for_payload(ctx.app_config, payload),
            speaker_manifest_path=payload.get("speaker_manifest_path"),
            speaker_hint=payload.get("speaker_hint"),
            formats=payload.get("formats"),
        )
    except ValueError as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    return json_response(batch_to_response(result), HTTPStatus.CREATED)


def scan_watch_folder_endpoint(ctx: Any) -> ApiResponse:
    try:
        payload = ctx.read_json_object()
        input_dir = payload.get("input_dir")
        if not isinstance(input_dir, str) or not input_dir:
            raise ValueError("'input_dir' is required.")
        result = scan_watch_folder(
            input_dir,
            output_root=payload.get("output_dir") or ctx.output_root,
            config=config_for_payload(ctx.app_config, payload),
            recursive=bool(payload.get("recursive", False)),
            stability_seconds=payload.get("stability_seconds"),
            speaker_manifest_path=payload.get("speaker_manifest_path"),
            speaker_hint=payload.get("speaker_hint"),
            formats=payload.get("formats"),
        )
    except ValueError as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    return json_response(batch_to_response(result), HTTPStatus.CREATED)


def run_background_job(
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
        write_failed_job_payload(
            output_root,
            job_id,
            input_path=input_path,
            message=result.message,
            display_title=display_title,
        )

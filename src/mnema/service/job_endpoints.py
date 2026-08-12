"""Job, batch, watch-folder, and artifact endpoint functions."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any

from mnema.app.config import AppConfig
from mnema.core.batch import process_batch, scan_watch_folder
from mnema.core.job_manager import create_job, persist_job
from mnema.core.processing import process_single_file
from mnema.ingest.input_resolver import InputResolutionError, resolve_single_input
from mnema.service.batch_session_store import (
    BATCH_SESSION_LOCK,
    batch_session_response,
    create_batch_session,
    find_batch_item,
    list_batch_sessions,
    load_batch_session,
    load_batch_session_payload,
    write_batch_session,
)
from mnema.service.contracts import (
    ArtifactsResponse,
    EventsResponse,
    TranscriptResponse,
    dataclass_payload,
)
from mnema.service.http_response import ApiResponse, file_response, json_response
from mnema.service.job_store import (
    artifact_by_name,
    list_artifacts,
    list_events,
    list_jobs,
    load_job,
    read_json_file,
    write_failed_job_payload,
    write_job_payload,
)
from mnema.service.responses import (
    batch_to_response,
    config_for_payload,
    display_title_from_payload,
    job_to_response,
)
from mnema.service.types import JsonObject
from mnema.storage.final_markdown import (
    inspect_saved_final_markdown,
    save_final_markdown,
    sync_saved_markdown_metadata,
    title_derived_markdown_filename,
    validate_final_markdown_dir,
)
from mnema.storage.paths import build_job_paths
from mnema.storage.speaker_review import (
    apply_speaker_assignments_to_segment_payloads,
    build_speaker_review_payload,
    update_speaker_assignments,
)
from mnema.storage.temp_cleanup import (
    cleanup_stale_temporary_media,
    cleanup_successful_job_media,
)


def list_jobs_endpoint(ctx: Any) -> ApiResponse:
    return json_response({"jobs": list_jobs(ctx.output_root)})


def list_batch_sessions_endpoint(ctx: Any) -> ApiResponse:
    return json_response({"batch_sessions": list_batch_sessions(ctx.output_root)})


def get_batch_session_endpoint(ctx: Any, session_id: str) -> ApiResponse:
    try:
        session = load_batch_session(ctx.output_root, session_id)
    except ValueError as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    if session is None:
        return json_response({"error": "batch_session_not_found"}, HTTPStatus.NOT_FOUND)
    return json_response({"batch_session": session})


def create_batch_session_endpoint(ctx: Any) -> ApiResponse:
    try:
        request = ctx.read_json_object()
        raw_items = request.get("items")
        if not isinstance(raw_items, list) or not all(isinstance(item, dict) for item in raw_items):
            raise ValueError("'items' must be a non-empty list of objects.")
        raw_common_output_dir = request.get("common_output_dir")
        common_output_dir = (
            str(validate_final_markdown_dir(raw_common_output_dir))
            if isinstance(raw_common_output_dir, str) and raw_common_output_dir.strip()
            else None
        )
        session = create_batch_session(
            ctx.output_root,
            raw_items,
            common_output_dir=common_output_dir,
        )
    except InputResolutionError as error:
        return json_response({"error": str(error)}, HTTPStatus.UNPROCESSABLE_ENTITY)
    except ValueError as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    return json_response({"batch_session": session}, HTTPStatus.CREATED)


def update_batch_session_output_endpoint(ctx: Any, session_id: str) -> ApiResponse:
    with BATCH_SESSION_LOCK:
        return _update_batch_session_output_endpoint(ctx, session_id)


def _update_batch_session_output_endpoint(ctx: Any, session_id: str) -> ApiResponse:
    try:
        session = load_batch_session_payload(ctx.output_root, session_id)
        if session is None:
            return json_response({"error": "batch_session_not_found"}, HTTPStatus.NOT_FOUND)
        request = ctx.read_json_object()
        raw_output_dir = request.get("common_output_dir")
        if not isinstance(raw_output_dir, str) or not raw_output_dir.strip():
            raise ValueError("'common_output_dir' is required.")
        session["common_output_dir"] = str(validate_final_markdown_dir(raw_output_dir))
        write_batch_session(ctx.output_root, session)
    except ValueError as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    return json_response({"batch_session": batch_session_response(ctx.output_root, session)})


def submit_batch_session_item_endpoint(ctx: Any, session_id: str, item_id: str) -> ApiResponse:
    with BATCH_SESSION_LOCK:
        return _submit_batch_session_item_endpoint(ctx, session_id, item_id)


def _submit_batch_session_item_endpoint(ctx: Any, session_id: str, item_id: str) -> ApiResponse:
    try:
        session = load_batch_session_payload(ctx.output_root, session_id)
        if session is None:
            return json_response({"error": "batch_session_not_found"}, HTTPStatus.NOT_FOUND)
        item = find_batch_item(session, item_id)
        if item is None:
            return json_response({"error": "batch_item_not_found"}, HTTPStatus.NOT_FOUND)
        current = next(
            entry
            for entry in batch_session_response(ctx.output_root, session)["items"]
            if entry["item_id"] == item_id
        )
        if current["status"] in {"processing", "ready"}:
            raise ValueError("Only unconfigured or failed batch items can be started.")
        if current["status"] == "configure":
            first_unconfigured = next(
                entry
                for entry in batch_session_response(ctx.output_root, session)["items"]
                if entry["status"] == "configure"
            )
            if first_unconfigured["item_id"] != item_id:
                raise ValueError("Configure batch items in order.")

        request = _read_batch_item_request(ctx)
        raw_input_path = request.get("input_path") or item.get("input_path")
        if not isinstance(raw_input_path, str) or not raw_input_path.strip():
            raise ValueError("Batch item media is no longer available. Choose the files again.")
        resolved_input = resolve_single_input(raw_input_path)
        display_title = display_title_from_payload(request) or str(item["display_title"])
        raw_output_dir = (
            request.get("final_markdown_dir")
            or item.get("output_dir")
            or session.get("common_output_dir")
        )
        if not isinstance(raw_output_dir, str) or not raw_output_dir.strip():
            raise ValueError("Выберите папку для сохранения транскрипций")
        final_markdown_dir = str(validate_final_markdown_dir(raw_output_dir))
        job_config = config_for_payload(ctx.app_config, request)
        initial_metadata: dict[str, object] = {
            "final_markdown_dir": final_markdown_dir,
            "batch_session_id": session_id,
            "batch_item_id": item_id,
        }
        job, _ = create_job(
            source_path=resolved_input.path,
            output_root=ctx.output_root,
            config=job_config,
            display_title=display_title,
            initial_metadata=initial_metadata,
        )
        job.metadata["execution"] = "background"
        persist_job(job, build_job_paths(ctx.output_root, job.job_id))

        item["input_path"] = str(resolved_input.path)
        item["display_title"] = display_title
        item["output_dir"] = final_markdown_dir
        item["output_dir_override"] = (
            final_markdown_dir
            if final_markdown_dir != session.get("common_output_dir")
            else None
        )
        item["job_id"] = job.job_id
        attempts = item.setdefault("attempt_job_ids", [])
        if isinstance(attempts, list):
            attempts.append(job.job_id)
        write_batch_session(ctx.output_root, session)
        ctx.executor.submit(
            run_background_job,
            input_path=str(resolved_input.path),
            output_root=ctx.output_root,
            config=job_config,
            job_id=job.job_id,
            display_title=display_title,
            speaker_manifest_path=request.get("speaker_manifest_path"),
            speaker_hint=request.get("speaker_hint"),
            formats=request.get("formats"),
            final_markdown_dir=final_markdown_dir,
            initial_metadata=initial_metadata,
        )
    except InputResolutionError as error:
        return json_response({"error": str(error)}, HTTPStatus.UNPROCESSABLE_ENTITY)
    except (KeyError, StopIteration, ValueError) as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    return json_response(
        {
            "job": job_to_response(job),
            "batch_session": batch_session_response(ctx.output_root, session),
        },
        HTTPStatus.ACCEPTED,
    )


def cleanup_temp_endpoint(ctx: Any) -> ApiResponse:
    report = cleanup_stale_temporary_media(
        output_root=ctx.output_root,
        temp_root=Path(ctx.app_config.app.temp_dir),
    )
    return json_response(report.to_payload())


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
    job = load_job(ctx.output_root, job_id)
    segment_payloads = segments if isinstance(segments, list) else []
    if job is not None:
        segment_payloads = apply_speaker_assignments_to_segment_payloads(job, segment_payloads)
    return json_response(
        dataclass_payload(
            TranscriptResponse(
                job=job,
                segments=segment_payloads,
                words=words if isinstance(words, list) else [],
            )
        )
    )


def speaker_review_endpoint(ctx: Any, job_id: str) -> ApiResponse:
    job = load_job(ctx.output_root, job_id)
    if job is None:
        return json_response({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
    segments = read_json_file(ctx.output_root / job_id / "segments.json", [])
    segment_payloads = segments if isinstance(segments, list) else []
    return json_response(build_speaker_review_payload(job, segment_payloads))


def update_speaker_review_endpoint(ctx: Any, job_id: str) -> ApiResponse:
    job = load_job(ctx.output_root, job_id)
    if job is None:
        return json_response({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
    segments = read_json_file(ctx.output_root / job_id / "segments.json", [])
    segment_payloads = segments if isinstance(segments, list) else []
    try:
        payload = ctx.read_json_object()
        raw_assignments = payload.get("assignments", {})
        if not isinstance(raw_assignments, dict):
            raise ValueError("'assignments' must be an object.")
        review_payload = update_speaker_assignments(
            job,
            segment_payloads,
            {str(key): str(value) for key, value in raw_assignments.items()},
            skipped=bool(payload.get("skipped", False)),
        )
        final_markdown = None
        raw_metadata = job.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        autosave_dir = payload.get("autosave_dir") or metadata.get("final_markdown_dir")
        if isinstance(autosave_dir, str) and autosave_dir.strip():
            status = save_final_markdown(job, ctx.output_root, autosave_dir)
            sync_saved_markdown_metadata(job, status)
            cleanup_report = cleanup_successful_job_media(
                job,
                output_root=ctx.output_root,
                job_id=job_id,
                temp_root=Path(ctx.app_config.app.temp_dir),
            )
            job["metadata"]["saved_markdown_cleanup"] = cleanup_report.to_payload()
            final_markdown = status.to_payload()
        write_job_payload(ctx.output_root / job_id / "job.json", job)
    except FileNotFoundError as error:
        return json_response({"error": str(error)}, HTTPStatus.NOT_FOUND)
    except ValueError as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    response = {"speaker_review": review_payload}
    if final_markdown is not None:
        response["final_markdown"] = final_markdown
    return json_response(response)


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
    download_name = artifact.name
    if artifact_name == "final_speech_text_md":
        job = load_job(ctx.output_root, job_id)
        if job is not None:
            download_name = title_derived_markdown_filename(job)
    return file_response(artifact, download_name)


def final_markdown_status_endpoint(ctx: Any, job_id: str) -> ApiResponse:
    job = load_job(ctx.output_root, job_id)
    if job is None:
        return json_response({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
    status = inspect_saved_final_markdown(job)
    sync_saved_markdown_metadata(job, status)
    write_job_payload(ctx.output_root / job_id / "job.json", job)
    return json_response(status.to_payload())


def save_final_markdown_endpoint(ctx: Any, job_id: str) -> ApiResponse:
    job = load_job(ctx.output_root, job_id)
    if job is None:
        return json_response({"error": "job_not_found"}, HTTPStatus.NOT_FOUND)
    try:
        payload = ctx.read_json_object()
        raw_metadata = job.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        autosave_dir = payload.get("autosave_dir") or metadata.get("final_markdown_dir")
        if not isinstance(autosave_dir, str) or not autosave_dir.strip():
            raise ValueError("Выберите папку для сохранения транскрипций")
        status = save_final_markdown(job, ctx.output_root, autosave_dir)
        sync_saved_markdown_metadata(job, status)
        cleanup_report = cleanup_successful_job_media(
            job,
            output_root=ctx.output_root,
            job_id=job_id,
            temp_root=Path(ctx.app_config.app.temp_dir),
        )
        job["metadata"]["saved_markdown_cleanup"] = cleanup_report.to_payload()
        write_job_payload(ctx.output_root / job_id / "job.json", job)
    except FileNotFoundError as error:
        return json_response({"error": str(error)}, HTTPStatus.NOT_FOUND)
    except ValueError as error:
        return json_response({"error": str(error)}, HTTPStatus.BAD_REQUEST)
    return json_response(status.to_payload())


def create_job_endpoint(ctx: Any) -> ApiResponse:
    try:
        payload = ctx.read_job_request()
        job_config = config_for_payload(ctx.app_config, payload)
        resolved_input = resolve_single_input(payload["input_path"])
        output_root = Path(payload.get("output_dir") or ctx.output_root)
        display_title = display_title_from_payload(payload)
        raw_final_markdown_dir = payload.get("final_markdown_dir")
        final_markdown_dir = (
            str(validate_final_markdown_dir(raw_final_markdown_dir))
            if isinstance(raw_final_markdown_dir, str) and raw_final_markdown_dir.strip()
            else None
        )
        initial_metadata: dict[str, object] | None = (
            {"final_markdown_dir": final_markdown_dir} if final_markdown_dir else None
        )
        job, _ = create_job(
            source_path=resolved_input.path,
            output_root=output_root,
            config=job_config,
            display_title=display_title,
            initial_metadata=initial_metadata,
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
            final_markdown_dir=final_markdown_dir,
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
            executor=ctx.executor,
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
            executor=ctx.executor,
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
    final_markdown_dir: str | None = None,
    initial_metadata: dict[str, object] | None = None,
) -> None:
    result = process_single_file(
        input_path,
        output_root=output_root,
        config=config,
        job_id=job_id,
        display_title=display_title,
        initial_metadata=initial_metadata
        or ({"final_markdown_dir": final_markdown_dir} if final_markdown_dir else None),
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
        if initial_metadata:
            payload = load_job(output_root, job_id)
            if payload is not None:
                metadata = payload.setdefault("metadata", {})
                if isinstance(metadata, dict):
                    metadata.update(initial_metadata)
                write_job_payload(output_root / job_id / "job.json", payload)
        return
    if final_markdown_dir:
        payload = load_job(output_root, job_id)
        segments = read_json_file(output_root / job_id / "segments.json", [])
        segment_payloads = segments if isinstance(segments, list) else []
        if (
            payload is not None
            and build_speaker_review_payload(payload, segment_payloads)["status"] != "pending"
        ):
            status = save_final_markdown(payload, output_root, final_markdown_dir)
            sync_saved_markdown_metadata(payload, status)
            cleanup_report = cleanup_successful_job_media(
                payload,
                output_root=output_root,
                job_id=job_id,
                temp_root=Path(config.app.temp_dir),
            )
            payload["metadata"]["saved_markdown_cleanup"] = cleanup_report.to_payload()
            write_job_payload(output_root / job_id / "job.json", payload)


def _read_batch_item_request(ctx: Any) -> JsonObject:
    """Allow native JSON submits to inherit the source path stored by the session."""
    headers = getattr(ctx, "headers", None)
    content_type = headers.get("Content-Type", "") if headers is not None else ""
    if not content_type or content_type.startswith("multipart/form-data"):
        return ctx.read_job_request()
    return ctx.read_json_object()

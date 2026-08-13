"""Reusable processing entrypoints shared by CLI and local service."""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from mnema.alignment.factory import build_alignment_backend
from mnema.app.config import AppConfig
from mnema.app.models import Job, JobStatus, TranscriptSegment
from mnema.asr.factory import build_asr_backend
from mnema.asr.transcription_service import TranscriptionResult, TranscriptionService
from mnema.core.job_manager import append_job_event, create_job
from mnema.diarization.factory import build_diarization_backend
from mnema.diarization.quality import (
    build_diarization_confidence,
    collect_diarization_quality_summary,
)
from mnema.diarization.speaker_mapper import apply_expected_speaker_mapping
from mnema.export.writers import export_all
from mnema.ingest.input_resolver import InputResolutionError, resolve_single_input
from mnema.ingest.manifest_loader import load_speaker_manifest, speaker_hint_to_manifest
from mnema.media.normalizer import normalize_media
from mnema.media.probes import probe_media
from mnema.storage.artifact_store import (
    mutate_job_payload,
    save_segments,
    save_transcription_result,
    save_words,
)
from mnema.storage.paths import JobPaths
from mnema.storage.temp_cleanup import cleanup_successful_job_media
from mnema.summary.extractive import write_summary

T = TypeVar("T")


@dataclass(frozen=True)
class ProcessingResult:
    """Result returned to CLI and API callers."""

    exit_code: int
    job: Job | None
    job_paths: JobPaths | None
    message: str


@dataclass(frozen=True)
class StageEvent:
    """Canonical event metadata for visible processing stages."""

    stage: str
    message: str
    progress: int


STAGE_EVENTS = {
    "queued": StageEvent("queued", "Задача создана и ожидает запуска", 0),
    "processing": StageEvent("processing", "Обработка началась", 5),
    "probe": StageEvent("probe", "Проверяю медиафайл", 10),
    "normalize": StageEvent("normalize", "Нормализую аудио через ffmpeg", 20),
    "speakers_hint": StageEvent("speakers", "Подсказка по участникам учтена", 28),
    "speakers_manifest": StageEvent("speakers", "Список спикеров загружен", 28),
    "asr_start": StageEvent("asr", "Запускаю распознавание речи", 35),
    "transcript": StageEvent("transcript", "", 65),
    "diarization": StageEvent("diarization", "Сохраняю диагностику спикеров", 72),
    "speaker_mapping": StageEvent("speaker_mapping", "Сопоставляю имена спикеров", 76),
    "artifacts": StageEvent("artifacts", "Сохраняю JSON-артефакты", 82),
    "export": StageEvent("export", "Генерирую пользовательские форматы", 90),
    "summary": StageEvent("summary", "Генерирую краткое summary", 95),
    "done_ok": StageEvent("done", "Задача успешно завершена", 100),
    "done_warning": StageEvent("done", "Задача завершена с предупреждениями", 100),
}


@dataclass
class ProcessingContext:
    """Mutable state shared by explicit single-file processing stages."""

    resolved_input_path: Path
    config: AppConfig
    job: Job
    job_paths: JobPaths
    speaker_manifest_path: str | Path | None
    speaker_hint: str | None
    formats: str | None
    asr_backend_factory: Callable[[AppConfig], Any]
    diarization_backend_factory: Callable[[AppConfig, dict[str, Any] | None], Any]
    speaker_manifest: dict[str, Any] | None = None
    transcription_result: TranscriptionResult | None = None


def process_single_file(
    input_path: str | Path,
    *,
    output_root: str | Path,
    config: AppConfig,
    job_id: str | None = None,
    display_title: str | None = None,
    initial_metadata: dict[str, object] | None = None,
    speaker_manifest_path: str | Path | None = None,
    speaker_hint: str | None = None,
    formats: str | None = None,
    asr_backend_factory=build_asr_backend,
    diarization_backend_factory=build_diarization_backend,
) -> ProcessingResult:
    """Run the single-file pipeline and persist all job artifacts."""
    try:
        resolved_input = resolve_single_input(str(input_path))
    except InputResolutionError as error:
        return ProcessingResult(1, None, None, str(error))

    job, job_paths = create_job(
        source_path=resolved_input.path,
        output_root=output_root,
        config=config,
        job_id=job_id,
        display_title=display_title,
        initial_metadata=initial_metadata,
    )
    context = ProcessingContext(
        resolved_input_path=resolved_input.path,
        config=config,
        job=job,
        job_paths=job_paths,
        speaker_manifest_path=speaker_manifest_path,
        speaker_hint=speaker_hint,
        formats=formats,
        asr_backend_factory=asr_backend_factory,
        diarization_backend_factory=diarization_backend_factory,
    )

    try:
        for stage in SINGLE_FILE_PIPELINE:
            stage(context)
        _cleanup_successful_intermediates(context)

        return ProcessingResult(
            0,
            job,
            job_paths,
            f"Job {job.job_id} wrote transcript to {job_paths.segments_json}",
        )
    except Exception as error:
        failure_message = _public_failure_message(error)
        failure_detail = _failure_detail(error)
        job.status = JobStatus.FAILED
        job.warnings.append(failure_detail)
        append_job_event(
            job,
            job_paths,
            stage="failed",
            status="error",
            message=failure_message,
            progress=int(job.metadata.get("progress", 0)),
        )
        if failure_detail != failure_message:
            with job_paths.log_file.open("a", encoding="utf-8") as handle:
                handle.write(f"Failure detail:\n{failure_detail}\n")
        return ProcessingResult(1, job, job_paths, failure_message)


def start_job_stage(context: ProcessingContext) -> None:
    _emit(context, "queued")
    context.job.status = JobStatus.PROCESSING
    _emit(context, "processing")


def probe_media_stage(context: ProcessingContext) -> None:
    _emit(context, "probe")
    probe_media(context.resolved_input_path)


def normalize_audio_stage(context: ProcessingContext) -> None:
    _emit(context, "normalize")
    normalize_media(
        context.resolved_input_path,
        context.job_paths.normalized_audio,
        sample_rate=context.config.media.sample_rate,
        mono=context.config.media.mono,
    )


def resolve_speakers_stage(context: ProcessingContext) -> None:
    context.speaker_manifest = load_speaker_manifest(
        str(context.speaker_manifest_path) if context.speaker_manifest_path is not None else None
    ) or speaker_hint_to_manifest(context.speaker_hint)
    if not context.speaker_manifest:
        return

    context.job.metadata["speaker_manifest"] = context.speaker_manifest
    event_key = (
        "speakers_hint"
        if context.speaker_manifest.get("source") == "freeform_speaker_hint"
        else "speakers_manifest"
    )
    _emit(context, event_key)


def transcribe_stage(context: ProcessingContext) -> None:
    _emit(context, "asr_start")
    asr_backend = context.asr_backend_factory(context.config)
    alignment_backend = build_alignment_backend(context.config)
    diarization_backend = context.diarization_backend_factory(
        context.config,
        context.speaker_manifest,
    )
    context.transcription_result = _run_with_heartbeat(
        lambda: TranscriptionService(
            asr_backend=asr_backend,
            alignment_backend=alignment_backend,
            diarization_backend=diarization_backend,
        ).transcribe(str(context.job_paths.normalized_audio)),
        job=context.job,
        job_paths=context.job_paths,
        stage="asr",
        message="Распознавание всё ещё выполняется. Это может быть загрузка модели или обработка длинного файла",
        start_progress=40,
        max_progress=60,
    )
    _emit(
        context,
        "transcript",
        message=f"Распознавание завершено: сегментов {len(context.transcription_result.segments)}",
    )


def diagnose_diarization_stage(context: ProcessingContext) -> None:
    transcription_result = _require_transcription_result(context)
    diarization_quality_summary = collect_diarization_quality_summary(transcription_result.segments)
    if diarization_quality_summary is not None:
        context.job.metadata["diarization_quality"] = diarization_quality_summary
    if _has_diarization_annotations(transcription_result.segments):
        _emit(context, "diarization")
        save_segments(transcription_result.segments, context.job_paths.diarization_dump)
    if diarization_quality_summary is not None:
        confidence = build_diarization_confidence(diarization_quality_summary)
        context.job.metadata["diarization_confidence"] = confidence
        if confidence["mode"] == "transcript_without_labels":
            context.transcription_result = transcription_result.__class__(
                segments=[
                    _without_speaker_label(segment) for segment in transcription_result.segments
                ],
                warnings=transcription_result.warnings,
                detected_language=transcription_result.detected_language,
            )
            return
    if context.speaker_manifest and context.config.diarization.allow_expected_speaker_mapping:
        _emit(context, "speaker_mapping")
        context.transcription_result = transcription_result.__class__(
            segments=apply_expected_speaker_mapping(
                transcription_result.segments,
                context.speaker_manifest,
            ),
            warnings=transcription_result.warnings,
            detected_language=transcription_result.detected_language,
        )


def persist_artifacts_stage(context: ProcessingContext) -> None:
    transcription_result = _require_transcription_result(context)
    _emit(context, "artifacts")
    save_transcription_result(transcription_result, context.job_paths.transcript_raw_json)
    save_segments(transcription_result.segments, context.job_paths.segments_json)
    save_words(transcription_result.segments, context.job_paths.words_json)


def export_stage(context: ProcessingContext) -> None:
    transcription_result = _require_transcription_result(context)
    _emit(context, "export")
    export_all(
        transcription_result.segments,
        _selected_export_paths(context.config, context.job_paths, context.formats),
        title=str(context.job.metadata.get("display_title") or ""),
    )


def summary_stage(context: ProcessingContext) -> None:
    transcription_result = _require_transcription_result(context)
    if not context.config.summary.enabled:
        return
    _emit(context, "summary")
    write_summary(
        transcription_result.segments,
        context.job_paths.summary_md,
        context.job_paths.summary_json,
    )


def complete_job_stage(context: ProcessingContext) -> None:
    transcription_result = _require_transcription_result(context)
    context.job.detected_language = transcription_result.detected_language
    if transcription_result.warnings:
        context.job.status = JobStatus.COMPLETED_WITH_WARNINGS
        context.job.warnings.extend(transcription_result.warnings)
        _emit(context, "done_warning", status="warning")
        return

    context.job.status = JobStatus.COMPLETED
    _emit(context, "done_ok")


def _cleanup_successful_intermediates(context: ProcessingContext) -> None:
    """Remove session artifacts after a completed job has durable outputs."""
    if context.job.status not in {JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_WARNINGS}:
        return
    def cleanup(payload: dict[str, Any]) -> None:
        cleanup_successful_job_media(
            payload,
            output_root=context.job_paths.job_dir.parent,
            job_id=context.job.job_id,
            temp_root=Path(context.config.app.temp_dir),
        )

    payload = mutate_job_payload(context.job_paths.job_json, cleanup)
    metadata = payload.get("metadata") if payload is not None else None
    if isinstance(metadata, dict):
        context.job.metadata.update(metadata)


SINGLE_FILE_PIPELINE: tuple[Callable[[ProcessingContext], None], ...] = (
    start_job_stage,
    probe_media_stage,
    normalize_audio_stage,
    resolve_speakers_stage,
    transcribe_stage,
    diagnose_diarization_stage,
    persist_artifacts_stage,
    export_stage,
    summary_stage,
    complete_job_stage,
)


def _emit(
    context: ProcessingContext,
    event_key: str,
    *,
    status: str = "ok",
    message: str | None = None,
) -> None:
    event = STAGE_EVENTS[event_key]
    append_job_event(
        context.job,
        context.job_paths,
        stage=event.stage,
        status=status,
        message=message if message is not None else event.message,
        progress=event.progress,
    )


def _require_transcription_result(context: ProcessingContext) -> TranscriptionResult:
    if context.transcription_result is None:
        raise RuntimeError("Transcription stage did not produce a result")
    return context.transcription_result


def _has_diarization_annotations(segments: list[TranscriptSegment]) -> bool:
    return any(segment.speaker_label is not None or segment.mapping is not None for segment in segments)


def _without_speaker_label(segment: TranscriptSegment) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=segment.segment_id,
        start_seconds=segment.start_seconds,
        end_seconds=segment.end_seconds,
        text_raw=segment.text_raw,
        text_clean=segment.text_clean,
        words=segment.words,
    )


def _selected_export_paths(
    config: AppConfig,
    job_paths: JobPaths,
    formats: str | None,
) -> dict[str, Path]:
    if formats:
        enabled = {item.strip().lower() for item in formats.split(",") if item.strip()}
    else:
        enabled = {
            name
            for name in ("txt", "md", "docx", "pdf", "srt", "json")
            if bool(getattr(config.export, name))
        }
    available = {
        "txt": job_paths.transcript_clean_txt,
        "md": job_paths.transcript_clean_md,
        "final_text_md": job_paths.final_speech_text_md,
        "docx": job_paths.transcript_clean_docx,
        "pdf": job_paths.transcript_clean_pdf,
        "srt": job_paths.subtitles_srt,
        "json": job_paths.segments_json,
    }
    selected = {name: path for name, path in available.items() if name in enabled}
    if "md" in enabled:
        selected["final_text_md"] = job_paths.final_speech_text_md
    return selected


def _run_with_heartbeat(
    action: Callable[[], T],
    *,
    job: Job,
    job_paths: JobPaths,
    stage: str,
    message: str,
    start_progress: int,
    max_progress: int,
    interval_seconds: float = 30.0,
) -> T:
    stop = threading.Event()

    def heartbeat() -> None:
        progress = start_progress
        while not stop.wait(interval_seconds):
            append_job_event(
                job,
                job_paths,
                stage=stage,
                status="ok",
                message=message,
                progress=progress,
            )
            progress = min(max_progress, progress + 5)

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        return action()
    finally:
        stop.set()
        thread.join(timeout=0.2)


def _public_failure_message(error: Exception) -> str:
    message = str(error)
    if error.__cause__ is not None and "CoreML" in _failure_detail(error):
        return message
    return message


def _failure_detail(error: Exception) -> str:
    if error.__cause__ is None:
        return str(error)
    return "".join(traceback.format_exception(error)).strip()

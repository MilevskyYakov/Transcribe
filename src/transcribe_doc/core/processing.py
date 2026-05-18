"""Reusable processing entrypoints shared by CLI and local service."""

from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from transcribe_doc.alignment.factory import build_alignment_backend
from transcribe_doc.app.config import AppConfig
from transcribe_doc.app.models import Job, JobStatus, TranscriptSegment
from transcribe_doc.asr.factory import build_asr_backend
from transcribe_doc.asr.transcription_service import TranscriptionService
from transcribe_doc.core.job_manager import append_job_event, create_job
from transcribe_doc.diarization.factory import build_diarization_backend
from transcribe_doc.diarization.quality import collect_diarization_quality_summary
from transcribe_doc.diarization.speaker_mapper import apply_expected_speaker_mapping
from transcribe_doc.export.writers import export_all
from transcribe_doc.ingest.input_resolver import InputResolutionError, resolve_single_input
from transcribe_doc.ingest.manifest_loader import load_speaker_manifest, speaker_hint_to_manifest
from transcribe_doc.media.normalizer import normalize_media
from transcribe_doc.media.probes import probe_media
from transcribe_doc.storage.artifact_store import (
    save_segments,
    save_transcription_result,
    save_words,
)
from transcribe_doc.storage.paths import JobPaths
from transcribe_doc.summary.extractive import write_summary

T = TypeVar("T")


@dataclass(frozen=True)
class ProcessingResult:
    """Result returned to CLI and API callers."""

    exit_code: int
    job: Job | None
    job_paths: JobPaths | None
    message: str


def process_single_file(
    input_path: str | Path,
    *,
    output_root: str | Path,
    config: AppConfig,
    job_id: str | None = None,
    display_title: str | None = None,
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
    )

    try:
        append_job_event(
            job,
            job_paths,
            stage="queued",
            status="ok",
            message="Задача создана и ожидает запуска",
            progress=0,
        )
        job.status = JobStatus.PROCESSING
        append_job_event(
            job,
            job_paths,
            stage="processing",
            status="ok",
            message="Обработка началась",
            progress=5,
        )

        append_job_event(
            job,
            job_paths,
            stage="probe",
            status="ok",
            message="Проверяю медиафайл",
            progress=10,
        )
        probe_media(resolved_input.path)
        append_job_event(
            job,
            job_paths,
            stage="normalize",
            status="ok",
            message="Нормализую аудио через ffmpeg",
            progress=20,
        )
        normalize_media(
            resolved_input.path,
            job_paths.normalized_audio,
            sample_rate=config.media.sample_rate,
            mono=config.media.mono,
        )

        speaker_manifest = load_speaker_manifest(
            str(speaker_manifest_path) if speaker_manifest_path is not None else None
        ) or speaker_hint_to_manifest(speaker_hint)
        if speaker_manifest:
            job.metadata["speaker_manifest"] = speaker_manifest
            message = (
                "Подсказка по участникам учтена"
                if speaker_manifest.get("source") == "freeform_speaker_hint"
                else "Список спикеров загружен"
            )
            append_job_event(
                job,
                job_paths,
                stage="speakers",
                status="ok",
                message=message,
                progress=28,
            )

        append_job_event(
            job,
            job_paths,
            stage="asr",
            status="ok",
            message="Запускаю распознавание речи",
            progress=35,
        )
        asr_backend = asr_backend_factory(config)
        alignment_backend = build_alignment_backend(config)
        diarization_backend = diarization_backend_factory(config, speaker_manifest)
        transcription_result = _run_with_heartbeat(
            lambda: TranscriptionService(
                asr_backend=asr_backend,
                alignment_backend=alignment_backend,
                diarization_backend=diarization_backend,
            ).transcribe(str(job_paths.normalized_audio)),
            job=job,
            job_paths=job_paths,
            stage="asr",
            message="Распознавание всё ещё выполняется. Это может быть загрузка модели или обработка длинного файла",
            start_progress=40,
            max_progress=60,
        )
        append_job_event(
            job,
            job_paths,
            stage="transcript",
            status="ok",
            message=f"Распознавание завершено: сегментов {len(transcription_result.segments)}",
            progress=65,
        )

        diarization_quality_summary = collect_diarization_quality_summary(
            transcription_result.segments
        )
        if diarization_quality_summary is not None:
            job.metadata["diarization_quality"] = diarization_quality_summary
        if _has_diarization_annotations(transcription_result.segments):
            append_job_event(
                job,
                job_paths,
                stage="diarization",
                status="ok",
                message="Сохраняю диагностику спикеров",
                progress=72,
            )
            save_segments(transcription_result.segments, job_paths.diarization_dump)
        if speaker_manifest and config.diarization.allow_expected_speaker_mapping:
            append_job_event(
                job,
                job_paths,
                stage="speaker_mapping",
                status="ok",
                message="Сопоставляю имена спикеров",
                progress=76,
            )
            transcription_result = transcription_result.__class__(
                segments=apply_expected_speaker_mapping(
                    transcription_result.segments,
                    speaker_manifest,
                ),
                warnings=transcription_result.warnings,
                detected_language=transcription_result.detected_language,
            )

        append_job_event(
            job,
            job_paths,
            stage="artifacts",
            status="ok",
            message="Сохраняю JSON-артефакты",
            progress=82,
        )
        save_transcription_result(transcription_result, job_paths.transcript_raw_json)
        save_segments(transcription_result.segments, job_paths.segments_json)
        save_words(transcription_result.segments, job_paths.words_json)
        append_job_event(
            job,
            job_paths,
            stage="export",
            status="ok",
            message="Генерирую пользовательские форматы",
            progress=90,
        )
        export_all(
            transcription_result.segments,
            _selected_export_paths(config, job_paths, formats),
        )
        if config.summary.enabled:
            append_job_event(
                job,
                job_paths,
                stage="summary",
                status="ok",
                message="Генерирую краткое summary",
                progress=95,
            )
            write_summary(
                transcription_result.segments,
                job_paths.summary_md,
                job_paths.summary_json,
            )
        job.detected_language = transcription_result.detected_language

        if transcription_result.warnings:
            job.status = JobStatus.COMPLETED_WITH_WARNINGS
            job.warnings.extend(transcription_result.warnings)
            append_job_event(
                job,
                job_paths,
                stage="done",
                status="warning",
                message="Задача завершена с предупреждениями",
                progress=100,
            )
        else:
            job.status = JobStatus.COMPLETED
            append_job_event(
                job,
                job_paths,
                stage="done",
                status="ok",
                message="Задача успешно завершена",
                progress=100,
            )
        return ProcessingResult(
            0,
            job,
            job_paths,
            f"Job {job.job_id} wrote transcript to {job_paths.transcript_raw_json}",
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


def _has_diarization_annotations(segments: list[TranscriptSegment]) -> bool:
    return any(segment.speaker_label is not None or segment.mapping is not None for segment in segments)


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

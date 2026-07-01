"""Batch, directory, and watch-folder orchestration."""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Sequence
from concurrent.futures import Executor, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from transcribe_doc.app.config import AppConfig
from transcribe_doc.app.constants import SUPPORTED_AUDIO_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS
from transcribe_doc.core.processing import ProcessingResult, process_single_file


SUPPORTED_MEDIA_EXTENSIONS = set(SUPPORTED_AUDIO_EXTENSIONS) | set(SUPPORTED_VIDEO_EXTENSIONS)


@dataclass(frozen=True)
class BatchItemResult:
    input_path: str
    exit_code: int
    job_id: str | None
    status: str | None
    message: str


@dataclass(frozen=True)
class BatchResult:
    exit_code: int
    total: int
    succeeded: int
    failed: int
    report_path: Path
    items: list[BatchItemResult]


def process_batch(
    input_paths: Sequence[str | Path],
    *,
    output_root: str | Path,
    config: AppConfig,
    speaker_manifest_path: str | Path | None = None,
    speaker_hint: str | None = None,
    formats: str | None = None,
    executor: Executor | None = None,
    on_item_result: Callable[[BatchItemResult], None] | None = None,
) -> BatchResult:
    """Process multiple files through the canonical single-file job runner."""
    local_executor: ThreadPoolExecutor | None = None
    if executor is None:
        local_executor = ThreadPoolExecutor(max_workers=max(1, config.runtime.max_parallel_jobs))
        executor = local_executor

    try:
        futures = {
            executor.submit(
                process_single_file,
                input_path,
                output_root=output_root,
                config=config,
                speaker_manifest_path=speaker_manifest_path,
                speaker_hint=speaker_hint,
                formats=formats,
            ): (index, input_path)
            for index, input_path in enumerate(input_paths)
        }
        ordered_results: list[BatchItemResult | None] = [None] * len(futures)
        for future in as_completed(futures):
            index, input_path = futures[future]
            try:
                processing_result = future.result()
                item_result = _item_from_processing_result(input_path, processing_result)
            except Exception as error:
                item_result = BatchItemResult(
                    input_path=str(Path(input_path).expanduser().resolve()),
                    exit_code=1,
                    job_id=None,
                    status="failed",
                    message=str(error),
                )
            ordered_results[index] = item_result
            if on_item_result is not None:
                on_item_result(item_result)
        results = [item for item in ordered_results if item is not None]
    finally:
        if local_executor is not None:
            local_executor.shutdown(wait=True)
    return _write_batch_report(Path(output_root), results)


def process_directory(
    input_dir: str | Path,
    *,
    output_root: str | Path,
    config: AppConfig,
    recursive: bool = False,
    speaker_manifest_path: str | Path | None = None,
    speaker_hint: str | None = None,
    formats: str | None = None,
    executor: Executor | None = None,
) -> BatchResult:
    """Process all supported media files from a directory."""
    files = discover_media_files(input_dir, recursive=recursive)
    return process_batch(
        files,
        output_root=output_root,
        config=config,
        speaker_manifest_path=speaker_manifest_path,
        speaker_hint=speaker_hint,
        formats=formats,
        executor=executor,
    )


def scan_watch_folder(
    input_dir: str | Path,
    *,
    output_root: str | Path,
    config: AppConfig,
    recursive: bool = False,
    stability_seconds: int | None = None,
    speaker_manifest_path: str | Path | None = None,
    speaker_hint: str | None = None,
    formats: str | None = None,
    executor: Executor | None = None,
) -> BatchResult:
    """Process currently stable files and move them to processed/failed folders."""
    root = Path(input_dir).expanduser().resolve()
    stable_files = [
        path
        for path in discover_media_files(root, recursive=recursive)
        if _is_stable(path, stability_seconds or config.watch_folder.stability_seconds)
    ]

    def move_terminal_item(item: BatchItemResult) -> None:
        source = Path(item.input_path)
        if item.exit_code == 0 and config.watch_folder.move_processed:
            _move_to_bucket(source, root / "processed")
        elif item.exit_code != 0 and config.watch_folder.move_failed:
            _move_to_bucket(source, root / "failed")

    return process_batch(
        stable_files,
        output_root=output_root,
        config=config,
        speaker_manifest_path=speaker_manifest_path,
        speaker_hint=speaker_hint,
        formats=formats,
        executor=executor,
        on_item_result=move_terminal_item,
    )


def discover_media_files(input_dir: str | Path, *, recursive: bool = False) -> list[Path]:
    root = Path(input_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Input directory not found: {root}")
    iterator = root.rglob("*") if recursive else root.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower().lstrip(".") in SUPPORTED_MEDIA_EXTENSIONS
        and "processed" not in path.parts
        and "failed" not in path.parts
    )


def _item_from_processing_result(
    input_path: str | Path,
    result: ProcessingResult,
) -> BatchItemResult:
    return BatchItemResult(
        input_path=str(Path(input_path).expanduser().resolve()),
        exit_code=result.exit_code,
        job_id=result.job.job_id if result.job else None,
        status=result.job.status.value if result.job else None,
        message=result.message,
    )


def _write_batch_report(output_root: Path, results: list[BatchItemResult]) -> BatchResult:
    output_root.mkdir(parents=True, exist_ok=True)
    succeeded = sum(1 for item in results if item.exit_code == 0)
    failed = len(results) - succeeded
    report_path = output_root / f"batch-{int(time.time())}.json"
    payload = {
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "items": [asdict(item) for item in results],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return BatchResult(
        exit_code=0 if failed == 0 else 1,
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        report_path=report_path,
        items=results,
    )


def _is_stable(path: Path, stability_seconds: int) -> bool:
    if stability_seconds <= 0:
        return True
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds >= stability_seconds


def _move_to_bucket(source: Path, bucket: Path) -> None:
    if not source.exists():
        return
    bucket.mkdir(parents=True, exist_ok=True)
    destination = bucket / source.name
    if destination.exists():
        destination = bucket / f"{source.stem}-{int(time.time())}{source.suffix}"
    shutil.move(str(source), str(destination))

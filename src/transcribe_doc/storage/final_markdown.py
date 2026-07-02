"""Save final Markdown transcripts to a user-selected external folder."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from transcribe_doc.app.models import TranscriptSegment
from transcribe_doc.export.writers import write_final_text_md
from transcribe_doc.service.types import JsonObject

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class FinalMarkdownStatus:
    """Visible state for the external final Markdown file linked to a job."""

    status: str
    message: str
    path: str | None = None
    filename: str | None = None
    missing: bool = False

    def to_payload(self) -> JsonObject:
        payload: JsonObject = {
            "status": self.status,
            "message": self.message,
            "missing": self.missing,
        }
        if self.path:
            payload["path"] = self.path
        if self.filename:
            payload["filename"] = self.filename
        return payload


def title_derived_markdown_filename(job: JsonObject) -> str:
    """Return the stable safe `.md` filename for a job's display title."""
    title = _title_from_job(job)
    stem = safe_filename_stem(title)
    return f"{stem}.md"


def safe_filename_stem(value: str) -> str:
    """Sanitize a user title for a portable filesystem filename while preserving words."""
    stem = Path(value).stem if Path(value).suffix else value
    stem = re.sub(r"[\x00-\x1f/:*?\"<>|\\]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    if not stem:
        stem = "transcript"
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        stem = f"{stem}-transcript"
    return stem[:180].rstrip(" .") or "transcript"


def inspect_saved_final_markdown(job: JsonObject) -> FinalMarkdownStatus:
    """Report whether a job's linked external Markdown file still exists."""
    metadata = _metadata(job)
    saved_path = _string_or_none(metadata.get("saved_markdown_path"))
    if not saved_path:
        return FinalMarkdownStatus(
            status="not_saved",
            message="Выберите папку для сохранения транскрипций",
        )
    path = Path(saved_path)
    filename = _string_or_none(metadata.get("saved_markdown_filename")) or path.name
    if path.exists() and path.is_file():
        return FinalMarkdownStatus(
            status="saved",
            message=f"Сохранено: {filename}",
            path=str(path),
            filename=filename,
        )
    return FinalMarkdownStatus(
        status="missing",
        message="Файл транскрипции не найден",
        path=str(path),
        filename=filename,
        missing=True,
    )


def save_final_markdown(job: JsonObject, output_root: Path, autosave_dir: str | Path) -> FinalMarkdownStatus:
    """Write or update the job's linked final Markdown file in `autosave_dir`."""
    destination_dir = Path(autosave_dir).expanduser()
    if not str(destination_dir).strip():
        raise ValueError("Выберите папку для сохранения транскрипций")
    if destination_dir.exists() and not destination_dir.is_dir():
        raise ValueError("Путь сохранения должен быть папкой")
    destination_dir.mkdir(parents=True, exist_ok=True)

    segments = _load_segments(output_root, str(job.get("job_id") or ""))
    filename = title_derived_markdown_filename(job)
    target = destination_dir / filename
    previous_path = _string_or_none(_metadata(job).get("saved_markdown_path"))
    if previous_path:
        previous = Path(previous_path)
        if previous.exists() and previous.is_file() and previous.resolve() != target.resolve():
            previous.replace(target)

    write_final_text_md(target, segments)
    metadata = _metadata(job)
    metadata.update(
        {
            "saved_markdown_path": str(target),
            "saved_markdown_filename": target.name,
            "saved_markdown_dir": str(destination_dir),
            "saved_markdown_missing": False,
            "saved_markdown_saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
    )
    job["metadata"] = metadata
    return FinalMarkdownStatus(
        status="saved",
        message=f"Сохранено: {target.name}",
        path=str(target),
        filename=target.name,
    )


def sync_saved_markdown_metadata(job: JsonObject, status: FinalMarkdownStatus) -> None:
    """Mirror the current external file status into job metadata for app display."""
    metadata = _metadata(job)
    metadata["saved_markdown_status"] = status.status
    metadata["saved_markdown_message"] = status.message
    metadata["saved_markdown_missing"] = status.missing
    if status.path:
        metadata["saved_markdown_path"] = status.path
    if status.filename:
        metadata["saved_markdown_filename"] = status.filename
    job["metadata"] = metadata


def _load_segments(output_root: Path, job_id: str) -> list[TranscriptSegment]:
    segments_path = output_root / job_id / "segments.json"
    if not segments_path.exists():
        raise FileNotFoundError("Нет сохранённых сегментов для повторного сохранения Markdown")
    import json

    payload = json.loads(segments_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Сохранённые сегменты повреждены")
    segments: list[TranscriptSegment] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        segments.append(
            TranscriptSegment(
                segment_id=str(item.get("segment_id") or f"segment-{index}"),
                start_seconds=float(item.get("start_seconds") or 0.0),
                end_seconds=float(item.get("end_seconds") or 0.0),
                text_raw=str(item.get("text_raw") or ""),
                text_clean=str(item.get("text_clean") or item.get("text_raw") or ""),
                speaker_label=_string_or_none(item.get("speaker_label")),
            )
        )
    if not segments:
        raise ValueError("Нет текста для сохранения Markdown")
    return segments


def _title_from_job(job: JsonObject) -> str:
    metadata = _metadata(job)
    for key in ("display_title", "title", "source_filename"):
        value = _string_or_none(metadata.get(key))
        if value:
            return value
    source_paths = job.get("source_paths")
    if isinstance(source_paths, list) and source_paths:
        return Path(str(source_paths[0])).stem
    return str(job.get("job_id") or "transcript")


def _metadata(job: JsonObject) -> JsonObject:
    metadata = job.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _string_or_none(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None

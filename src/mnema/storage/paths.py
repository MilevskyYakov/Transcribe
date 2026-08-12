"""Helpers for job-scoped filesystem layout."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JobPaths:
    """Filesystem layout for a single processing job."""

    job_dir: Path
    artifacts_dir: Path
    job_json: Path
    transcript_raw_json: Path
    segments_json: Path
    words_json: Path
    transcript_clean_txt: Path
    transcript_clean_md: Path
    final_speech_text_md: Path
    transcript_clean_docx: Path
    transcript_clean_pdf: Path
    subtitles_srt: Path
    summary_md: Path
    summary_json: Path
    diarization_dump: Path
    events_jsonl: Path
    config_snapshot: Path
    extracted_audio: Path
    normalized_audio: Path
    log_file: Path


def build_job_paths(
    output_root: Path | str,
    job_id: str,
    *,
    final_speech_text_filename: str = "final_speech_text.md",
) -> JobPaths:
    """Create and return the canonical directory layout for a job."""
    root = Path(output_root)
    job_dir = root / job_id
    artifacts_dir = job_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    return JobPaths(
        job_dir=job_dir,
        artifacts_dir=artifacts_dir,
        job_json=job_dir / "job.json",
        transcript_raw_json=job_dir / "transcript_raw.json",
        segments_json=job_dir / "segments.json",
        words_json=job_dir / "words.json",
        transcript_clean_txt=job_dir / "transcript_clean.txt",
        transcript_clean_md=job_dir / "transcript_clean.md",
        final_speech_text_md=job_dir / final_speech_text_filename,
        transcript_clean_docx=job_dir / "transcript_clean.docx",
        transcript_clean_pdf=job_dir / "transcript_clean.pdf",
        subtitles_srt=job_dir / "subtitles.srt",
        summary_md=job_dir / "summary.md",
        summary_json=job_dir / "summary.json",
        diarization_dump=artifacts_dir / "diarization_dump.json",
        events_jsonl=artifacts_dir / "events.jsonl",
        config_snapshot=artifacts_dir / "config_snapshot.json",
        extracted_audio=artifacts_dir / "extracted_audio.wav",
        normalized_audio=artifacts_dir / "normalized_audio.wav",
        log_file=artifacts_dir / "job.log",
    )

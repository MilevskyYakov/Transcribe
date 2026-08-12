import json
from pathlib import Path

from mnema.app.config import load_config
from mnema.app.models import JobStatus
from mnema.core.job_manager import create_job
from mnema.storage.filenames import safe_markdown_filename


def test_create_job_initializes_workspace_and_snapshot(tmp_path: Path) -> None:
    config = load_config(Path("configs/default.yaml"))

    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    job, job_paths = create_job(
        source_path=source_file,
        output_root=tmp_path / "output",
        config=config,
        job_id="job-123",
        initial_metadata={"final_markdown_dir": str(tmp_path)},
    )

    assert job.job_id == "job-123"
    assert job.status is JobStatus.QUEUED
    assert job_paths.job_dir.exists()
    assert job_paths.artifacts_dir.exists()
    assert job_paths.config_snapshot.exists()
    assert job_paths.diarization_dump.name == "diarization_dump.json"
    assert job_paths.final_speech_text_md.name == "sample.md"

    snapshot = json.loads(job_paths.config_snapshot.read_text(encoding="utf-8"))
    assert snapshot["app"]["output_dir"] == "./output"
    assert job.artifacts.diarization_dump == str(job_paths.diarization_dump)
    assert job.artifacts.final_speech_text_md == str(job_paths.final_speech_text_md)
    assert job.metadata["display_title"] == "sample"
    assert job.metadata["source_filename"] == "sample.mp3"
    assert job.metadata["final_markdown_dir"] == str(tmp_path)


def test_create_job_preserves_manual_display_title(tmp_path: Path) -> None:
    config = load_config(Path("configs/default.yaml"))
    source_file = tmp_path / "raw-meeting.wav"
    source_file.write_bytes(b"fake-audio")

    job, job_paths = create_job(
        source_path=source_file,
        output_root=tmp_path / "output",
        config=config,
        display_title=" Созвон с клиентом ",
    )

    assert job.metadata["display_title"] == "Созвон с клиентом"
    assert job.metadata["source_filename"] == "raw-meeting.wav"
    assert job_paths.final_speech_text_md.name == "Созвон с клиентом.md"


def test_safe_markdown_filename_sanitizes_title_and_fallbacks(tmp_path: Path) -> None:
    assert (
        safe_markdown_filename(" Client/Call: Q&A?\nnext  step ", source_path=tmp_path / "raw.mov")
        == "Client Call Q&A next step.md"
    )
    assert safe_markdown_filename(" /// ", source_path=tmp_path / "Source: Call.mov") == "Source Call.md"
    assert safe_markdown_filename(" ??? ") == "transcription.md"

    long_title = "A" * 140
    filename = safe_markdown_filename(long_title)

    assert filename == f"{'A' * 120}.md"
    assert len(filename.removesuffix(".md")) == 120

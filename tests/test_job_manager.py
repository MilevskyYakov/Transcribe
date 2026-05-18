import json
from pathlib import Path

from transcribe_doc.app.config import load_config
from transcribe_doc.app.models import JobStatus
from transcribe_doc.core.job_manager import create_job


def test_create_job_initializes_workspace_and_snapshot(tmp_path: Path) -> None:
    config = load_config(Path("configs/default.yaml"))

    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    job, job_paths = create_job(
        source_path=source_file,
        output_root=tmp_path / "output",
        config=config,
        job_id="job-123",
    )

    assert job.job_id == "job-123"
    assert job.status is JobStatus.QUEUED
    assert job_paths.job_dir.exists()
    assert job_paths.artifacts_dir.exists()
    assert job_paths.config_snapshot.exists()
    assert job_paths.diarization_dump.name == "diarization_dump.json"

    snapshot = json.loads(job_paths.config_snapshot.read_text(encoding="utf-8"))
    assert snapshot["app"]["output_dir"] == "./output"
    assert job.artifacts.diarization_dump == str(job_paths.diarization_dump)
    assert job.artifacts.final_speech_text_md == str(job_paths.final_speech_text_md)
    assert job.metadata["display_title"] == "sample"
    assert job.metadata["source_filename"] == "sample.mp3"


def test_create_job_preserves_manual_display_title(tmp_path: Path) -> None:
    config = load_config(Path("configs/default.yaml"))
    source_file = tmp_path / "raw-meeting.wav"
    source_file.write_bytes(b"fake-audio")

    job, _ = create_job(
        source_path=source_file,
        output_root=tmp_path / "output",
        config=config,
        display_title=" Созвон с клиентом ",
    )

    assert job.metadata["display_title"] == "Созвон с клиентом"
    assert job.metadata["source_filename"] == "raw-meeting.wav"

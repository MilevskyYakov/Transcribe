import json
import os
import time
from pathlib import Path

from transcribe_doc.storage.temp_cleanup import (
    cleanup_stale_temporary_media,
    cleanup_successful_job_media,
)


def test_cleanup_successful_job_media_deletes_only_managed_temp_files(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    temp_root = tmp_path / "tmp"
    job_dir = output_root / "job-clean"
    artifacts_dir = job_dir / "artifacts"
    uploads_dir = temp_root / "uploads"
    artifacts_dir.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)

    uploaded_source = uploads_dir / "source.wav"
    normalized_audio = artifacts_dir / "normalized_audio.wav"
    external_original = tmp_path / "original.wav"
    uploaded_source.write_bytes(b"uploaded")
    normalized_audio.write_bytes(b"normalized")
    external_original.write_bytes(b"original")
    job = {
        "job_id": "job-clean",
        "source_paths": [str(uploaded_source), str(external_original)],
        "status": "completed",
        "artifacts": {"normalized_audio": str(normalized_audio)},
        "metadata": {},
    }

    report = cleanup_successful_job_media(
        job,
        output_root=output_root,
        job_id="job-clean",
        temp_root=temp_root,
    )

    assert report.removed_count == 2
    assert report.freed_bytes == len(b"uploaded") + len(b"normalized")
    assert not uploaded_source.exists()
    assert not normalized_audio.exists()
    assert external_original.exists()
    assert job["artifacts"]["normalized_audio"] is None
    assert job["metadata"]["temp_cleanup"]["reason"] == "job_success"


def test_cleanup_successful_job_removes_internal_artifacts_but_keeps_durable_outputs(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    temp_root = tmp_path / "tmp"
    job_dir = output_root / "job-clean"
    artifacts_dir = job_dir / "artifacts"
    model_dir = tmp_path / "app-data" / "models"
    artifacts_dir.mkdir(parents=True)
    model_dir.mkdir(parents=True)

    durable_segment = job_dir / "segments.json"
    durable_final = job_dir / "final_speech_text.md"
    raw_transcript = job_dir / "transcript_raw.json"
    diarization_dump = artifacts_dir / "diarization_dump.json"
    events_jsonl = artifacts_dir / "events.jsonl"
    log_file = artifacts_dir / "job.log"
    config_snapshot = artifacts_dir / "config_snapshot.json"
    model_file = model_dir / "parakeet.onnx"
    for path in (
        durable_segment,
        durable_final,
        raw_transcript,
        diarization_dump,
        events_jsonl,
        log_file,
        config_snapshot,
        model_file,
    ):
        path.write_text("data", encoding="utf-8")
    job = {
        "job_id": "job-clean",
        "source_paths": [],
        "status": "completed",
        "artifacts": {
            "segments_json": str(durable_segment),
            "final_speech_text_md": str(durable_final),
            "raw_transcript": str(raw_transcript),
            "diarization_dump": str(diarization_dump),
            "events_jsonl": str(events_jsonl),
            "log_file": str(log_file),
            "config_snapshot": str(config_snapshot),
        },
        "metadata": {"model_dir": str(model_dir)},
    }

    report = cleanup_successful_job_media(
        job,
        output_root=output_root,
        job_id="job-clean",
        temp_root=temp_root,
    )

    assert report.removed_count == 5
    assert durable_segment.exists()
    assert durable_final.exists()
    assert model_file.exists()
    assert not raw_transcript.exists()
    assert not diarization_dump.exists()
    assert not events_jsonl.exists()
    assert not log_file.exists()
    assert not config_snapshot.exists()
    assert job["artifacts"]["segments_json"] == str(durable_segment)
    assert job["artifacts"]["final_speech_text_md"] == str(durable_final)
    assert job["artifacts"]["raw_transcript"] is None
    assert job["artifacts"]["diarization_dump"] is None
    assert job["artifacts"]["events_jsonl"] is None
    assert job["artifacts"]["log_file"] is None
    assert job["artifacts"]["config_snapshot"] is None


def test_stale_cleanup_removes_failed_old_media_but_retains_recent(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    temp_root = tmp_path / "tmp"
    old_job_dir = output_root / "job-old"
    recent_job_dir = output_root / "job-recent"
    old_artifact = old_job_dir / "artifacts" / "normalized_audio.wav"
    recent_artifact = recent_job_dir / "artifacts" / "normalized_audio.wav"
    old_artifact.parent.mkdir(parents=True)
    recent_artifact.parent.mkdir(parents=True)
    old_artifact.write_bytes(b"old")
    recent_artifact.write_bytes(b"recent")
    old_timestamp = time.time() - 8 * 24 * 60 * 60
    os.utime(old_artifact, (old_timestamp, old_timestamp))

    _write_job(
        old_job_dir / "job.json",
        {
            "job_id": "job-old",
            "source_paths": [],
            "status": "failed",
            "artifacts": {"normalized_audio": str(old_artifact)},
            "metadata": {},
        },
    )
    _write_job(
        recent_job_dir / "job.json",
        {
            "job_id": "job-recent",
            "source_paths": [],
            "status": "failed",
            "artifacts": {"normalized_audio": str(recent_artifact)},
            "metadata": {},
        },
    )

    report = cleanup_stale_temporary_media(output_root=output_root, temp_root=temp_root)

    assert report.removed_files == [str(old_artifact)]
    assert not old_artifact.exists()
    assert recent_artifact.exists()
    old_job = json.loads((old_job_dir / "job.json").read_text(encoding="utf-8"))
    assert old_job["artifacts"]["normalized_audio"] is None
    assert old_job["metadata"]["temp_cleanup"]["reason"] == "stale_retention"


def test_stale_cleanup_removes_orphan_uploads(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    upload_root = tmp_path / "tmp" / "uploads"
    upload_root.mkdir(parents=True)
    old_upload = upload_root / "orphan.mov"
    recent_upload = upload_root / "recent.mov"
    old_upload.write_bytes(b"old")
    recent_upload.write_bytes(b"recent")
    old_timestamp = time.time() - 8 * 24 * 60 * 60
    os.utime(old_upload, (old_timestamp, old_timestamp))

    report = cleanup_stale_temporary_media(output_root=output_root, temp_root=tmp_path / "tmp")

    assert report.removed_files == [str(old_upload)]
    assert not old_upload.exists()
    assert recent_upload.exists()


def _write_job(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

from pathlib import Path

from transcribe_doc.app.config import AppConfig, AppSection, WatchFolderSection
from transcribe_doc.app.models import Job, JobStatus
from transcribe_doc.core import batch as batch_module
from transcribe_doc.core.batch import discover_media_files, process_batch, process_directory, scan_watch_folder
from transcribe_doc.core.processing import ProcessingResult


def test_process_batch_continues_after_failed_item(tmp_path: Path, monkeypatch) -> None:
    good = tmp_path / "good.wav"
    bad = tmp_path / "bad.wav"
    good.write_bytes(b"ok")
    bad.write_bytes(b"bad")

    def fake_process(input_path, **kwargs):
        path = Path(input_path)
        job = Job(
            job_id=f"job-{path.stem}",
            source_paths=[str(path)],
            status=JobStatus.COMPLETED if path.name == "good.wav" else JobStatus.FAILED,
        )
        return ProcessingResult(0 if path.name == "good.wav" else 1, job, None, path.name)

    monkeypatch.setattr(batch_module, "process_single_file", fake_process)

    result = process_batch(
        [good, bad],
        output_root=tmp_path / "output",
        config=AppConfig(app=AppSection(output_dir=str(tmp_path / "output"))),
    )

    assert result.exit_code == 1
    assert result.succeeded == 1
    assert result.failed == 1
    assert result.report_path.exists()


def test_process_directory_discovers_supported_media(tmp_path: Path, monkeypatch) -> None:
    media = tmp_path / "a.wav"
    ignored = tmp_path / "notes.txt"
    media.write_bytes(b"ok")
    ignored.write_text("skip", encoding="utf-8")

    monkeypatch.setattr(
        batch_module,
        "process_single_file",
        lambda input_path, **kwargs: ProcessingResult(
            0,
            Job(job_id="job-a", source_paths=[str(input_path)], status=JobStatus.COMPLETED),
            None,
            "ok",
        ),
    )

    result = process_directory(
        tmp_path,
        output_root=tmp_path / "output",
        config=AppConfig(app=AppSection(output_dir=str(tmp_path / "output"))),
    )

    assert result.total == 1
    assert result.items[0].input_path == str(media.resolve())
    assert discover_media_files(tmp_path) == [media.resolve()]


def test_watch_scan_moves_processed_files(tmp_path: Path, monkeypatch) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    media = incoming / "a.wav"
    media.write_bytes(b"ok")

    monkeypatch.setattr(
        batch_module,
        "process_single_file",
        lambda input_path, **kwargs: ProcessingResult(
            0,
            Job(job_id="job-a", source_paths=[str(input_path)], status=JobStatus.COMPLETED),
            None,
            "ok",
        ),
    )

    result = scan_watch_folder(
        incoming,
        output_root=tmp_path / "output",
        config=AppConfig(
            app=AppSection(output_dir=str(tmp_path / "output")),
            watch_folder=WatchFolderSection(stability_seconds=0),
        ),
    )

    assert result.exit_code == 0
    assert not media.exists()
    assert (incoming / "processed" / "a.wav").exists()

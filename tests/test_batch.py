import threading
import time
from pathlib import Path

from transcribe_doc.app.config import AppConfig, AppSection, RuntimeSection, WatchFolderSection
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


def test_process_batch_runs_files_up_to_configured_parallelism(tmp_path: Path, monkeypatch) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    first.write_bytes(b"ok")
    second.write_bytes(b"ok")
    started = 0
    max_active = 0
    active = 0
    lock = threading.Lock()
    both_started = threading.Event()

    def fake_process(input_path, **kwargs):
        nonlocal active, max_active, started
        with lock:
            active += 1
            started += 1
            max_active = max(max_active, active)
            if started == 2:
                both_started.set()
        assert both_started.wait(timeout=2)
        time.sleep(0.01)
        with lock:
            active -= 1
        path = Path(input_path)
        return ProcessingResult(
            0,
            Job(job_id=f"job-{path.stem}", source_paths=[str(path)], status=JobStatus.COMPLETED),
            None,
            "ok",
        )

    monkeypatch.setattr(batch_module, "process_single_file", fake_process)

    result = process_batch(
        [first, second],
        output_root=tmp_path / "output",
        config=AppConfig(
            app=AppSection(output_dir=str(tmp_path / "output")),
            runtime=RuntimeSection(max_parallel_jobs=2),
        ),
    )

    assert result.exit_code == 0
    assert max_active == 2


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


def test_watch_scan_moves_each_file_when_item_reaches_terminal_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    good = incoming / "good.wav"
    bad = incoming / "bad.wav"
    good.write_bytes(b"ok")
    bad.write_bytes(b"bad")

    def fake_process(input_path, **kwargs):
        path = Path(input_path)
        if path.name == "bad.wav":
            deadline = time.time() + 2
            while time.time() < deadline:
                if (incoming / "processed" / "good.wav").exists():
                    break
                time.sleep(0.01)
            assert (incoming / "processed" / "good.wav").exists()
            return ProcessingResult(
                1,
                Job(job_id="job-bad", source_paths=[str(path)], status=JobStatus.FAILED),
                None,
                "bad",
            )
        return ProcessingResult(
            0,
            Job(job_id="job-good", source_paths=[str(path)], status=JobStatus.COMPLETED),
            None,
            "ok",
        )

    monkeypatch.setattr(batch_module, "process_single_file", fake_process)

    result = scan_watch_folder(
        incoming,
        output_root=tmp_path / "output",
        config=AppConfig(
            app=AppSection(output_dir=str(tmp_path / "output")),
            runtime=RuntimeSection(max_parallel_jobs=2),
            watch_folder=WatchFolderSection(stability_seconds=0),
        ),
    )

    assert result.exit_code == 1
    assert (incoming / "processed" / "good.wav").exists()
    assert (incoming / "failed" / "bad.wav").exists()

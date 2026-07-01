import json
from pathlib import Path

from transcribe_doc.app.config import AppConfig, ExportSection, SummarySection
from transcribe_doc.app.models import TranscriptSegment
from transcribe_doc.asr.base import AsrBackend, AsrTranscription
from transcribe_doc.core import processing


class FakeAsrBackend(AsrBackend):
    name = "fake-asr"

    def transcribe(self, media_path: str) -> AsrTranscription:
        return AsrTranscription(
            segments=[
                TranscriptSegment(
                    segment_id="seg-001",
                    start_seconds=0.0,
                    end_seconds=1.0,
                    text_raw="привет",
                    text_clean="привет",
                )
            ],
            detected_language="ru",
        )


def _stage_test_config() -> AppConfig:
    return AppConfig(
        summary=SummarySection(enabled=False),
        export=ExportSection(txt=True, md=False, docx=False, pdf=False, srt=False, json=False),
    )


def test_process_single_file_records_canonical_stage_order(tmp_path: Path, monkeypatch) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    monkeypatch.setattr(processing, "probe_media", lambda path: None)
    monkeypatch.setattr(
        processing,
        "normalize_media",
        lambda source, target, *, sample_rate, mono: target.write_bytes(b"wav"),
    )
    monkeypatch.setattr(processing, "build_alignment_backend", lambda config: None)

    result = processing.process_single_file(
        source_file,
        output_root=tmp_path / "output",
        config=_stage_test_config(),
        job_id="job-stage-order",
        speaker_hint="Алексей — интервьюер",
        formats="txt",
        asr_backend_factory=lambda config: FakeAsrBackend(),
        diarization_backend_factory=lambda config, speaker_manifest: None,
    )

    assert result.exit_code == 0
    assert result.job_paths is not None
    events = [
        json.loads(line)
        for line in result.job_paths.events_jsonl.read_text(encoding="utf-8").splitlines()
    ]
    assert [(event["stage"], event["progress"]) for event in events] == [
        ("queued", 0),
        ("processing", 5),
        ("probe", 10),
        ("normalize", 20),
        ("speakers", 28),
        ("asr", 35),
        ("transcript", 65),
        ("speaker_mapping", 76),
        ("artifacts", 82),
        ("export", 90),
        ("done", 100),
    ]
    assert processing.STAGE_EVENTS["normalize"].progress == 20
    assert result.job is not None
    assert result.job.status.value == "completed"
    assert result.job.detected_language == "ru"


def test_process_single_file_failure_uses_last_stage_progress(tmp_path: Path, monkeypatch) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    def fail_normalize(source, target, *, sample_rate, mono) -> None:
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr(processing, "probe_media", lambda path: None)
    monkeypatch.setattr(processing, "normalize_media", fail_normalize)

    result = processing.process_single_file(
        source_file,
        output_root=tmp_path / "output",
        config=_stage_test_config(),
        job_id="job-failure",
        formats="txt",
        asr_backend_factory=lambda config: FakeAsrBackend(),
        diarization_backend_factory=lambda config, speaker_manifest: None,
    )

    assert result.exit_code == 1
    assert result.job is not None
    assert result.job.status.value == "failed"
    assert result.job_paths is not None
    events = [
        json.loads(line)
        for line in result.job_paths.events_jsonl.read_text(encoding="utf-8").splitlines()
    ]
    assert [(event["stage"], event["progress"]) for event in events] == [
        ("queued", 0),
        ("processing", 5),
        ("probe", 10),
        ("normalize", 20),
        ("failed", 20),
    ]
    assert result.message == "ffmpeg exploded"

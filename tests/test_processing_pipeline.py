import json
from pathlib import Path

from mnema.app.config import AppConfig, ExportSection, SummarySection
from mnema.app.models import SpeakerMapping, TranscriptSegment
from mnema.asr.base import AsrBackend, AsrTranscription
from mnema.core import processing


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
    persisted_job = json.loads(result.job_paths.job_json.read_text(encoding="utf-8"))
    events = persisted_job["metadata"]["events"]
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
    assert persisted_job["metadata"]["temp_cleanup"]["reason"] == "job_success"
    assert persisted_job["artifacts"]["normalized_audio"] is None
    assert not result.job_paths.normalized_audio.exists()
    assert not result.job_paths.events_jsonl.exists()
    assert (result.job_paths.job_dir / "transcript_clean.txt").exists()


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


def test_degraded_diarization_keeps_chronology_without_labels(tmp_path: Path, monkeypatch) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    class LowConfidenceDiarization:
        def diarize(self, media_path, segments):
            segment = segments[0]
            return [
                TranscriptSegment(
                    segment_id=segment.segment_id,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    text_raw=segment.text_raw,
                    text_clean=segment.text_clean,
                    speaker_label="SPEAKER_00",
                    mapping=SpeakerMapping(
                        machine_label="SPEAKER_00",
                        display_label="SPEAKER_00",
                        metadata={
                            "backend": "resemblyzer",
                            "cluster_size": 1,
                            "detected_cluster_count": 1,
                            "centroid_similarity_margin": 0.04,
                        },
                    ),
                )
            ]

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
        job_id="job-degraded",
        speaker_hint="Алексей",
        formats="txt",
        asr_backend_factory=lambda config: FakeAsrBackend(),
        diarization_backend_factory=lambda config, speaker_manifest: LowConfidenceDiarization(),
    )

    assert result.exit_code == 0
    assert result.job is not None
    assert result.job.status.value == "completed"
    assert result.job.metadata["diarization_confidence"]["mode"] == "transcript_without_labels"
    assert result.job_paths is not None
    public_segments = json.loads(result.job_paths.segments_json.read_text(encoding="utf-8"))
    assert public_segments[0]["speaker_label"] is None
    assert public_segments[0]["mapping"] is None
    assert result.job.metadata["diarization_quality"]["min_centroid_similarity_margin"] == 0.04
    assert result.job_paths.transcript_clean_txt.read_text(encoding="utf-8") == (
        "[00:00.0-00:01.0] Привет.\n"
    )

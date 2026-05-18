import json
import os
from pathlib import Path

from transcribe_doc.app.exceptions import ExternalDependencyError
from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment
from transcribe_doc.cli.main import main


def test_run_command_records_failed_job_when_media_tools_missing(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  temp_dir: "./tmp"
  output_dir: "__OUTPUT__"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
""".replace("__OUTPUT__", str(tmp_path / "output")),
        encoding="utf-8",
    )

    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = ""
    try:
        exit_code = main(["--config", str(config_path), "run", str(source_file)])
    finally:
        os.environ["PATH"] = original_path

    assert exit_code == 1

    job_dirs = [path for path in (tmp_path / "output").iterdir() if path.is_dir()]
    assert len(job_dirs) == 1

    job_payload = json.loads((job_dirs[0] / "job.json").read_text(encoding="utf-8"))
    assert job_payload["status"] == "failed"
    assert any("ffprobe" in warning or "ffmpeg" in warning for warning in job_payload["warnings"])


def test_run_command_records_failed_job_when_asr_backend_crashes(
    tmp_path: Path, monkeypatch
) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    ffprobe_script = bin_dir / "ffprobe"
    ffprobe_script.write_text(
        "#!/bin/sh\n"
        "printf '{\"streams\": [], \"format\": {\"duration\": \"1.0\"}}'\n",
        encoding="utf-8",
    )
    ffprobe_script.chmod(0o755)

    ffmpeg_script = bin_dir / "ffmpeg"
    ffmpeg_script.write_text(
        "#!/bin/sh\n"
        "eval \"out=\\${$#}\"\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf 'wav' > \"$out\"\n",
        encoding="utf-8",
    )
    ffmpeg_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    class CrashingAsrBackend:
        name = "crashing-asr"

        def transcribe(self, media_path: str):
            raise RuntimeError("onnx runtime failed")

    monkeypatch.setattr(
        "transcribe_doc.cli.commands.build_asr_backend",
        lambda config: CrashingAsrBackend(),
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  temp_dir: "./tmp"
  output_dir: "__OUTPUT__"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
""".replace("__OUTPUT__", str(tmp_path / "output")),
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path), "run", str(source_file)])

    assert exit_code == 1
    job_dir = next(path for path in (tmp_path / "output").iterdir() if path.is_dir())
    job_payload = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert job_payload["status"] == "failed"
    assert job_payload["warnings"] == ["onnx runtime failed"]
    assert job_payload["metadata"]["current_stage"] == "failed"


def test_run_command_keeps_coreml_failure_detail_out_of_last_message(
    tmp_path: Path, monkeypatch
) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    ffprobe_script = bin_dir / "ffprobe"
    ffprobe_script.write_text(
        "#!/bin/sh\n"
        "printf '{\"streams\": [], \"format\": {\"duration\": \"1.0\"}}'\n",
        encoding="utf-8",
    )
    ffprobe_script.chmod(0o755)

    ffmpeg_script = bin_dir / "ffmpeg"
    ffmpeg_script.write_text(
        "#!/bin/sh\n"
        "eval \"out=\\${$#}\"\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf 'wav' > \"$out\"\n",
        encoding="utf-8",
    )
    ffmpeg_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    class CrashingAsrBackend:
        name = "crashing-asr"

        def transcribe(self, media_path: str):
            raise ExternalDependencyError(
                "ONNX ASR модель не смогла обработать аудио. "
                "Попробуйте другую модель или повторите позже."
            ) from RuntimeError("CoreMLExecutionProvider raw failure")

    monkeypatch.setattr(
        "transcribe_doc.cli.commands.build_asr_backend",
        lambda config: CrashingAsrBackend(),
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  temp_dir: "./tmp"
  output_dir: "__OUTPUT__"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
""".replace("__OUTPUT__", str(tmp_path / "output")),
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path), "run", str(source_file)])

    assert exit_code == 1
    job_dir = next(path for path in (tmp_path / "output").iterdir() if path.is_dir())
    job_payload = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert job_payload["status"] == "failed"
    assert job_payload["metadata"]["last_message"] == (
        "ONNX ASR модель не смогла обработать аудио. "
        "Попробуйте другую модель или повторите позже."
    )
    assert "CoreMLExecutionProvider raw failure" in job_payload["warnings"][0]
    assert "CoreMLExecutionProvider raw failure" in (
        job_dir / "artifacts" / "job.log"
    ).read_text(encoding="utf-8")


def test_run_command_completes_with_fake_media_tools(tmp_path: Path, monkeypatch) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    ffprobe_script = bin_dir / "ffprobe"
    ffprobe_script.write_text(
        "#!/bin/sh\n"
        "printf '{\"streams\": [], \"format\": {\"duration\": \"1.0\"}}'\n",
        encoding="utf-8",
    )
    ffprobe_script.chmod(0o755)

    ffmpeg_script = bin_dir / "ffmpeg"
    ffmpeg_script.write_text(
        "#!/bin/sh\n"
        "eval \"out=\\${$#}\"\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf 'wav' > \"$out\"\n",
        encoding="utf-8",
    )
    ffmpeg_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    class FakeAsrBackend:
        name = "fake-asr"

        def transcribe(self, media_path: str):
            from transcribe_doc.asr.base import AsrTranscription

            return AsrTranscription(
                segments=[
                    TranscriptSegment(
                        segment_id="seg-0000",
                        start_seconds=0.0,
                        end_seconds=1.0,
                        text_raw="  привет   мир ",
                        text_clean="  привет   мир ",
                    )
                ],
                detected_language="ru",
            )

    monkeypatch.setattr("transcribe_doc.cli.commands.build_asr_backend", lambda config: FakeAsrBackend())
    monkeypatch.setattr("transcribe_doc.diarization.factory.is_resemblyzer_available", lambda: False)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  temp_dir: "./tmp"
  output_dir: "__OUTPUT__"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
""".replace("__OUTPUT__", str(tmp_path / "output")),
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path), "run", str(source_file)])

    assert exit_code == 0

    job_dirs = [path for path in (tmp_path / "output").iterdir() if path.is_dir()]
    assert len(job_dirs) == 1

    normalized_audio = job_dirs[0] / "artifacts" / "normalized_audio.wav"
    assert normalized_audio.exists()

    transcript_raw_path = job_dirs[0] / "transcript_raw.json"
    assert transcript_raw_path.exists()
    assert (job_dirs[0] / "segments.json").exists()
    assert (job_dirs[0] / "words.json").exists()

    job_payload = json.loads((job_dirs[0] / "job.json").read_text(encoding="utf-8"))
    assert job_payload["status"] == "completed"
    assert job_payload["warnings"] == []


def test_run_command_writes_transcript_artifact_when_asr_backend_available(
    tmp_path: Path, monkeypatch
) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    ffprobe_script = bin_dir / "ffprobe"
    ffprobe_script.write_text(
        "#!/bin/sh\n"
        "printf '{\"streams\": [], \"format\": {\"duration\": \"1.0\"}}'\n",
        encoding="utf-8",
    )
    ffprobe_script.chmod(0o755)

    ffmpeg_script = bin_dir / "ffmpeg"
    ffmpeg_script.write_text(
        "#!/bin/sh\n"
        "eval \"out=\\${$#}\"\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf 'wav' > \"$out\"\n",
        encoding="utf-8",
    )
    ffmpeg_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    class FakeAsrBackend:
        name = "fake-asr"

        def transcribe(self, media_path: str):
            from transcribe_doc.asr.base import AsrTranscription
            from transcribe_doc.app.models import WordToken

            return AsrTranscription(
                segments=[
                    TranscriptSegment(
                        segment_id="seg-0000",
                        start_seconds=0.0,
                        end_seconds=1.0,
                        text_raw="  привет   мир ",
                        text_clean="  привет   мир ",
                        words=[
                            WordToken(text="привет", start_seconds=0.0, end_seconds=0.5),
                            WordToken(text="мир", start_seconds=0.6, end_seconds=1.0),
                        ],
                    )
                ],
                detected_language="ru",
            )

    monkeypatch.setattr("transcribe_doc.cli.commands.build_asr_backend", lambda config: FakeAsrBackend())

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  temp_dir: "./tmp"
  output_dir: "__OUTPUT__"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
asr:
  backend: "whisper"
  model_name: "tiny"
  language: "ru"
""".replace("__OUTPUT__", str(tmp_path / "output")),
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path), "run", str(source_file)])

    assert exit_code == 0

    job_dirs = [path for path in (tmp_path / "output").iterdir() if path.is_dir()]
    assert len(job_dirs) == 1

    transcript_raw_path = job_dirs[0] / "transcript_raw.json"
    assert transcript_raw_path.exists()
    segments_path = job_dirs[0] / "segments.json"
    words_path = job_dirs[0] / "words.json"
    assert segments_path.exists()
    assert words_path.exists()

    transcript_payload = json.loads(transcript_raw_path.read_text(encoding="utf-8"))
    assert transcript_payload["segments"][0]["text_raw"] == "  привет   мир "
    assert transcript_payload["segments"][0]["text_clean"] == "Привет мир."
    assert transcript_payload["segments"][0]["words"][0]["text"] == "привет"
    assert transcript_payload["detected_language"] == "ru"

    segments_payload = json.loads(segments_path.read_text(encoding="utf-8"))
    assert segments_payload[0]["speaker_label"] == "SPEAKER_00"

    words_payload = json.loads(words_path.read_text(encoding="utf-8"))
    assert words_payload[0]["segment_id"] == "seg-0000"
    assert words_payload[0]["speaker_label"] == "SPEAKER_00"
    assert words_payload[0]["text"] == "привет"
    assert words_payload[0]["text_clean"] == "привет"
    assert words_payload[0]["issues"] == []

    job_payload = json.loads((job_dirs[0] / "job.json").read_text(encoding="utf-8"))
    assert job_payload["status"] == "completed"
    assert job_payload["detected_language"] == "ru"


def test_run_command_maps_single_expected_speaker_from_manifest(tmp_path: Path, monkeypatch) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    ffprobe_script = bin_dir / "ffprobe"
    ffprobe_script.write_text(
        "#!/bin/sh\n"
        "printf '{\"streams\": [], \"format\": {\"duration\": \"1.0\"}}'\n",
        encoding="utf-8",
    )
    ffprobe_script.chmod(0o755)

    ffmpeg_script = bin_dir / "ffmpeg"
    ffmpeg_script.write_text(
        "#!/bin/sh\n"
        "eval \"out=\\${$#}\"\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf 'wav' > \"$out\"\n",
        encoding="utf-8",
    )
    ffmpeg_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    class FakeAsrBackend:
        name = "fake-asr"

        def transcribe(self, media_path: str):
            from transcribe_doc.asr.base import AsrTranscription

            return AsrTranscription(
                segments=[
                    TranscriptSegment(
                        segment_id="seg-0000",
                        start_seconds=0.0,
                        end_seconds=1.0,
                        text_raw="привет",
                        text_clean="привет",
                    )
                ],
                detected_language="ru",
            )

    monkeypatch.setattr("transcribe_doc.cli.commands.build_asr_backend", lambda config: FakeAsrBackend())
    monkeypatch.setattr("transcribe_doc.diarization.factory.is_resemblyzer_available", lambda: False)

    manifest_path = tmp_path / "speakers.json"
    manifest_path.write_text(
        json.dumps(
            {"expected_speakers": [{"name": "Алексей", "role": "Интервьюер"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  temp_dir: "./tmp"
  output_dir: "__OUTPUT__"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
asr:
  backend: "whisper"
  model_name: "tiny"
  language: "ru"
""".replace("__OUTPUT__", str(tmp_path / "output")),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "run",
            str(source_file),
            "--speaker-manifest",
            str(manifest_path),
        ]
    )

    assert exit_code == 0

    job_dir = next(path for path in (tmp_path / "output").iterdir() if path.is_dir())
    segments_payload = json.loads((job_dir / "segments.json").read_text(encoding="utf-8"))
    assert segments_payload[0]["speaker_label"] == "Алексей"
    assert segments_payload[0]["mapping"]["machine_label"] == "SPEAKER_00"
    assert segments_payload[0]["mapping"]["display_label"] == "Алексей"

    job_payload = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert job_payload["metadata"]["speaker_manifest"]["expected_speakers"][0]["name"] == "Алексей"


def test_run_command_maps_two_expected_speakers_across_multiple_segments(
    tmp_path: Path, monkeypatch
) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    ffprobe_script = bin_dir / "ffprobe"
    ffprobe_script.write_text(
        "#!/bin/sh\n"
        "printf '{\"streams\": [], \"format\": {\"duration\": \"2.0\"}}'\n",
        encoding="utf-8",
    )
    ffprobe_script.chmod(0o755)

    ffmpeg_script = bin_dir / "ffmpeg"
    ffmpeg_script.write_text(
        "#!/bin/sh\n"
        "eval \"out=\\${$#}\"\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf 'wav' > \"$out\"\n",
        encoding="utf-8",
    )
    ffmpeg_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    class FakeAsrBackend:
        name = "fake-asr"

        def transcribe(self, media_path: str):
            from transcribe_doc.asr.base import AsrTranscription

            return AsrTranscription(
                segments=[
                    TranscriptSegment(
                        segment_id="seg-0000",
                        start_seconds=0.0,
                        end_seconds=1.0,
                        text_raw="привет",
                        text_clean="привет",
                    ),
                    TranscriptSegment(
                        segment_id="seg-0001",
                        start_seconds=1.1,
                        end_seconds=2.0,
                        text_raw="здравствуйте",
                        text_clean="здравствуйте",
                    ),
                ],
                detected_language="ru",
            )

    monkeypatch.setattr("transcribe_doc.cli.commands.build_asr_backend", lambda config: FakeAsrBackend())
    monkeypatch.setattr("transcribe_doc.diarization.factory.is_resemblyzer_available", lambda: False)

    manifest_path = tmp_path / "speakers.json"
    manifest_path.write_text(
        json.dumps(
            {"expected_speakers": [{"name": "Алексей"}, {"name": "Марина"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  temp_dir: "./tmp"
  output_dir: "__OUTPUT__"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
asr:
  backend: "whisper"
  model_name: "tiny"
  language: "ru"
""".replace("__OUTPUT__", str(tmp_path / "output")),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "run",
            str(source_file),
            "--speaker-manifest",
            str(manifest_path),
        ]
    )

    assert exit_code == 0

    job_dir = next(path for path in (tmp_path / "output").iterdir() if path.is_dir())
    segments_payload = json.loads((job_dir / "segments.json").read_text(encoding="utf-8"))
    assert [segment["speaker_label"] for segment in segments_payload] == ["Алексей", "Марина"]

    diarization_dump_path = job_dir / "artifacts" / "diarization_dump.json"
    assert diarization_dump_path.exists()

    diarization_dump = json.loads(diarization_dump_path.read_text(encoding="utf-8"))
    assert [segment["speaker_label"] for segment in diarization_dump] == ["SPEAKER_00", "SPEAKER_01"]

    job_payload = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert job_payload["artifacts"]["diarization_dump"] == str(diarization_dump_path)


def test_run_command_stores_low_diarization_quality_without_warning_status(
    tmp_path: Path, monkeypatch
) -> None:
    source_file = tmp_path / "sample.mp3"
    source_file.write_bytes(b"fake-audio")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    ffprobe_script = bin_dir / "ffprobe"
    ffprobe_script.write_text(
        "#!/bin/sh\n"
        "printf '{\"streams\": [], \"format\": {\"duration\": \"1.0\"}}'\n",
        encoding="utf-8",
    )
    ffprobe_script.chmod(0o755)

    ffmpeg_script = bin_dir / "ffmpeg"
    ffmpeg_script.write_text(
        "#!/bin/sh\n"
        "eval \"out=\\${$#}\"\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf 'wav' > \"$out\"\n",
        encoding="utf-8",
    )
    ffmpeg_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    class FakeAsrBackend:
        name = "fake-asr"

        def transcribe(self, media_path: str):
            from transcribe_doc.asr.base import AsrTranscription

            return AsrTranscription(
                segments=[
                    TranscriptSegment(
                        segment_id="seg-0000",
                        start_seconds=0.0,
                        end_seconds=1.0,
                        text_raw="привет",
                        text_clean="привет",
                    )
                ],
                detected_language="ru",
            )

    class FakeLowQualityDiarizationBackend:
        def diarize(self, media_path: str, segments):
            return [
                TranscriptSegment(
                    segment_id=segments[0].segment_id,
                    start_seconds=segments[0].start_seconds,
                    end_seconds=segments[0].end_seconds,
                    text_raw=segments[0].text_raw,
                    text_clean=segments[0].text_clean,
                    speaker_label="SPEAKER_00",
                    mapping=SpeakerMapping(
                        machine_label="SPEAKER_00",
                        display_label="SPEAKER_00",
                        confidence=0.75,
                        metadata={
                            "backend": "resemblyzer",
                            "cluster_label": 0,
                            "cluster_size": 1,
                            "detected_cluster_count": 2,
                            "assigned_centroid_similarity": 0.82,
                            "nearest_alternative_similarity": 0.77,
                            "centroid_similarity_margin": 0.05,
                        },
                    ),
                )
            ]

    monkeypatch.setattr("transcribe_doc.cli.commands.build_asr_backend", lambda config: FakeAsrBackend())
    monkeypatch.setattr(
        "transcribe_doc.cli.commands.build_diarization_backend",
        lambda config, speaker_manifest=None: FakeLowQualityDiarizationBackend(),
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
app:
  temp_dir: "./tmp"
  output_dir: "__OUTPUT__"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
asr:
  backend: "whisper"
  model_name: "tiny"
  language: "ru"
""".replace("__OUTPUT__", str(tmp_path / "output")),
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path), "run", str(source_file)])

    assert exit_code == 0

    job_dir = next(path for path in (tmp_path / "output").iterdir() if path.is_dir())
    job_payload = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert job_payload["status"] == "completed"
    assert job_payload["warnings"] == []
    assert job_payload["metadata"]["diarization_quality"] == {
        "backend": "resemblyzer",
        "segment_count": 1,
        "detected_cluster_count_max": 2,
        "min_centroid_similarity_margin": 0.05,
        "avg_centroid_similarity_margin": 0.05,
        "min_assigned_centroid_similarity": 0.82,
        "max_nearest_alternative_similarity": 0.77,
        "dominant_cluster_share": 1.0,
    }

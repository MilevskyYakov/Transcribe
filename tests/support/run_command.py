from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment, WordToken
from transcribe_doc.asr.base import AsrTranscription
from transcribe_doc.cli.main import main


@dataclass(frozen=True)
class CompletedAsrBackend:
    segments: list[TranscriptSegment]
    detected_language: str = "ru"
    name: str = "fake-asr"

    def transcribe(self, media_path: str) -> AsrTranscription:
        return AsrTranscription(
            segments=self.segments,
            detected_language=self.detected_language,
        )


@dataclass(frozen=True)
class CrashingAsrBackend:
    error: Exception
    name: str = "crashing-asr"

    def transcribe(self, media_path: str) -> AsrTranscription:
        raise self.error


class LowQualityDiarizationBackend:
    def diarize(self, media_path: str, segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
        source = segments[0]
        return [
            TranscriptSegment(
                segment_id=source.segment_id,
                start_seconds=source.start_seconds,
                end_seconds=source.end_seconds,
                text_raw=source.text_raw,
                text_clean=source.text_clean,
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


class RunCommandHarness:
    def __init__(self, tmp_path: Path, monkeypatch: Any) -> None:
        self.tmp_path = tmp_path
        self.monkeypatch = monkeypatch
        self.output_dir = tmp_path / "output"
        self.config_path = tmp_path / "config.yaml"
        self.source_file = self.fake_media_input()

    def fake_media_input(self, name: str = "sample.mp3") -> Path:
        source_file = self.tmp_path / name
        source_file.write_bytes(b"fake-audio")
        return source_file

    def install_fake_media_tools(self, duration: str = "1.0") -> Path:
        bin_dir = self.tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)

        ffprobe_script = bin_dir / "ffprobe"
        ffprobe_script.write_text(
            "#!/bin/sh\n"
            f"printf '{{\"streams\": [], \"format\": {{\"duration\": \"{duration}\"}}}}'\n",
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

        self.monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
        return bin_dir

    def hide_media_tools(self) -> None:
        self.monkeypatch.setenv("PATH", "")

    def write_config(self, *, include_asr: bool = False) -> Path:
        asr_block = ""
        if include_asr:
            asr_block = '\nasr:\n  backend: "whisper"\n  model_name: "tiny"\n  language: "ru"\n'

        self.config_path.write_text(
            f"""
app:
  temp_dir: "./tmp"
  output_dir: "{self.output_dir}"
  keep_temp: true
  save_artifacts: true
runtime:
  device: "cpu"
  max_parallel_jobs: 1
media:
  sample_rate: 16000
  mono: true
  normalize_audio: true
{asr_block}""",
            encoding="utf-8",
        )
        return self.config_path

    def use_asr_backend(self, backend: object) -> None:
        self.monkeypatch.setattr("transcribe_doc.cli.commands.build_asr_backend", lambda config: backend)

    def use_crashing_asr(self, error: Exception) -> None:
        self.use_asr_backend(CrashingAsrBackend(error))

    def use_completed_asr(
        self,
        segments: Iterable[TranscriptSegment] | None = None,
        *,
        detected_language: str = "ru",
    ) -> None:
        self.use_asr_backend(
            CompletedAsrBackend(
                segments=list(segments or [transcript_segment()]),
                detected_language=detected_language,
            )
        )

    def disable_resemblyzer(self) -> None:
        self.monkeypatch.setattr("transcribe_doc.diarization.factory.is_resemblyzer_available", lambda: False)

    def use_low_quality_diarization(self) -> None:
        self.monkeypatch.setattr(
            "transcribe_doc.cli.commands.build_diarization_backend",
            lambda config, speaker_manifest=None: LowQualityDiarizationBackend(),
        )

    def write_speaker_manifest(self, expected_speakers: list[dict[str, str]]) -> Path:
        manifest_path = self.tmp_path / "speakers.json"
        manifest_path.write_text(
            json.dumps({"expected_speakers": expected_speakers}, ensure_ascii=False),
            encoding="utf-8",
        )
        return manifest_path

    def run(self, *extra_args: str) -> int:
        return main(["--config", str(self.config_path), "run", str(self.source_file), *extra_args])

    def job_dirs(self) -> list[Path]:
        return [path for path in self.output_dir.iterdir() if path.is_dir()]

    def single_job_dir(self) -> Path:
        job_dirs = self.job_dirs()
        assert len(job_dirs) == 1
        return job_dirs[0]

    def read_json(self, relative_path: str) -> Any:
        return json.loads((self.single_job_dir() / relative_path).read_text(encoding="utf-8"))

    def job_payload(self) -> dict[str, Any]:
        return self.read_json("job.json")


def transcript_segment(
    *,
    segment_id: str = "seg-0000",
    start_seconds: float = 0.0,
    end_seconds: float = 1.0,
    text_raw: str = "привет",
    text_clean: str = "привет",
    words: list[WordToken] | None = None,
) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=segment_id,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        text_raw=text_raw,
        text_clean=text_clean,
        words=words or [],
    )


def word_token(text: str, start_seconds: float, end_seconds: float) -> WordToken:
    return WordToken(text=text, start_seconds=start_seconds, end_seconds=end_seconds)

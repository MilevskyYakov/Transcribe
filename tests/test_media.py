from pathlib import Path

import pytest

from mnema.app.exceptions import ExternalDependencyError
from mnema.media.normalizer import build_normalize_command, normalize_media
from mnema.media.probes import build_ffprobe_command, probe_media


def test_build_ffprobe_command_targets_input_file(tmp_path: Path) -> None:
    media_file = tmp_path / "sample.mp4"
    media_file.write_bytes(b"fake-video")

    command = build_ffprobe_command(media_file)

    assert command[0] == "ffprobe"
    assert command[-1] == str(media_file)


def test_build_normalize_command_targets_pcm_wav(tmp_path: Path) -> None:
    media_file = tmp_path / "sample.mp4"
    normalized = tmp_path / "normalized.wav"
    media_file.write_bytes(b"fake-video")

    command = build_normalize_command(media_file, normalized, sample_rate=16000, mono=True)

    assert command[0] == "ffmpeg"
    assert command[-1] == str(normalized)
    assert "-ar" in command
    assert "16000" in command


def test_probe_media_raises_when_ffprobe_missing(tmp_path: Path) -> None:
    media_file = tmp_path / "sample.mp3"
    media_file.write_bytes(b"fake-audio")

    with pytest.raises(ExternalDependencyError, match="ffprobe"):
        probe_media(media_file, ffprobe_path="")


def test_normalize_media_raises_when_ffmpeg_missing(tmp_path: Path) -> None:
    media_file = tmp_path / "sample.mp3"
    normalized = tmp_path / "normalized.wav"
    media_file.write_bytes(b"fake-audio")

    with pytest.raises(ExternalDependencyError, match="ffmpeg"):
        normalize_media(media_file, normalized, ffmpeg_path="")

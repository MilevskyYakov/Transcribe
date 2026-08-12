"""ffmpeg-based audio normalization helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from mnema.app.exceptions import ExternalDependencyError


def build_normalize_command(
    input_path: Path | str,
    output_path: Path | str,
    sample_rate: int,
    mono: bool,
) -> list[str]:
    """Build the ffmpeg command used for canonical WAV normalization."""
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
    ]
    if mono:
        command.extend(["-ac", "1"])
    command.append(str(output_path))
    return command


def normalize_media(
    input_path: Path | str,
    output_path: Path | str,
    sample_rate: int = 16000,
    mono: bool = True,
    ffmpeg_path: str | None = None,
    runner: Any = subprocess.run,
) -> Path:
    """Normalize media into a WAV working file."""
    binary = ffmpeg_path if ffmpeg_path is not None else shutil.which("ffmpeg")
    if not binary:
        raise ExternalDependencyError("ffmpeg is required but was not found in PATH.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    command = build_normalize_command(input_path, destination, sample_rate=sample_rate, mono=mono)
    command[0] = binary
    runner(
        command,
        capture_output=True,
        check=True,
        text=True,
    )
    return destination

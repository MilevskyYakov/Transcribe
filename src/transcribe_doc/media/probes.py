"""ffprobe helpers for media inspection."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from transcribe_doc.app.exceptions import ExternalDependencyError


def build_ffprobe_command(input_path: Path | str) -> list[str]:
    """Build the ffprobe command used for media metadata inspection."""
    return [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]


def probe_media(
    input_path: Path | str,
    ffprobe_path: str | None = None,
    runner: Any = subprocess.run,
) -> Dict[str, Any]:
    """Inspect media metadata using ffprobe."""
    binary = ffprobe_path if ffprobe_path is not None else shutil.which("ffprobe")
    if not binary:
        raise ExternalDependencyError("ffprobe is required but was not found in PATH.")

    command = build_ffprobe_command(input_path)
    command[0] = binary
    completed = runner(
        command,
        capture_output=True,
        check=True,
        text=True,
    )
    return json.loads(completed.stdout or "{}")

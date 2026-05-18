"""Health payload helpers for the local API."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from transcribe_doc.app.config import AppConfig

from .types import JsonObject


def health_payload(config: AppConfig) -> JsonObject:
    return {
        "status": "ok",
        "app": {
            "output_dir": config.app.output_dir,
            "temp_dir": config.app.temp_dir,
            "cache_dir": os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache")),
        },
        "media_tools": {
            "ffmpeg": tool_status("ffmpeg"),
            "ffprobe": tool_status("ffprobe"),
        },
    }


def tool_status(name: str) -> JsonObject:
    path = shutil.which(name)
    return {
        "available": path is not None,
        "path": path,
    }

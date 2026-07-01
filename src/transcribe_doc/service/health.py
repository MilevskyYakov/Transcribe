"""Health payload helpers for the local API."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from transcribe_doc.app.config import AppConfig

from .contracts import (
    AppPathsResponse,
    HealthResponse,
    MediaToolsResponse,
    MediaToolStatusResponse,
    dataclass_payload,
)
from .types import JsonObject


def health_payload(config: AppConfig) -> JsonObject:
    return dataclass_payload(
        HealthResponse(
            status="ok",
            app=AppPathsResponse(
                output_dir=config.app.output_dir,
                temp_dir=config.app.temp_dir,
                cache_dir=os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache")),
            ),
            media_tools=MediaToolsResponse(
                ffmpeg=tool_status_response("ffmpeg"),
                ffprobe=tool_status_response("ffprobe"),
            ),
        )
    )


def tool_status(name: str) -> JsonObject:
    return dataclass_payload(tool_status_response(name))


def tool_status_response(name: str) -> MediaToolStatusResponse:
    path = shutil.which(name)
    return MediaToolStatusResponse(available=path is not None, path=path)

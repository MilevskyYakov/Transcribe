"""Concrete whisper-compatible ASR backend."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Optional

from mnema.app.exceptions import ExternalDependencyError
from mnema.app.models import TranscriptSegment, WordToken
from mnema.asr.base import AsrBackend, AsrTranscription
from mnema.asr.whisper_cache import ensure_whisper_model_ready


class WhisperBackend(AsrBackend):
    """Thin adapter over an OpenAI Whisper-compatible model object."""

    name = "whisper"

    def __init__(
        self,
        model_name: str = "base",
        *,
        language: Optional[str] = None,
        loader: Optional[Callable[[str], Any]] = None,
        model: Any = None,
    ) -> None:
        self._model_name = model_name
        self._language = language
        self._loader = loader or _default_loader
        self._model = model

    def transcribe(self, media_path: str) -> AsrTranscription:
        model = self._model
        if model is None:
            ensure_whisper_model_ready(self._model_name)
            model = self._loader(self._model_name)
            if model is None:
                raise ExternalDependencyError(
                    "The 'whisper' package is required for WhisperBackend but is not installed."
                )
            self._model = model

        result = model.transcribe(media_path, language=self._language, word_timestamps=True)
        segments = result.get("segments", [])

        return AsrTranscription(
            segments=[
                TranscriptSegment(
                    segment_id=f"seg-{index:04d}",
                    start_seconds=float(segment.get("start", 0.0)),
                    end_seconds=float(segment.get("end", 0.0)),
                    text_raw=str(segment.get("text", "")),
                    text_clean=str(segment.get("text", "")),
                    words=[
                        WordToken(
                            text=str(word.get("word", "")).strip(),
                            start_seconds=float(word.get("start", 0.0)),
                            end_seconds=float(word.get("end", 0.0)),
                        )
                        for word in segment.get("words", [])
                    ],
                )
                for index, segment in enumerate(segments)
            ],
            detected_language=result.get("language"),
        )


def _default_loader(model_name: str) -> Any:
    try:
        whisper_module = import_module("whisper")
    except ModuleNotFoundError:
        return None
    return whisper_module.load_model(model_name)

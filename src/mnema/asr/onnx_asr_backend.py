"""ONNX ASR backend for Parakeet and GigaAM models."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
import wave

from mnema.app.exceptions import ExternalDependencyError
from mnema.app.models import TranscriptSegment
from mnema.asr.base import AsrBackend, AsrTranscription
from mnema.asr.external_model_cache import (
    ensure_external_model_ready,
    external_model_runtime_path,
    external_runtime_name,
)


_DEFAULT_CHUNK_SECONDS = 60.0
_CPU_PROVIDERS = ["CPUExecutionProvider"]
_ONNX_RUNTIME_FAILURE_MESSAGE = (
    "ONNX ASR модель не смогла обработать аудио. "
    "Попробуйте другую модель или повторите позже."
)


class OnnxAsrBackend(AsrBackend):
    """Adapter over the optional onnx-asr package."""

    name = "onnx-asr"

    def __init__(
        self,
        model_name: str,
        *,
        loader: Callable[..., Any] | None = None,
        model: Any = None,
        chunk_seconds: float = _DEFAULT_CHUNK_SECONDS,
    ) -> None:
        self._model_name = model_name
        self._loader = loader or _default_loader
        self._model = model
        self._chunk_seconds = chunk_seconds

    def transcribe(self, media_path: str) -> AsrTranscription:
        model = self._model
        if model is None:
            ensure_external_model_ready(self._model_name)
            model = self._load_model()
            if model is None:
                raise ExternalDependencyError(
                    "The 'onnx-asr' package is required for Parakeet/GigaAM but is not installed."
                )
            self._model = model

        segments: list[TranscriptSegment] = []
        with _chunk_wav_if_needed(Path(media_path), self._chunk_seconds) as chunks:
            for index, chunk in enumerate(chunks):
                result = self._recognize_with_coreml_fallback(model, str(chunk.path))
                model = self._model
                text = _extract_text(result).strip()
                if not text:
                    continue
                segments.append(
                    TranscriptSegment(
                        segment_id=f"seg-{index:04d}",
                        start_seconds=chunk.start_seconds,
                        end_seconds=chunk.end_seconds,
                        text_raw=text,
                        text_clean=text,
                    )
                )
        if not segments:
            segments = [
                TranscriptSegment(
                    segment_id="seg-0000",
                    start_seconds=0.0,
                    end_seconds=0.0,
                    text_raw="",
                    text_clean="",
                )
            ]
        return AsrTranscription(
            segments=segments,
            detected_language="ru" if self._model_name == "gigaam-v3" else None,
        )

    def _load_model(self, *, providers: list[str] | None = None) -> Any:
        runtime_name = external_runtime_name(self._model_name)
        model_path = external_model_runtime_path(self._model_name)
        if providers is None:
            if self._model_name == "parakeet-v3":
                return self._loader(runtime_name, path=model_path, providers=_CPU_PROVIDERS)
            try:
                return self._loader(runtime_name, path=model_path)
            except Exception as error:
                if not _should_retry_load_on_cpu(error):
                    raise
                return self._loader(runtime_name, path=model_path, providers=_CPU_PROVIDERS)
        return self._loader(runtime_name, path=model_path, providers=providers)

    def _recognize_with_coreml_fallback(self, model: Any, media_path: str) -> object:
        try:
            return model.recognize(media_path)
        except Exception as error:
            if not _is_coreml_runtime_error(error):
                raise
            cpu_model = self._load_model(providers=_CPU_PROVIDERS)
            if cpu_model is None:
                raise ExternalDependencyError(_ONNX_RUNTIME_FAILURE_MESSAGE) from error
            self._model = cpu_model
            try:
                return cpu_model.recognize(media_path)
            except Exception as cpu_error:
                raise ExternalDependencyError(_ONNX_RUNTIME_FAILURE_MESSAGE) from cpu_error


def _default_loader(runtime_name: str, *, path: Path | None = None, providers: list[str] | None = None) -> Any:
    try:
        onnx_asr = import_module("onnx_asr")
    except ModuleNotFoundError:
        return None
    if providers is None:
        return onnx_asr.load_model(runtime_name, path=path)
    return onnx_asr.load_model(runtime_name, path=path, providers=providers)


def _is_coreml_runtime_error(error: Exception) -> bool:
    message = str(error)
    return "CoreMLExecutionProvider" in message or "CoreML" in message


def _should_retry_load_on_cpu(error: Exception) -> bool:
    message = str(error)
    return _is_coreml_runtime_error(error) or "model_path must not be empty" in message


def _extract_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        return "\n".join(_extract_text(item) for item in result if item is not None)
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text
    if isinstance(result, dict):
        value = result.get("text") or result.get("transcription")
        if isinstance(value, str):
            return value
    return str(result)


class _AudioChunk:
    def __init__(self, path: Path, start_seconds: float, end_seconds: float) -> None:
        self.path = path
        self.start_seconds = start_seconds
        self.end_seconds = end_seconds


@contextmanager
def _chunk_wav_if_needed(path: Path, chunk_seconds: float):
    try:
        with wave.open(str(path), "rb") as source:
            params = source.getparams()
            frame_rate = source.getframerate()
            frame_count = source.getnframes()
            if frame_rate <= 0 or frame_count <= 0:
                yield [_AudioChunk(path, 0.0, 0.0)]
                return
            duration_seconds = frame_count / frame_rate
            if duration_seconds <= chunk_seconds:
                yield [_AudioChunk(path, 0.0, duration_seconds)]
                return
            frames_per_chunk = max(1, int(frame_rate * chunk_seconds))
            with TemporaryDirectory(prefix="onnx-asr-chunks-") as temp_dir:
                chunks: list[_AudioChunk] = []
                for index, start_frame in enumerate(range(0, frame_count, frames_per_chunk)):
                    source.setpos(start_frame)
                    frames_to_read = min(frames_per_chunk, frame_count - start_frame)
                    chunk_path = Path(temp_dir) / f"chunk-{index:04d}.wav"
                    with wave.open(str(chunk_path), "wb") as target:
                        target.setparams(params)
                        target.writeframes(source.readframes(frames_to_read))
                    chunks.append(
                        _AudioChunk(
                            path=chunk_path,
                            start_seconds=start_frame / frame_rate,
                            end_seconds=(start_frame + frames_to_read) / frame_rate,
                        )
                    )
                yield chunks
                return
    except (OSError, wave.Error):
        yield [_AudioChunk(path, 0.0, 0.0)]

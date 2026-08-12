"""Factory helpers for selecting ASR backends from configuration."""

from __future__ import annotations

from mnema.app.config import AppConfig
from mnema.app.exceptions import ConfigurationError
from mnema.asr.base import AsrBackend
from mnema.asr.onnx_asr_backend import OnnxAsrBackend
from mnema.asr.whisper_backend import WhisperBackend


def build_asr_backend(config: AppConfig) -> AsrBackend:
    """Construct the configured ASR backend."""
    backend_name = config.asr.backend.strip().lower()

    if backend_name == "whisper":
        return WhisperBackend(
            model_name=config.asr.model_name,
            language=config.asr.language,
        )
    if backend_name in {"onnx-asr", "onnx_asr"}:
        return OnnxAsrBackend(model_name=config.asr.model_name)

    raise ConfigurationError(f"Unsupported ASR backend: {config.asr.backend}")

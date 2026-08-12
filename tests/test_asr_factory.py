import pytest

from mnema.app.config import AppConfig, AsrSection
from mnema.app.exceptions import ConfigurationError
from mnema.asr.factory import build_asr_backend
from mnema.asr.onnx_asr_backend import OnnxAsrBackend
from mnema.asr.whisper_backend import WhisperBackend


def test_build_asr_backend_returns_whisper_backend_for_whisper_config() -> None:
    config = AppConfig(asr=AsrSection(backend="whisper", model_name="tiny", language="ru"))

    backend = build_asr_backend(config)

    assert isinstance(backend, WhisperBackend)


def test_build_asr_backend_returns_onnx_backend_for_onnx_config() -> None:
    config = AppConfig(asr=AsrSection(backend="onnx-asr", model_name="gigaam-v3", language="ru"))

    backend = build_asr_backend(config)

    assert isinstance(backend, OnnxAsrBackend)


def test_build_asr_backend_rejects_unknown_backend() -> None:
    config = AppConfig(asr=AsrSection(backend="unknown", model_name="tiny", language="ru"))

    with pytest.raises(ConfigurationError, match="Unsupported ASR backend"):
        build_asr_backend(config)

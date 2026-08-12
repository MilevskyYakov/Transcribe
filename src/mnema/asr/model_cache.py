"""Compatibility facade for ASR model cache operations.

Concrete registry, status, Whisper, and external-model cache behavior lives in
focused modules. Keep this file thin so older imports continue to work while new
code depends on the explicit boundary modules directly.
"""

from __future__ import annotations

from mnema.asr.external_model_cache import (
    download_external_model,
    ensure_external_model_ready,
    external_download_progress_payload,
    external_model_runtime_path,
    external_runtime_name,
    inspect_external_model,
    mark_model_download_error,
    mark_model_download_queued,
)
from mnema.asr.model_registry import EXTERNAL_MODELS, ExternalModelSpec
from mnema.asr.whisper_cache import (
    ModelProgress,
    download_whisper_model,
    ensure_whisper_model_ready,
    inspect_whisper_model,
    inspect_whisper_models,
)

__all__ = [
    "EXTERNAL_MODELS",
    "ExternalModelSpec",
    "ModelProgress",
    "download_external_model",
    "download_whisper_model",
    "ensure_external_model_ready",
    "ensure_whisper_model_ready",
    "external_download_progress_payload",
    "external_model_runtime_path",
    "external_runtime_name",
    "inspect_external_model",
    "inspect_whisper_model",
    "inspect_whisper_models",
    "mark_model_download_error",
    "mark_model_download_queued",
]

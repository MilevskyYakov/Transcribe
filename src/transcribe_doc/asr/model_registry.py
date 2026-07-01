"""Known ASR model registry data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]


@dataclass(frozen=True)
class ExternalModelSpec:
    name: str
    label: str
    backend: str
    runtime_name: str
    url: str
    filename: str
    expected_sha256: str | None
    language: str
    description: str

    def metadata(self, path: Path | str) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "backend": self.backend,
            "runtime_name": self.runtime_name,
            "language": self.language,
            "description": self.description,
            "path": str(path),
        }


EXTERNAL_MODELS = [
    ExternalModelSpec(
        name="parakeet-v3",
        label="Parakeet V3",
        backend="onnx-asr",
        runtime_name="nemo-parakeet-tdt-0.6b-v3",
        url="https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/resolve/main/parakeet-tdt-0.6b-v3.nemo",
        filename="parakeet-tdt-0.6b-v3.nemo",
        expected_sha256=None,
        language="Многоязычная",
        description="NVIDIA Parakeet-TDT 0.6B v3 через ONNX ASR",
    ),
    ExternalModelSpec(
        name="gigaam-v3",
        label="GigaAM v3",
        backend="onnx-asr",
        runtime_name="gigaam-v3-e2e-ctc",
        url="https://huggingface.co/protocolvoice/asr-models/resolve/main/gigaam_v3_e2e_ctc_int8.onnx",
        filename="gigaam_v3_e2e_ctc_int8.onnx",
        expected_sha256="0aacb41f70f0f5aaac4b45dd430337b9e16b180f22c72af04db8516e7609c3c0",
        language="Только Russian",
        description="GigaAM v3 E2E CTC int8 ONNX с пунктуацией",
    ),
]


def external_spec(model_name: str) -> ExternalModelSpec | None:
    return next((spec for spec in EXTERNAL_MODELS if spec.name == model_name), None)

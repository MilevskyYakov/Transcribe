from pathlib import Path
import wave

import pytest

from mnema.app.exceptions import ExternalDependencyError
from mnema.asr.onnx_asr_backend import OnnxAsrBackend


class FakeOnnxModel:
    def __init__(self, result: object) -> None:
        self.result = result

    def recognize(self, media_path: str) -> object:
        assert media_path == "audio.wav"
        return self.result


def test_onnx_backend_transcribes_string_result() -> None:
    backend = OnnxAsrBackend("gigaam-v3", model=FakeOnnxModel("Привет, это тест"))

    result = backend.transcribe("audio.wav")

    assert result.detected_language == "ru"
    assert result.segments[0].text_clean == "Привет, это тест"


def test_onnx_backend_transcribes_segment_list_result() -> None:
    backend = OnnxAsrBackend(
        "parakeet-v3",
        model=FakeOnnxModel([{"text": "Первый фрагмент"}, {"text": "Второй фрагмент"}]),
    )

    result = backend.transcribe("audio.wav")

    assert result.detected_language is None
    assert result.segments[0].text_clean == "Первый фрагмент\nВторой фрагмент"


def test_onnx_backend_splits_long_wav_before_recognition(tmp_path: Path) -> None:
    wav_path = tmp_path / "long.wav"
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(10)
        wav.writeframes(b"\0\0" * 25)

    class CountingModel:
        def __init__(self) -> None:
            self.paths: list[str] = []

        def recognize(self, media_path: str) -> str:
            self.paths.append(media_path)
            return f"chunk {len(self.paths)}"

    model = CountingModel()
    backend = OnnxAsrBackend("gigaam-v3", model=model, chunk_seconds=1.0)

    result = backend.transcribe(str(wav_path))

    assert len(model.paths) == 3
    assert [segment.text_clean for segment in result.segments] == ["chunk 1", "chunk 2", "chunk 3"]
    assert [segment.start_seconds for segment in result.segments] == [0.0, 1.0, 2.0]
    assert result.segments[-1].end_seconds == 2.5


def test_onnx_backend_retries_coreml_failure_on_cpu(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.ensure_external_model_ready",
        lambda model_name: None,
    )
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.external_model_runtime_path",
        lambda model_name: tmp_path / model_name,
    )

    class CoreMlFailingModel:
        def recognize(self, media_path: str) -> str:
            raise RuntimeError("CoreMLExecutionProvider failed")

    class CpuModel:
        def recognize(self, media_path: str) -> str:
            assert media_path == "audio.wav"
            return "CPU распознал"

    calls: list[tuple[str, list[str] | None]] = []

    def loader(runtime_name: str, *, path=None, providers: list[str] | None = None):
        calls.append((runtime_name, path, providers))
        assert runtime_name == "gigaam-v3-e2e-ctc"
        if providers == ["CPUExecutionProvider"]:
            return CpuModel()
        return CoreMlFailingModel()

    backend = OnnxAsrBackend("gigaam-v3", loader=loader)

    result = backend.transcribe("audio.wav")

    assert [segment.text_clean for segment in result.segments] == ["CPU распознал"]
    assert calls[0][0] == "gigaam-v3-e2e-ctc"
    assert calls[0][1].name == "gigaam-v3"
    assert calls[0][2] is None
    assert calls[1][0] == "gigaam-v3-e2e-ctc"
    assert calls[1][1].name == "gigaam-v3"
    assert calls[1][2] == ["CPUExecutionProvider"]


def test_onnx_backend_retries_coreml_load_failure_on_cpu(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.ensure_external_model_ready",
        lambda model_name: None,
    )
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.external_model_runtime_path",
        lambda model_name: tmp_path / model_name,
    )
    calls = []

    class CpuModel:
        def recognize(self, media_path: str) -> str:
            return "CPU загрузился"

    def loader(runtime_name: str, *, path=None, providers: list[str] | None = None):
        calls.append((runtime_name, path, providers))
        if providers == ["CPUExecutionProvider"]:
            return CpuModel()
        raise RuntimeError("CoreMLExecutionProvider failed while loading")

    backend = OnnxAsrBackend("gigaam-v3", loader=loader)

    result = backend.transcribe("audio.wav")

    assert [segment.text_clean for segment in result.segments] == ["CPU загрузился"]
    assert calls[0][2] is None
    assert calls[1][2] == ["CPUExecutionProvider"]


def test_parakeet_loads_with_cpu_provider_first(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.ensure_external_model_ready",
        lambda model_name: None,
    )
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.external_model_runtime_path",
        lambda model_name: tmp_path / model_name,
    )
    calls = []

    class CpuModel:
        def recognize(self, media_path: str) -> str:
            return "Parakeet CPU"

    def loader(runtime_name: str, *, path=None, providers: list[str] | None = None):
        calls.append((runtime_name, path, providers))
        if providers == ["CPUExecutionProvider"]:
            return CpuModel()
        raise RuntimeError("model_path must not be empty")

    backend = OnnxAsrBackend("parakeet-v3", loader=loader)

    result = backend.transcribe("audio.wav")

    assert [segment.text_clean for segment in result.segments] == ["Parakeet CPU"]
    assert len(calls) == 1
    assert calls[0][0] == "nemo-parakeet-tdt-0.6b-v3"
    assert calls[0][1].name == "parakeet-v3"
    assert calls[0][2] == ["CPUExecutionProvider"]


def test_onnx_backend_retries_model_path_load_failure_on_cpu(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.ensure_external_model_ready",
        lambda model_name: None,
    )
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.external_model_runtime_path",
        lambda model_name: tmp_path / model_name,
    )
    calls = []

    class CpuModel:
        def recognize(self, media_path: str) -> str:
            return "CPU после model_path"

    def loader(runtime_name: str, *, path=None, providers: list[str] | None = None):
        calls.append((runtime_name, path, providers))
        if providers == ["CPUExecutionProvider"]:
            return CpuModel()
        raise RuntimeError("model_path must not be empty")

    backend = OnnxAsrBackend("gigaam-v3", loader=loader)

    result = backend.transcribe("audio.wav")

    assert [segment.text_clean for segment in result.segments] == ["CPU после model_path"]
    assert calls[0][2] is None
    assert calls[1][2] == ["CPUExecutionProvider"]


def test_onnx_backend_raises_short_error_when_cpu_retry_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.ensure_external_model_ready",
        lambda model_name: None,
    )
    monkeypatch.setattr(
        "mnema.asr.onnx_asr_backend.external_model_runtime_path",
        lambda model_name: tmp_path / model_name,
    )

    class FailingModel:
        def __init__(self, message: str) -> None:
            self.message = message

        def recognize(self, media_path: str) -> str:
            raise RuntimeError(self.message)

    def loader(runtime_name: str, *, path=None, providers: list[str] | None = None):
        if providers == ["CPUExecutionProvider"]:
            return FailingModel("CPUExecutionProvider failed too")
        return FailingModel("CoreMLExecutionProvider failed")

    backend = OnnxAsrBackend("gigaam-v3", loader=loader)

    with pytest.raises(ExternalDependencyError) as exc_info:
        backend.transcribe("audio.wav")

    assert str(exc_info.value) == (
        "ONNX ASR модель не смогла обработать аудио. "
        "Попробуйте другую модель или повторите позже."
    )
    assert "CPUExecutionProvider failed too" in str(exc_info.value.__cause__)

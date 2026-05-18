import hashlib
from pathlib import Path

from transcribe_doc.asr import model_cache


def test_inspect_whisper_model_reports_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(model_cache, "_model_url", lambda name: f"https://example.test/{'a' * 64}/{name}.pt")

    status = model_cache.inspect_whisper_model("large-v3")

    assert status["status"] == "missing"
    assert status["name"] == "large-v3"


def test_inspect_whisper_model_reports_corrupt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(model_cache, "_model_url", lambda name: f"https://example.test/{'a' * 64}/{name}.pt")
    model_path = tmp_path / "cache" / "whisper" / "large-v3.pt"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"partial")

    status = model_cache.inspect_whisper_model("large-v3")

    assert status["status"] == "corrupt"
    assert status["size_bytes"] == len(b"partial")


def test_inspect_whisper_model_reports_ready(tmp_path: Path, monkeypatch) -> None:
    payload = b"model"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(model_cache, "_model_url", lambda name: f"https://example.test/{digest}/{name}.pt")
    model_path = tmp_path / "cache" / "whisper" / "tiny.pt"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(payload)

    status = model_cache.inspect_whisper_model("tiny")

    assert status["status"] == "ready"


def test_inspect_external_model_reports_download_errors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    model_cache.mark_model_download_error("parakeet-v3", "network failed")

    status = model_cache.inspect_external_model(model_cache.EXTERNAL_MODELS[0])

    assert status["name"] == "parakeet-v3"
    assert status["status"] == "error"
    assert status["stale_download"] is True
    assert status["message"] == "network failed"


def test_inspect_external_model_prefers_ready_files_over_stale_error(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    model_cache.mark_model_download_error("parakeet-v3", "old CoreML failure")
    runtime_dir = tmp_path / "cache" / "transcribe-doc" / "models" / "parakeet-v3"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "config.json").write_text("{}", encoding="utf-8")
    (runtime_dir / "encoder-model.onnx").write_bytes(b"onnx")

    status = model_cache.inspect_external_model(model_cache.EXTERNAL_MODELS[0])

    assert status["status"] == "ready"
    assert status["message"] == "Модель готова"


def test_download_external_model_uses_app_cache_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    calls = []

    class FakeOnnxAsr:
        @staticmethod
        def load_model(runtime_name, path=None, providers=None):
            path = Path(path)
            calls.append((runtime_name, path, providers))
            path.mkdir(parents=True)
            (path / "config.json").write_text("{}", encoding="utf-8")
            (path / "model.onnx").write_bytes(b"onnx")
            return object()

    monkeypatch.setattr(model_cache, "import_module", lambda name: FakeOnnxAsr)

    result = model_cache.download_external_model(model_cache.EXTERNAL_MODELS[0])

    assert calls == [
        (
            "nemo-parakeet-tdt-0.6b-v3",
            tmp_path / "cache" / "transcribe-doc" / "models" / "parakeet-v3",
            ["CPUExecutionProvider"],
        )
    ]
    assert result["status"] == "ready"


def test_download_external_model_clears_incomplete_runtime_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    runtime_dir = tmp_path / "cache" / "transcribe-doc" / "models" / "parakeet-v3"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "config.json").write_text("{}", encoding="utf-8")
    calls = []

    class FakeOnnxAsr:
        @staticmethod
        def load_model(runtime_name, path=None, providers=None):
            path = Path(path)
            calls.append(path.exists())
            path.mkdir(parents=True)
            (path / "config.json").write_text("{}", encoding="utf-8")
            (path / "model.onnx").write_bytes(b"onnx")
            return object()

    monkeypatch.setattr(model_cache, "import_module", lambda name: FakeOnnxAsr)

    model_cache.download_external_model(model_cache.EXTERNAL_MODELS[0])

    assert calls == [False]


def test_external_download_progress_counts_partial_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    runtime_dir = tmp_path / "cache" / "transcribe-doc" / "models" / "parakeet-v3"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "encoder-model.onnx").write_bytes(b"12345")
    partial_dir = runtime_dir / ".cache" / "huggingface" / "download"
    partial_dir.mkdir(parents=True)
    (partial_dir / "encoder-model.onnx.data.incomplete").write_bytes(b"123")

    payload = model_cache.external_download_progress_payload(model_cache.EXTERNAL_MODELS[0])

    assert payload["downloaded_bytes"] == 8
    assert payload["progress"] == 1

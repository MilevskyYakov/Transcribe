from pathlib import Path

import pytest

from transcribe_doc.app.exceptions import ExternalDependencyError
from transcribe_doc.asr.base import AsrTranscription
from transcribe_doc.asr.whisper_backend import WhisperBackend


class FakeWhisperModel:
    def transcribe(self, media_path: str, **kwargs):
        return {
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 1.25,
                    "text": "  привет   мир ",
                    "words": [
                        {"word": "привет", "start": 0.0, "end": 0.5},
                        {"word": "мир", "start": 0.6, "end": 1.0},
                    ],
                }
            ],
            "language": "ru",
            "text": "  привет   мир ",
        }


def test_whisper_backend_maps_segments_to_transcript_contract(tmp_path: Path) -> None:
    media_file = tmp_path / "sample.wav"
    media_file.write_bytes(b"wav")

    backend = WhisperBackend(model=FakeWhisperModel(), model_name="tiny")

    transcription = backend.transcribe(str(media_file))

    assert isinstance(transcription, AsrTranscription)
    assert transcription.detected_language == "ru"
    assert len(transcription.segments) == 1
    assert transcription.segments[0].segment_id == "seg-0000"
    assert transcription.segments[0].text_raw == "  привет   мир "
    assert transcription.segments[0].text_clean == "  привет   мир "
    assert [word.text for word in transcription.segments[0].words] == ["привет", "мир"]


def test_whisper_backend_requires_dependency_when_model_not_injected(tmp_path: Path) -> None:
    media_file = tmp_path / "sample.wav"
    media_file.write_bytes(b"wav")

    backend = WhisperBackend(model=None, model_name="tiny", loader=lambda _: None)

    with pytest.raises(ExternalDependencyError, match="whisper"):
        backend.transcribe(str(media_file))


def test_whisper_backend_fails_fast_for_corrupt_cached_model(tmp_path: Path, monkeypatch) -> None:
    media_file = tmp_path / "sample.wav"
    media_file.write_bytes(b"wav")
    cache_dir = tmp_path / "cache"
    whisper_dir = cache_dir / "whisper"
    whisper_dir.mkdir(parents=True)
    (whisper_dir / "tiny.pt").write_bytes(b"incomplete")
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_dir))

    backend = WhisperBackend(model=None, model_name="tiny")

    with pytest.raises(ExternalDependencyError, match="поврежд"):
        backend.transcribe(str(media_file))

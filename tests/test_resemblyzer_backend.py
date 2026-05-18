from pathlib import Path
from importlib import import_module

import numpy as np

from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment
from transcribe_doc.diarization.resemblyzer_backend import (
    ResemblyzerDiarizationBackend,
    is_resemblyzer_available,
)


class FakeVoiceEncoder:
    def embed_utterance(self, wav_segment):
        if len(wav_segment) < 5:
            return np.array([1.0, 0.0], dtype=float)
        return np.array([0.0, 1.0], dtype=float)


class FakeClusterer:
    def fit_predict(self, embeddings):
        return np.array([0, 1], dtype=int)


class FakeSingleClusterer:
    def fit_predict(self, embeddings):
        return np.array([0, 0], dtype=int)


class SequenceVoiceEncoder:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self._embeddings = [np.asarray(embedding, dtype=float) for embedding in embeddings]
        self._index = 0

    def embed_utterance(self, wav_segment):
        embedding = self._embeddings[self._index]
        self._index += 1
        return embedding


def test_resemblyzer_backend_assigns_clustered_speaker_labels(tmp_path: Path) -> None:
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"wav")

    def wav_loader(path: str):
        return np.arange(0, 32000, dtype=np.float32)

    backend = ResemblyzerDiarizationBackend(
        encoder=FakeVoiceEncoder(),
        wav_loader=wav_loader,
        clusterer=FakeClusterer(),
        sample_rate=16000,
    )

    diarized = backend.diarize(
        str(wav_path),
        [
            TranscriptSegment(
                segment_id="seg-0000",
                start_seconds=0.0,
                end_seconds=0.0002,
                text_raw="привет",
                text_clean="привет",
            ),
            TranscriptSegment(
                segment_id="seg-0001",
                start_seconds=0.5,
                end_seconds=1.0,
                text_raw="здравствуйте",
                text_clean="здравствуйте",
            ),
        ],
    )

    assert diarized[0].speaker_label == "SPEAKER_00"
    assert diarized[1].speaker_label == "SPEAKER_01"
    assert diarized[0].mapping == SpeakerMapping(
        machine_label="SPEAKER_00",
        display_label="SPEAKER_00",
        confidence=0.75,
        metadata={
            "backend": "resemblyzer",
            "cluster_label": 0,
            "segment_duration_seconds": 0.0002,
            "wav_slice_samples": 3,
            "cluster_size": 1,
            "detected_cluster_count": 2,
            "assigned_centroid_similarity": 1.0,
            "nearest_alternative_similarity": 0.0,
            "centroid_similarity_margin": 1.0,
        },
    )


def test_resemblyzer_backend_records_quality_metrics_for_single_detected_cluster(
    tmp_path: Path,
) -> None:
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"wav")

    def wav_loader(path: str):
        return np.ones(32000, dtype=np.float32)

    backend = ResemblyzerDiarizationBackend(
        encoder=FakeVoiceEncoder(),
        wav_loader=wav_loader,
        clusterer=FakeSingleClusterer(),
        sample_rate=16000,
    )

    diarized = backend.diarize(
        str(wav_path),
        [
            TranscriptSegment(
                segment_id="seg-0000",
                start_seconds=0.0,
                end_seconds=0.0002,
                text_raw="привет",
                text_clean="привет",
            ),
            TranscriptSegment(
                segment_id="seg-0001",
                start_seconds=0.0003,
                end_seconds=0.0005,
                text_raw="здравствуйте",
                text_clean="здравствуйте",
            ),
        ],
    )

    assert diarized[0].mapping is not None
    assert diarized[0].mapping.metadata == {
        "backend": "resemblyzer",
        "cluster_label": 0,
        "segment_duration_seconds": 0.0002,
        "wav_slice_samples": 3,
        "cluster_size": 2,
        "detected_cluster_count": 1,
        "assigned_centroid_similarity": 1.0,
        "nearest_alternative_similarity": None,
        "centroid_similarity_margin": None,
    }


def test_resemblyzer_backend_clamps_out_of_bounds_segments_to_non_empty_slices(
    tmp_path: Path,
) -> None:
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"wav")

    def wav_loader(path: str):
        return np.arange(0, 10, dtype=np.float32)

    backend = ResemblyzerDiarizationBackend(
        encoder=FakeVoiceEncoder(),
        wav_loader=wav_loader,
        clusterer=FakeClusterer(),
        sample_rate=10,
    )

    diarized = backend.diarize(
        str(wav_path),
        [
            TranscriptSegment(
                segment_id="seg-0000",
                start_seconds=0.0,
                end_seconds=0.2,
                text_raw="привет",
                text_clean="привет",
            ),
            TranscriptSegment(
                segment_id="seg-0001",
                start_seconds=0.95,
                end_seconds=1.4,
                text_raw="здравствуйте",
                text_clean="здравствуйте",
            ),
        ],
    )

    assert diarized[1].mapping is not None
    assert diarized[1].mapping.metadata["wav_slice_samples"] == 1


def test_resemblyzer_backend_auto_detects_two_speakers_from_embeddings(tmp_path: Path) -> None:
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"wav")

    def wav_loader(path: str):
        return np.ones(64000, dtype=np.float32)

    backend = ResemblyzerDiarizationBackend(
        encoder=SequenceVoiceEncoder(
            [
                [1.0, 0.0],
                [0.98, 0.02],
                [0.0, 1.0],
                [0.02, 0.98],
            ]
        ),
        wav_loader=wav_loader,
        sample_rate=16000,
        num_speakers="auto",
    )

    diarized = backend.diarize(
        str(wav_path),
        [
            TranscriptSegment(
                segment_id=f"seg-{index:04d}",
                start_seconds=float(index),
                end_seconds=float(index + 1),
                text_raw="текст",
                text_clean="текст",
            )
            for index in range(4)
        ],
    )

    labels = [segment.speaker_label for segment in diarized]

    assert len(set(labels)) == 2
    assert diarized[0].mapping is not None
    assert diarized[0].mapping.metadata["speaker_count_mode"] == "auto"
    assert diarized[0].mapping.metadata["selected_speaker_count"] == 2


def test_resemblyzer_backend_auto_keeps_single_speaker_when_embeddings_are_close(
    tmp_path: Path,
) -> None:
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"wav")

    def wav_loader(path: str):
        return np.ones(64000, dtype=np.float32)

    backend = ResemblyzerDiarizationBackend(
        encoder=SequenceVoiceEncoder(
            [
                [1.0, 0.0],
                [0.99, 0.01],
                [0.98, 0.02],
                [0.97, 0.03],
            ]
        ),
        wav_loader=wav_loader,
        sample_rate=16000,
        num_speakers="auto",
    )

    diarized = backend.diarize(
        str(wav_path),
        [
            TranscriptSegment(
                segment_id=f"seg-{index:04d}",
                start_seconds=float(index),
                end_seconds=float(index + 1),
                text_raw="текст",
                text_clean="текст",
            )
            for index in range(4)
        ],
    )

    labels = [segment.speaker_label for segment in diarized]

    assert labels == ["SPEAKER_00", "SPEAKER_00", "SPEAKER_00", "SPEAKER_00"]
    assert diarized[0].mapping is not None
    assert diarized[0].mapping.metadata["selected_speaker_count"] == 1


def test_is_resemblyzer_available_returns_false_when_import_fails(monkeypatch) -> None:
    original_import_module = import_module
    is_resemblyzer_available.cache_clear()

    def fake_import_module(module_name: str):
        if module_name == "resemblyzer":
            raise ModuleNotFoundError(module_name)
        return original_import_module(module_name)

    monkeypatch.setattr(
        "transcribe_doc.diarization.resemblyzer_backend.import_module",
        fake_import_module,
    )

    assert is_resemblyzer_available() is False

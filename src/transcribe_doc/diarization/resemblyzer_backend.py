"""Embedding-based local diarization backend powered by Resemblyzer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from importlib import import_module
from typing import Any, Callable, List, Optional

import numpy as np

from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment
from transcribe_doc.diarization.base import DiarizationBackend


_MIN_AUTO_SPEAKER_SCORE = 0.22
_AUTO_TINY_CLUSTER_PENALTY = 0.10
_MIN_AUTO_PAIRWISE_DISTANCE = 0.08


@dataclass(frozen=True)
class _SpeakerCountSelection:
    labels: np.ndarray
    selected_count: int
    score: float | None
    mode: str


class ResemblyzerDiarizationBackend(DiarizationBackend):
    """Cluster segment-level speaker embeddings into stable local labels."""

    def __init__(
        self,
        *,
        encoder: Any = None,
        wav_loader: Optional[Callable[[str], np.ndarray]] = None,
        clusterer: Any = None,
        sample_rate: int = 16000,
        num_speakers: int | str = 2,
        max_auto_speakers: int = 6,
    ) -> None:
        self._encoder = encoder
        self._sample_rate = sample_rate
        self._auto_detect_speakers = num_speakers == "auto"
        self._num_speakers = 1 if self._auto_detect_speakers else max(1, int(num_speakers))
        self._max_auto_speakers = max(2, max_auto_speakers)
        self._wav_loader = wav_loader or (
            lambda media_path: _default_wav_loader(media_path, sample_rate=self._sample_rate)
        )
        self._clusterer = clusterer

    @property
    def speaker_count_mode(self) -> str:
        return "auto" if self._auto_detect_speakers else "fixed"

    def diarize(self, media_path: str, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        if len(segments) < 2:
            return [
                replace(
                    segment,
                    speaker_label="SPEAKER_00",
                    mapping=SpeakerMapping(
                        machine_label="SPEAKER_00",
                        display_label="SPEAKER_00",
                        confidence=0.75,
                    ),
                )
                for segment in segments
            ]

        wav = self._wav_loader(media_path)
        encoder = self._encoder or _default_encoder()

        embeddings = []
        wav_slice_lengths = []
        for segment in segments:
            wav_slice = _extract_wav_slice(
                wav,
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                sample_rate=self._sample_rate,
            )
            prepared_slice = _prepare_wav_slice_for_embedding(
                wav_slice,
                sample_rate=self._sample_rate,
            )
            embeddings.append(encoder.embed_utterance(prepared_slice))
            wav_slice_lengths.append(len(wav_slice))

        embeddings_array = np.asarray(embeddings, dtype=float)
        selection = self._select_speaker_count(embeddings_array)
        labels = selection.labels
        cluster_metrics = _build_cluster_metrics(embeddings_array, labels)
        diarized_segments: List[TranscriptSegment] = []
        for segment, cluster_label, wav_slice_length, quality_metrics in zip(
            segments,
            labels,
            wav_slice_lengths,
            cluster_metrics,
        ):
            cluster_label_int = int(cluster_label)
            machine_label = f"SPEAKER_{int(cluster_label):02d}"
            metadata = {
                "backend": "resemblyzer",
                "cluster_label": cluster_label_int,
                "segment_duration_seconds": round(
                    segment.end_seconds - segment.start_seconds,
                    4,
                ),
                "wav_slice_samples": wav_slice_length,
                **quality_metrics,
            }
            if selection.mode == "auto":
                metadata.update(
                    {
                        "speaker_count_mode": "auto",
                        "selected_speaker_count": selection.selected_count,
                        "speaker_count_score": (
                            round(selection.score, 4) if selection.score is not None else None
                        ),
                    }
                )
            diarized_segments.append(
                replace(
                    segment,
                    speaker_label=machine_label,
                    mapping=SpeakerMapping(
                        machine_label=machine_label,
                        display_label=machine_label,
                        confidence=0.75,
                        metadata=metadata,
                    ),
                )
            )
        return diarized_segments

    def _select_speaker_count(self, embeddings: np.ndarray) -> _SpeakerCountSelection:
        if self._clusterer is not None:
            labels = np.asarray(self._clusterer.fit_predict(embeddings), dtype=int)
            return _SpeakerCountSelection(
                labels=labels,
                selected_count=len(set(labels.tolist())),
                score=None,
                mode="fixed",
            )

        if not self._auto_detect_speakers:
            if self._num_speakers == 1:
                labels = np.zeros(len(embeddings), dtype=int)
            else:
                cluster_count = min(self._num_speakers, len(embeddings))
                labels = np.asarray(_default_clusterer(cluster_count).fit_predict(embeddings), dtype=int)
            return _SpeakerCountSelection(
                labels=labels,
                selected_count=len(set(labels.tolist())),
                score=None,
                mode="fixed",
            )

        return _detect_speaker_count(embeddings, max_speakers=self._max_auto_speakers)


@lru_cache(maxsize=1)
def is_resemblyzer_available() -> bool:
    """Return whether the optional diarization dependency can be imported."""
    try:
        import_module("resemblyzer")
        import_module("sklearn.cluster")
    except ModuleNotFoundError:
        return False
    return True


def _default_wav_loader(media_path: str, *, sample_rate: int) -> np.ndarray:
    librosa_module = import_module("librosa")
    wav, _ = librosa_module.load(media_path, sr=sample_rate, mono=True)
    return np.asarray(wav, dtype=np.float32)


def _default_encoder() -> Any:
    resemblyzer_module = import_module("resemblyzer")
    return resemblyzer_module.VoiceEncoder()


def _default_clusterer(num_speakers: int) -> Any:
    sklearn_cluster = import_module("sklearn.cluster")
    return sklearn_cluster.AgglomerativeClustering(n_clusters=num_speakers)


def _detect_speaker_count(embeddings: np.ndarray, *, max_speakers: int) -> _SpeakerCountSelection:
    normalized_embeddings = np.asarray([_normalize_vector(row) for row in embeddings], dtype=float)
    sample_count = len(normalized_embeddings)
    if sample_count < 2:
        return _SpeakerCountSelection(
            labels=np.zeros(sample_count, dtype=int),
            selected_count=1,
            score=None,
            mode="auto",
        )

    max_pairwise_distance = _max_pairwise_cosine_distance(normalized_embeddings)
    if max_pairwise_distance < _MIN_AUTO_PAIRWISE_DISTANCE:
        return _SpeakerCountSelection(
            labels=np.zeros(sample_count, dtype=int),
            selected_count=1,
            score=max_pairwise_distance,
            mode="auto",
        )

    best_labels = np.zeros(sample_count, dtype=int)
    best_count = 1
    best_score: float | None = None
    max_cluster_count = min(max_speakers, sample_count - 1)
    if max_cluster_count < 2:
        similarity = _cosine_similarity(normalized_embeddings[0], normalized_embeddings[1])
        labels = np.array([0, 1], dtype=int) if similarity < 0.72 else best_labels
        return _SpeakerCountSelection(
            labels=labels,
            selected_count=len(set(labels.tolist())),
            score=round(1.0 - similarity, 4),
            mode="auto",
        )

    sklearn_metrics = import_module("sklearn.metrics")
    for cluster_count in range(2, max_cluster_count + 1):
        labels = np.asarray(_default_clusterer(cluster_count).fit_predict(normalized_embeddings), dtype=int)
        unique_labels = set(labels.tolist())
        if len(unique_labels) < 2:
            continue

        score = float(
            sklearn_metrics.silhouette_score(
                normalized_embeddings,
                labels,
                metric="cosine",
            )
        )
        smallest_cluster = min(int(np.sum(labels == label)) for label in unique_labels)
        if smallest_cluster / sample_count < 0.15:
            score -= _AUTO_TINY_CLUSTER_PENALTY

        if best_score is None or score > best_score:
            best_labels = labels
            best_count = cluster_count
            best_score = score

    if best_score is None or best_score < _MIN_AUTO_SPEAKER_SCORE:
        return _SpeakerCountSelection(
            labels=np.zeros(sample_count, dtype=int),
            selected_count=1,
            score=best_score,
            mode="auto",
        )
    return _SpeakerCountSelection(
        labels=best_labels,
        selected_count=best_count,
        score=best_score,
        mode="auto",
    )


def _extract_wav_slice(
    wav: np.ndarray,
    *,
    start_seconds: float,
    end_seconds: float,
    sample_rate: int,
) -> np.ndarray:
    wav_length = len(wav)
    if wav_length == 0:
        return np.zeros(1, dtype=np.float32)

    start_index = max(0, min(int(start_seconds * sample_rate), wav_length - 1))
    end_index = max(start_index + 1, min(int(end_seconds * sample_rate), wav_length))
    return np.asarray(wav[start_index:end_index], dtype=np.float32)


def _prepare_wav_slice_for_embedding(wav_slice: np.ndarray, *, sample_rate: int) -> np.ndarray:
    resemblyzer_module = import_module("resemblyzer")
    prepared_slice = resemblyzer_module.preprocess_wav(wav_slice, source_sr=sample_rate)
    if len(prepared_slice) == 0:
        return np.asarray(wav_slice, dtype=np.float32)
    return np.asarray(prepared_slice, dtype=np.float32)


def _build_cluster_metrics(embeddings: np.ndarray, labels: np.ndarray) -> list[dict[str, Any]]:
    normalized_embeddings = np.asarray([_normalize_vector(row) for row in embeddings], dtype=float)
    unique_labels = sorted({int(label) for label in labels})
    centroids = {
        label: _normalize_vector(normalized_embeddings[labels == label].mean(axis=0))
        for label in unique_labels
    }
    cluster_sizes = {label: int(np.sum(labels == label)) for label in unique_labels}

    metrics: list[dict[str, Any]] = []
    for embedding, label in zip(normalized_embeddings, labels):
        label_int = int(label)
        similarities = {
            centroid_label: _cosine_similarity(embedding, centroid)
            for centroid_label, centroid in centroids.items()
        }
        assigned_similarity = similarities[label_int]
        alternative_similarities = [
            similarity
            for centroid_label, similarity in similarities.items()
            if centroid_label != label_int
        ]
        nearest_alternative_similarity = (
            max(alternative_similarities) if alternative_similarities else None
        )
        centroid_similarity_margin = (
            round(assigned_similarity - nearest_alternative_similarity, 4)
            if nearest_alternative_similarity is not None
            else None
        )
        metrics.append(
            {
                "cluster_size": cluster_sizes[label_int],
                "detected_cluster_count": len(unique_labels),
                "assigned_centroid_similarity": round(assigned_similarity, 4),
                "nearest_alternative_similarity": (
                    round(nearest_alternative_similarity, 4)
                    if nearest_alternative_similarity is not None
                    else None
                ),
                "centroid_similarity_margin": centroid_similarity_margin,
            }
        )
    return metrics


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector.astype(float)
    return vector.astype(float) / norm


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.dot(left, right))


def _max_pairwise_cosine_distance(embeddings: np.ndarray) -> float:
    max_distance = 0.0
    for left_index in range(len(embeddings)):
        for right_index in range(left_index + 1, len(embeddings)):
            similarity = _cosine_similarity(embeddings[left_index], embeddings[right_index])
            max_distance = max(max_distance, 1.0 - similarity)
    return max_distance

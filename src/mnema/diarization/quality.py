"""Helpers for summarizing and warning on diarization quality signals."""

from __future__ import annotations

from typing import Any, List

from mnema.app.models import TranscriptSegment

MIN_DIARIZATION_MARGIN_WARNING = 0.1
MIN_DIARIZATION_CLUSTER_IMBALANCE_WARNING = 0.8
MIN_SEGMENTS_FOR_CLUSTER_IMBALANCE_WARNING = 4
DIARIZATION_CONFIDENCE_VERSION = 1


def collect_diarization_quality_summary(
    segments: List[TranscriptSegment],
) -> dict[str, Any] | None:
    rows = _resemblyzer_rows(segments)
    if not rows:
        return None

    segment_count = len(rows)
    margins = [row["centroid_similarity_margin"] for row in rows if row["centroid_similarity_margin"] is not None]
    assigned_similarities = [
        row["assigned_centroid_similarity"]
        for row in rows
        if row["assigned_centroid_similarity"] is not None
    ]
    alternative_similarities = [
        row["nearest_alternative_similarity"]
        for row in rows
        if row["nearest_alternative_similarity"] is not None
    ]
    cluster_sizes = [row["cluster_size"] for row in rows if row["cluster_size"] is not None]
    detected_cluster_counts = [
        row["detected_cluster_count"]
        for row in rows
        if row["detected_cluster_count"] is not None
    ]

    return {
        "backend": "resemblyzer",
        "segment_count": segment_count,
        "detected_cluster_count_max": max(detected_cluster_counts) if detected_cluster_counts else None,
        "min_centroid_similarity_margin": _rounded(min(margins)) if margins else None,
        "avg_centroid_similarity_margin": _rounded(sum(margins) / len(margins)) if margins else None,
        "min_assigned_centroid_similarity": (
            _rounded(min(assigned_similarities)) if assigned_similarities else None
        ),
        "max_nearest_alternative_similarity": (
            _rounded(max(alternative_similarities)) if alternative_similarities else None
        ),
        "dominant_cluster_share": (
            _rounded(max(cluster_sizes) / segment_count) if cluster_sizes else None
        ),
    }


def build_diarization_confidence(summary: dict[str, Any]) -> dict[str, Any]:
    """Classify Resemblyzer labels using the calibrated conservative gate."""
    detected_cluster_count = summary.get("detected_cluster_count_max")
    min_margin = summary.get("min_centroid_similarity_margin")
    dominant_cluster_share = summary.get("dominant_cluster_share")
    segment_count = summary.get("segment_count")
    reason_codes: list[str] = []

    if not isinstance(detected_cluster_count, int) or detected_cluster_count < 2:
        reason_codes.append("fewer_than_two_clusters")
    if not isinstance(min_margin, (int, float)) or min_margin < MIN_DIARIZATION_MARGIN_WARNING:
        reason_codes.append("low_cluster_separation")
    if (
        isinstance(segment_count, int)
        and segment_count >= MIN_SEGMENTS_FOR_CLUSTER_IMBALANCE_WARNING
        and isinstance(dominant_cluster_share, (int, float))
        and dominant_cluster_share >= MIN_DIARIZATION_CLUSTER_IMBALANCE_WARNING
    ):
        reason_codes.append("imbalanced_clusters")

    return {
        "version": DIARIZATION_CONFIDENCE_VERSION,
        "mode": "transcript_without_labels" if reason_codes else "reliable_labels",
        "reason_codes": reason_codes,
        "metrics": {
            "detected_cluster_count": detected_cluster_count,
            "min_centroid_margin": min_margin,
            "dominant_cluster_share": dominant_cluster_share,
        },
        "thresholds": {
            "min_centroid_margin": MIN_DIARIZATION_MARGIN_WARNING,
            "max_dominant_cluster_share": MIN_DIARIZATION_CLUSTER_IMBALANCE_WARNING,
            "min_segments_for_imbalance": MIN_SEGMENTS_FOR_CLUSTER_IMBALANCE_WARNING,
        },
    }


def collect_diarization_quality_warnings(segments: List[TranscriptSegment]) -> List[str]:
    warnings: List[str] = []
    summary = collect_diarization_quality_summary(segments)
    if summary is None:
        return warnings

    min_margin = summary.get("min_centroid_similarity_margin")
    if isinstance(min_margin, (int, float)) and min_margin < MIN_DIARIZATION_MARGIN_WARNING:
        warnings.append(
            "Diarization quality warning: low cluster separation "
            f"(min centroid margin={min_margin:.2f})."
        )

    detected_cluster_count = summary.get("detected_cluster_count_max")
    if isinstance(detected_cluster_count, int) and detected_cluster_count < 2:
        warnings.append(
            "Diarization quality warning: embedding diarization detected fewer than 2 clusters."
        )

    dominant_cluster_share = summary.get("dominant_cluster_share")
    segment_count = summary.get("segment_count")
    if (
        isinstance(detected_cluster_count, int)
        and detected_cluster_count >= 2
        and isinstance(segment_count, int)
        and segment_count >= MIN_SEGMENTS_FOR_CLUSTER_IMBALANCE_WARNING
        and isinstance(dominant_cluster_share, (int, float))
        and dominant_cluster_share >= MIN_DIARIZATION_CLUSTER_IMBALANCE_WARNING
    ):
        warnings.append(
            "Diarization quality warning: imbalanced speaker clusters "
            f"(dominant cluster share={dominant_cluster_share:.2f})."
        )

    return warnings


def _resemblyzer_rows(segments: List[TranscriptSegment]) -> List[dict[str, Any]]:
    rows: List[dict[str, Any]] = []
    for segment in segments:
        metadata = segment.mapping.metadata if segment.mapping is not None else {}
        if metadata.get("backend") != "resemblyzer":
            continue
        rows.append(
            {
                "cluster_size": _optional_int(metadata.get("cluster_size")),
                "detected_cluster_count": _optional_int(metadata.get("detected_cluster_count")),
                "assigned_centroid_similarity": _optional_float(
                    metadata.get("assigned_centroid_similarity")
                ),
                "nearest_alternative_similarity": _optional_float(
                    metadata.get("nearest_alternative_similarity")
                ),
                "centroid_similarity_margin": _optional_float(
                    metadata.get("centroid_similarity_margin")
                ),
            }
        )
    return rows


def _optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _rounded(value: float) -> float:
    return round(value, 2)

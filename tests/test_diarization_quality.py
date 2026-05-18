from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment
from transcribe_doc.diarization.quality import collect_diarization_quality_summary


def test_collect_diarization_quality_summary_aggregates_resemblyzer_metrics() -> None:
    summary = collect_diarization_quality_summary(
        [
            TranscriptSegment(
                segment_id="seg-001",
                start_seconds=0.0,
                end_seconds=1.0,
                text_raw="привет",
                text_clean="привет",
                speaker_label="SPEAKER_00",
                mapping=SpeakerMapping(
                    machine_label="SPEAKER_00",
                    display_label="SPEAKER_00",
                    confidence=0.75,
                    metadata={
                        "backend": "resemblyzer",
                        "cluster_label": 0,
                        "cluster_size": 3,
                        "detected_cluster_count": 2,
                        "assigned_centroid_similarity": 0.92,
                        "nearest_alternative_similarity": 0.71,
                        "centroid_similarity_margin": 0.21,
                    },
                ),
            ),
            TranscriptSegment(
                segment_id="seg-002",
                start_seconds=1.1,
                end_seconds=2.0,
                text_raw="здравствуйте",
                text_clean="здравствуйте",
                speaker_label="SPEAKER_00",
                mapping=SpeakerMapping(
                    machine_label="SPEAKER_00",
                    display_label="SPEAKER_00",
                    confidence=0.75,
                    metadata={
                        "backend": "resemblyzer",
                        "cluster_label": 0,
                        "cluster_size": 3,
                        "detected_cluster_count": 2,
                        "assigned_centroid_similarity": 0.91,
                        "nearest_alternative_similarity": 0.70,
                        "centroid_similarity_margin": 0.21,
                    },
                ),
            ),
            TranscriptSegment(
                segment_id="seg-003",
                start_seconds=2.1,
                end_seconds=3.0,
                text_raw="реплика",
                text_clean="реплика",
                speaker_label="SPEAKER_00",
                mapping=SpeakerMapping(
                    machine_label="SPEAKER_00",
                    display_label="SPEAKER_00",
                    confidence=0.75,
                    metadata={
                        "backend": "resemblyzer",
                        "cluster_label": 0,
                        "cluster_size": 3,
                        "detected_cluster_count": 2,
                        "assigned_centroid_similarity": 0.93,
                        "nearest_alternative_similarity": 0.74,
                        "centroid_similarity_margin": 0.19,
                    },
                ),
            ),
            TranscriptSegment(
                segment_id="seg-004",
                start_seconds=1.1,
                end_seconds=2.0,
                text_raw="здравствуйте",
                text_clean="здравствуйте",
                speaker_label="SPEAKER_01",
                mapping=SpeakerMapping(
                    machine_label="SPEAKER_01",
                    display_label="SPEAKER_01",
                    confidence=0.75,
                    metadata={
                        "backend": "resemblyzer",
                        "cluster_label": 1,
                        "cluster_size": 1,
                        "detected_cluster_count": 2,
                        "assigned_centroid_similarity": 0.88,
                        "nearest_alternative_similarity": 0.81,
                        "centroid_similarity_margin": 0.07,
                    },
                ),
            ),
        ]
    )

    assert summary == {
        "backend": "resemblyzer",
        "segment_count": 4,
        "detected_cluster_count_max": 2,
        "min_centroid_similarity_margin": 0.07,
        "avg_centroid_similarity_margin": 0.17,
        "min_assigned_centroid_similarity": 0.88,
        "max_nearest_alternative_similarity": 0.81,
        "dominant_cluster_share": 0.75,
    }


def test_collect_diarization_quality_summary_returns_none_without_resemblyzer_metadata() -> None:
    summary = collect_diarization_quality_summary(
        [
            TranscriptSegment(
                segment_id="seg-001",
                start_seconds=0.0,
                end_seconds=1.0,
                text_raw="привет",
                text_clean="привет",
                speaker_label="SPEAKER_00",
                mapping=SpeakerMapping(
                    machine_label="SPEAKER_00",
                    display_label="SPEAKER_00",
                    confidence=1.0,
                    metadata={"backend": "single_speaker"},
                ),
            )
        ]
    )

    assert summary is None

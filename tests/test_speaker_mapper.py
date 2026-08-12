from mnema.app.models import SpeakerMapping, TranscriptSegment
from mnema.diarization.speaker_mapper import apply_expected_speaker_mapping


def test_apply_expected_speaker_mapping_maps_single_expected_speaker_unambiguously() -> None:
    segments = [
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

    mapped = apply_expected_speaker_mapping(
        segments,
        {
            "expected_speakers": [
                {"name": "Алексей", "role": "Интервьюер"},
            ]
        },
    )

    assert mapped[0].speaker_label == "Алексей"
    assert mapped[0].mapping == SpeakerMapping(
        machine_label="SPEAKER_00",
        display_label="Алексей",
        confidence=1.0,
        metadata={
            "backend": "single_speaker",
            "display_label_source": "expected_speaker_manifest",
        },
    )


def test_apply_expected_speaker_mapping_keeps_machine_label_when_ambiguous() -> None:
    segments = [
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

    mapped = apply_expected_speaker_mapping(
        segments,
        {
            "expected_speakers": [
                {"name": "Алексей"},
                {"name": "Марина"},
            ]
        },
    )

    assert mapped[0].speaker_label == "SPEAKER_00"
    assert mapped[0].mapping == SpeakerMapping(
        machine_label="SPEAKER_00",
        display_label="SPEAKER_00",
        confidence=1.0,
        metadata={"backend": "single_speaker"},
    )


def test_apply_expected_speaker_mapping_maps_multiple_labels_by_order_when_counts_match() -> None:
    segments = [
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
                confidence=0.8,
                metadata={"backend": "resemblyzer", "cluster_label": 0},
            ),
        ),
        TranscriptSegment(
            segment_id="seg-002",
            start_seconds=1.0,
            end_seconds=2.0,
            text_raw="здравствуйте",
            text_clean="здравствуйте",
            speaker_label="SPEAKER_01",
            mapping=SpeakerMapping(
                machine_label="SPEAKER_01",
                display_label="SPEAKER_01",
                confidence=0.8,
                metadata={"backend": "resemblyzer", "cluster_label": 1},
            ),
        ),
    ]

    mapped = apply_expected_speaker_mapping(
        segments,
        {
            "expected_speakers": [
                {"name": "Алексей"},
                {"name": "Марина"},
            ]
        },
    )

    assert mapped[0].speaker_label == "Алексей"
    assert mapped[1].speaker_label == "Марина"
    assert mapped[0].mapping == SpeakerMapping(
        machine_label="SPEAKER_00",
        display_label="Алексей",
        confidence=1.0,
        metadata={
            "backend": "resemblyzer",
            "cluster_label": 0,
            "display_label_source": "expected_speaker_manifest",
        },
    )
    assert mapped[1].mapping == SpeakerMapping(
        machine_label="SPEAKER_01",
        display_label="Марина",
        confidence=1.0,
        metadata={
            "backend": "resemblyzer",
            "cluster_label": 1,
            "display_label_source": "expected_speaker_manifest",
        },
    )

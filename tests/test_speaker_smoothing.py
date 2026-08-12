from mnema.app.models import SpeakerMapping, TranscriptSegment
from mnema.postprocess.speaker_smoothing import smooth_speaker_turns


def _segment(
    segment_id: str,
    speaker: str,
    start: float,
    end: float,
    margin: float,
) -> TranscriptSegment:
    return TranscriptSegment(
        segment_id=segment_id,
        start_seconds=start,
        end_seconds=end,
        text_raw=segment_id,
        text_clean=segment_id,
        speaker_label=speaker,
        mapping=SpeakerMapping(
            machine_label=speaker,
            display_label=speaker,
            confidence=0.75,
            metadata={
                "backend": "resemblyzer",
                "centroid_similarity_margin": margin,
            },
        ),
    )


def test_speaker_smoothing_repairs_short_low_confidence_aba_turn() -> None:
    smoothed = smooth_speaker_turns(
        [
            _segment("seg-001", "SPEAKER_00", 0.0, 2.0, 0.24),
            _segment("seg-002", "SPEAKER_01", 2.0, 2.5, 0.04),
            _segment("seg-003", "SPEAKER_00", 2.5, 4.0, 0.22),
        ]
    )

    assert [segment.speaker_label for segment in smoothed] == [
        "SPEAKER_00",
        "SPEAKER_00",
        "SPEAKER_00",
    ]
    assert smoothed[1].mapping is not None
    assert smoothed[1].mapping.machine_label == "SPEAKER_01"
    assert smoothed[1].mapping.display_label == "SPEAKER_00"
    assert smoothed[1].mapping.metadata["speaker_smoothing_reason"] == "short_low_confidence_aba"


def test_speaker_smoothing_keeps_long_or_confident_turns() -> None:
    long_turn = smooth_speaker_turns(
        [
            _segment("seg-001", "SPEAKER_00", 0.0, 2.0, 0.24),
            _segment("seg-002", "SPEAKER_01", 2.0, 4.2, 0.04),
            _segment("seg-003", "SPEAKER_00", 4.2, 6.0, 0.22),
        ]
    )
    confident_turn = smooth_speaker_turns(
        [
            _segment("seg-001", "SPEAKER_00", 0.0, 2.0, 0.24),
            _segment("seg-002", "SPEAKER_01", 2.0, 2.5, 0.2),
            _segment("seg-003", "SPEAKER_00", 2.5, 4.0, 0.22),
        ]
    )

    assert long_turn[1].speaker_label == "SPEAKER_01"
    assert confident_turn[1].speaker_label == "SPEAKER_01"

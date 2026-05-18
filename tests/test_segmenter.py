from transcribe_doc.app.models import TranscriptSegment, WordToken
from transcribe_doc.postprocess.segmenter import split_segments_on_long_pauses


def test_split_segments_on_long_pauses_splits_single_segment_by_word_gap() -> None:
    segments = [
        TranscriptSegment(
            segment_id="seg-001",
            start_seconds=0.0,
            end_seconds=2.8,
            text_raw="привет как дела",
            text_clean="привет как дела",
            words=[
                WordToken(text="привет", start_seconds=0.0, end_seconds=0.4),
                WordToken(text="как", start_seconds=1.6, end_seconds=1.8),
                WordToken(text="дела", start_seconds=1.9, end_seconds=2.2),
            ],
        )
    ]

    split_segments = split_segments_on_long_pauses(segments, pause_threshold_seconds=0.8)

    assert len(split_segments) == 2
    assert split_segments[0].segment_id == "seg-001-000"
    assert split_segments[0].text_clean == "привет"
    assert split_segments[0].start_seconds == 0.0
    assert split_segments[0].end_seconds == 0.4
    assert split_segments[1].segment_id == "seg-001-001"
    assert split_segments[1].text_clean == "как дела"
    assert [word.text for word in split_segments[1].words] == ["как", "дела"]


def test_split_segments_on_long_pauses_splits_on_sentence_boundary_with_shorter_pause() -> None:
    segments = [
        TranscriptSegment(
            segment_id="seg-002",
            start_seconds=0.0,
            end_seconds=3.4,
            text_raw="Здравствуйте! Меня зовут Алексей. Меня зовут Марина.",
            text_clean="Здравствуйте! Меня зовут Алексей. Меня зовут Марина.",
            words=[
                WordToken(text="Здравствуйте!", start_seconds=0.0, end_seconds=0.7),
                WordToken(text="Меня", start_seconds=1.0, end_seconds=1.2),
                WordToken(text="зовут", start_seconds=1.2, end_seconds=1.5),
                WordToken(text="Алексей.", start_seconds=1.5, end_seconds=2.0),
                WordToken(text="Меня", start_seconds=2.3, end_seconds=2.5),
                WordToken(text="зовут", start_seconds=2.5, end_seconds=2.8),
                WordToken(text="Марина.", start_seconds=2.8, end_seconds=3.4),
            ],
        )
    ]

    split_segments = split_segments_on_long_pauses(segments, pause_threshold_seconds=0.8)

    assert len(split_segments) == 2
    assert split_segments[0].text_clean == "Здравствуйте! Меня зовут Алексей."
    assert split_segments[1].text_clean == "Меня зовут Марина."

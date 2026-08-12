from mnema.app.models import TranscriptSegment, WordToken
from mnema.postprocess.word_quality import apply_word_quality_checks


def test_word_quality_marks_repeats_domain_terms_and_suspicious_words() -> None:
    segment = TranscriptSegment(
        segment_id="seg-001",
        start_seconds=0.0,
        end_seconds=2.0,
        text_raw="привет привет crm шрекслово",
        text_clean="привет привет crm шрекслово",
        words=[
            WordToken(text="привет", start_seconds=0.0, end_seconds=0.3),
            WordToken(text="привет", start_seconds=0.4, end_seconds=0.7),
            WordToken(text="crm", start_seconds=0.8, end_seconds=1.0),
            WordToken(text="шрекслово", start_seconds=1.1, end_seconds=1.6),
        ],
    )

    checked = apply_word_quality_checks([segment])

    words = checked[0].words
    assert words[1].issues[0]["code"] == "repeated_word"
    assert words[2].text_clean == "CRM"
    assert words[2].issues[0]["code"] == "domain_term"
    assert words[3].issues[0]["code"] == "unknown_word"
    assert checked[0].text_raw == "привет привет crm шрекслово"


def test_word_quality_keeps_old_segments_without_words_compatible() -> None:
    segment = TranscriptSegment(
        segment_id="seg-001",
        start_seconds=0.0,
        end_seconds=1.0,
        text_raw="ну  привет",
        text_clean="ну  привет",
    )

    checked = apply_word_quality_checks([segment])

    assert checked[0].words == []
    assert checked[0].text_clean == "ну  привет"

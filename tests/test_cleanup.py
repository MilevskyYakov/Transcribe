from transcribe_doc.app.models import TranscriptSegment
from transcribe_doc.postprocess.transcript_cleaner import apply_conservative_cleanup


def test_apply_conservative_cleanup_normalizes_spacing_without_rewriting_text() -> None:
    segment = TranscriptSegment(
        segment_id="seg-001",
        start_seconds=0.0,
        end_seconds=1.0,
        text_raw="  ну   привет  ",
        text_clean="  ну   привет  ",
        speaker_label="SPEAKER_00",
    )

    cleaned = apply_conservative_cleanup([segment])

    assert cleaned[0].text_raw == "  ну   привет  "
    assert cleaned[0].text_clean == "Ну привет."


def test_apply_conservative_cleanup_polishes_punctuation_and_repeated_words() -> None:
    segment = TranscriptSegment(
        segment_id="seg-001",
        start_seconds=0.0,
        end_seconds=1.0,
        text_raw="привет привет , как дела",
        text_clean="привет привет , как дела",
        speaker_label="SPEAKER_00",
    )

    cleaned = apply_conservative_cleanup([segment])

    assert cleaned[0].text_raw == "привет привет , как дела"
    assert cleaned[0].text_clean == "Привет, как дела."

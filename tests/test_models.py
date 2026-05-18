from transcribe_doc.app.models import (
    ArtifactManifest,
    Job,
    JobStatus,
    SpeakerMapping,
    TranscriptSegment,
    WordToken,
)


def test_job_defaults_to_queued_with_empty_artifacts() -> None:
    job = Job(job_id="job-001", source_paths=["sample.mp3"])

    assert job.status is JobStatus.QUEUED
    assert job.artifacts == ArtifactManifest()
    assert job.warnings == []


def test_transcript_segment_keeps_raw_and_clean_text() -> None:
    segment = TranscriptSegment(
        segment_id="seg-001",
        start_seconds=0.0,
        end_seconds=1.2,
        text_raw="ну привет",
        text_clean="Ну привет.",
        speaker_label="SPEAKER_00",
        words=[
            WordToken(text="ну", start_seconds=0.0, end_seconds=0.2),
            WordToken(text="привет", start_seconds=0.3, end_seconds=0.8),
        ],
        mapping=SpeakerMapping(machine_label="SPEAKER_00", display_label="Алексей", confidence=0.82),
    )

    assert segment.text_raw == "ну привет"
    assert segment.text_clean == "Ну привет."
    assert segment.mapping.display_label == "Алексей"
    assert len(segment.words) == 2

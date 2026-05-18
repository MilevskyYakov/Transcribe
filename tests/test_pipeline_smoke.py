from transcribe_doc.alignment.base import AlignmentBackend
from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment, WordToken
from transcribe_doc.asr.base import AsrBackend, AsrTranscription
from transcribe_doc.asr.transcription_service import TranscriptionService
from transcribe_doc.diarization.base import DiarizationBackend
from transcribe_doc.diarization.heuristic_multi_speaker_backend import (
    HeuristicMultiSpeakerDiarizationBackend,
)
from transcribe_doc.diarization.single_speaker_backend import SingleSpeakerDiarizationBackend


class FakeAsrBackend(AsrBackend):
    name = "fake-asr"

    def transcribe(self, media_path: str):
        return AsrTranscription(
            segments=[
                TranscriptSegment(
                    segment_id="seg-001",
                    start_seconds=0.0,
                    end_seconds=1.0,
                    text_raw="  ну   привет  ",
                    text_clean="  ну   привет  ",
                )
            ],
            detected_language="ru",
        )


class FakeAlignmentBackend(AlignmentBackend):
    def align(self, segments):
        return [
            TranscriptSegment(
                segment_id=segments[0].segment_id,
                start_seconds=0.1,
                end_seconds=1.1,
                text_raw=segments[0].text_raw,
                text_clean=segments[0].text_clean,
                speaker_label=segments[0].speaker_label,
                words=segments[0].words,
                mapping=segments[0].mapping,
            )
        ]


class FakeFailingAlignmentBackend(AlignmentBackend):
    def align(self, segments):
        raise RuntimeError("alignment backend unavailable")


class FakeDiarizationBackend(DiarizationBackend):
    def diarize(self, media_path: str, segments):
        return [
            TranscriptSegment(
                segment_id=segments[0].segment_id,
                start_seconds=segments[0].start_seconds,
                end_seconds=segments[0].end_seconds,
                text_raw=segments[0].text_raw,
                text_clean=segments[0].text_clean,
                speaker_label="SPEAKER_00",
                words=segments[0].words,
                mapping=segments[0].mapping,
            )
        ]


class FakeLowQualityDiarizationBackend(DiarizationBackend):
    def diarize(self, media_path: str, segments):
        return [
            TranscriptSegment(
                segment_id=segments[0].segment_id,
                start_seconds=segments[0].start_seconds,
                end_seconds=segments[0].end_seconds,
                text_raw=segments[0].text_raw,
                text_clean=segments[0].text_clean,
                speaker_label="SPEAKER_00",
                words=segments[0].words,
                mapping=SpeakerMapping(
                    machine_label="SPEAKER_00",
                    display_label="SPEAKER_00",
                    confidence=0.75,
                    metadata={
                        "backend": "resemblyzer",
                        "cluster_label": 0,
                        "cluster_size": 1,
                        "detected_cluster_count": 2,
                        "assigned_centroid_similarity": 0.82,
                        "nearest_alternative_similarity": 0.77,
                        "centroid_similarity_margin": 0.05,
                    },
                ),
            )
        ]


class FakeImbalancedDiarizationBackend(DiarizationBackend):
    def diarize(self, media_path: str, segments):
        diarized = []
        labels = ["SPEAKER_00", "SPEAKER_00", "SPEAKER_00", "SPEAKER_00", "SPEAKER_01"]
        cluster_sizes = [4, 4, 4, 4, 1]
        for index, segment in enumerate(segments):
            diarized.append(
                TranscriptSegment(
                    segment_id=segment.segment_id,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    text_raw=segment.text_raw,
                    text_clean=segment.text_clean,
                    speaker_label=labels[index],
                    words=segment.words,
                    mapping=SpeakerMapping(
                        machine_label=labels[index],
                        display_label=labels[index],
                        confidence=0.75,
                        metadata={
                            "backend": "resemblyzer",
                            "cluster_label": 0 if labels[index] == "SPEAKER_00" else 1,
                            "cluster_size": cluster_sizes[index],
                            "detected_cluster_count": 2,
                            "assigned_centroid_similarity": 0.96,
                            "nearest_alternative_similarity": 0.72,
                            "centroid_similarity_margin": 0.24,
                        },
                    ),
                )
            )
        return diarized


def test_transcription_service_applies_alignment_diarization_and_cleanup() -> None:
    service = TranscriptionService(
        asr_backend=FakeAsrBackend(),
        alignment_backend=FakeAlignmentBackend(),
        diarization_backend=FakeDiarizationBackend(),
    )

    result = service.transcribe("sample.mp3")

    assert result.warnings == []
    assert result.detected_language == "ru"
    assert result.segments[0].start_seconds == 0.1
    assert result.segments[0].speaker_label == "SPEAKER_00"
    assert result.segments[0].text_clean == "Ну привет."


def test_transcription_service_degrades_gracefully_when_alignment_fails() -> None:
    service = TranscriptionService(
        asr_backend=FakeAsrBackend(),
        alignment_backend=FakeFailingAlignmentBackend(),
    )

    result = service.transcribe("sample.mp3")

    assert len(result.warnings) == 1
    assert "alignment" in result.warnings[0].lower()
    assert result.segments[0].start_seconds == 0.0
    assert result.segments[0].text_clean == "Ну привет."


def test_transcription_service_keeps_low_diarization_quality_as_diagnostic_signal() -> None:
    service = TranscriptionService(
        asr_backend=FakeAsrBackend(),
        diarization_backend=FakeLowQualityDiarizationBackend(),
    )

    result = service.transcribe("sample.mp3")

    assert result.warnings == []
    assert result.segments[0].speaker_label == "SPEAKER_00"
    assert result.segments[0].mapping is not None
    assert result.segments[0].mapping.metadata["centroid_similarity_margin"] == 0.05


def test_transcription_service_keeps_imbalanced_diarization_as_diagnostic_signal() -> None:
    class FakeMultiSegmentAsrBackend(AsrBackend):
        name = "fake-asr-multi"

        def transcribe(self, media_path: str):
            return AsrTranscription(
                segments=[
                    TranscriptSegment(
                        segment_id=f"seg-{index:03d}",
                        start_seconds=float(index),
                        end_seconds=float(index) + 0.8,
                        text_raw=f"реплика {index}",
                        text_clean=f"реплика {index}",
                    )
                    for index in range(5)
                ],
                detected_language="ru",
            )

    service = TranscriptionService(
        asr_backend=FakeMultiSegmentAsrBackend(),
        diarization_backend=FakeImbalancedDiarizationBackend(),
    )

    result = service.transcribe("sample.mp3")

    assert result.warnings == []
    assert [segment.speaker_label for segment in result.segments] == [
        "SPEAKER_00",
        "SPEAKER_00",
        "SPEAKER_00",
        "SPEAKER_00",
        "SPEAKER_01",
    ]


def test_single_speaker_diarization_backend_labels_segments_consistently() -> None:
    backend = SingleSpeakerDiarizationBackend()

    diarized = backend.diarize(
        "sample.mp3",
        [
            TranscriptSegment(
                segment_id="seg-001",
                start_seconds=0.0,
                end_seconds=1.0,
                text_raw="привет",
                text_clean="привет",
            )
        ],
    )

    assert diarized[0].speaker_label == "SPEAKER_00"
    assert diarized[0].mapping == SpeakerMapping(
        machine_label="SPEAKER_00",
        display_label="SPEAKER_00",
        confidence=1.0,
        metadata={
            "backend": "single_speaker",
            "strategy": "uniform_label",
        },
    )


def test_heuristic_multi_speaker_backend_alternates_labels_for_multiple_segments() -> None:
    backend = HeuristicMultiSpeakerDiarizationBackend()

    diarized = backend.diarize(
        "sample.mp3",
        [
            TranscriptSegment(
                segment_id="seg-001",
                start_seconds=0.0,
                end_seconds=1.0,
                text_raw="привет",
                text_clean="привет",
            ),
            TranscriptSegment(
                segment_id="seg-002",
                start_seconds=1.1,
                end_seconds=2.0,
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
        confidence=0.6,
        metadata={
            "backend": "heuristic_multi_speaker",
            "strategy": "alternating_index",
            "speaker_index": 0,
        },
    )
    assert diarized[1].mapping == SpeakerMapping(
        machine_label="SPEAKER_01",
        display_label="SPEAKER_01",
        confidence=0.6,
        metadata={
            "backend": "heuristic_multi_speaker",
            "strategy": "alternating_index",
            "speaker_index": 1,
        },
    )


class FakeAsrBackendWithLongPause(AsrBackend):
    name = "fake-asr-long-pause"

    def transcribe(self, media_path: str):
        return AsrTranscription(
            segments=[
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
            ],
            detected_language="ru",
        )


def test_transcription_service_splits_long_pause_before_multi_speaker_diarization() -> None:
    service = TranscriptionService(
        asr_backend=FakeAsrBackendWithLongPause(),
        diarization_backend=HeuristicMultiSpeakerDiarizationBackend(),
    )

    result = service.transcribe("sample.mp3")

    assert [segment.speaker_label for segment in result.segments] == ["SPEAKER_00", "SPEAKER_01"]
    assert [segment.text_clean for segment in result.segments] == ["Привет.", "Как дела."]


class FakeAsrBackendWithQuestionableWords(AsrBackend):
    name = "fake-asr-questionable-words"

    def transcribe(self, media_path: str):
        return AsrTranscription(
            segments=[
                TranscriptSegment(
                    segment_id="seg-001",
                    start_seconds=0.0,
                    end_seconds=1.8,
                    text_raw="привет привет crm",
                    text_clean="привет привет crm",
                    words=[
                        WordToken(text="привет", start_seconds=0.0, end_seconds=0.3),
                        WordToken(text="привет", start_seconds=0.4, end_seconds=0.7),
                        WordToken(text="crm", start_seconds=0.8, end_seconds=1.0),
                    ],
                )
            ],
            detected_language="ru",
        )


def test_transcription_service_applies_word_quality_before_cleanup() -> None:
    service = TranscriptionService(
        asr_backend=FakeAsrBackendWithQuestionableWords(),
        diarization_backend=SingleSpeakerDiarizationBackend(),
    )

    result = service.transcribe("sample.mp3")

    assert result.segments[0].text_raw == "привет привет crm"
    assert result.segments[0].text_clean == "Привет CRM."
    assert result.segments[0].words[1].issues[0]["code"] == "repeated_word"
    assert result.segments[0].words[2].text_clean == "CRM"

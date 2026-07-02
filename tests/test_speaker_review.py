from transcribe_doc.storage.speaker_review import (
    apply_speaker_assignments_to_segment_payloads,
    build_speaker_review_payload,
    update_speaker_assignments,
)


def _segments():
    return [
        {
            "segment_id": "s1",
            "start_seconds": 0,
            "end_seconds": 2,
            "text_raw": "hello",
            "text_clean": "Здравствуйте, это Яков.",
            "speaker_label": "SPEAKER_00",
        },
        {
            "segment_id": "s2",
            "start_seconds": 2,
            "end_seconds": 4,
            "text_raw": "answer",
            "text_clean": "Привет, это Анна.",
            "speaker_label": "SPEAKER_01",
        },
    ]


def test_speaker_review_groups_hide_machine_labels_and_suggest_participants() -> None:
    job = {
        "metadata": {
            "speaker_manifest": {
                "expected_speakers": [{"name": "Яков"}, {"name": "Анна"}],
            }
        }
    }

    payload = build_speaker_review_payload(job, _segments())

    assert payload["status"] == "pending"
    assert payload["suggestions"] == ["Яков", "Анна"]
    assert payload["groups"][0] == {
        "machine_label": "SPEAKER_00",
        "fallback_label": "Спикер 1",
        "display_label": "Спикер 1",
        "example": "Здравствуйте, это Яков.",
        "suggestions": ["Яков", "Анна"],
    }
    assert payload["groups"][1]["fallback_label"] == "Спикер 2"


def test_speaker_assignments_persist_and_relabel_transcript_payloads() -> None:
    job = {"metadata": {}}
    review = update_speaker_assignments(job, _segments(), {"SPEAKER_00": "Яков"})

    assert review["status"] == "confirmed"
    assert job["metadata"]["speaker_assignments"] == {"SPEAKER_00": "Яков"}

    relabeled = apply_speaker_assignments_to_segment_payloads(job, _segments())

    assert relabeled[0]["speaker_label"] == "Яков"
    assert relabeled[1]["speaker_label"] == "Спикер 2"
    assert relabeled[0]["mapping"] == {
        "machine_label": "SPEAKER_00",
        "display_label": "Яков",
    }

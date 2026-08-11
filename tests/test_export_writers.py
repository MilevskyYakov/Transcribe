import json
import zipfile
from pathlib import Path

from transcribe_doc.app.models import SpeakerMapping, TranscriptSegment, WordToken
from transcribe_doc.export.writers import export_all, write_final_text_md, write_srt
from transcribe_doc.summary.extractive import write_summary


def test_export_all_writes_user_formats(tmp_path: Path) -> None:
    segments = [
        TranscriptSegment(
            segment_id="seg-0000",
            start_seconds=0.0,
            end_seconds=1.2,
            text_raw="привет мир",
            text_clean="Привет мир.",
            speaker_label="Алексей",
            words=[WordToken(text="привет", start_seconds=0.0, end_seconds=0.5)],
        )
    ]
    paths = {
        "txt": tmp_path / "transcript_clean.txt",
        "md": tmp_path / "transcript_clean.md",
        "final_text_md": tmp_path / "final_speech_text.md",
        "json": tmp_path / "segments.json",
        "docx": tmp_path / "transcript_clean.docx",
        "pdf": tmp_path / "transcript_clean.pdf",
    }

    written = export_all(segments, paths, title="Созвон с клиентом")

    assert set(written) == set(paths.values())
    assert "Алексей" in paths["txt"].read_text(encoding="utf-8")
    assert "# Созвон с клиентом" in paths["final_text_md"].read_text(encoding="utf-8")
    assert paths["pdf"].read_bytes().startswith(b"%PDF-1.4")
    assert json.loads(paths["json"].read_text(encoding="utf-8"))[0]["segment_id"] == "seg-0000"
    with zipfile.ZipFile(paths["docx"]) as archive:
        assert "word/document.xml" in archive.namelist()


def test_export_json_keeps_word_diagnostics(tmp_path: Path) -> None:
    segments = [
        TranscriptSegment(
            segment_id="seg-0000",
            start_seconds=0.0,
            end_seconds=1.0,
            text_raw="crm",
            text_clean="CRM.",
            words=[
                WordToken(
                    text="crm",
                    text_clean="CRM",
                    start_seconds=0.0,
                    end_seconds=0.5,
                    issues=[
                        {
                            "code": "domain_term",
                            "severity": "info",
                            "message": "Known domain term normalized.",
                        }
                    ],
                )
            ],
        )
    ]
    paths = {"json": tmp_path / "segments.json"}

    export_all(segments, paths)

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload[0]["words"][0]["text_clean"] == "CRM"
    assert payload[0]["words"][0]["issues"][0]["code"] == "domain_term"


def test_srt_export_uses_subtitle_time_format(tmp_path: Path) -> None:
    path = tmp_path / "subtitles.srt"
    write_srt(
        path,
        [
            TranscriptSegment(
                segment_id="seg-0000",
                start_seconds=1.25,
                end_seconds=3.5,
                text_raw="hello",
                text_clean="hello",
                speaker_label="SPEAKER_00",
            )
        ],
    )

    assert "00:00:01,250 --> 00:00:03,500" in path.read_text(encoding="utf-8")


def test_final_markdown_uses_canonical_title_times_and_speaker_labels(tmp_path: Path) -> None:
    path = tmp_path / "final.md"

    write_final_text_md(
        path,
        [
            TranscriptSegment(
                segment_id="seg-0000",
                start_seconds=3.2,
                end_seconds=17.4,
                text_raw="hello",
                text_clean="Привет.",
                speaker_label="SPEAKER_00",
                mapping=SpeakerMapping(
                    machine_label="SPEAKER_00",
                    display_label="Алексей",
                ),
            ),
            TranscriptSegment(
                segment_id="seg-0001",
                start_seconds=17.4,
                end_seconds=42.0,
                text_raw="raw text",
                text_clean="Чистый текст.",
                speaker_label="SPEAKER_01",
            ),
        ],
        title="Название транскрипции",
    )

    content = path.read_text(encoding="utf-8")
    assert content.startswith("# Название транскрипции\n\n## Транскрипция")
    assert "[00:00:03–00:00:17] Алексей: Привет." in content
    assert "[00:00:17–00:00:42] Спикер 2: Чистый текст." in content
    assert "SPEAKER_00" not in content
    assert "SPEAKER_01" not in content


def test_final_markdown_omits_speaker_placeholder_for_unlabeled_transcript(tmp_path: Path) -> None:
    path = tmp_path / "final.md"

    write_final_text_md(
        path,
        [
            TranscriptSegment(
                segment_id="seg-0000",
                start_seconds=3.2,
                end_seconds=17.4,
                text_raw="hello",
                text_clean="Привет.",
            )
        ],
        title="Запись",
    )

    assert "[00:00:03–00:00:17] Привет." in path.read_text(encoding="utf-8")


def test_summary_writes_markdown_and_json(tmp_path: Path) -> None:
    segments = [
        TranscriptSegment(
            segment_id="seg-0000",
            start_seconds=0.0,
            end_seconds=2.0,
            text_raw="hello",
            text_clean="hello",
            speaker_label="SPEAKER_00",
        )
    ]

    write_summary(segments, tmp_path / "summary.md", tmp_path / "summary.json")

    assert "# Summary" in (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))["segment_count"] == 1

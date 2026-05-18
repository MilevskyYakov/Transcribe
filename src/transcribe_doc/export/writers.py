"""Concrete local transcript exporters."""

from __future__ import annotations

import json
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from transcribe_doc.app.models import TranscriptSegment


def export_all(segments: list[TranscriptSegment], output_paths: dict[str, Path]) -> list[Path]:
    """Write all requested transcript formats."""
    written: list[Path] = []
    if path := output_paths.get("txt"):
        written.append(write_txt(path, segments))
    if path := output_paths.get("md"):
        written.append(write_md(path, segments))
    if path := output_paths.get("final_text_md"):
        written.append(write_final_text_md(path, segments))
    if path := output_paths.get("srt"):
        written.append(write_srt(path, segments))
    if path := output_paths.get("json"):
        written.append(write_json(path, segments))
    if path := output_paths.get("docx"):
        written.append(write_docx(path, segments))
    if path := output_paths.get("pdf"):
        written.append(write_pdf(path, segments))
    return written


def write_txt(path: Path, segments: Iterable[TranscriptSegment]) -> Path:
    lines = [_format_plain_segment(segment) for segment in segments]
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def write_md(path: Path, segments: Iterable[TranscriptSegment]) -> Path:
    lines = ["# Transcript", ""]
    for segment in segments:
        lines.append(
            f"**{_speaker(segment)}** "
            f"`{_format_time(segment.start_seconds)}-{_format_time(segment.end_seconds)}`"
        )
        lines.append("")
        lines.append(segment.text_clean or segment.text_raw)
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def write_final_text_md(path: Path, segments: Iterable[TranscriptSegment]) -> Path:
    lines = ["# Готовый текст", ""]
    for segment in segments:
        lines.append(
            f"**{_speaker(segment)}** "
            f"`{_format_time(segment.start_seconds)}-{_format_time(segment.end_seconds)}`"
        )
        lines.append("")
        lines.append(segment.text_clean or segment.text_raw)
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def write_srt(path: Path, segments: Iterable[TranscriptSegment]) -> Path:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_srt_time(segment.start_seconds)} --> {_format_srt_time(segment.end_seconds)}",
                    f"{_speaker(segment)}: {segment.text_clean or segment.text_raw}",
                ]
            )
        )
    path.write_text("\n\n".join(blocks).strip() + "\n", encoding="utf-8")
    return path


def write_json(path: Path, segments: Iterable[TranscriptSegment]) -> Path:
    payload = [asdict(segment) for segment in segments]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_docx(path: Path, segments: Iterable[TranscriptSegment]) -> Path:
    paragraphs = "".join(
        f"<w:p><w:r><w:t>{escape(_format_plain_segment(segment))}</w:t></w:r></w:p>"
        for segment in segments
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr("word/document.xml", document_xml)
    return path


def write_pdf(path: Path, segments: Iterable[TranscriptSegment]) -> Path:
    text = "\n".join(_format_plain_segment(segment) for segment in segments)
    lines = _wrap_pdf_text(text)
    stream = "BT /F1 11 Tf 50 780 Td 14 TL " + " T* ".join(
        f"({_escape_pdf(line)}) Tj" for line in lines[:52]
    ) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream.encode('latin-1', errors='replace'))} >>\nstream\n{stream}\nendstream",
    ]
    chunks = ["%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk.encode("latin-1", errors="replace")) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n{obj}\nendobj\n")
    xref_offset = sum(len(chunk.encode("latin-1", errors="replace")) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n")
    chunks.append(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    )
    path.write_bytes("".join(chunks).encode("latin-1", errors="replace"))
    return path


def _format_plain_segment(segment: TranscriptSegment) -> str:
    return (
        f"[{_format_time(segment.start_seconds)}-{_format_time(segment.end_seconds)}] "
        f"{_speaker(segment)}: {segment.text_clean or segment.text_raw}"
    )


def _speaker(segment: TranscriptSegment) -> str:
    return segment.speaker_label or "SPEAKER"


def _format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:04.1f}"


def _format_srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _wrap_pdf_text(text: str, width: int = 86) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line
        while len(line) > width:
            lines.append(line[:width])
            line = line[width:]
        lines.append(line)
    return lines or [""]


def _escape_pdf(value: str) -> str:
    return value.encode("latin-1", errors="replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

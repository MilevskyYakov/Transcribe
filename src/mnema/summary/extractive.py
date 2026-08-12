"""Small local extractive summary implementation."""

from __future__ import annotations

import json
from pathlib import Path

from mnema.app.models import TranscriptSegment


def write_summary(segments: list[TranscriptSegment], md_path: Path, json_path: Path) -> None:
    """Write compact local summary artifacts."""
    text_segments = [segment.text_clean or segment.text_raw for segment in segments if segment.text_clean or segment.text_raw]
    total_seconds = max((segment.end_seconds for segment in segments), default=0.0)
    speakers = sorted({segment.speaker_label for segment in segments if segment.speaker_label})
    highlights = text_segments[:5]

    md_lines = [
        "# Summary",
        "",
        f"- Duration: {total_seconds:.1f} seconds",
        f"- Segments: {len(segments)}",
        f"- Speakers: {', '.join(speakers) if speakers else 'unknown'}",
        "",
        "## Highlights",
        "",
    ]
    md_lines.extend(f"- {highlight}" for highlight in highlights)
    md_path.write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "duration_seconds": total_seconds,
                "segment_count": len(segments),
                "speakers": speakers,
                "highlights": highlights,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

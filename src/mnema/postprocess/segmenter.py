"""Helpers for splitting coarse ASR segments into smaller turn-like chunks."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, List

from mnema.app.models import TranscriptSegment, WordToken


def split_segments_on_long_pauses(
    segments: Iterable[TranscriptSegment],
    pause_threshold_seconds: float = 0.8,
) -> List[TranscriptSegment]:
    """Split segments into smaller chunks when word-level pauses are large."""
    split_segments: List[TranscriptSegment] = []
    for segment in segments:
        if len(segment.words) < 2:
            split_segments.append(segment)
            continue

        current_words: List[WordToken] = []
        chunk_index = 0
        split_happened = False
        for word in segment.words:
            if current_words:
                previous_word = current_words[-1]
                pause_duration = word.start_seconds - previous_word.end_seconds
                if pause_duration >= pause_threshold_seconds or _is_sentence_pause_split(
                    current_words,
                    previous_word.text,
                    pause_duration,
                ):
                    split_segments.append(_build_split_segment(segment, current_words, chunk_index))
                    chunk_index += 1
                    split_happened = True
                    current_words = []
            current_words.append(word)

        if current_words:
            if not split_happened and len(current_words) == len(segment.words):
                split_segments.append(segment)
            else:
                split_segments.append(_build_split_segment(segment, current_words, chunk_index))

    return split_segments


def _build_split_segment(
    source_segment: TranscriptSegment,
    words: List[WordToken],
    chunk_index: int,
) -> TranscriptSegment:
    text = " ".join(word.text for word in words).strip()
    return replace(
        source_segment,
        segment_id=f"{source_segment.segment_id}-{chunk_index:03d}",
        start_seconds=words[0].start_seconds,
        end_seconds=words[-1].end_seconds,
        text_raw=text,
        text_clean=text,
        words=list(words),
    )


def _is_sentence_pause_split(
    current_words: List[WordToken],
    previous_word_text: str,
    pause_duration: float,
) -> bool:
    sentence_endings = (".", "!", "?", "…")
    return (
        len(current_words) >= 3
        and previous_word_text.rstrip().endswith(sentence_endings)
        and pause_duration >= 0.25
    )

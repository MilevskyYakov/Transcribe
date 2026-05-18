"""Local word-level transcript quality checks."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable, List

from transcribe_doc.app.models import TranscriptSegment, WordToken

_DOMAIN_TERMS = {
    "ai": "AI",
    "amo": "amo",
    "amocrm": "amoCRM",
    "api": "API",
    "crm": "CRM",
    "gpt": "GPT",
    "llm": "LLM",
    "tauri": "Tauri",
}

_ASR_REPLACEMENTS = {
    "црм": "CRM",
    "сиэрэм": "CRM",
    "апи": "API",
}

_COMMON_RU_WORDS = {
    "а",
    "будет",
    "в",
    "да",
    "дела",
    "и",
    "как",
    "мы",
    "на",
    "не",
    "ну",
    "по",
    "привет",
    "реплика",
    "с",
    "что",
    "это",
    "я",
}

_CYRILLIC_WORD_RE = re.compile(r"^[а-яё-]+$", re.IGNORECASE)
_TOKEN_CLEAN_RE = re.compile(r"^\W+|\W+$", re.UNICODE)


def apply_word_quality_checks(
    segments: Iterable[TranscriptSegment],
) -> List[TranscriptSegment]:
    """Annotate word tokens and rebuild clean text from conservative fixes."""
    checked_segments: List[TranscriptSegment] = []
    for segment in segments:
        if not segment.words:
            checked_segments.append(segment)
            continue

        previous_clean = ""
        checked_words: List[WordToken] = []
        clean_parts: List[str] = []
        for word in segment.words:
            checked_word = _check_word(word, previous_clean)
            checked_words.append(checked_word)

            if not _has_issue(checked_word, "repeated_word"):
                clean_parts.append(checked_word.text_clean or checked_word.text)
            previous_clean = _normalized_token(checked_word.text_clean or checked_word.text)

        checked_segments.append(
            replace(
                segment,
                text_clean=" ".join(clean_parts).strip() or segment.text_clean,
                words=checked_words,
            )
        )
    return checked_segments


def _check_word(word: WordToken, previous_clean: str) -> WordToken:
    raw_clean = _strip_outer_punctuation(word.text)
    normalized = _normalized_token(raw_clean)
    text_clean = _clean_word_text(raw_clean, normalized)
    issues = list(word.issues)

    if previous_clean and normalized == previous_clean:
        issues.append(
            {
                "code": "repeated_word",
                "severity": "warning",
                "message": "Adjacent repeated word kept in raw transcript and removed from clean text.",
            }
        )

    if normalized in _DOMAIN_TERMS:
        issues.append(
            {
                "code": "domain_term",
                "severity": "info",
                "message": "Known domain term normalized.",
            }
        )

    if normalized in _ASR_REPLACEMENTS:
        issues.append(
            {
                "code": "asr_suspect",
                "severity": "warning",
                "message": "Common ASR spelling normalized.",
            }
        )

    if _looks_unknown_russian_word(normalized):
        issues.append(
            {
                "code": "unknown_word",
                "severity": "warning",
                "message": "Word is not in the local lightweight vocabulary.",
            }
        )

    if any(issue.get("code") == "repeated_word" for issue in issues):
        text_clean = ""
    return replace(word, text_clean=text_clean, issues=issues)


def _clean_word_text(raw_clean: str, normalized: str) -> str:
    if normalized in _DOMAIN_TERMS:
        return _DOMAIN_TERMS[normalized]
    if normalized in _ASR_REPLACEMENTS:
        return _ASR_REPLACEMENTS[normalized]
    return raw_clean


def _looks_unknown_russian_word(normalized: str) -> bool:
    return (
        len(normalized) >= 7
        and bool(_CYRILLIC_WORD_RE.match(normalized))
        and normalized not in _COMMON_RU_WORDS
    )


def _strip_outer_punctuation(value: str) -> str:
    return _TOKEN_CLEAN_RE.sub("", value).strip()


def _normalized_token(value: str) -> str:
    return _strip_outer_punctuation(value).casefold()


def _has_issue(word: WordToken, code: str) -> bool:
    return any(issue.get("code") == code for issue in word.issues)

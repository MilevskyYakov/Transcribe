"""Factory helpers for diarization backends."""

from __future__ import annotations

from typing import Any, Dict, cast

from mnema.app.config import AppConfig
from mnema.diarization.base import DiarizationBackend
from mnema.diarization.heuristic_multi_speaker_backend import (
    HeuristicMultiSpeakerDiarizationBackend,
)
from mnema.diarization.resemblyzer_backend import (
    ResemblyzerDiarizationBackend,
    is_resemblyzer_available,
)
from mnema.diarization.single_speaker_backend import SingleSpeakerDiarizationBackend


def build_diarization_backend(
    config: AppConfig,
    speaker_manifest: Dict[str, Any] | None = None,
) -> DiarizationBackend | None:
    """Construct the configured diarization backend, if enabled."""
    if not config.diarization.enabled:
        return None

    expected_speakers = []
    if speaker_manifest is not None:
        manifest_speakers = speaker_manifest.get("expected_speakers", [])
        if isinstance(manifest_speakers, list):
            expected_speakers = manifest_speakers

    if len(expected_speakers) == 1:
        return SingleSpeakerDiarizationBackend()

    if len(expected_speakers) > 1:
        if is_resemblyzer_available():
            return ResemblyzerDiarizationBackend(num_speakers=len(expected_speakers))
        return HeuristicMultiSpeakerDiarizationBackend(num_speakers=len(expected_speakers))

    auto_speakers = _speaker_count_setting(config.diarization.num_speakers)
    if auto_speakers == 1:
        return SingleSpeakerDiarizationBackend()
    if is_resemblyzer_available():
        return ResemblyzerDiarizationBackend(num_speakers=auto_speakers)
    heuristic_speakers = 2 if auto_speakers == "auto" else cast(int, auto_speakers)
    return HeuristicMultiSpeakerDiarizationBackend(
        num_speakers=heuristic_speakers,
    )


def _speaker_count_setting(value: str) -> int | str:
    if value == "auto":
        return "auto"
    if value != "auto":
        try:
            return max(1, int(value))
        except ValueError:
            return 2
    return "auto"

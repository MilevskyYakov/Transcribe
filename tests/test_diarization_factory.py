from mnema.app.config import AppConfig, DiarizationSection
from mnema.diarization.factory import build_diarization_backend
from mnema.diarization.heuristic_multi_speaker_backend import (
    HeuristicMultiSpeakerDiarizationBackend,
)
from mnema.diarization.resemblyzer_backend import (
    ResemblyzerDiarizationBackend,
    is_resemblyzer_available,
)
from mnema.diarization.single_speaker_backend import SingleSpeakerDiarizationBackend


def test_build_diarization_backend_returns_single_speaker_backend_when_enabled() -> None:
    config = AppConfig(diarization=DiarizationSection(enabled=True, num_speakers="1"))

    backend = build_diarization_backend(config)

    assert isinstance(backend, SingleSpeakerDiarizationBackend)


def test_build_diarization_backend_returns_multi_speaker_backend_for_auto() -> None:
    config = AppConfig(diarization=DiarizationSection(enabled=True, num_speakers="auto"))

    backend = build_diarization_backend(config)

    assert isinstance(backend, (HeuristicMultiSpeakerDiarizationBackend, ResemblyzerDiarizationBackend))
    if isinstance(backend, ResemblyzerDiarizationBackend):
        assert backend.speaker_count_mode == "auto"


def test_build_diarization_backend_returns_none_when_disabled() -> None:
    config = AppConfig(diarization=DiarizationSection(enabled=False, num_speakers="auto"))

    backend = build_diarization_backend(config)

    assert backend is None


def test_build_diarization_backend_returns_multi_speaker_backend_for_manifest() -> None:
    config = AppConfig(diarization=DiarizationSection(enabled=True, num_speakers="auto"))

    backend = build_diarization_backend(
        config,
        {"expected_speakers": [{"name": "Алексей"}, {"name": "Марина"}]},
    )

    assert isinstance(backend, (HeuristicMultiSpeakerDiarizationBackend, ResemblyzerDiarizationBackend))


def test_build_diarization_backend_falls_back_to_heuristic_when_resemblyzer_missing(
    monkeypatch,
) -> None:
    config = AppConfig(diarization=DiarizationSection(enabled=True, num_speakers="auto"))

    is_resemblyzer_available.cache_clear()
    monkeypatch.setattr(
        "mnema.diarization.factory.is_resemblyzer_available",
        lambda: False,
    )

    backend = build_diarization_backend(
        config,
        {"expected_speakers": [{"name": "Алексей"}, {"name": "Марина"}]},
    )

    assert isinstance(backend, HeuristicMultiSpeakerDiarizationBackend)

from transcribe_doc.app.config import AlignmentSection, AppConfig
from transcribe_doc.alignment.factory import build_alignment_backend
from transcribe_doc.alignment.passthrough_backend import PassthroughAlignmentBackend


def test_build_alignment_backend_returns_passthrough_backend_when_enabled() -> None:
    config = AppConfig(alignment=AlignmentSection(enabled=True, word_timestamps=True))

    backend = build_alignment_backend(config)

    assert isinstance(backend, PassthroughAlignmentBackend)


def test_build_alignment_backend_returns_none_when_disabled() -> None:
    config = AppConfig(alignment=AlignmentSection(enabled=False, word_timestamps=True))

    backend = build_alignment_backend(config)

    assert backend is None

from pathlib import Path

import pytest

from mnema.ingest.input_resolver import InputResolutionError, resolve_single_input
from mnema.storage.paths import build_job_paths


def test_resolve_single_input_accepts_supported_media(tmp_path: Path) -> None:
    media_file = tmp_path / "sample.mp3"
    media_file.write_bytes(b"fake-audio")

    resolved = resolve_single_input(media_file)

    assert resolved.path == media_file.resolve()
    assert resolved.media_kind == "audio"
    assert resolved.extension == "mp3"


def test_resolve_single_input_rejects_unsupported_extension(tmp_path: Path) -> None:
    media_file = tmp_path / "sample.txt"
    media_file.write_text("hello", encoding="utf-8")

    with pytest.raises(InputResolutionError, match="Unsupported media format"):
        resolve_single_input(media_file)


def test_build_job_paths_creates_expected_layout(tmp_path: Path) -> None:
    job_paths = build_job_paths(tmp_path, "job-001")

    assert job_paths.job_dir == tmp_path / "job-001"
    assert job_paths.artifacts_dir == tmp_path / "job-001" / "artifacts"
    assert job_paths.job_json == tmp_path / "job-001" / "job.json"
    assert job_paths.final_speech_text_md == tmp_path / "job-001" / "final_speech_text.md"

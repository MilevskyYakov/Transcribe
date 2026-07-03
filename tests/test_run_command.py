from transcribe_doc.app.exceptions import ExternalDependencyError

from support.run_command import RunCommandHarness, transcript_segment, word_token


def test_run_command_records_failed_job_when_media_tools_missing(
    run_cli: RunCommandHarness,
) -> None:
    run_cli.hide_media_tools()
    run_cli.write_config()

    exit_code = run_cli.run()

    assert exit_code == 1
    job_payload = run_cli.job_payload()
    assert job_payload["status"] == "failed"
    assert any("ffprobe" in warning or "ffmpeg" in warning for warning in job_payload["warnings"])


def test_run_command_records_failed_job_when_asr_backend_crashes(
    run_cli: RunCommandHarness,
) -> None:
    run_cli.install_fake_media_tools()
    run_cli.use_crashing_asr(RuntimeError("onnx runtime failed"))
    run_cli.write_config()

    exit_code = run_cli.run()

    assert exit_code == 1
    job_payload = run_cli.job_payload()
    assert job_payload["status"] == "failed"
    assert job_payload["warnings"] == ["onnx runtime failed"]
    assert job_payload["metadata"]["current_stage"] == "failed"


def test_run_command_keeps_coreml_failure_detail_out_of_last_message(
    run_cli: RunCommandHarness,
) -> None:
    public_error = ExternalDependencyError(
        "ONNX ASR модель не смогла обработать аудио. Попробуйте другую модель или повторите позже."
    )
    public_error.__cause__ = RuntimeError("CoreMLExecutionProvider raw failure")
    run_cli.install_fake_media_tools()
    run_cli.use_crashing_asr(public_error)
    run_cli.write_config()

    exit_code = run_cli.run()

    assert exit_code == 1
    job_dir = run_cli.single_job_dir()
    job_payload = run_cli.job_payload()
    assert job_payload["status"] == "failed"
    assert job_payload["metadata"]["last_message"] == (
        "ONNX ASR модель не смогла обработать аудио. Попробуйте другую модель или повторите позже."
    )
    assert "CoreMLExecutionProvider raw failure" in job_payload["warnings"][0]
    assert "CoreMLExecutionProvider raw failure" in (
        job_dir / "artifacts" / "job.log"
    ).read_text(encoding="utf-8")


def test_run_command_completes_with_fake_media_tools(run_cli: RunCommandHarness) -> None:
    run_cli.install_fake_media_tools()
    run_cli.use_completed_asr(
        [transcript_segment(text_raw="  привет   мир ", text_clean="  привет   мир ")]
    )
    run_cli.disable_resemblyzer()
    run_cli.write_config()

    exit_code = run_cli.run()

    assert exit_code == 0
    job_dir = run_cli.single_job_dir()
    assert not (job_dir / "artifacts" / "normalized_audio.wav").exists()
    assert not (job_dir / "transcript_raw.json").exists()
    assert (job_dir / "segments.json").exists()
    assert (job_dir / "words.json").exists()

    job_payload = run_cli.job_payload()
    assert job_payload["status"] == "completed"
    assert job_payload["warnings"] == []
    assert job_payload["artifacts"]["normalized_audio"] is None
    assert job_payload["artifacts"]["raw_transcript"] is None
    assert job_payload["metadata"]["temp_cleanup"]["reason"] == "job_success"


def test_run_command_writes_transcript_artifact_when_asr_backend_available(
    run_cli: RunCommandHarness,
) -> None:
    run_cli.install_fake_media_tools()
    run_cli.use_completed_asr(
        [
            transcript_segment(
                text_raw="  привет   мир ",
                text_clean="  привет   мир ",
                words=[
                    word_token("привет", 0.0, 0.5),
                    word_token("мир", 0.6, 1.0),
                ],
            )
        ]
    )
    run_cli.write_config(include_asr=True)

    exit_code = run_cli.run()

    assert exit_code == 0
    assert not (run_cli.single_job_dir() / "transcript_raw.json").exists()

    segments_payload = run_cli.read_json("segments.json")
    assert segments_payload[0]["text_raw"] == "  привет   мир "
    assert segments_payload[0]["text_clean"] == "Привет мир."
    assert segments_payload[0]["speaker_label"] == "SPEAKER_00"

    words_payload = run_cli.read_json("words.json")
    assert words_payload[0]["segment_id"] == "seg-0000"
    assert words_payload[0]["speaker_label"] == "SPEAKER_00"
    assert words_payload[0]["text"] == "привет"
    assert words_payload[0]["text_clean"] == "привет"
    assert words_payload[0]["issues"] == []

    job_payload = run_cli.job_payload()
    assert job_payload["status"] == "completed"
    assert job_payload["detected_language"] == "ru"
    assert job_payload["artifacts"]["raw_transcript"] is None


def test_run_command_maps_single_expected_speaker_from_manifest(
    run_cli: RunCommandHarness,
) -> None:
    run_cli.install_fake_media_tools()
    run_cli.use_completed_asr()
    run_cli.disable_resemblyzer()
    manifest_path = run_cli.write_speaker_manifest([{"name": "Алексей", "role": "Интервьюер"}])
    run_cli.write_config(include_asr=True)

    exit_code = run_cli.run("--speaker-manifest", str(manifest_path))

    assert exit_code == 0
    segments_payload = run_cli.read_json("segments.json")
    assert segments_payload[0]["speaker_label"] == "Алексей"
    assert segments_payload[0]["mapping"]["machine_label"] == "SPEAKER_00"
    assert segments_payload[0]["mapping"]["display_label"] == "Алексей"

    job_payload = run_cli.job_payload()
    assert job_payload["metadata"]["speaker_manifest"]["expected_speakers"][0]["name"] == "Алексей"


def test_run_command_maps_two_expected_speakers_across_multiple_segments(
    run_cli: RunCommandHarness,
) -> None:
    run_cli.install_fake_media_tools(duration="2.0")
    run_cli.use_completed_asr(
        [
            transcript_segment(text_raw="привет", text_clean="привет"),
            transcript_segment(
                segment_id="seg-0001",
                start_seconds=1.1,
                end_seconds=2.0,
                text_raw="здравствуйте",
                text_clean="здравствуйте",
            ),
        ]
    )
    run_cli.disable_resemblyzer()
    manifest_path = run_cli.write_speaker_manifest([{"name": "Алексей"}, {"name": "Марина"}])
    run_cli.write_config(include_asr=True)

    exit_code = run_cli.run("--speaker-manifest", str(manifest_path))

    assert exit_code == 0
    segments_payload = run_cli.read_json("segments.json")
    assert [segment["speaker_label"] for segment in segments_payload] == ["Алексей", "Марина"]

    job_dir = run_cli.single_job_dir()
    diarization_dump_path = job_dir / "artifacts" / "diarization_dump.json"
    assert not diarization_dump_path.exists()

    job_payload = run_cli.job_payload()
    assert job_payload["artifacts"]["diarization_dump"] is None


def test_run_command_stores_low_diarization_quality_without_warning_status(
    run_cli: RunCommandHarness,
) -> None:
    run_cli.install_fake_media_tools()
    run_cli.use_completed_asr()
    run_cli.use_low_quality_diarization()
    run_cli.write_config(include_asr=True)

    exit_code = run_cli.run()

    assert exit_code == 0
    job_payload = run_cli.job_payload()
    assert job_payload["status"] == "completed"
    assert job_payload["warnings"] == []
    assert job_payload["metadata"]["diarization_quality"] == {
        "backend": "resemblyzer",
        "segment_count": 1,
        "detected_cluster_count_max": 2,
        "min_centroid_similarity_margin": 0.05,
        "avg_centroid_similarity_margin": 0.05,
        "min_assigned_centroid_similarity": 0.82,
        "max_nearest_alternative_similarity": 0.77,
        "dominant_cluster_share": 1.0,
    }

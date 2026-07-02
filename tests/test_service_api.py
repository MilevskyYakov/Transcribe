import json
import threading
import urllib.request
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from transcribe_doc.app.config import AppConfig, AppSection
from transcribe_doc.app.models import ArtifactManifest, Job, JobStatus
from transcribe_doc.core.batch import BatchItemResult, BatchResult
from transcribe_doc.core.processing import ProcessingResult
from transcribe_doc.ingest.manifest_loader import speaker_hint_to_manifest
from transcribe_doc.service import job_endpoints, model_endpoints
from transcribe_doc.service.responses import job_to_response
from transcribe_doc.service.request_parsing import payload_from_multipart_form
from transcribe_doc.service import server as service_server
from transcribe_doc.service.server import build_server, list_artifacts, list_events, list_jobs
from transcribe_doc.storage.artifact_store import save_job


def test_list_jobs_and_artifacts_from_output_root(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "job-local"
    job_dir.mkdir(parents=True)
    segments_path = job_dir / "segments.json"
    segments_path.write_text("[]", encoding="utf-8")
    events_path = job_dir / "artifacts" / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text(
        '{"timestamp":"2026-05-08T00:00:00Z","stage":"asr","status":"ok","message":"run","progress":35}\n',
        encoding="utf-8",
    )

    save_job(
        Job(
            job_id="job-local",
            source_paths=[str(tmp_path / "sample.wav")],
            status=JobStatus.COMPLETED,
            artifacts=ArtifactManifest(segments_json=str(segments_path)),
        ),
        job_dir / "job.json",
    )

    jobs = list_jobs(output_root)
    artifacts = list_artifacts(output_root, "job-local")
    events = list_events(output_root, "job-local")

    assert jobs[0]["job_id"] == "job-local"
    assert jobs[0]["status"] == "completed"
    assert artifacts == [
        {
            "name": "segments_json",
            "filename": "segments.json",
            "size_bytes": 2,
            "download_url": "/jobs/job-local/artifacts/segments_json",
        }
    ]
    assert events[0]["stage"] == "asr"
    assert events[0]["progress"] == 35


def test_http_health_and_jobs_endpoint(tmp_path: Path) -> None:
    config = AppConfig(app=AppSection(output_dir=str(tmp_path / "output")))
    httpd = build_server(config=config, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_port}"

    try:
        health = _get_json(f"{base_url}/health")
        jobs = _get_json(f"{base_url}/jobs")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

    assert health["status"] == "ok"
    assert health["app"]["output_dir"] == str(tmp_path / "output")
    assert "ffmpeg" in health["media_tools"]
    assert "ffprobe" in health["media_tools"]
    assert jobs == {"jobs": []}


def test_http_models_endpoint_returns_cache_status(tmp_path: Path, monkeypatch) -> None:
    config = AppConfig(app=AppSection(output_dir=str(tmp_path / "output")))
    monkeypatch.setattr(
        model_endpoints,
        "inspect_whisper_models",
        lambda: [{"name": "tiny", "status": "ready"}],
    )
    httpd = build_server(config=config, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_port}"

    try:
        models = _get_json(f"{base_url}/models")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

    assert models["current_model"] == "large-v3"
    assert models["models"] == [{"name": "tiny", "status": "ready"}]


def test_job_response_uses_typed_metadata_contract() -> None:
    job = Job(
        job_id="job-contract",
        source_paths=["sample.wav"],
        status=JobStatus.COMPLETED_WITH_WARNINGS,
        metadata={
            "display_title": "Contract sample",
            "progress": 100,
            "diarization_quality": {
                "detected_cluster_count_max": 1,
                "min_centroid_similarity_margin": 0.04,
                "dominant_cluster_share": 0.9,
            },
        },
        warnings=["Diarization quality warning: low margin"],
    )

    response = job_to_response(job)

    assert response["job_id"] == "job-contract"
    assert response["status"] == "completed_with_warnings"
    assert response["metadata"]["display_title"] == "Contract sample"
    assert response["metadata"]["progress"] == 100
    assert response["metadata"]["diarization_quality"] == {
        "detected_cluster_count_max": 1,
        "min_centroid_similarity_margin": 0.04,
        "dominant_cluster_share": 0.9,
    }


def test_transcript_artifacts_events_endpoints_use_contract_payloads(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "job-local"
    artifacts_dir = job_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    segments_path = job_dir / "segments.json"
    words_path = job_dir / "words.json"
    segments_path.write_text(
        '[{"segment_id":"s1","start_seconds":0,"end_seconds":1,"text_raw":"Hi","text_clean":"Hi"}]',
        encoding="utf-8",
    )
    words_path.write_text('[{"text":"Hi","start_seconds":0,"end_seconds":1}]', encoding="utf-8")
    (artifacts_dir / "events.jsonl").write_text(
        '{"timestamp":"2026-05-08T00:00:00Z","stage":"done","status":"ok","message":"ready","progress":100}\n',
        encoding="utf-8",
    )
    save_job(
        Job(
            job_id="job-local",
            source_paths=["sample.wav"],
            status=JobStatus.COMPLETED,
            artifacts=ArtifactManifest(segments_json=str(segments_path)),
        ),
        job_dir / "job.json",
    )
    ctx = SimpleNamespace(output_root=output_root)

    transcript = job_endpoints.transcript_endpoint(ctx, "job-local").payload
    artifacts = job_endpoints.artifacts_endpoint(ctx, "job-local").payload
    events = job_endpoints.events_endpoint(ctx, "job-local").payload

    assert transcript["job"]["job_id"] == "job-local"
    assert transcript["segments"][0]["segment_id"] == "s1"
    assert transcript["words"][0]["text"] == "Hi"
    assert artifacts["artifacts"][0] == {
        "name": "segments_json",
        "filename": "segments.json",
        "size_bytes": segments_path.stat().st_size,
        "download_url": "/jobs/job-local/artifacts/segments_json",
    }
    assert events["events"][0] == {
        "timestamp": "2026-05-08T00:00:00Z",
        "stage": "done",
        "status": "ok",
        "message": "ready",
        "progress": 100,
    }



def test_speaker_review_endpoint_persists_assignment_and_saves_markdown(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    temp_root = tmp_path / "tmp"
    job_dir = output_root / "job-local"
    job_dir.mkdir(parents=True)
    (job_dir / "segments.json").write_text(
        '[{"segment_id":"s1","start_seconds":0,"end_seconds":1,"text_raw":"Hi",'
        '"text_clean":"Привет","speaker_label":"SPEAKER_00"},'
        '{"segment_id":"s2","start_seconds":1,"end_seconds":2,"text_raw":"Yo",'
        '"text_clean":"Ответ","speaker_label":"SPEAKER_01"}]',
        encoding="utf-8",
    )
    save_job(
        Job(
            job_id="job-local",
            source_paths=["sample.wav"],
            status=JobStatus.COMPLETED,
            metadata={
                "display_title": "Client call",
                "speaker_manifest": {"expected_speakers": [{"name": "Яков"}]},
            },
        ),
        job_dir / "job.json",
    )
    autosave_dir = tmp_path / "saved"
    ctx = SimpleNamespace(
        app_config=AppConfig(app=AppSection(output_dir=str(output_root), temp_dir=str(temp_root))),
        output_root=output_root,
        read_json_object=lambda: {
            "assignments": {"SPEAKER_00": "Яков"},
            "autosave_dir": str(autosave_dir),
        },
    )

    review = job_endpoints.speaker_review_endpoint(ctx, "job-local")
    saved = job_endpoints.update_speaker_review_endpoint(ctx, "job-local")
    transcript = job_endpoints.transcript_endpoint(ctx, "job-local")

    assert review.payload["status"] == "pending"
    assert review.payload["groups"][0]["fallback_label"] == "Спикер 1"
    assert saved.payload["speaker_review"]["status"] == "confirmed"
    assert saved.payload["final_markdown"]["status"] == "saved"
    content = (autosave_dir / "Client call.md").read_text(encoding="utf-8")
    assert "Яков: Привет" in content
    assert "Спикер 2: Ответ" in content
    assert "SPEAKER_" not in content
    assert transcript.payload["segments"][0]["speaker_label"] == "Яков"
    assert transcript.payload["segments"][1]["speaker_label"] == "Спикер 2"

def test_final_markdown_endpoint_saves_external_file_and_uses_title_download_name(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    temp_root = tmp_path / "tmp"
    job_dir = output_root / "job-local"
    artifacts_dir = job_dir / "artifacts"
    uploads_dir = temp_root / "uploads"
    artifacts_dir.mkdir(parents=True)
    uploads_dir.mkdir(parents=True)
    segments_path = job_dir / "segments.json"
    final_text_path = job_dir / "final_speech_text.md"
    uploaded_source_path = uploads_dir / "source.wav"
    normalized_audio_path = artifacts_dir / "normalized_audio.wav"
    uploaded_source_path.write_bytes(b"uploaded-media")
    normalized_audio_path.write_bytes(b"normalized-media")
    segments_path.write_text(
        '[{"segment_id":"s1","start_seconds":0,"end_seconds":1,"text_raw":"Hi","text_clean":"Hi"}]',
        encoding="utf-8",
    )
    final_text_path.write_text("# internal\n", encoding="utf-8")
    save_job(
        Job(
            job_id="job-local",
            source_paths=[str(uploaded_source_path), str(tmp_path / "original.wav")],
            status=JobStatus.COMPLETED,
            artifacts=ArtifactManifest(
                final_speech_text_md=str(final_text_path),
                normalized_audio=str(normalized_audio_path),
            ),
            metadata={"display_title": "Client call"},
        ),
        job_dir / "job.json",
    )
    autosave_dir = tmp_path / "saved"
    ctx = SimpleNamespace(
        app_config=AppConfig(app=AppSection(output_dir=str(output_root), temp_dir=str(temp_root))),
        output_root=output_root,
        read_json_object=lambda: {"autosave_dir": str(autosave_dir)},
    )

    saved = job_endpoints.save_final_markdown_endpoint(ctx, "job-local")
    status = job_endpoints.final_markdown_status_endpoint(ctx, "job-local")
    download = job_endpoints.artifact_download_endpoint(ctx, "job-local", "final_speech_text_md")

    assert saved.payload["message"] == "Сохранено: Client call.md"
    assert (autosave_dir / "Client call.md").exists()
    assert not uploaded_source_path.exists()
    assert not normalized_audio_path.exists()
    assert status.payload["status"] == "saved"
    assert download.download_name == "Client call.md"


def test_post_jobs_uses_shared_processing_entrypoint(tmp_path: Path, monkeypatch) -> None:
    output_root = tmp_path / "output"
    config = AppConfig(app=AppSection(output_dir=str(output_root)))
    source_file = tmp_path / "sample.wav"
    source_file.write_bytes(b"fake")

    def fake_process_single_file(
        input_path,
        *,
        output_root,
        config,
        job_id=None,
        display_title=None,
        speaker_manifest_path=None,
        speaker_hint=None,
        formats=None,
    ):
        job = Job(
            job_id=job_id or "job-created",
            source_paths=[str(input_path)],
            status=JobStatus.COMPLETED,
            artifacts=ArtifactManifest(),
        )
        return ProcessingResult(
            exit_code=0,
            job=job,
            job_paths=None,
            message="created",
        )

    monkeypatch.setattr(job_endpoints, "process_single_file", fake_process_single_file)

    httpd = build_server(config=config, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_port}"

    try:
        response = _post_json(
            f"{base_url}/jobs",
            {"input_path": str(source_file), "display_title": "Client sync"},
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

    assert response["exit_code"] is None
    assert response["job"]["status"] == "queued"
    assert response["job"]["metadata"]["display_title"] == "Client sync"
    assert response["job"]["metadata"]["source_filename"] == "sample.wav"
    assert response["message"].endswith("queued")


def test_post_batch_returns_report(tmp_path: Path, monkeypatch) -> None:
    config = AppConfig(app=AppSection(output_dir=str(tmp_path / "output")))

    def fake_process_batch(input_paths, **kwargs):
        return BatchResult(
            exit_code=0,
            total=1,
            succeeded=1,
            failed=0,
            report_path=tmp_path / "output" / "batch.json",
            items=[
                BatchItemResult(
                    input_path=str(input_paths[0]),
                    exit_code=0,
                    job_id="job-a",
                    status="completed",
                    message="ok",
                )
            ],
        )

    monkeypatch.setattr(job_endpoints, "process_batch", fake_process_batch)

    httpd = build_server(config=config, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_port}"

    try:
        response = _post_json(f"{base_url}/batch", {"input_paths": [str(tmp_path / "a.wav")]})
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

    assert response["total"] == 1
    assert response["items"][0]["job_id"] == "job-a"


def test_freeform_speaker_hint_extracts_names() -> None:
    manifest = speaker_hint_to_manifest("вот был Яков и Никита на встрече")

    assert manifest["source"] == "freeform_speaker_hint"
    assert manifest["expected_speakers"] == [{"name": "Яков"}, {"name": "Никита"}]


def test_freeform_speaker_hint_ignores_capitalized_stop_words() -> None:
    manifest = speaker_hint_to_manifest("Был Яков, Никита на встрече")

    assert manifest["expected_speakers"] == [{"name": "Яков"}, {"name": "Никита"}]


def test_empty_speaker_hint_keeps_automatic_detection() -> None:
    assert speaker_hint_to_manifest("   ") == {}


def test_multipart_payload_parser_stores_uploads(tmp_path: Path) -> None:
    class FakeForm(dict):
        pass

    form = FakeForm(
        media=SimpleNamespace(filename="source.wav", file=BytesIO(b"audio")),
        speaker_hint=SimpleNamespace(value="Яков"),
        title=SimpleNamespace(value="Planning sync"),
        speaker_manifest=SimpleNamespace(filename="speakers.json", file=BytesIO(b"{}")),
    )

    payload = payload_from_multipart_form(form, tmp_path / "uploads")

    assert Path(str(payload["input_path"])).read_bytes() == b"audio"
    assert payload["speaker_hint"] == "Яков"
    assert payload["display_title"] == "Planning sync"
    assert Path(str(payload["speaker_manifest_path"])).read_bytes() == b"{}"


def test_models_response_marks_interrupted_download_as_recoverable() -> None:
    model = {
        "name": "parakeet-v3",
        "status": "downloading",
        "progress": 0,
        "message": "Готовлю ONNX ASR модель",
    }

    response = service_server._model_download_state_for_response(model, active_downloads=set())

    assert response["status"] == "error"
    assert response["stale_download"] is True
    assert "Скачать заново" in response["message"]


def test_models_response_keeps_active_download_in_progress() -> None:
    model = {"name": "parakeet-v3", "status": "downloading", "progress": 0}

    response = service_server._model_download_state_for_response(
        model, active_downloads={"parakeet-v3"}
    )

    assert response == model


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))

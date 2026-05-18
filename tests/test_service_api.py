import json
import threading
import urllib.request
from pathlib import Path

from transcribe_doc.app.config import AppConfig, AppSection
from transcribe_doc.app.models import ArtifactManifest, Job, JobStatus
from transcribe_doc.core.batch import BatchItemResult, BatchResult
from transcribe_doc.core.processing import ProcessingResult
from transcribe_doc.ingest.manifest_loader import speaker_hint_to_manifest
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
        service_server,
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

    monkeypatch.setattr(service_server, "process_single_file", fake_process_single_file)

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

    monkeypatch.setattr(service_server, "process_batch", fake_process_batch)

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

    response = service_server._model_download_state_for_response(model, active_downloads={"parakeet-v3"})

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

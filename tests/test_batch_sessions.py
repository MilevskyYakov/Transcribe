from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from mnema.app.config import AppConfig, AppSection
from mnema.service import job_endpoints
from mnema.service.batch_session_store import (
    create_batch_session,
    list_batch_sessions,
    load_batch_session,
    load_batch_session_payload,
    reconcile_batch_session_jobs,
    write_batch_session,
)
from mnema.service.job_store import (
    load_job,
    mark_interrupted_jobs,
    read_json_file,
    write_job_payload,
)


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def submit(self, function, *args, **kwargs):
        self.calls.append((function, args, kwargs))
        return SimpleNamespace()


def _config(output_root: Path) -> AppConfig:
    return AppConfig(app=AppSection(output_dir=str(output_root)))


def _create_session(tmp_path: Path, names: tuple[str, ...] = ("one.wav", "two.wav")):
    output_root = tmp_path / "output"
    destination = tmp_path / "saved"
    destination.mkdir()
    items = []
    for name in names:
        source = tmp_path / name
        source.write_bytes(b"audio")
        items.append({"input_path": str(source), "source_name": name})
    session = create_batch_session(output_root, items, common_output_dir=str(destination))
    return output_root, destination, session


def _submit_context(output_root: Path, payload: dict[str, object], executor: RecordingExecutor):
    return SimpleNamespace(
        output_root=output_root,
        app_config=_config(output_root),
        executor=executor,
        read_job_request=lambda: payload,
    )


def test_batch_session_persists_order_and_unconfigured_state(tmp_path: Path) -> None:
    output_root, destination, session = _create_session(tmp_path)

    restored = load_batch_session(output_root, session["session_id"])

    assert restored is not None
    assert restored["common_output_dir"] == str(destination)
    assert [item["source_name"] for item in restored["items"]] == ["one.wav", "two.wav"]
    assert [item["status"] for item in restored["items"]] == ["configure", "configure"]
    assert list_batch_sessions(output_root)[0]["session_id"] == session["session_id"]


def test_submit_links_canonical_job_and_keeps_siblings_independent(tmp_path: Path) -> None:
    output_root, destination, session = _create_session(tmp_path)
    executor = RecordingExecutor()
    ctx = _submit_context(
        output_root,
        {
            "display_title": "Первый",
            "final_markdown_dir": str(destination),
            "asr_model_name": "large-v3",
        },
        executor,
    )

    response = job_endpoints.submit_batch_session_item_endpoint(
        ctx, session["session_id"], "item-1"
    )
    job_id = response.payload["job"]["job_id"]
    restored = load_batch_session(output_root, session["session_id"])
    job = load_job(output_root, job_id)

    assert response.status == 202
    assert restored is not None
    assert restored["items"][0]["job_id"] == job_id
    assert restored["items"][0]["status"] == "processing"
    assert restored["items"][1]["status"] == "configure"
    assert job is not None
    assert job["metadata"]["batch_session_id"] == session["session_id"]
    assert job["metadata"]["batch_item_id"] == "item-1"
    assert len(executor.calls) == 1
    assert executor.calls[0][2]["final_markdown_dir"] == str(destination)

    next_destination = tmp_path / "next-saved"
    next_destination.mkdir()
    updated = job_endpoints.update_batch_session_output_endpoint(
        SimpleNamespace(
            output_root=output_root,
            read_json_object=lambda: {"common_output_dir": str(next_destination)},
        ),
        session["session_id"],
    ).payload["batch_session"]
    assert updated["items"][0]["output_dir"] == str(destination)
    assert updated["items"][1]["output_dir"] == str(next_destination)


def test_native_json_submit_inherits_persisted_item_path(tmp_path: Path) -> None:
    output_root, destination, session = _create_session(tmp_path)
    executor = RecordingExecutor()
    ctx = SimpleNamespace(
        output_root=output_root,
        app_config=_config(output_root),
        executor=executor,
        headers={"Content-Type": "application/json"},
        read_json_object=lambda: {
            "display_title": "Первый",
            "final_markdown_dir": str(destination),
        },
        read_job_request=lambda: (_ for _ in ()).throw(AssertionError("wrong parser")),
    )

    response = job_endpoints.submit_batch_session_item_endpoint(
        ctx, session["session_id"], "item-1"
    )

    assert response.status == 202
    assert response.payload["job"]["source_paths"][0].endswith("one.wav")


def test_concurrent_submit_creates_only_one_canonical_attempt(tmp_path: Path) -> None:
    output_root, destination, session = _create_session(tmp_path)
    executor = RecordingExecutor()

    def submit():
        return job_endpoints.submit_batch_session_item_endpoint(
            _submit_context(
                output_root,
                {"display_title": "one", "final_markdown_dir": str(destination)},
                executor,
            ),
            session["session_id"],
            "item-1",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    restored = load_batch_session(output_root, session["session_id"])

    assert sorted(response.status for response in responses) == [202, 400]
    assert restored is not None
    assert len(restored["items"][0]["attempt_job_ids"]) == 1
    assert len(executor.calls) == 1


def test_unconfigured_items_must_start_in_order(tmp_path: Path) -> None:
    output_root, destination, session = _create_session(tmp_path)
    executor = RecordingExecutor()

    response = job_endpoints.submit_batch_session_item_endpoint(
        _submit_context(
            output_root,
            {"display_title": "two", "final_markdown_dir": str(destination)},
            executor,
        ),
        session["session_id"],
        "item-2",
    )
    restored = load_batch_session(output_root, session["session_id"])

    assert response.status == 400
    assert restored is not None
    assert restored["items"][1]["job_id"] is None
    assert executor.calls == []


def test_restart_reconciles_job_created_before_batch_link_write(tmp_path: Path) -> None:
    output_root, destination, session = _create_session(tmp_path)
    executor = RecordingExecutor()
    response = job_endpoints.submit_batch_session_item_endpoint(
        _submit_context(
            output_root,
            {"display_title": "one", "final_markdown_dir": str(destination)},
            executor,
        ),
        session["session_id"],
        "item-1",
    )
    payload = load_batch_session_payload(output_root, session["session_id"])
    assert payload is not None
    payload["items"][0]["job_id"] = None
    payload["items"][0]["attempt_job_ids"] = []
    write_batch_session(output_root, payload)

    reconcile_batch_session_jobs(output_root)
    restored = load_batch_session(output_root, session["session_id"])

    assert restored is not None
    assert restored["items"][0]["job_id"] == response.payload["job"]["job_id"]


def test_failed_item_retry_creates_one_new_attempt_without_touching_ready_item(
    tmp_path: Path,
) -> None:
    output_root, destination, session = _create_session(tmp_path)
    executor = RecordingExecutor()

    job_ids = []
    for item_id in ("item-1", "item-2"):
        response = job_endpoints.submit_batch_session_item_endpoint(
            _submit_context(
                output_root,
                {"display_title": item_id, "final_markdown_dir": str(destination)},
                executor,
            ),
            session["session_id"],
            item_id,
        )
        job_ids.append(response.payload["job"]["job_id"])

    failed = load_job(output_root, job_ids[0])
    ready = load_job(output_root, job_ids[1])
    assert failed is not None and ready is not None
    failed["status"] = "failed"
    ready["status"] = "completed"
    write_job_payload(output_root / job_ids[0] / "job.json", failed)
    write_job_payload(output_root / job_ids[1] / "job.json", ready)

    retry = job_endpoints.submit_batch_session_item_endpoint(
        _submit_context(
            output_root,
            {"display_title": "retry", "final_markdown_dir": str(destination)},
            executor,
        ),
        session["session_id"],
        "item-1",
    )
    restored = load_batch_session(output_root, session["session_id"])

    assert retry.status == 202
    assert restored is not None
    assert restored["items"][0]["job_id"] != job_ids[0]
    assert restored["items"][0]["attempt_job_ids"] == [job_ids[0], restored["items"][0]["job_id"]]
    assert restored["items"][1]["job_id"] == job_ids[1]
    assert restored["items"][1]["status"] == "ready"


def test_job_payload_write_never_exposes_partial_json(tmp_path: Path, monkeypatch) -> None:
    job_json = tmp_path / "job.json"
    job_json.write_text('{"status": "queued"}', encoding="utf-8")
    original_replace = Path.replace

    def inspect_before_replace(source: Path, destination: Path) -> Path:
        assert read_json_file(destination, None) == {"status": "queued"}
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", inspect_before_replace)
    write_job_payload(job_json, {"status": "completed"})

    assert read_json_file(job_json, None) == {"status": "completed"}


def test_restart_marks_only_active_batch_job_failed_and_restores_queue(tmp_path: Path) -> None:
    output_root, destination, session = _create_session(tmp_path)
    executor = RecordingExecutor()
    response = job_endpoints.submit_batch_session_item_endpoint(
        _submit_context(
            output_root,
            {"display_title": "one", "final_markdown_dir": str(destination)},
            executor,
        ),
        session["session_id"],
        "item-1",
    )

    mark_interrupted_jobs(output_root)
    restored = load_batch_session(output_root, session["session_id"])

    assert response.status == 202
    assert restored is not None
    assert [item["status"] for item in restored["items"]] == ["failed", "configure"]
    assert restored["totals"] == {
        "total": 2,
        "configure": 1,
        "processing": 0,
        "ready": 0,
        "failed": 1,
    }

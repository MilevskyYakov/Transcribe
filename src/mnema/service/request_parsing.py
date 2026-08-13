"""Request-body parsing helpers for the local API."""

from __future__ import annotations

import json
import shutil
import warnings
from pathlib import Path
from typing import IO, Any, Protocol, cast
from uuid import uuid4

from .types import JsonObject

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=DeprecationWarning, message="'cgi' is deprecated.*")
    import cgi


class HeadersLike(Protocol):
    def get(self, name: str, default: str = "") -> str: ...


def read_json_object(headers: HeadersLike, rfile: IO[bytes]) -> JsonObject:
    length = int(headers.get("Content-Length", "0"))
    raw_body = rfile.read(length) if length else b"{}"
    payload = json.loads(raw_body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")
    return payload


def read_job_request(headers: HeadersLike, rfile: IO[bytes], upload_root: Path) -> JsonObject:
    content_type = headers.get("Content-Type", "")
    if content_type.startswith("multipart/form-data"):
        return read_multipart_job_request(headers, rfile, upload_root)
    payload = read_json_object(headers, rfile)
    if not payload.get("input_path"):
        raise ValueError("'input_path' is required.")
    return payload


def read_multipart_job_request(headers: HeadersLike, rfile: IO[bytes], upload_root: Path) -> JsonObject:
    form = cgi.FieldStorage(
        fp=cast(IO[Any], rfile),
        headers=cast(Any, headers),
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": headers.get("Content-Type", ""),
        },
    )
    return payload_from_multipart_form(form, upload_root)


def payload_from_multipart_form(form: Any, upload_root: Path) -> JsonObject:
    media_item = form["media"] if "media" in form else None
    if media_item is None or not getattr(media_item, "filename", None):
        raise ValueError("multipart field 'media' is required.")

    request_root = upload_root / uuid4().hex
    request_root.mkdir(parents=True)
    source_filename = Path(media_item.filename).name
    media_path = _store_upload(media_item, request_root, f"media{Path(source_filename).suffix}")

    payload: JsonObject = {
        "input_path": str(media_path),
        "source_filename": source_filename,
    }
    for field_name, payload_key in [
        ("speaker_hint", "speaker_hint"),
        ("asr_backend", "asr_backend"),
        ("asr_model_name", "asr_model_name"),
        ("final_markdown_dir", "final_markdown_dir"),
    ]:
        value = field_value(form, field_name)
        if value:
            payload[payload_key] = value

    payload["display_title"] = (
        field_value(form, "display_title")
        or field_value(form, "title")
        or Path(source_filename).stem
    )

    speaker_item = form["speaker_manifest"] if "speaker_manifest" in form else None
    if speaker_item is not None and getattr(speaker_item, "filename", None):
        speaker_path = _store_upload(
            speaker_item,
            request_root,
            f"speaker_manifest{Path(speaker_item.filename).suffix}",
        )
        payload["speaker_manifest_path"] = str(speaker_path)
    return payload


def _store_upload(item: Any, request_root: Path, storage_name: str) -> Path:
    path = request_root / storage_name
    partial_path = path.with_name(f".{path.name}.part")
    with partial_path.open("wb") as handle:
        shutil.copyfileobj(item.file, handle)
    partial_path.replace(path)
    return path


def field_value(form: Any, name: str) -> str | None:
    if name not in form:
        return None
    item = form[name]
    value = getattr(item, "value", None)
    return value if isinstance(value, str) and value.strip() else None

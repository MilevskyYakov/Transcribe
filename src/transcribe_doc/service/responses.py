"""Response mapping and request-derived config helpers for the local API."""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from transcribe_doc.app.config import AppConfig

from .types import JsonObject


def config_for_payload(config: AppConfig, payload: JsonObject) -> AppConfig:
    backend = payload.get("asr_backend")
    model_name = payload.get("asr_model_name")
    if not isinstance(backend, str) and not isinstance(model_name, str):
        return config
    next_asr = replace(
        config.asr,
        backend=backend.strip() if isinstance(backend, str) and backend.strip() else config.asr.backend,
        model_name=model_name.strip()
        if isinstance(model_name, str) and model_name.strip()
        else config.asr.model_name,
    )
    return replace(config, asr=next_asr)


def display_title_from_payload(payload: JsonObject) -> str | None:
    value = payload.get("display_title") or payload.get("title")
    return value.strip() if isinstance(value, str) and value.strip() else None


def job_to_response(job: Any) -> JsonObject:
    if isinstance(job, dict):
        return dict(job)
    return {
        "job_id": job.job_id,
        "source_paths": job.source_paths,
        "status": job.status.value,
        "detected_language": job.detected_language,
        "artifacts": asdict(job.artifacts),
        "metadata": job.metadata,
        "warnings": job.warnings,
    }


def batch_to_response(result: Any) -> JsonObject:
    return {
        "exit_code": result.exit_code,
        "total": result.total,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "report_path": str(result.report_path),
        "items": [asdict(item) for item in result.items],
    }

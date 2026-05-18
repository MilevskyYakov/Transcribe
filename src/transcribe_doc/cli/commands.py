"""Command handlers for the local transcription application."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from transcribe_doc.app.config import AppConfig
from transcribe_doc.asr.factory import build_asr_backend
from transcribe_doc.core.batch import process_batch, process_directory, scan_watch_folder
from transcribe_doc.core.processing import process_single_file
from transcribe_doc.diarization.factory import build_diarization_backend
from transcribe_doc.service.server import run_server


def run_command(args: argparse.Namespace, config: Optional[AppConfig] = None) -> int:
    if config is None:
        raise ValueError("Resolved config is required for the run command.")

    result = process_single_file(
        args.input_path,
        output_root=Path(args.out or config.app.output_dir),
        config=config,
        speaker_manifest_path=args.speaker_manifest,
        speaker_hint=args.speaker_hint,
        formats=args.formats,
        asr_backend_factory=build_asr_backend,
        diarization_backend_factory=build_diarization_backend,
    )
    print(result.message)
    return result.exit_code


def batch_command(args: argparse.Namespace, config: Optional[AppConfig] = None) -> int:
    if config is None:
        raise ValueError("Resolved config is required for the batch command.")
    result = process_batch(
        args.input_paths,
        output_root=Path(args.out or config.app.output_dir),
        config=config,
        speaker_manifest_path=args.speaker_manifest,
        speaker_hint=args.speaker_hint,
        formats=args.formats,
    )
    print(f"Batch report: {result.report_path} ({result.succeeded}/{result.total} succeeded)")
    return result.exit_code


def dir_command(args: argparse.Namespace, config: Optional[AppConfig] = None) -> int:
    if config is None:
        raise ValueError("Resolved config is required for the dir command.")
    result = process_directory(
        args.input_dir,
        output_root=Path(args.out or config.app.output_dir),
        config=config,
        recursive=args.recursive,
        speaker_manifest_path=args.speaker_manifest,
        speaker_hint=args.speaker_hint,
        formats=args.formats,
    )
    print(f"Directory report: {result.report_path} ({result.succeeded}/{result.total} succeeded)")
    return result.exit_code


def watch_command(args: argparse.Namespace, config: Optional[AppConfig] = None) -> int:
    if config is None:
        raise ValueError("Resolved config is required for the watch command.")
    result = scan_watch_folder(
        args.input_dir,
        output_root=Path(args.out or config.app.output_dir),
        config=config,
        recursive=args.recursive,
        stability_seconds=args.watch_stability_seconds,
        speaker_manifest_path=args.speaker_manifest,
        speaker_hint=args.speaker_hint,
        formats=args.formats,
    )
    print(f"Watch scan report: {result.report_path} ({result.succeeded}/{result.total} succeeded)")
    return result.exit_code


def serve_command(args: argparse.Namespace, config: Optional[AppConfig] = None) -> int:
    if config is None:
        raise ValueError("Resolved config is required for the serve command.")
    run_server(config=config, host=args.host, port=args.port)
    return 0

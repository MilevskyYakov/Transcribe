"""Argparse-based CLI scaffold for the transcription service."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from transcribe_doc.app.config import AppConfig, config_for_app_data_dir, load_config
from transcribe_doc.app.constants import APP_NAME, DEFAULT_CONFIG_PATH
from transcribe_doc.app.exceptions import CommandNotImplementedError, ConfigurationError
from transcribe_doc.app.logging import configure_logging
from transcribe_doc.cli import commands

CommandHandler = Callable[[argparse.Namespace, AppConfig | None], int]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="Local-first transcription scaffold.")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to YAML config file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    _build_run_parser(subparsers)
    _build_batch_parser(subparsers)
    _build_dir_parser(subparsers)
    _build_watch_parser(subparsers)
    _build_serve_parser(subparsers)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        app_data_dir = getattr(args, "app_data_dir", None)
        if app_data_dir:
            app_data_path = Path(app_data_dir).expanduser()
            config = config_for_app_data_dir(config, app_data_path)
            os.environ["XDG_CACHE_HOME"] = str(app_data_path / "cache")
            os.environ["TRANSCRIBE_DOC_MODEL_DIR"] = str(app_data_path / "models")
        media_bin_dir = getattr(args, "media_bin_dir", None)
        if media_bin_dir:
            current_path = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{Path(media_bin_dir).expanduser()}{os.pathsep}{current_path}"
    except ConfigurationError as error:
        parser.exit(status=2, message=f"{error}\n")

    handler_map: Dict[str, CommandHandler] = {
        "run": commands.run_command,
        "batch": commands.batch_command,
        "dir": commands.dir_command,
        "watch": commands.watch_command,
        "serve": commands.serve_command,
    }

    try:
        return handler_map[args.command](args, config)
    except CommandNotImplementedError as error:
        print(error, file=sys.stderr)
        return 1


def console_main() -> None:
    raise SystemExit(main())


def _build_run_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("run", help="Process a single media file.")
    parser.add_argument("input_path", nargs="?", help="Path to the media file.")
    _add_common_processing_arguments(parser)


def _build_batch_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("batch", help="Process multiple media files.")
    parser.add_argument("input_paths", nargs="*", help="Paths to media files.")
    _add_common_processing_arguments(parser)


def _build_dir_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("dir", help="Process files from a directory.")
    parser.add_argument("input_dir", nargs="?", help="Directory with media files.")
    _add_common_processing_arguments(parser)
    parser.add_argument("--recursive", action="store_true", help="Scan directories recursively.")


def _build_watch_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("watch", help="Watch a directory for new media files.")
    parser.add_argument("input_dir", nargs="?", help="Directory to watch.")
    _add_common_processing_arguments(parser)
    parser.add_argument(
        "--watch-stability-seconds",
        type=int,
        default=None,
        help="Override file stability delay before processing.",
    )
    parser.add_argument("--recursive", action="store_true", help="Scan directories recursively.")


def _build_serve_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("serve", help="Start the local mini-service.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    parser.add_argument(
        "--app-data-dir",
        default=None,
        help="Store runtime output, temp files, and model cache under this app data directory.",
    )
    parser.add_argument(
        "--media-bin-dir",
        default=None,
        help="Prepend this directory to PATH so bundled ffmpeg and ffprobe are discovered.",
    )


def _add_common_processing_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", default=None, help="Output directory.")
    parser.add_argument("--language", default=None, help="Force transcription language.")
    parser.add_argument("--model", default=None, help="Override ASR model name.")
    parser.add_argument("--preset", default="default", help="Named processing preset.")
    parser.add_argument("--num-speakers", default=None, help="Expected number of speakers.")
    parser.add_argument("--speaker-hint", default=None, help="Free-form participant hint, e.g. 'Яков и Никита'.")
    parser.add_argument("--speaker-manifest", default=None, help="Advanced: path to speaker manifest JSON.")
    parser.add_argument("--formats", default=None, help="Comma-separated export formats.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary files.")
    parser.add_argument("--save-artifacts", action="store_true", help="Save intermediate artifacts.")
    parser.add_argument("--device", default=None, help="Override runtime device.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs.")


if __name__ == "__main__":
    console_main()

import os
import subprocess
import sys
from pathlib import Path

import pytest

from transcribe_doc.cli.main import build_parser, main


def test_parser_defines_required_commands() -> None:
    parser = build_parser()
    subparsers_action = next(
        action for action in parser._actions if getattr(action, "choices", None)
    )

    assert {"run", "batch", "dir", "watch", "serve"} <= set(subparsers_action.choices)


def test_help_lists_core_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 0
    assert "run" in captured.out
    assert "serve" in captured.out


def test_serve_accepts_app_packaging_overrides() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--config",
            "configs/default.yaml",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--app-data-dir",
            "/tmp/transcribe-doc-app",
            "--media-bin-dir",
            "/tmp/transcribe-doc-bin",
        ]
    )

    assert args.command == "serve"
    assert args.app_data_dir == "/tmp/transcribe-doc-app"
    assert args.media_bin_dir == "/tmp/transcribe-doc-bin"


def test_python_module_invocation_executes_cli_help() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    result = subprocess.run(
        [sys.executable, "-m", "transcribe_doc.cli.main", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "run" in result.stdout
    assert "serve" in result.stdout

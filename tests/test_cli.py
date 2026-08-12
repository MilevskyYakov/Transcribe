import os
import subprocess
import sys
from pathlib import Path

import pytest

from mnema.cli import commands
from mnema.cli.main import build_parser, main


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
            "/tmp/mnema-app",
            "--media-bin-dir",
            "/tmp/mnema-bin",
        ]
    )

    assert args.command == "serve"
    assert args.app_data_dir == "/tmp/mnema-app"
    assert args.media_bin_dir == "/tmp/mnema-bin"


def test_serve_app_data_dir_sets_durable_model_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "old-cache"))
    monkeypatch.setenv("MNEMA_MODEL_DIR", str(tmp_path / "old-models"))
    monkeypatch.setattr(commands, "serve_command", lambda args, config: 0)

    result = main(
        [
            "--config",
            "configs/default.yaml",
            "serve",
            "--app-data-dir",
            str(tmp_path / "app-data"),
        ]
    )

    assert result == 0
    assert os.environ["XDG_CACHE_HOME"] == str(tmp_path / "app-data" / "cache")
    assert os.environ["MNEMA_MODEL_DIR"] == str(tmp_path / "app-data" / "models")


def test_python_module_invocation_executes_cli_help() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    result = subprocess.run(
        [sys.executable, "-m", "mnema.cli.main", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "mnema" in result.stdout
    assert "run" in result.stdout
    assert "serve" in result.stdout


def test_legacy_module_help_redirects_to_mnema() -> None:
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
    assert "mnema" in result.stdout

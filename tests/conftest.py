from pathlib import Path
from typing import Any

import pytest

from support.run_command import RunCommandHarness


@pytest.fixture
def run_cli(tmp_path: Path, monkeypatch: Any) -> RunCommandHarness:
    return RunCommandHarness(tmp_path, monkeypatch)

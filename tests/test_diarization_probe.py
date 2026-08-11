import json
import subprocess
import sys
from pathlib import Path


def test_probe_reproduces_overlap_and_short_interruption_failures() -> None:
    root = Path(__file__).parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts/diarization_probe.py"), str(root / "tests/fixtures/diarization_probe.json")],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)["candidates"]

    current = {fixture["name"]: fixture for fixture in result["current"]["fixtures"]}
    assert current["overlap"]["false_label_rate"] == 0.5
    assert current["rapid_aba_interruption"]["speaker_turn_accuracy"] == 0.667
    assert result["current"]["reliable_labels_precision"] == 1.0
    assert result["current"]["degraded_mode_precision"] == 0.667
    assert result["without_smoothing"]["mean_speaker_turn_accuracy"] > result["current"]["mean_speaker_turn_accuracy"]
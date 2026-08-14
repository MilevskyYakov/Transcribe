import json
import subprocess
import sys
from pathlib import Path


def test_build_update_feed_keeps_macos_and_windows(tmp_path: Path) -> None:
    signature = tmp_path / "artifact.sig"
    signature.write_text("signed-value\n", encoding="utf-8")
    output = tmp_path / "latest.json"
    script = Path(__file__).parents[1] / "scripts" / "build-update-feed.py"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--version",
            "0.2.0",
            "--notes",
            "Signed release",
            "--pub-date",
            "2026-08-14T00:00:00Z",
            "--platform",
            f"darwin-aarch64=https://example.test/Mnema.app.tar.gz={signature}",
            "--platform",
            f"windows-x86_64=https://example.test/Mnema-setup.exe={signature}",
            "--output",
            str(output),
        ],
        check=True,
    )

    feed = json.loads(output.read_text(encoding="utf-8"))
    assert set(feed["platforms"]) == {"darwin-aarch64", "windows-x86_64"}
    assert feed["platforms"]["windows-x86_64"]["signature"] == "signed-value"

    incomplete = subprocess.run(
        [
            sys.executable,
            str(script),
            "--version",
            "0.2.0",
            "--pub-date",
            "2026-08-14T00:00:00Z",
            "--platform",
            f"darwin-aarch64=https://example.test/Mnema.app.tar.gz={signature}",
            "--output",
            str(output),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert incomplete.returncode != 0
    assert "updater platforms must be exactly" in incomplete.stderr

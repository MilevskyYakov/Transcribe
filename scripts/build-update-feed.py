#!/usr/bin/env python3
"""Build a Tauri static updater feed from signed artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_platform(value: str) -> tuple[str, str, Path]:
    try:
        name, url, signature_path = value.split("=", 2)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected PLATFORM=URL=SIGNATURE_FILE") from error
    if not name or not url.startswith("https://"):
        raise argparse.ArgumentTypeError("platform and HTTPS URL are required")
    return name, url, Path(signature_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--pub-date", required=True)
    parser.add_argument("--platform", action="append", type=parse_platform, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    platforms: dict[str, dict[str, str]] = {}
    for name, url, signature_path in args.platform:
        if name in platforms:
            raise SystemExit(f"duplicate updater platform: {name}")
        signature = signature_path.read_text(encoding="utf-8").strip()
        if not signature:
            raise SystemExit(f"empty updater signature: {signature_path}")
        platforms[name] = {"signature": signature, "url": url}
    required_platforms = {"darwin-aarch64", "windows-x86_64"}
    if set(platforms) != required_platforms:
        raise SystemExit(
            "updater platforms must be exactly: " + ", ".join(sorted(required_platforms))
        )

    feed = {
        "version": args.version,
        "notes": args.notes,
        "pub_date": args.pub_date,
        "platforms": platforms,
    }
    args.output.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

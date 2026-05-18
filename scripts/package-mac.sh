#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$HOME/.cargo/env" ]; then
  # rustup updates PATH for the whole packaging process, including Tauri CLI.
  # shellcheck source=/dev/null
  . "$HOME/.cargo/env"
fi

cd "$ROOT_DIR/frontend"
"$ROOT_DIR/scripts/setup-tauri-prereqs.sh"
"$ROOT_DIR/scripts/build-embedded-runtime.sh"
npm run tauri:build

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAURI_DIR="$ROOT_DIR/frontend/src-tauri"
RESOURCES_DIR="$TAURI_DIR/resources"
PYTHON_DIR="$RESOURCES_DIR/python"
BIN_DIR="$RESOURCES_DIR/bin"
BINARY_DIR="$TAURI_DIR/binaries"
CONFIG_DIR="$RESOURCES_DIR/configs"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

mkdir -p "$BIN_DIR" "$BINARY_DIR" "$CONFIG_DIR"
cp "$ROOT_DIR/configs/default.yaml" "$CONFIG_DIR/default.yaml"

if [ ! -x "$PYTHON_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$PYTHON_DIR"
fi

"$PYTHON_DIR/bin/python" -m pip install --upgrade pip wheel
"$PYTHON_DIR/bin/python" -m pip uninstall -y transcribe-doc >/dev/null 2>&1 || true
"$PYTHON_DIR/bin/python" -m pip install "$ROOT_DIR"

for tool in ffmpeg ffprobe; do
  tool_path="$(command -v "$tool" || true)"
  if [ -z "$tool_path" ]; then
    echo "Missing $tool. Install it with Homebrew before packaging." >&2
    exit 1
  fi
  cp "$tool_path" "$BIN_DIR/$tool"
  cp "$tool_path" "$BINARY_DIR/$tool-aarch64-apple-darwin"
  chmod 755 "$BIN_DIR/$tool"
  chmod 755 "$BINARY_DIR/$tool-aarch64-apple-darwin"
  xattr -c "$BIN_DIR/$tool" 2>/dev/null || true
  xattr -c "$BINARY_DIR/$tool-aarch64-apple-darwin" 2>/dev/null || true
done

echo "Embedded runtime prepared in $RESOURCES_DIR"

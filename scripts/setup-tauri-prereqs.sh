#!/usr/bin/env bash
set -euo pipefail

if { ! command -v rustc >/dev/null 2>&1 || ! command -v cargo >/dev/null 2>&1; } \
  && [ -f "$HOME/.cargo/env" ]; then
  # rustup installs Cargo there, but non-login shells do not always load it.
  # shellcheck source=/dev/null
  . "$HOME/.cargo/env"
fi

if ! command -v rustc >/dev/null 2>&1 || ! command -v cargo >/dev/null 2>&1; then
  echo "Rust toolchain is required for Tauri builds."
  echo "Install with: brew install rustup-init && rustup-init"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required for frontend and Tauri CLI commands."
  exit 1
fi

host_tuple="$(rustc --print host-tuple 2>/dev/null || rustc -Vv | awk '/host:/ {print $2}')"
if [ "$host_tuple" != "aarch64-apple-darwin" ]; then
  echo "Expected Apple Silicon target aarch64-apple-darwin, got $host_tuple"
  exit 1
fi

echo "Tauri prerequisites ready for $host_tuple"

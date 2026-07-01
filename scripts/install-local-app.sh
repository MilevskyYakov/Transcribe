#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Transcribe Doc"
APP_BUNDLE_NAME="$APP_NAME.app"
DEFAULT_INSTALL_DIR="/Applications"
BUNDLE_RELATIVE_PATH="frontend/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/$APP_BUNDLE_NAME"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

build_app=true
open_after_install=true
quit_running=false
install_dir="$DEFAULT_INSTALL_DIR"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Build and install the local macOS Tauri app bundle.

Options:
  --no-build         Install an already built app bundle without running package:mac.
  --no-open          Do not open the app after installation.
  --quit-running     Quit a running Transcribe Doc app before replacing it.
  --install-dir DIR  Install into DIR instead of /Applications.
  -h, --help         Show this help.
EOF
}

fail() {
  echo "install-local-app: $*" >&2
  exit 1
}

is_app_running() {
  pgrep -x "$APP_NAME" >/dev/null 2>&1 || pgrep -x "transcribe-doc" >/dev/null 2>&1
}

quit_app() {
  osascript -e "tell application \"$APP_NAME\" to quit" >/dev/null 2>&1 || true

  for _ in {1..20}; do
    if ! is_app_running; then
      return 0
    fi
    sleep 0.5
  done

  return 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --no-build)
      build_app=false
      ;;
    --no-open)
      open_after_install=false
      ;;
    --quit-running)
      quit_running=true
      ;;
    --install-dir)
      shift
      [ "$#" -gt 0 ] || fail "--install-dir requires a directory argument"
      install_dir="$1"
      ;;
    --install-dir=*)
      install_dir="${1#--install-dir=}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
  shift
done

if [ "$build_app" = true ]; then
  echo "Building $APP_BUNDLE_NAME with npm run package:mac..."
  (cd "$ROOT_DIR/frontend" && npm run package:mac)
fi

built_app="$ROOT_DIR/$BUNDLE_RELATIVE_PATH"
installed_app="$install_dir/$APP_BUNDLE_NAME"
backup_app=""

[ -d "$built_app" ] || fail "built app bundle not found: $built_app"
[ -d "$install_dir" ] || fail "install directory does not exist: $install_dir"

if is_app_running; then
  if [ "$quit_running" != true ]; then
    fail "$APP_NAME is running. Quit it first or pass --quit-running."
  fi

  echo "Quitting running $APP_NAME..."
  quit_app || fail "could not quit $APP_NAME; stop it manually and retry"
fi

tmp_parent="$(mktemp -d "${TMPDIR:-/tmp}/transcribe-doc-install.XXXXXX")"
cleanup() {
  rm -rf "$tmp_parent"
}
trap cleanup EXIT

restore_backup() {
  if [ -n "$backup_app" ] && [ -d "$backup_app" ]; then
    rm -rf "$installed_app"
    mv "$backup_app" "$installed_app"
  fi
}

if [ -e "$installed_app" ]; then
  backup_app="$tmp_parent/$APP_BUNDLE_NAME.backup"
  echo "Moving existing app to temporary backup..."
  mv "$installed_app" "$backup_app"
fi

if ! ditto "$built_app" "$installed_app"; then
  echo "Install failed; restoring previous app if available..." >&2
  restore_backup
  exit 1
fi

if [ -n "$backup_app" ]; then
  rm -rf "$backup_app"
fi

xattr -dr com.apple.quarantine "$installed_app" >/dev/null 2>&1 || true

echo "Installed $installed_app"

if [ "$open_after_install" = true ]; then
  open "$installed_app"
fi

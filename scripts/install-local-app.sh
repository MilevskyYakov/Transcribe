#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Mnema"
APP_BUNDLE_NAME="$APP_NAME.app"
DEFAULT_INSTALL_DIR="/Applications"
BUNDLE_RELATIVE_PATH="frontend/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/$APP_BUNDLE_NAME"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

build_app=true
open_after_install=true
quit_running=false
install_dir="$DEFAULT_INSTALL_DIR"
tmp_parent="$(mktemp -d "${TMPDIR:-/tmp}/mnema-install.XXXXXX")"
original_tauri_conf=""
local_signing_key=""
local_signing_password=""

cleanup() {
  if [ -n "$original_tauri_conf" ] && [ -f "$original_tauri_conf" ]; then
    cp "$original_tauri_conf" "$ROOT_DIR/frontend/src-tauri/tauri.conf.json"
  fi
  rm -rf "$tmp_parent"
}
trap cleanup EXIT

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Build and install the local macOS Tauri app bundle.

Options:
  --no-build         Install an already built app bundle without running package:mac.
  --no-open          Do not open the app after installation.
  --quit-running     Quit a running Mnema app before replacing it.
  --install-dir DIR  Install into DIR instead of /Applications.
  -h, --help         Show this help.
EOF
}

fail() {
  echo "install-local-app: $*" >&2
  exit 1
}

prepare_local_updater_signing() {
  local tauri_conf="$ROOT_DIR/frontend/src-tauri/tauri.conf.json"

  if [ -n "${TAURI_SIGNING_PRIVATE_KEY:-}" ]; then
    return 0
  fi
  if ! grep -q '"pubkey"' "$tauri_conf"; then
    return 0
  fi

  echo "No TAURI_SIGNING_PRIVATE_KEY set; generating temporary local updater key for this install..."
  original_tauri_conf="$tmp_parent/tauri.conf.json.original"
  local_signing_key="$tmp_parent/local-updater.key"
  local_signing_password="$(uuidgen)"
  cp "$tauri_conf" "$original_tauri_conf"

  (cd "$ROOT_DIR/frontend" && npx tauri signer generate --ci -f -p "$local_signing_password" -w "$local_signing_key" >/dev/null)
  python3 - "$tauri_conf" "$local_signing_key.pub" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
pubkey_path = Path(sys.argv[2])
config = json.loads(config_path.read_text())
config.setdefault("plugins", {}).setdefault("updater", {})["pubkey"] = pubkey_path.read_text().strip()
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
PY

  export TAURI_SIGNING_PRIVATE_KEY="$local_signing_key"
  export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="$local_signing_password"
}

repair_installed_python_venv() {
  local app_path="$1"
  local python_dir="$app_path/Contents/Resources/resources/python"
  local bin_dir="$python_dir/bin"
  local cfg="$python_dir/pyvenv.cfg"
  local target_python=""

  [ -f "$cfg" ] || return 0
  [ -d "$bin_dir" ] || return 0

  target_python="$(python3 - "$cfg" <<'PY'
import sys
from pathlib import Path

cfg = Path(sys.argv[1])
values = {}
for line in cfg.read_text().splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

for candidate in [values.get("executable"), str(Path(values.get("home", "")) / "python3.11")]:
    if candidate and Path(candidate).exists():
        print(candidate)
        break
PY
)"

  if [ -z "$target_python" ]; then
    echo "Warning: could not repair embedded Python symlinks; base interpreter from $cfg was not found." >&2
    return 0
  fi

  rm -f "$bin_dir/python" "$bin_dir/python3" "$bin_dir/python3.11"
  ln -s python3.11 "$bin_dir/python"
  ln -s python3.11 "$bin_dir/python3"
  ln -s "$target_python" "$bin_dir/python3.11"
}

is_app_running() {
  pgrep -x "$APP_NAME" >/dev/null 2>&1 || pgrep -x "mnema" >/dev/null 2>&1 || pgrep -x "Transcribe Doc" >/dev/null 2>&1
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

stop_orphaned_backends() {
  local pid=""
  local parent_pid=""

  while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    parent_pid="$(ps -p "$pid" -o ppid= | tr -d ' ' || true)"
    if [ "$parent_pid" = "1" ]; then
      echo "Stopping orphaned backend process $pid..."
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done < <(pgrep -f '(mnema|transcribe_doc)\.cli\.main.*--app-data-dir .*local\.(mnema|transcribe-doc)' || true)
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
  prepare_local_updater_signing
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
stop_orphaned_backends

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
repair_installed_python_venv "$installed_app"

echo "Installed $installed_app"

if [ "$open_after_install" = true ]; then
  open "$installed_app"
fi

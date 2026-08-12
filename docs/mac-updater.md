# Signed macOS in-app updater

Mnema uses the Tauri v2 updater for the packaged macOS app. The updater is only a desktop-app feature; the browser dashboard remains a development surface and does not install app updates.

## Release hosting

Default endpoint in `frontend/src-tauri/tauri.conf.json`:

```text
https://github.com/MilevskyYakov/Mnema/releases/latest/download/latest.json
```

The default strategy is a static `latest.json` attached to the latest GitHub Release. If this project later moves to a dedicated HTTPS update server, keep TLS enabled and update only the `plugins.updater.endpoints` list.

## Signing keys and secret boundary

Tauri requires every update artifact to be signed. Signature verification must not be disabled.

- `plugins.updater.pubkey` in `frontend/src-tauri/tauri.conf.json` is public and safe to commit.
- `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` are secrets and must never be committed, pasted into Issues/chats, or stored in `.env` files.
- For production releases, store the private key only in GitHub Actions secrets or another release-secret manager.
- If you rotate the private key, update the committed public key before shipping an app that should trust future releases signed by that key.

Generate keys outside the repo. For CI/non-interactive release builds, create a password-protected key and store both the key and password in the release-secret manager:

```bash
cd frontend
npx tauri signer generate --ci -p '<strong-password>' -w ~/.tauri/mnema-updater.key
```

Then copy only the generated public key into `frontend/src-tauri/tauri.conf.json` → `plugins.updater.pubkey`. Do not commit `~/.tauri/mnema-updater.key`.

## Local/staging signed build

```bash
cd frontend
export TAURI_SIGNING_PRIVATE_KEY="$HOME/.tauri/mnema-updater.key"
# export TAURI_SIGNING_PRIVATE_KEY_PASSWORD="..."  # only if the key has a password
npm run package:mac
```

With `bundle.createUpdaterArtifacts=true`, macOS builds create the normal `.app` plus updater artifacts under `frontend/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/`:

- `Mnema.app`
- `Mnema.app.tar.gz`
- `Mnema.app.tar.gz.sig`

## `latest.json` shape for GitHub Releases

For Apple Silicon macOS, attach a `latest.json` similar to:

```json
{
  "version": "0.2.0",
  "notes": "Release notes for users.",
  "pub_date": "2026-07-03T00:00:00Z",
  "platforms": {
    "darwin-aarch64": {
      "signature": "CONTENTS_OF_Mnema.app.tar.gz.sig",
      "url": "https://github.com/MilevskyYakov/Mnema/releases/download/v0.2.0/Mnema.app.tar.gz"
    }
  }
}
```

The `signature` value is the content of the `.sig` file, not a path or URL.

## Manual app-first smoke

1. Build and install version A with `npm run install:local`.
2. Download at least one ASR model and confirm `/models` or the UI shows it as `ready`.
3. Save settings and create or keep one user output/history item.
4. Bump the app version for version B in `frontend/src-tauri/tauri.conf.json` and `frontend/package.json` when appropriate.
5. Build B with signing env set and publish `Mnema.app.tar.gz`, its `.sig`, and `latest.json` to the release endpoint.
6. Open installed app A, use the sidebar update card, and install B.
7. Restart the app when prompted.
8. Confirm the backend is online, the previously downloaded model is still `ready`, settings are preserved, and user output/history is still available.

If code signing/notarization for public macOS distribution is not configured yet, treat it as a release prerequisite. Do not bypass updater signatures or commit private keys to make the smoke easier.

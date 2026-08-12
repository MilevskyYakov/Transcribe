# Security Policy

Mnema is a local-first desktop app. Please do not upload private audio, transcripts, API keys, personal documents, or other sensitive data to public GitHub Issues, Pull Requests, or Discussions.

## Reporting a vulnerability

If you find a security issue, create a minimal report that avoids private data:

- describe the affected feature and expected impact;
- include safe reproduction steps using dummy files or synthetic data;
- do not attach real recordings, transcripts, secrets, private keys, or personal documents.

If a report requires sensitive material, contact the maintainer privately instead of posting it publicly.

## Local data boundary

The app is designed to process media locally on macOS. Downloaded ASR models, settings, transcripts, and job history live in the app-managed local data area and should not be committed to this repository.

## Updater signing keys

Tauri updater private keys are secrets. Never commit or paste `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`, `.key`, `.key.pass`, or equivalent signing material into GitHub.

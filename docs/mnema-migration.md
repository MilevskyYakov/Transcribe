# Mnema rename and local-data migration

## Identifier inventory before rename

| Surface | Legacy identifier |
| --- | --- |
| Python distribution / namespace / CLI | `transcribe-doc`, `transcribe_doc`, `transcribe-doc` |
| Model environment / fallback cache | `TRANSCRIBE_DOC_MODEL_DIR`, `~/.cache/transcribe-doc/models` |
| Tauri product / bundle / app-data | `Transcribe Doc`, `local.transcribe-doc` |
| Rust package / executable / sidecar | `transcribe-doc`, `transcribe-doc-backend` |
| Browser storage | `transcribe-doc-api-base`, `transcribe-doc-default-model`, `transcribe-doc-autosave-markdown-dir` |
| Installer | `Transcribe Doc.app` and matching process patterns |
| Updater repository | `MilevskyYakov/Transcribe` |

## Active identifiers after rename

| Surface | Canonical identifier |
| --- | --- |
| Python distribution / namespace / CLI | `mnema`, `mnema`, `mnema` |
| Model environment / fallback cache | `MNEMA_MODEL_DIR`, `~/.cache/mnema/models` |
| Tauri product / bundle / app-data | `Mnema`, `local.mnema` |
| Rust package / executable / sidecar | `mnema`, `mnema-backend` |
| Browser storage | `mnema-api-base`, `mnema-default-model`, `mnema-autosave-markdown-dir` |
| Installer | `Mnema.app` |
| Updater repository | `MilevskyYakov/Transcribe` (repository rename is outside scope) |

## Upgrade behavior

On first Mnema startup, Tauri copies files missing from the legacy `local.transcribe-doc` app-data tree into `local.mnema`. Existing Mnema files win, old files remain untouched, and each file is installed through a temporary path before rename. This preserves output history, `settings.json`, temporary job state, and durable `models` without deleting the old installation data. Repeated startup is safe.

The backend still discovers the old external-model cache and accepts `TRANSCRIBE_DOC_MODEL_DIR` when `MNEMA_MODEL_DIR` is absent. Browser mode lazily copies legacy storage values into Mnema keys. The old `transcribe-doc` command and `transcribe_doc` imports remain compatibility aliases to the canonical `mnema` implementation.

Clean installations create only Mnema active paths. Legacy names remain only in this migration/compatibility contract, installer cleanup, and tests.

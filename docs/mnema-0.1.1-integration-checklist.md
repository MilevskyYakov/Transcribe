# Mnema 0.1.1 integration checklist

Проверено 2026-08-12 на macOS Apple Silicon, commit `df8bc61` плюс integration fix этой ветки.

## Automated suite

- Backend: `142 passed`; mypy: `76 source files`, ошибок нет.
- Frontend: `38 passed`; Playwright: `3 passed`; production build passed.
- Rust: `cargo fmt --check`; `cargo test`: `1 passed`.
- Tauri: `Mnema.app` и updater archive собраны. Production updater signature не проверена без owner key.

## Packaged app

- Bundle: `CFBundleDisplayName=Mnema`, `CFBundleIdentifier=local.mnema`, executables `mnema` и `mnema-backend`.
- Embedded backend поднялся на `127.0.0.1`; `/health` подтвердил `local.mnema`, bundled ffmpeg/ffprobe и canonical model directory.
- App открыл экран «Новая транскрипция» с migrated history и без backend error.
- Single fixture завершён; Markdown сохранён в выбранную папку после speaker review skip.
- Batch из 3 fixtures: `2 ready + 1 failed`; retry создал второй attempt только failed item. После restart session восстановилась как `3 ready`, attempts `1/2/1`. Найдена race при чтении `job.json`; JSON writes переведены на temporary-file replace.
- Reliable fixture показал speaker review. Degraded label gate покрыт calibration fixture и backend/frontend regression tests.
- Notification active/inactive/denied behavior покрыт unit contract. Фактический macOS permission reset не выполнялся, чтобы не менять пользовательские system settings.

## Upgrade

- Existing `local.transcribe-doc` history/settings/models migrated в `local.mnema`; packaged app увидел 79 jobs, default `large-v3`, 7 models.
- Повторный startup безопасен; новые Mnema files имеют приоритет, legacy data не удаляются.

## Не закрыто

- Clean-machine gate остаётся отдельным release check: текущий smoke выполнен на developer Mac с временной установкой bundle.
- Production updater требует owner `TAURI_SIGNING_PRIVATE_KEY` и опубликованный `latest.json`.
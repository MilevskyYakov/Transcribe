# Test Plan

## Source
- Task: подготовить и проверить локальное macOS desktop app для транскрибации с diarization
- Plan file: `docs/plans.md`
- Status file: `docs/status.md`
- Repo context: app-first локальный продукт с Python pipeline, local API и Tauri shell
- Last updated: 2026-05-14

## Validation Scope
- In scope: Tauri app bootstrap, transcript/job schema, ingest/media pipeline, ASR/alignment/diarization fallback paths, exporter contracts, local API, browser dev dashboard, watch-folder behavior, README-driven smoke checks.
- Out of scope: benchmark-гонка за максимальной скоростью, облачные backends, live microphone transcription, custom model training.

## Environment / Fixtures
- Data fixtures: короткие sample files для `single speaker`, `two speakers`, `video input`, `broken/unsupported file`, `watch-folder incoming copy`.
- External dependencies: `ffmpeg`, локальные Python-библиотеки ASR/diarization/export, macOS Apple Silicon runtime.
- Setup assumptions: Python 3.11+, доступный `ffmpeg` в PATH, presets `default` и `lightweight_test`, локальный output/temp paths.

## Test Levels

### Unit
- Загрузка и валидация YAML-конфига.
- Path/job resolution и генерация артефактных путей.
- Media probe и normalization command builder.
- Transcript cleanup и almost-verbatim guards.
- Speaker merge and mapping logic.
- Exporter formatting для `json`, `txt`, `md`, `srt`.

### Integration
- Single-file pipeline с audio input.
- Video ingest с extraction + normalization.
- Multi-speaker pipeline с diarization merge.
- Fallback без diarization.
- Fallback без alignment.
- Fallback без summary.
- DOCX/PDF generation из общей transcript model.
- API lifecycle: create job, poll status, list artifacts.
- API observability: list structured job events and inspect job log artifacts.
- App/frontend API client: bootstrap, health, jobs, transcript, artifacts, upload job, model defaults.

### End-to-End / Smoke
- CLI `run` создаёт job directory и обязательные outputs.
- CLI `batch` продолжает работу при ошибке одного файла.
- CLI `watch` корректно обрабатывает файл после stability window.
- Service `serve` отвечает на `GET /health` и принимает `POST /jobs`.
- Tauri app builds or smoke-runs when local prerequisites are available.
- App UI renders and shows the upload/job/transcript shell.
- App UI shows processing progress and event timeline.
- README onboarding проходит без скрытых ручных шагов.

## Negative / Edge Cases
- Неподдерживаемый формат файла.
- Повреждённый media file.
- Отсутствие `ffmpeg`.
- Diarization backend unavailable.
- Summary backend unavailable.
- PDF export failure при сохранении остальных форматов.
- Низкая уверенность speaker mapping и fallback к `SPEAKER_00`.
- Повторное появление того же файла в watch folder.

## Acceptance Gates
- [ ] `python -m ruff check src tests`
- [ ] `python -m mypy src`
- [ ] `python -m pytest`
- [ ] `python -m transcribe_doc.cli.main run sample_data/dialogue.mp3 --out ./output`
- [ ] `python -m transcribe_doc.cli.main serve --host 127.0.0.1 --port 8765`
- [ ] `cd frontend && npm test`
- [ ] `cd frontend && npm run build`
- [ ] `cd frontend && npm run tauri:build`
- [ ] `cd frontend && npm run e2e`

## Release / Demo Readiness
- [ ] Single-file user path работает end-to-end
- [ ] Batch path не ломается на одном ошибочном файле
- [ ] Watch-folder сценарий воспроизводим локально
- [ ] Local API отражает реальные job statuses
- [ ] Tauri app creates a single-file job and shows transcript/artifacts
- [ ] Browser dashboard remains available as dev/debug mode
- [ ] README покрывает установку, запуск и troubleshooting

## Command Matrix
```sh
python -m pytest tests/test_config.py tests/test_models.py
python -m pytest tests/test_ingest.py tests/test_media.py
python -m pytest tests/test_pipeline_smoke.py tests/test_cleanup.py tests/test_speaker_merge.py
python -m pytest tests/test_exports.py tests/test_summary.py tests/test_schema.py
python -m pytest tests/test_batch.py tests/test_watch_folder.py tests/test_service_api.py tests/test_service_smoke.py
python -m ruff check src tests
python -m mypy src
python -m transcribe_doc.cli.main run sample_data/dialogue.mp3 --out ./output --speaker-manifest sample_data/speakers.json --save-artifacts
python -m transcribe_doc.cli.main serve --host 127.0.0.1 --port 8765
cd frontend && npm test
cd frontend && npm run build
cd frontend && npm run tauri:build
cd frontend && npm run e2e
```

## Open Risks
- Ещё не выбран конкретный backend stack, поэтому часть тестов пока формулируется на уровне контрактов и fallback-поведения.
- Тяжёлые модели могут сделать smoke-тесты слишком медленными без отдельного lightweight preset.
- PDF/DOCX экспорты могут потребовать платформенно-зависимую стабилизацию на macOS.

## Deferred Coverage
- Performance/regression benchmarks на длинных файлах.
- Packaging checks для canonical desktop app.
- Полная автоматизация качества summary beyond structural validity.

# Plans

## Source
- Task: построить план разработки локального macOS mini-service для транскрибации аудио/видео с diarization
- Canonical input: `task.md`, `README.md`, `decisions.md`, `acceptance_checklist.md`
- Repo context: стартовый репозиторий требований без исходного кода
- Last updated: 2026-04-18

## Execution Analysis
- Требования уже хорошо зафиксированы на продуктном уровне, поэтому главный риск не в нехватке требований, а в неправильной очередности реализации и выборе хрупкого speech-стека.
- План разбит по зависимостям: сначала каркас проекта, единая модель данных и конфиг; затем single-file pipeline как минимальный сквозной путь; после этого экспорты и деградации; затем batch/watch/service; в финале стабилизация, документация и приёмка.
- Так как кодовой базы и команд проверки ещё нет, первые milestone одновременно создают репозиторный каркас, pyproject, конфиги, sample data и базовую test harness.

## Assumptions
- Целевая реализация будет на Python 3.11+ под macOS Apple Silicon.
- Репозиторий пока не является git-репозиторием; это не блокирует планирование, но стоит исправить до начала активной разработки.
- MVP сначала оптимизируется под локальный sequential execution с `max_parallel_jobs=1`.
- Диаризация и alignment проектируются как опциональные слои с fallback, если локальный backend окажется нестабилен или потребует внешний токен.
- Summary в MVP допустимо реализовать через локальный extractive pipeline или локальный LLM-адаптер с отключаемым режимом.
- Frontend начинается как локальный web dashboard поверх mini-service API и проектируется так, чтобы позже его можно было упаковать в desktop app через Tauri/Electron.

## Validation Assumptions
- После появления Python-проекта валидация будет опираться на `pytest`, `ruff`, `mypy` и smoke-команды CLI.
- Для тяжёлых E2E-проверок понадобится отдельный набор sample media короткой длительности и lightweight preset.
- Проверки качества PDF/DOCX будут частично структурными, а не только побайтными.

## Milestone Order
| ID | Title | Depends on | Status |
| --- | --- | --- | --- |
| M1 | Project skeleton and runtime contracts | - | [x] |
| M2 | Single-file ingest and normalization pipeline | M1 | [x] |
| M3 | ASR, alignment, diarization, and transcript shaping | M2 | [ ] |
| M4 | Stable outputs and exporter layer | M3 | [x] |
| M5 | Batch, directory, and watch-folder orchestration | M4 | [x] |
| M6 | Local mini-service API and job lifecycle | M4 | [~] |
| M7 | App UI and local dashboard frontend | M6 | [x] |
| M8 | Hardening, tests, and operational docs | M5, M6, M7 | [ ] |

## M1. Project skeleton and runtime contracts `[x]`
### Goal
- Создать рабочий каркас проекта, в котором уже определены структура пакетов, конфиг, логирование, модели job/transcript и единые интерфейсы backend-слоёв.

### Tasks
- [ ] Инициализировать Python-проект (`pyproject.toml`, package layout, dev tooling).
- [ ] Создать каталоги `configs/`, `src/`, `tests/`, `scripts/`, `sample_data/`, `output/`, `tmp/`.
- [ ] Реализовать базовые модули `app.config`, `app.logging`, `app.exceptions`, `app.models`, `app.constants`.
- [ ] Определить внутреннюю transcript/job schema: `Job`, `JobStatus`, `TranscriptSegment`, `WordToken`, `SpeakerMapping`, `ArtifactManifest`.
- [ ] Описать абстракции для `asr`, `alignment`, `diarization`, `summary`, `export`.
- [ ] Добавить стартовые YAML-конфиги: `default`, `high_quality`, `batch`, `watch_folder`.
- [ ] Подготовить базовые CLI entrypoints и пустые команды с понятными сообщениями `not implemented`.

### Definition of Done
- В репозитории есть исполнимый Python-каркас и единая структура директорий.
- Базовый импорт пакета и загрузка конфига проходят без ошибки.
- Внутренние модели и абстракции достаточны, чтобы на них строить последующие стадии без крупных переделок.

### Validation
```sh
python -m pytest tests/test_config.py tests/test_models.py
python -m ruff check src tests
python -m mypy src
python -m transcribe_doc.cli.main --help
```

### Known Risks
- Если schema будет слишком бедной, позже экспорт и сервис начнут тащить несовместимые представления данных.
- Неверный выбор базовой структуры пакетов усложнит app packaging и sidecar runtime.

### Stop-and-Fix Rule
- Если конфиг, модели или CLI skeleton не проходят базовую проверку, не переходить к pipeline-этапам.

## M2. Single-file ingest and normalization pipeline `[x]`
### Goal
- Дать системе надёжный путь обработки одного файла: intake, probe, extraction/normalization, рабочая директория job и сохранение артефактов этапа.

### Tasks
- [ ] Реализовать `input_resolver`, `manifest_loader`, `job_manager`, `artifact_store`, `paths`.
- [ ] Реализовать media probe, извлечение аудио и нормализацию через `ffmpeg`.
- [ ] Добавить сохранение `job.json`, `config snapshot`, extracted/normalized audio и per-job logs.
- [ ] Поддержать single-file режим CLI `transcribe-doc run`.
- [ ] Добавить валидацию входных форматов и понятные ошибки для неподдерживаемых файлов.

### Definition of Done
- Один локальный файл проходит через создание job и media normalization.
- Для job создаётся предсказуемая файловая структура и артефакты стадии ingest/media.
- Ошибки в файле или `ffmpeg` логируются и отражаются в статусе job.

### Validation
```sh
python -m pytest tests/test_ingest.py tests/test_media.py
python -m transcribe_doc.cli.main run sample_data/sample.mp4 --out ./output --formats json --save-artifacts
```

### Known Risks
- Неправильная обработка контейнеров и нестабильных копирований позже сломает batch/watch.
- Без хорошей модели артефактов будет трудно делать partial success и переэкспорт.

### Stop-and-Fix Rule
- Если single-file intake или normalization нестабильны, не подключать ASR и последующие слои.

## M3. ASR, alignment, diarization, and transcript shaping `[ ]`
### Goal
- Построить quality-first распознавание с almost-verbatim transcript, word/segment timestamps, speaker labels и корректным degraded mode.

### Tasks
- [ ] Реализовать ASR backend abstraction и baseline whisper-compatible backend.
- [ ] Добавить transcript orchestration service для raw transcript и detected language.
- [ ] Реализовать alignment слой с coarse fallback при недоступности word timestamps.
- [ ] Реализовать diarization abstraction, merge со segment timeline и speaker mapping на expected names.
- [ ] Реализовать conservative cleanup: dual text representation, merge adjacent same-speaker, мягкая пунктуация.
- [ ] Зафиксировать правила degraded mode: transcript-only, coarse timestamps, no-summary-ready path.

### Definition of Done
- На sample media получается transcript с raw/clean текстом, сегментами и speaker labels/fallback labels.
- При падении alignment/diarization job не разваливается полностью и сохраняет полезный результат.
- Cleanup не нарушает stated transcript policy из `task.md`.

### Validation
```sh
python -m pytest tests/test_pipeline_smoke.py tests/test_cleanup.py tests/test_speaker_merge.py
python -m transcribe_doc.cli.main run sample_data/dialogue.mp3 --out ./output --speaker-manifest sample_data/speakers.json --save-artifacts
```

### Known Risks
- Локальный diarization backend может оказаться самым хрупким местом MVP.
- Слишком агрессивный cleanup легко нарушит продуктовую цель "почти дословно".

### Stop-and-Fix Rule
- Если transcript policy или degraded mode не подтверждены тестами, не переходить к полноформатным экспортам.

## M4. Stable outputs and exporter layer `[x]`
### Goal
- Сделать единый export layer, который строит все выходные форматы из общей transcript model и сохраняет стабильный JSON schema.

### Tasks
- [x] Реализовать exporters для `json`, `txt`, `md`, `srt`, `docx`, `pdf`.
- [x] Зафиксировать schema для `job.json`, `transcript_raw.json`, `segments.json`, `words.json`, `summary.json`.
- [x] Реализовать summary layer и генерацию `summary.md`/`summary.json`.
- [x] Добавить baseline formatting rules для DOCX/PDF и список warnings/diagnostics.
- [x] Реализовать selective export по `--formats`.

### Definition of Done
- Для успешного job формируются все обязательные пользовательские и технические выходы.
- JSON schema стабильна и отделена от конкретного backend-а.
- Падение необязательного экспортера не ломает остальные форматы.

### Validation
```sh
python -m pytest tests/test_exports.py tests/test_summary.py tests/test_schema.py
python -m transcribe_doc.cli.main run sample_data/dialogue.mp3 --out ./output --formats txt,md,docx,pdf,srt,json
```

### Known Risks
- Разные форматы могут начать расходиться по содержимому, если не держать их на одной transcript model.
- PDF/DOCX часто вносят тяжёлые системные зависимости и требуют отдельной стабилизации.

### Stop-and-Fix Rule
- Если schema и обязательные outputs расходятся или экспорт частично ломает job, исправить до добавления orchestration-режимов.

## M5. Batch, directory, and watch-folder orchestration `[x]`
### Goal
- Расширить одиночный pipeline до batch list, directory mode и watch folder с безопасной обработкой новых файлов.

### Tasks
- [x] Реализовать batch loader и directory traversal с фильтрацией поддерживаемых форматов.
- [x] Добавить batch lifecycle: независимые file jobs, частичные ошибки, общий отчёт batch.
- [x] Реализовать watch-folder scan, stability window и перемещение в `processed/` / `failed/`.
- [x] Поддержать CLI-команды `batch`, `dir`, `watch`.
- [x] Добавить базовую защиту от повторной обработки через `processed/` / `failed/` buckets.

### Definition of Done
- Список файлов и директория обрабатываются без остановки на одном упавшем элементе.
- Watch folder корректно ждёт завершения копирования и логирует каждый job.
- Все результаты сохраняются в той же модели артефактов, что и single-file path.

### Validation
```sh
python -m pytest tests/test_batch.py tests/test_watch_folder.py
python -m transcribe_doc.cli.main batch sample_data/a.mp3 sample_data/b.mp4 --out ./output
python -m transcribe_doc.cli.main dir sample_data/incoming --out ./output --recursive
```

### Known Risks
- Watch folder часто ломается на гонках записи и повторном захвате файла.
- Batch без ограничений по памяти может быть нестабилен на длинных файлах.

### Stop-and-Fix Rule
- Если один файл всё ещё валит весь batch или watch mode читает незавершённый файл, не двигаться дальше.

## M6. Local mini-service API and job lifecycle `[ ]`
### Goal
- Поднять локальный API для постановки job, получения статуса и просмотра артефактов на основе уже существующего pipeline.

### Tasks
- [x] Реализовать service app, request/response schemas и handlers для single-file dashboard slice.
- [x] Добавить endpoints `POST /jobs`, `GET /jobs/{job_id}`, `GET /jobs/{job_id}/artifacts`, `POST /batch`, `POST /watch-folder/scan`, `GET /health`.
- [x] Добавить dashboard endpoints `GET /jobs`, `GET /jobs/{job_id}/transcript` и artifact download.
- [x] Ограничить binding локальным интерфейсом по умолчанию.
- [x] Добавить async queue/serial executor для долгих jobs.
- [x] Синхронизировать статусы CLI и API вокруг одной job-state модели для single-file path.

### Definition of Done
- Локальный сервис создаёт и отслеживает jobs без дублирования логики pipeline.
- API отражает реальные статусы job и список артефактов.
- Сервис не открывается наружу по умолчанию.

### Validation
```sh
python -m pytest tests/test_service_api.py
python -m transcribe_doc.cli.main serve --host 127.0.0.1 --port 8765
python -m pytest tests/test_service_smoke.py
```

### Known Risks
- Если service слой начнёт дублировать orchestration, сопровождение быстро подорожает.
- Непродуманная очередь может создать висящие jobs и неочевидные статусы.

### Stop-and-Fix Rule
- Если API не использует общую lifecycle/job model или нарушает local-only assumption, исправить до финальной стабилизации.

## M7. App UI and local dashboard frontend `[x]`
### Goal
- Добавить UI для canonical desktop app и browser dev dashboard: создать job, отследить статус, посмотреть transcript, warnings/diagnostics и скачать артефакты.

### Tasks
- [x] Создать `frontend/` как TypeScript web-приложение.
- [x] Реализовать API client для `transcribe-doc serve`.
- [x] Реализовать upload/start-job flow для single-file MVP.
- [x] Реализовать job list и job detail view.
- [x] Реализовать transcript viewer для `segments.json` и `words.json`.
- [x] Реализовать diagnostics/artifacts panel.
- [x] Сделать конфигурацию API base URL без hard-code публичных endpoints.
- [x] Подготовить и поддерживать структуру для Tauri app как основной версии продукта.

### Definition of Done
- Пользователь может пройти основной сценарий через приложение: выбрать файл, запустить обработку, увидеть статус и прочитать результат.
- Frontend не дублирует pipeline logic и работает только через локальный API.
- UI остаётся local-first и не требует аккаунтов, токенов или внешних сервисов.

### Validation
```sh
python -m transcribe_doc.cli.main serve --host 127.0.0.1 --port 8765
cd frontend
npm test
npm run build
npm run e2e
```

### Known Risks
- Если API lifecycle будет нестабилен, UI начнёт компенсировать backend-логику и станет хрупким.
- App runtime станет хрупким, если frontend привязать к browser-only assumptions или публичным URL.

### Stop-and-Fix Rule
- Если основной single-file job нельзя создать и просмотреть через app UI поверх локального API, не переходить к финальной приёмке.

## M8. Hardening, tests, and operational docs `[ ]`
### Goal
- Довести MVP до приёмочного состояния: тесты, smoke-сценарии, README, troubleshooting и операционные сценарии запуска.

### Tasks
- [ ] Закрыть acceptance checklist по критичным разделам A, C, E, F, G, H, J, K, P.
- [ ] Добавить unit/integration/smoke tests для fallback-paths и schema validation.
- [ ] Подготовить sample data, test fixtures и lightweight preset для CI/local smoke.
- [ ] Обновить README: install, ffmpeg, CLI, service mode, frontend, watch folder, outputs, limitations, troubleshooting, transcript policy, JSON schema overview.
- [ ] Зафиксировать known limitations и backlog для packaged desktop app.

### Definition of Done
- Критичные acceptance criteria подтверждены командами и/или ручными smoke checks.
- Репозиторий можно локально развернуть и прогнать по README без восстановления контекста из чата.
- Остаточные ограничения явно задокументированы и не маскируются под готовую функциональность.

### Validation
```sh
python -m pytest
python -m ruff check src tests
python -m mypy src
python -m transcribe_doc.cli.main run sample_data/dialogue.mp3 --out ./output
python -m transcribe_doc.cli.main serve --host 127.0.0.1 --port 8765
cd frontend && npm run build
cd frontend && npm run tauri:build
```

### Known Risks
- Без минимального набора sample fixtures тесты будут слишком тяжёлыми и нестабильными.
- Есть риск "формально пройти чеклист", не проверив реальный пользовательский путь end-to-end.

### Stop-and-Fix Rule
- Если основной app/API сценарий не воспроизводится по README, MVP нельзя считать готовым.

# acceptance_checklist.md

## Цель

Этот чеклист нужен для ручной и полуавтоматической проверки того, что MVP соответствует требованиям.

## A. Платформа и запуск

- [x] Проект запускается локально на macOS Apple Silicon
- [x] Используется Python 3.11+ или задокументированная совместимая версия
- [x] Есть инструкция запуска в README
- [x] Есть конфиг по умолчанию
- [x] Проект не требует облачных API
- [x] Проект не требует обязательных внешних аккаунтов или токенов

## B. Архитектура

- [x] Главная версия проекта — Tauri desktop app
- [x] Проект использует local mini-service API как backend приложения
- [x] CLI и browser dashboard остаются поддерживающими/dev-интерфейсами
- [x] Кодовая база модульная
- [x] ASR вынесен в abstraction layer
- [x] Diarization вынесен в abstraction layer
- [x] Export layer отделён от transcript model
- [x] Код содержит Tauri shell и app bootstrap для desktop runtime

## C. Входные режимы

- [x] Поддерживается single file mode
- [x] Поддерживается batch mode по списку файлов
- [x] Поддерживается directory batch mode
- [x] Поддерживается watch folder mode

## D. Входные форматы

- [x] Поддерживается mp3
- [x] Поддерживается wav
- [x] Поддерживается m4a
- [x] Поддерживается aac
- [x] Поддерживается flac
- [x] Поддерживается ogg
- [x] Поддерживается mp4
- [x] Поддерживается mov
- [x] Поддерживается mkv
- [x] Поддерживается avi
- [x] Поддерживается webm

## E. Pipeline stages

- [x] Есть media normalization
- [x] Есть ASR stage
- [x] Есть alignment stage или documented fallback
- [x] Есть diarization stage или documented fallback
- [x] Есть conservative transcript shaping
- [x] Есть summary stage
- [x] Есть export stage

## F. Transcript quality policy

- [x] Transcript почти дословный
- [x] Нет агрессивного литературного переписывания
- [x] Смысл речи сохраняется
- [x] Слова-паразиты не удаляются по умолчанию
- [x] Хранятся `text_raw` и `text_clean`

## G. Speaker handling

- [x] В результате есть speaker labels
- [x] Можно передать expected speaker names заранее
- [x] Есть mapping machine label -> display label
- [x] При низкой уверенности проект не выдумывает имена
- [x] Допустим fallback к `SPEAKER_00`, `SPEAKER_01` и т.д.

## H. Выходные форматы

- [x] Генерируется `transcript_clean.txt`
- [x] Генерируется `transcript_clean.md`
- [x] Генерируется `transcript_clean.docx`
- [x] Генерируется `transcript_clean.pdf`
- [x] Генерируется `subtitles.srt`
- [x] Генерируется `transcript_raw.json`
- [x] Генерируется `segments.json`
- [x] Генерируется `summary.md`
- [x] Генерируется `summary.json`

## I. Intermediate artifacts

- [ ] Сохраняется extracted audio
- [x] Сохраняется normalized audio
- [x] Сохраняется raw transcript dump
- [ ] Сохраняется aligned transcript dump
- [x] Сохраняется diarization dump
- [ ] Сохраняется merged transcript dump
- [x] Сохраняются logs
- [x] Сохраняется snapshot конфига job

## J. Service API

- [x] Есть `POST /jobs`
- [x] Есть `GET /jobs/{job_id}`
- [x] Есть `GET /jobs/{job_id}/artifacts`
- [x] Есть `POST /batch`
- [x] Есть `POST /watch-folder/scan`
- [x] Есть `GET /health`
- [x] API по умолчанию слушает только локальный интерфейс

## K. CLI

- [x] Есть команда для single-file обработки
- [x] Есть команда для batch обработки
- [x] Есть команда для directory mode
- [x] Есть команда для watch folder
- [x] Есть команда для запуска сервиса
- [x] CLI поддерживает `--speaker-manifest`
- [x] CLI поддерживает `--formats`
- [x] CLI поддерживает `--keep-temp`
- [x] CLI поддерживает `--save-artifacts`

## L. Надёжность

- [x] Один упавший файл не валит весь batch
- [x] При падении diarization возможен transcript-only fallback
- [x] При падении alignment возможен coarse-timestamp fallback
- [x] При падении summary основной результат сохраняется
- [ ] При падении PDF остальные форматы сохраняются
- [x] Есть понятные статусы job
- [x] Долгие jobs выполняются в background executor и не блокируют HTTP request
- [x] Есть структурированные события прогресса по этапам pipeline

## M. Логи и диагностика

- [x] Есть console logs
- [ ] Есть file logs per job
- [ ] Логируется время этапов
- [x] Логируется detected language
- [ ] Логируется число сегментов
- [ ] Логируется число спикеров
- [x] Логируются degraded mode warnings
- [x] Логируются пути к выходным артефактам
- [x] События job доступны через API и сохраняются в `events.jsonl`

## N. Тесты

- [x] Есть unit tests
- [x] Есть integration tests
- [x] Есть smoke tests
- [x] Проверяется JSON schema
- [x] Проверяется watch folder сценарий
- [x] Проверяется fallback без diarization
- [ ] Проверяется fallback без summary

## O. README

- [x] README описывает назначение проекта
- [x] README содержит инструкции установки
- [x] README содержит примеры CLI-команд
- [x] README содержит описание service mode
- [x] README содержит описание frontend mode
- [x] README содержит описание watch folder
- [x] README содержит список выходных файлов
- [ ] README содержит troubleshooting
- [x] README описывает transcript policy
- [ ] README описывает JSON schema overview

## P. Frontend

- [x] Есть `frontend/` приложение
- [x] Frontend обслуживает Tauri app и browser dev dashboard поверх local service API
- [x] Можно создать single-file job через UI
- [x] Можно видеть список jobs и статусы
- [x] Можно открыть transcript segments
- [x] Можно увидеть warnings/diagnostics
- [x] Можно скачать доступные артефакты
- [x] API base URL конфигурируется локально
- [x] Frontend не требует облачных API, аккаунтов или токенов
- [x] Архитектура frontend поддерживает canonical Tauri app runtime

## Q. Desktop app

- [x] Есть `frontend/src-tauri` shell
- [x] App запускает backend sidecar на локальном порту
- [x] App bootstrap отдаёт API base URL, app data dir, output dir, cache dir и media tools status
- [x] Можно выбрать модель по умолчанию через app settings
- [x] Локальный `npm run tauri:build` собирает `.app`
- [ ] Bundle smoke подтверждён на чистой машине

## R. Mnema release candidate 0.1.1 (2026-08-12)

- [x] `Mnema.app`, `local.mnema`, `mnema` и `mnema-backend` используются как active identifiers
- [x] Upgrade fixture сохраняет history, settings, default/output folders и models из `local.transcribe-doc`
- [x] Packaged app запускает embedded backend, видит bundled ffmpeg/ffprobe и открывает New screen
- [x] Single job проходит processing/result и сохраняет Markdown в выбранную папку
- [x] Batch из 3 файлов изолирует failure; retry создаёт новый attempt только failed item
- [x] Batch/history/job state переживают restart через durable API storage
- [x] Unreliable diarization скрывает ложные labels; reliable result допускает review
- [x] Notifications покрыты focus/dedupe/aggregation tests; permission denied не блокирует processing
- [ ] Updater проверен с production signing key и опубликованным release feed
- [ ] Полный clean-machine smoke выполнен вне developer Mac

Версионированный factual evidence: `docs/mnema-0.1.1-integration-checklist.md`.

## Exit criteria

MVP можно считать принятым, если:
- все критичные пункты из разделов A, C, E, F, G, H, J, K, P, Q выполнены;
- невыполненные пункты задокументированы и не блокируют основную пользовательскую ценность;
- проект реально даёт локальный quality-first transcript pipeline без ручной сборки результата.

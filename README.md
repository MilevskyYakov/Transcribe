# Transcribe Doc macOS app

Проект предназначен для локальной обработки аудио- и видеофайлов на macOS Apple Silicon с получением почти дословного транскрипта, diarization, summary и экспортов в несколько форматов.

## Что делает проект

Система принимает медиафайл или набор файлов, извлекает и нормализует аудио, распознаёт речь, определяет смены спикеров, собирает структурированный transcript и сохраняет результат в человекочитаемом и техническом виде.

Главная версия продукта — локальное macOS desktop-приложение на Tauri. Поддерживающие режимы работы:
- один файл;
- список файлов;
- директория;
- watch folder;
- локальный mini-service API;
- browser dashboard для разработки и диагностики.

## Цели

- локальная обработка без облачных API;
- приоритет качества;
- пригодность для личного использования через desktop app;
- app-first архитектура: UI, local API и pipeline разделены, но пользовательский путь проектируется вокруг Tauri app;
- JSON-совместимость для дальнейшей автоматизации.

## Планируемые форматы входа

### Audio
- mp3
- wav
- m4a
- aac
- flac
- ogg

### Video
- mp4
- mov
- mkv
- avi
- webm

## Форматы выхода

- txt
- md
- docx
- pdf
- srt
- json

Во время обработки приложение создаёт промежуточные артефакты:
extracted/normalized audio, raw ASR payload, diarization dump, logs/events и
config snapshot. После успешного завершения job эти internal/session файлы
автоматически удаляются. Постоянно сохраняются только пользовательские результаты
и компактные данные, нужные для app history, просмотра transcript и повторного
сохранения результата: final markdown, выбранные exports, `segments.json`,
`words.json`, summary и `job.json`.

Failed jobs могут временно сохранять диагностический минимум. Старые failed/orphan
temp files удаляются retention cleanup'ом. Локальные ASR-модели хранятся в
durable app data/cache directory и не попадают под cleanup временных job-файлов.

## Архитектурная идея

Pipeline:

`input -> ffmpeg normalization -> ASR -> alignment -> diarization -> speaker merge -> conservative cleanup -> summary -> export`

Ключевая идея: не строить систему вокруг одной “магической” модели, а разделять проект на независимые слои, чтобы можно было менять backend без переписывания всего приложения.

## Основные свойства

- local-first;
- canonical Tauri desktop app;
- local mini-service API как backend приложения;
- CLI и browser dashboard как поддерживающие/dev-интерфейсы;
- batch processing;
- watch folder;
- almost-verbatim transcript;
- diarization;
- summary;
- stable JSON schema;
- graceful degradation.

## Transcript policy

Итоговый transcript должен быть почти дословным:
- не переписывать содержание литературно;
- не удалять слова-паразиты по умолчанию;
- не менять смысл;
- допускать только мягкую нормализацию пробелов, пунктуации и сегментов.

Хранить два представления:
- `text_raw`
- `text_clean`

## Speaker policy

Система должна:
- автоматически выполнять diarization;
- поддерживать передачу expected speaker names заранее;
- сопоставлять имена только при достаточной уверенности;
- не выдумывать сопоставление.

## Пример структуры проекта

```text
project-root/
  task.md
  README.md
  decisions.md
  acceptance_checklist.md
  configs/
  frontend/
  src/
  tests/
  output/
  tmp/
```

## Пример CLI

### Один файл
```bash
transcribe-doc run input.mp4 --out ./output
```

### Несколько файлов
```bash
transcribe-doc batch ./a.mp4 ./b.mp3 --out ./output
```

### Папка
```bash
transcribe-doc dir ./incoming --out ./output
```

### Watch folder
```bash
transcribe-doc watch ./incoming --out ./output
```

### Локальный сервис
```bash
transcribe-doc serve --host 127.0.0.1 --port 8765
```

## App и frontend

Главная пользовательская поверхность — Tauri desktop app. Он сам запускает локальный backend на свободном `127.0.0.1` порту, хранит runtime data в macOS Application Support и использует тот же React UI поверх local service API.

Browser frontend остаётся dev/debug режимом поверх `transcribe-doc serve`. Он тонкий: не запускает speech pipeline напрямую, а работает через локальный API и общую job-state модель.

Первый экран приложения:
- загрузка одного media-файла;
- необязательная подсказка по участникам обычным текстом, например `Яков и Никита`;
- список последних jobs и их статусов;
- просмотр transcript segments/words;
- просмотр warnings/diagnostics;
- скачивание доступных артефактов.

Архитектурное ограничение: UI обслуживает canonical desktop app и не должен зависеть от облачных API, внешней авторизации, публичных URL или прямого доступа к Python internals.

## Подсказка по спикерам

Спикеры определяются автоматически. Поле участников в интерфейсе можно оставить пустым.
Если известно, кто был на встрече, можно написать обычной фразой: `вот был Яков и Никита на встрече`.
Эта подсказка используется для человекочитаемых имён в результате, но не требует JSON-файлов.

Для продвинутых CLI-сценариев всё ещё поддерживается JSON-файл через `--speaker-manifest`.

```json
{
  "expected_speakers": [
    { "name": "Алексей", "role": "Интервьюер" },
    { "name": "Марина", "role": "Кандидат" }
  ]
}
```

## Пример выходных файлов на один job

```text
output/<job_id>/
  job.json
  segments.json
  words.json
  final_speech_text.md
  transcript_clean.txt
  transcript_clean.md
  transcript_clean.docx
  transcript_clean.pdf
  subtitles.srt
  summary.md
  summary.json
  artifacts/        # только временные diagnostics во время processing/failed retention
```

## Локальная установка

Целевая платформа:
- macOS Apple Silicon
- Python 3.11+

На macOS не используйте системный `/usr/bin/python3` для команд проекта: он
может быть Python 3.9 и не соответствует `pyproject.toml`. В репозитории есть
`.python-version` со значением `3.11`; используйте Homebrew/uv/pyenv Python 3.11
и проектный virtualenv.

Нужно предусмотреть:
- установку `ffmpeg`;
- установку Python-зависимостей;
- конфиг через YAML;
- локальное хранение временных и выходных файлов.

### Backend

```bash
uv venv --python python3.11 .venv
uv pip install -e ".[dev]"
.venv/bin/python -m transcribe_doc.cli.main --help
```

`uv pip` здесь намеренно используется вместо `.venv/bin/python -m pip`: `uv venv`
может создать окружение без установленного `pip`, но `uv pip install ...` всё равно
ставит зависимости в проектный `.venv`.

Для обычной работы можно активировать окружение один раз:

```bash
source .venv/bin/activate
python --version  # должно быть 3.11+
pytest
```

### Browser dashboard для разработки

```bash
cd frontend
npm install
npm run dev
```

### Локальный запуск browser dashboard

В одном терминале:

```bash
.venv/bin/python -m transcribe_doc.cli.main serve --host 127.0.0.1 --port 8765
```

Во втором терминале:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

После этого dev dashboard доступен на `http://127.0.0.1:5173/`.

### Canonical macOS desktop `.app`

Основной target — локальный `.app` для Apple Silicon через Tauri.

```bash
cd frontend
npm ci
npm run tauri:dev
```

Для bundle-сборки нужно заранее подготовить Rust toolchain и embedded runtime:

```bash
cd frontend
npm run package:mac
```

`package:mac` проверяет Rust/npm, собирает embedded Python venv в
`frontend/src-tauri/resources/python`, копирует `configs/default.yaml`,
бандлит найденные в PATH `ffmpeg` и `ffprobe`, затем запускает Tauri build под
`aarch64-apple-darwin`.

`package:mac` только создаёт bundle в репозитории. Уже установленное приложение
в `/Applications/Transcribe Doc.app` после изменений в коде само не обновляется:
для обычного локального обновления установленного `.app` используйте:

```bash
cd frontend
npm run install:local
```

`install:local` сначала выполняет `package:mac`, затем безопасно заменяет
`/Applications/Transcribe Doc.app`, снимает quarantine metadata best-effort и
открывает приложение. Если уже запущен старый app, команда остановится с явным
сообщением; чтобы автоматически закрыть его перед заменой:

```bash
npm run install:local -- --quit-running
```

Для повторной установки уже собранного bundle из корня репозитория:

```bash
./scripts/install-local-app.sh --no-build --no-open
```

Полезные флаги: `--no-open` для automation, `--install-dir DIR` для установки не
в `/Applications`, `--help` для справки.

### Signed in-app updates

Packaged macOS app also has a Tauri v2 signed updater. In the installed app,
use the sidebar card “Обновление” to check the configured release endpoint,
show no-update/update/error states, download a signed update, and install it.
After install the app asks for a restart so the new version opens cleanly.

Default release endpoint: GitHub Releases static `latest.json` at
`https://github.com/kairosUNIVERSAL/Transcribe/releases/latest/download/latest.json`.
Updater artifacts are generated during Tauri build when the release environment
provides `TAURI_SIGNING_PRIVATE_KEY` (and optional
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD`). The private key must stay outside the repo;
only the public updater key is committed in `frontend/src-tauri/tauri.conf.json`.
Full release/update runbook: `docs/mac-updater.md`.

В desktop-режиме приложение само запускает локальный backend на свободном
`127.0.0.1` порту. Runtime data хранится в macOS Application Support:
`output`, `tmp`, `cache` и durable ASR-модели не зависят от папки репозитория.

Локальные ASR-модели в packaged desktop app — постоянные данные приложения, а
не disposable cache. Backend sidecar получает `--app-data-dir`, после чего
использует `TRANSCRIBE_DOC_MODEL_DIR=<app_data_dir>/models`: Whisper-файлы лежат
в `<app_data_dir>/models/whisper`, external/ONNX ASR runtime — в
`<app_data_dir>/models/external`. При локальном upgrade/replacement через
`npm run install:local` не удаляйте macOS Application Support; модель должна
оставаться `ready` в `/models` и в UI без повторного скачивания. Старые валидные
модели из `<app_data_dir>/cache/whisper`, `<app_data_dir>/cache/transcribe-doc/models`
или пользовательского `~/.cache` копируются в canonical model dir при проверке
статуса; повреждённые/недокачанные файлы остаются `corrupt` и не считаются
готовыми.

## Что должно быть в финальной реализации

- Tauri desktop app как главная версия продукта;
- CLI;
- mini-service;
- browser dashboard для разработки и диагностики;
- watch folder;
- batch processing;
- quality-first pipeline;
- экспорт во все заявленные форматы;
- README с инструкциями запуска;
- тесты;
- documented JSON schema.

## Проверка

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src
cd frontend && npm test
cd frontend && npm run build
cd frontend && npm run e2e
cd frontend && npm run tauri:build
```

Если `.venv` активирован, первые три команды можно запускать короче:

```bash
pytest -q
ruff check src tests
mypy src
```

## Ограничения

В MVP не требуется:
- публичный интернет-сервис;
- live microphone transcription;
- collaborative editing;
- custom model training.

## Диагностика и отказоустойчивость

Если отдельный этап упал, проект должен по возможности завершать job частично:
- без diarization;
- без alignment;
- без summary;
- без PDF.

Остальные результаты должны сохраняться, если это возможно.

## Статус проекта

Этот документ — стартовый blueprint для разработки. Подробные требования смотри в `task.md`, инженерные фиксации — в `decisions.md`, критерии проверки — в `acceptance_checklist.md`.

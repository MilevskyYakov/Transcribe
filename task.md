# Task: Локальный macOS mini-service для транскрибации аудио/видео в структурированный документ с diarization

## 1. Overview

Нужно разработать локальный проект для macOS (Apple Silicon, мощная машина), который принимает аудио- и видеофайлы в распространённых форматах, обрабатывает их локально и выдаёт:

1. почти дословный транскрипт;
2. diarization (разделение по спикерам);
3. структурированный документ для чтения человеком;
4. технический JSON для дальнейшей автоматизации;
5. summary / краткое содержание.

Проект должен быть спроектирован так, чтобы:
- уже в MVP запускаться локально;
- работать как CLI + локальный mini-service;
- поддерживать batch processing;
- поддерживать watch folder;
- быть пригодным для будущей упаковки в desktop app для личного использования.

Главный приоритет: **качество результата**, а не максимальная скорость.

## 2. Product goal

Пользователь должен иметь возможность:

- положить один или несколько файлов в папку;
- либо передать список файлов через CLI;
- либо отправить их в локальный mini-service;
- получить на выходе:
  - чистый документ с репликами по спикерам;
  - JSON со всеми сегментами, таймкодами, словами, спикерами и метаданными;
  - субтитры;
  - summary;
  - промежуточные артефакты для дебага.

## 3. High-level requirements

### 3.1 Core flow

Pipeline должен работать так:

`input media -> media normalization -> speech detection / segmentation -> ASR -> alignment -> diarization -> speaker-aware merge -> light cleanup -> summary -> export`

### 3.2 Key constraints

- Всё должно работать **локально**.
- Нельзя требовать облачные API.
- Нельзя требовать обязательные внешние аккаунты или токены.
- Архитектура должна быть модульной и пригодной для замены backend-компонентов.
- Проект должен быть ориентирован на **macOS Apple Silicon**.
- Основной язык использования: **русский**.
- Система должна корректно обрабатывать русскую речь с англицизмами и mixed vocabulary.

## 4. Explicit product decisions

### 4.1 MVP shape

MVP — это **локальный mini-service + CLI**, а не только библиотека.

### 4.2 Packaging direction

Сразу проектировать кодовую базу так, чтобы позже её можно было упаковать в desktop app.

### 4.3 Input mode

Поддержать:
- single file;
- batch processing по списку файлов;
- batch processing по директории;
- watch folder mode.

### 4.4 Transcript style

Итоговый текст должен быть **почти дословным**:
- сохранять смысл и структуру речи;
- не переписывать содержание;
- не редактировать “литературно”;
- не удалять автоматически слова-паразиты по умолчанию;
- cleanup должен быть лёгким и консервативным.

### 4.5 Speaker handling

Нужно:
- автоматическое diarization;
- возможность заранее передать список ожидаемых имён спикеров;
- возможность после diarization назначать speaker labels на заранее заданные имена;
- если точное сопоставление невозможно, оставлять `SPEAKER_00`, `SPEAKER_01`, и т.д.

### 4.6 Output formats

Обязательно поддержать:
- `docx`
- `txt`
- `json`
- `srt`
- `md`
- `pdf`

### 4.7 Summary

Нужно генерировать summary / краткое содержание на основе распознанного текста.

### 4.8 Intermediate artifacts

Нужно сохранять промежуточные артефакты для дебага и анализа качества.

## 5. Non-goals for MVP

В первой версии не нужно:
- облачная обработка;
- пользовательские аккаунты;
- collaborative editing;
- live microphone transcription;
- real-time streaming transcription;
- полноценный GUI;
- ручной визуальный редактор таймлайна;
- обучение собственных speech models;
- полнофункциональная CRM/knowledge system.

## 6. Recommended technical direction

### 6.1 Overall principle

Для MVP использовать **устойчивый локальный speech pipeline**, а не экспериментальный research stack.

Приоритет:
1. локальность;
2. качество;
3. воспроизводимость;
4. расширяемость.

### 6.2 Suggested stack

Предпочтительно использовать стек, близкий к Whisper-based pipeline, потому что он наиболее зрелый для локальной транскрибации.

Предлагаемый baseline:
- `ffmpeg` для ingest и normalization;
- whisper-compatible ASR backend;
- alignment layer;
- diarization layer;
- summary layer;
- exporter layer.

Важно: выбор конкретного ASR backend должен учитывать ограничение:
- не требовать обязательный внешний токен;
- стабильно работать локально на macOS.

### 6.3 Strong implementation rule

Если компонент требует обязательную внешнюю регистрацию или токен для нормальной работы, он **не должен быть единственным критическим путём** в системе.

Нужно проектировать fallback path:
- если advanced diarization backend недоступен, транскрибация всё равно должна завершаться;
- если нет summary backend, основной transcript/export всё равно должен работать.

## 7. Architecture

Проект должен быть реализован как модульная система со следующими слоями:

1. `core` — job orchestration, config, lifecycle;
2. `ingest` — file intake, folder scan, watch mode;
3. `media` — ffmpeg, extraction, normalization;
4. `asr` — transcription backend abstraction;
5. `alignment` — timestamp refinement;
6. `diarization` — speaker segmentation and mapping;
7. `postprocess` — transcript shaping and conservative cleanup;
8. `summary` — краткое содержание;
9. `export` — generation of docx/txt/json/srt/md/pdf;
10. `service` — local API;
11. `cli` — command-line interface;
12. `storage` — outputs, temp, metadata, job artifacts.

## 8. Repository structure

Suggested structure:

```text
project-root/
  task.md
  README.md
  decisions.md
  acceptance_checklist.md
  pyproject.toml
  .env.example
  configs/
    default.yaml
    high_quality.yaml
    batch.yaml
    watch_folder.yaml
  src/
    app/
      __init__.py
      config.py
      logging.py
      constants.py
      exceptions.py
      models.py
    core/
      job_manager.py
      pipeline.py
      lifecycle.py
    ingest/
      input_resolver.py
      batch_loader.py
      watch_folder.py
      manifest_loader.py
    media/
      ffmpeg_utils.py
      extractor.py
      normalizer.py
      probes.py
    asr/
      base.py
      whisper_backend.py
      transcription_service.py
    alignment/
      base.py
      aligner.py
    diarization/
      base.py
      diarizer.py
      speaker_mapper.py
      merge.py
    postprocess/
      transcript_cleaner.py
      paragraph_builder.py
      speaker_formatter.py
      almost_verbatim.py
    summary/
      summarizer.py
      outline_builder.py
    export/
      export_json.py
      export_txt.py
      export_srt.py
      export_md.py
      export_docx.py
      export_pdf.py
    service/
      api.py
      schemas.py
      handlers.py
    cli/
      main.py
      commands.py
    storage/
      paths.py
      artifact_store.py
      job_state.py
    tests/
      fixtures/
      test_ingest.py
      test_media.py
      test_pipeline_smoke.py
      test_exports.py
      test_cleanup.py
      test_summary.py
      test_watch_folder.py
  scripts/
    run_local.sh
    run_watch_folder.sh
  sample_data/
  output/
  tmp/
```

## 9. Input requirements

### 9.1 Supported media formats

At minimum support:
- audio: `mp3`, `wav`, `m4a`, `aac`, `flac`, `ogg`
- video: `mp4`, `mov`, `mkv`, `avi`, `webm`

### 9.2 Input modes

Нужно поддержать следующие режимы:

#### Mode A: single file
Передача одного файла через CLI или API.

#### Mode B: multi-file batch
Передача списка файлов через CLI или API.

#### Mode C: directory batch
Обработка директории целиком.

#### Mode D: watch folder
Сервис следит за директориями и автоматически обрабатывает новые файлы.

### 9.3 Watch folder behavior

Нужно реализовать:
- мониторинг входной папки;
- обнаружение новых файлов;
- защита от чтения файла до завершения копирования;
- перенос обработанных файлов в `processed/` или маркировка статуса;
- перенос ошибочных файлов в `failed/`;
- логирование каждого job.

## 10. Speaker metadata requirements

Пользователь должен иметь возможность передать:
- список ожидаемых спикеров;
- их порядок приоритета;
- опционально заметки о ролях, например:
  - `Интервьюер`
  - `Клиент`
  - `Менеджер`

Пример входного speaker manifest:

```json
{
  "expected_speakers": [
    { "name": "Алексей", "role": "Интервьюер" },
    { "name": "Марина", "role": "Кандидат" }
  ]
}
```

Система должна:
- сохранить эту информацию в metadata job;
- попытаться сопоставить diarization labels с ожидаемыми именами;
- если уверенность недостаточна, не выдумывать сопоставление;
- сохранять both:
  - machine label (`SPEAKER_00`)
  - display label (`Алексей` или fallback machine label)

## 11. Pipeline stages

### 11.1 Stage 1 — Job creation
- принять input;
- валидировать файл(ы);
- создать `job_id`;
- создать рабочую директорию job;
- собрать метаданные.

### 11.2 Stage 2 — Media probe and normalization
- определить длительность;
- определить codec/container;
- извлечь аудио при необходимости;
- привести всё к стандартному рабочему формату;
- сохранить normalized WAV.

### 11.3 Stage 3 — ASR transcription
- загрузить локальный backend;
- выполнить transcription;
- сохранить raw segments;
- сохранить raw transcript;
- сохранить detected language.

### 11.4 Stage 4 — Alignment
- уточнить таймкоды сегментов;
- при возможности получить timestamps по словам;
- сохранить aligned result.

### 11.5 Stage 5 — Diarization
- определить speaker turns;
- проставить speaker labels;
- объединить diarization result с transcript segments;
- сохранить merged segments.

### 11.6 Stage 6 — Speaker mapping
- попытаться сопоставить labels с именами из manifest;
- не делать агрессивных догадок;
- сохранить mapping и confidence metadata.

### 11.7 Stage 7 — Conservative transcript shaping
- привести текст к читаемому виду;
- нормализовать пробелы;
- склеить избыточно мелкие сегменты;
- сгруппировать соседние сегменты одного спикера;
- не переписывать смысл;
- не удалять наполнители по умолчанию.

### 11.8 Stage 8 — Summary
- построить краткое содержание;
- выделить ключевые темы;
- при наличии явных договорённостей — перечислить их;
- summary должен быть отдельным output, а не заменой transcript.

### 11.9 Stage 9 — Export
Сохранить:
- machine-readable JSON;
- clean TXT;
- markdown;
- DOCX;
- PDF;
- SRT;
- intermediate artifacts.

## 12. Transcript policy

### 12.1 Desired style
Transcript должен быть:
- почти дословным;
- читаемым;
- с корректной разбивкой по спикерам;
- с таймкодами;
- с минимальной косметической нормализацией.

### 12.2 Allowed cleanup
Разрешено:
- исправление регистров в начале предложений;
- исправление лишних пробелов;
- мягкая пунктуация;
- объединение слишком мелких сегментов;
- выравнивание переносов;
- базовая типографика.

### 12.3 Forbidden cleanup by default
Нельзя по умолчанию:
- удалять смысловые паузы;
- переписывать фразы литературно;
- делать резюме вместо транскрипта;
- автоматически удалять слова-паразиты;
- “улучшать” речь так, чтобы менялся смысл;
- выдумывать имена спикеров.

### 12.4 Dual text representation
Нужно хранить:
- `text_raw`
- `text_clean`

## 13. Output requirements

### 13.1 Required files per job
Для каждого job сохранить:
- `job.json` — общие метаданные job;
- `transcript_raw.json` — сырой результат ASR/alignment/diarization;
- `segments.json` — сегменты со спикерами и таймкодами;
- `words.json` — word-level timestamps, если доступны;
- `transcript_clean.txt`
- `transcript_clean.md`
- `transcript_clean.docx`
- `transcript_clean.pdf`
- `subtitles.srt`
- `summary.md`
- `summary.json`
- `artifacts/` — промежуточные файлы.

### 13.2 DOCX structure
DOCX должен содержать:
1. Title page / header:
   - имя файла;
   - дата обработки;
   - длительность;
   - язык;
   - detected speakers;
   - pipeline preset;
   - notes/warnings.
2. Summary section:
   - краткое содержание;
   - ключевые темы;
   - возможные action items.
3. Transcript section:
   - блоки по спикерам;
   - таймкод диапазона;
   - текст реплики.
4. Appendix:
   - технические параметры;
   - список артефактов;
   - diagnostics/warnings.

### 13.3 PDF generation
PDF должен формироваться из структурированного текста и быть пригодным к отправке человеку.  
Не делать PDF как dump JSON.

### 13.4 JSON schema
JSON должен быть стабильным и пригодным для автоматизации. Нужно чётко задокументировать schema.

## 14. API and service requirements

### 14.1 Service shape
Нужен локальный mini-service.

Примерный функционал:
- `POST /jobs` — создать job;
- `GET /jobs/{job_id}` — статус job;
- `GET /jobs/{job_id}/artifacts` — список результатов;
- `POST /batch` — создать batch job;
- `POST /watch-folder/scan` — ручной триггер сканирования;
- `GET /health` — health check.

### 14.2 Execution model
Сервис может обрабатывать jobs последовательно или через ограниченную очередь.  
Нужно избегать бесконтрольного параллелизма, который может перегружать память.

### 14.3 Local-only assumption
API слушает только локальный интерфейс по умолчанию и не рассчитан на публичный интернет-доступ.

## 15. CLI requirements

Нужен CLI entrypoint, например:

```bash
transcribe-doc file.mp4 --out ./output
```

### 15.1 Required commands

#### Single file
```bash
transcribe-doc run input.mp4 --out ./output
```

#### Multiple files
```bash
transcribe-doc batch ./file1.mp4 ./file2.mp3 --out ./output
```

#### Directory
```bash
transcribe-doc dir ./incoming --out ./output
```

#### Watch folder
```bash
transcribe-doc watch ./incoming --out ./output
```

#### Service
```bash
transcribe-doc serve --host 127.0.0.1 --port 8765
```

### 15.2 CLI options
Нужно поддержать:
- `--out`
- `--language`
- `--model`
- `--preset`
- `--num-speakers`
- `--speaker-manifest`
- `--formats`
- `--keep-temp`
- `--save-artifacts`
- `--device`
- `--overwrite`
- `--recursive`
- `--watch-stability-seconds`

## 16. Configuration

Использовать YAML config.

Пример `configs/default.yaml`:

```yaml
app:
  temp_dir: "./tmp"
  output_dir: "./output"
  keep_temp: true
  save_artifacts: true

runtime:
  device: "mps"
  max_parallel_jobs: 1

media:
  sample_rate: 16000
  mono: true
  normalize_audio: true

asr:
  backend: "whisper"
  model_name: "large-v3"
  language: "ru"
  allow_mixed_vocabulary: true

alignment:
  enabled: true
  word_timestamps: true

diarization:
  enabled: true
  num_speakers: "auto"
  allow_expected_speaker_mapping: true

postprocess:
  mode: "almost_verbatim"
  remove_fillers: false
  aggressive_cleanup: false
  merge_adjacent_same_speaker: true

summary:
  enabled: true
  mode: "extractive_or_local_llm"

export:
  txt: true
  md: true
  docx: true
  pdf: true
  srt: true
  json: true

watch_folder:
  enabled: false
  stability_seconds: 10
  move_processed: true
  move_failed: true
```

## 17. Intermediate artifacts requirements

Сохранять в `artifacts/`:
- extracted audio;
- normalized audio;
- raw transcript dump;
- aligned transcript dump;
- diarization dump;
- merged transcript dump;
- logs;
- config snapshot for job.

Это нужно для:
- дебага;
- оценки качества;
- переэкспорта без полного повторного запуска;
- future QA.

## 18. Error handling and degradation policy

Система должна быть отказоустойчивой.

### 18.1 General rules
- падение одного необязательного этапа не должно по возможности ломать весь pipeline;
- обязательно логировать ошибку и статус этапа;
- сохранять partial outputs, если это возможно.

### 18.2 Required degradation behavior
- если diarization failed, экспортировать transcript без speaker labels;
- если alignment failed, экспортировать transcript с coarse timestamps;
- если summary failed, считать job успешным без summary;
- если PDF export failed, остальные форматы всё равно должны сохраниться;
- если один файл в batch упал, остальные продолжить.

### 18.3 Job statuses
Поддержать статусы:
- `queued`
- `processing`
- `completed`
- `completed_with_warnings`
- `failed_partial`
- `failed`

## 19. Logging and observability

Нужно логировать:
- job lifecycle;
- stage start/end;
- duration per stage;
- model/backend info;
- detected language;
- number of segments;
- number of speakers;
- degradation mode warnings;
- output paths.

Должны быть:
- console logs;
- file logs per job;
- machine-readable job summary JSON.

## 20. Performance expectations

Поскольку главный приоритет — качество, допускается не самая быстрая обработка.

Ожидания:
- устойчиво обрабатывать длинные файлы;
- не падать на batch jobs при разумных ограничениях;
- корректно использовать Apple Silicon acceleration там, где это стабильно;
- управлять памятью через chunking и controlled batching.

## 21. Testing requirements

### 21.1 Unit tests
Покрыть:
- media normalization;
- path/job resolution;
- transcript cleanup;
- speaker merge logic;
- summary formatting;
- exporters.

### 21.2 Integration tests
Покрыть:
- single speaker audio;
- multi-speaker audio;
- video input;
- batch directory processing;
- watch folder processing;
- fallback mode without diarization;
- fallback mode without summary.

### 21.3 Smoke tests
Нужен end-to-end smoke test:
- запускается CLI;
- создаются output files;
- output files non-empty;
- JSON schema valid.

## 22. Acceptance criteria

MVP считается выполненным, если:

1. Проект запускается локально на macOS Apple Silicon.
2. Есть CLI.
3. Есть локальный mini-service API.
4. Поддерживается single file processing.
5. Поддерживается batch processing.
6. Поддерживается watch folder.
7. Поддерживаются форматы:
   - `mp3`
   - `wav`
   - `m4a`
   - `mp4`
   - `mov`
8. Генерируются:
   - `docx`
   - `txt`
   - `json`
   - `srt`
   - `md`
   - `pdf`
9. В результате есть diarization.
10. Есть summary.
11. Есть стабильный JSON schema.
12. Есть сохранение intermediate artifacts.
13. Есть возможность передавать expected speaker names.
14. Transcript почти дословный, без агрессивного редакторского переписывания.
15. README позволяет установить и запустить проект локально.

## 23. README requirements

Codex должен создать `README.md`, в котором есть:
- описание проекта;
- supported formats;
- supported modes;
- install instructions for macOS;
- how to install ffmpeg;
- how to run CLI;
- how to run local service;
- how to configure watch folder;
- output examples;
- limitations;
- troubleshooting;
- explanation of transcript modes;
- JSON schema overview.

## 24. Implementation priorities

Приоритет разработки:
1. skeleton + config + logging;
2. single-file pipeline;
3. batch mode;
4. diarization merge;
5. exports;
6. summary;
7. local service;
8. watch folder;
9. tests + stabilization;
10. packaging readiness for future app.

## 25. Definition of done

Пользователь локально запускает проект на своём Mac, передаёт один файл или папку, либо кладёт файлы в watch folder, и получает готовый набор документов и JSON-артефактов с почти дословным транскриптом, diarization, summary и экспортом без ручной сборки результата.

## 26. Important engineering rules

- Код должен быть модульным.
- Нельзя жёстко зашивать конкретный backend во весь проект.
- Все ключевые этапы должны иметь abstraction layer.
- Все экспорты должны строиться из единой внутренней transcript model.
- Все важные параметры должны управляться конфигом.
- Нельзя делать магические неподконтрольные преобразования текста.
- Нельзя выдумывать speaker identity.
- Нужно сохранять raw + clean представления текста.
- Нужно проектировать код так, чтобы позже можно было добавить GUI / desktop app shell без полной переделки backend-а.

## 27. Open technical note for Codex

Если выбранный стек для diarization требует внешний токен или нестабилен в полностью локальном режиме, реализовать:
- fallback diarization strategy, либо
- degraded mode with transcript-only success path,
не блокируя весь проект.

Критерий успеха проекта — не идеальная research-точность, а работающий качественный локальный pipeline для личного использования.

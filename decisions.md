# decisions.md

## MVP decisions

- Platform: macOS Apple Silicon
- Runtime: Python 3.11+
- App shape: canonical Tauri desktop app + local mini-service backend
- Main priority: quality
- Transcript mode: almost verbatim
- Batch mode: required
- Watch folder: required
- Exports: docx, txt, json, srt, md, pdf
- Summary: required
- Intermediate artifacts: required
- Local-only operation: required
- No mandatory cloud APIs: required
- No mandatory external account/token: required

## Product intent

Проект нужен для личного локального использования на мощном Mac.
Главная версия продукта — packaged Tauri desktop app. CLI, local API и browser dashboard остаются поддерживающими интерфейсами для автоматизации, разработки и диагностики.

## Input assumptions

- Основной язык: русский
- Mixed vocabulary / англицизмы: поддержать
- Input modes:
  - single file
  - batch list
  - directory batch
  - watch folder

## Output assumptions

Обязательные выходы:
- machine-readable JSON
- readable transcript
- summary
- intermediate artifacts

## Speaker policy

- diarization required
- expected speaker names can be supplied in advance
- system may map labels to names only if confidence is sufficient
- fallback to `SPEAKER_00` etc. is always allowed

## Transcript policy

- preserve meaning
- stay almost verbatim
- do not aggressively rewrite
- do not remove fillers by default
- keep raw and clean representations separately

## Engineering principle

Prefer a robust, modular, local-first pipeline over an experimental cutting-edge stack.
User-facing changes are app-first: design and verify them through the desktop app flow before treating CLI/API behavior as complete.

## Failure policy

The project should degrade gracefully:
- transcript without diarization is acceptable fallback
- transcript without alignment is acceptable fallback
- transcript without summary is acceptable fallback
- one failed file must not block a batch

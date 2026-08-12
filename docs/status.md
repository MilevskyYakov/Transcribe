# Status

## Snapshot
- Current phase: App-first hardening and refactor
- Plan file: `docs/plans.md`
- Status: yellow
- Last updated: 2026-05-14

## Done
- Изучены `README.md`, `task.md`, `decisions.md`, `acceptance_checklist.md`.
- Собран dependency-ordered план MVP с учётом graceful degradation и local-only ограничений.
- Выделены стартовые validation assumptions для будущего Python-проекта.
- Создан Python skeleton: `pyproject.toml`, `src/mnema`, `configs/`, `tests/`, базовые app-модули и backend abstractions.
- Реализованы single-file intake и job workspace: input resolver, job paths, artifact/config snapshot store, `job.json`.
- Реализованы ffprobe/ffmpeg wrappers и CLI `run`, который создаёт failed job при отсутствии системных media tools и проходит success-path через тест с фейковыми бинарями.
- Добавлен начальный `M3` orchestration layer: `TranscriptionService`, conservative transcript cleanup и degraded-mode warnings для alignment/diarization fallback.
- Установлены системные зависимости: Homebrew `python@3.11`, `ffmpeg`, `ffprobe`.
- Поднят проектный `.venv` на Python 3.11, установлены `.[dev]`, `types-PyYAML` и `openai-whisper`.
- Реализованы `WhisperBackend`, `build_asr_backend`, сохранение `transcript_raw.json` и интеграция ASR-этапа в `run`.
- Добавлены ASR metadata contracts: `detected_language` и word-level tokens проходят через backend, orchestration, `transcript_raw.json` и `job.json`.
- Выполнен реальный smoke run на локально сгенерированном русском `wav` через `configs/lightweight_test.yaml`; получен `completed` job с `detected_language="ru"` и word-level timestamps.
- Добавлены concrete baseline adapters для следующих стадий: `PassthroughAlignmentBackend` и `SingleSpeakerDiarizationBackend`.
- `run` теперь сохраняет отдельные стабильные артефакты `segments.json` и `words.json`, а baseline diarization размечает single-speaker path как `SPEAKER_00`.
- Добавлен manifest-driven speaker mapping: при однозначном single-speaker сценарии `expected_speakers` из manifest безопасно мапятся в display label, а `speaker_manifest` сохраняется в `job.json`.
- Добавлен heuristic multi-speaker fallback path: при manifest на 2+ ожидаемых спикеров diarization factory переключается на multi-speaker backend, а mapper переносит `SPEAKER_00`/`SPEAKER_01` в имена по порядку.
- Добавлен split длинных ASR-сегментов по паузам и sentence boundaries, чтобы heuristic multi-speaker path работал даже когда Whisper возвращает один крупный сегмент.
- Подготовлены synthetic multi-speaker fixtures `sample_data/smoke_duo.wav` и `sample_data/smoke_duo_speakers.json`, а также отдельный preset `configs/lightweight_diarization.yaml`.
- Выполнен реальный end-to-end diarization smoke: synthetic duo sample расколот на два turn-а и размечен как `Алексей` / `Марина` в `segments.json` и `words.json`.
- Добавлен optional local embedding-based diarization backend `ResemblyzerDiarizationBackend`; при наличии `resemblyzer` и `scikit-learn` factory предпочитает его для manifest на 2+ ожидаемых спикеров, а heuristic backend остаётся fallback-path.
- Зафиксирована и исправлена regression в CLI entrypoint: `python -m mnema.cli.main ...` теперь действительно запускает `console_main()` через `__main__` hook, а не завершается молча.
- Выполнен реальный smoke run через `python -m mnema.cli.main` на synthetic duo fixture с новым embedding-based backend; получен `completed` job без warning-ветки в `output_smoke_duo_resemblyzer/`.
- Добавлен отдельный debug artifact `artifacts/diarization_dump.json`: он сохраняет сырой speaker-label output до manifest-driven remap, чтобы можно было отдельно анализировать качество diarization и качество display-label mapping.
- Выполнен повторный реальный smoke run с проверкой observability path в `output_smoke_duo_observable/`: `diarization_dump.json` содержит `SPEAKER_XX`, а финальный `segments.json` содержит remapped `Алексей` / `Марина`.
- `SpeakerMapping` расширен диагностическим `metadata`: local diarization backends теперь помечают происхождение метки (`backend`, `strategy`/`cluster_label`, длительность сегмента, размер wav slice), а manifest remap сохраняет эти данные и добавляет `display_label_source`.
- Выполнен дополнительный smoke run в `output_smoke_duo_diagnostics/`: подтверждено, что `diarization_dump.json` сохраняет raw `resemblyzer` diagnostics, а финальный `segments.json` переносит их вместе с remapped display labels.
- Для `ResemblyzerDiarizationBackend` добавлены cluster-quality diagnostics: `cluster_size`, `detected_cluster_count`, `assigned_centroid_similarity`, `nearest_alternative_similarity`, `centroid_similarity_margin`.
- Выполнен дополнительный smoke run в `output_smoke_duo_quality/`: quality-метрики видны и в сыром `diarization_dump.json`, и в финальном `segments.json` после manifest remap.
- `TranscriptionService` теперь поднимает non-fatal quality warnings для embedding diarization, если separation margin слишком мал или backend фактически схлопнул всё в один cluster; это подтверждено и на service-level, и на `run_command` path.
- Добавлен richer multi-turn fixture `sample_data/smoke_duo_rich.wav` с manifest `sample_data/smoke_duo_rich_speakers.json` для менее тривиального diarization smoke.
- Исправлен важный timeline bug в `ResemblyzerDiarizationBackend`: full-file `preprocess_wav` больше не ломает соответствие timestamps и waveform slicing. Теперь backend грузит raw mono waveform, режет его по timeline, а preprocessing применяет уже к каждому slice отдельно.
- Повторный rich smoke в `output_smoke_duo_rich/` теперь даёт 6 speaker turns с корректными ненулевыми `wav_slice_samples`; observed `centroid_similarity_margin` на richer fixture лежит примерно в диапазоне `0.125-0.163`, а job остаётся `completed` без quality warnings.
- Добавлен второй quality signal: warning для `imbalanced speaker clusters`, если один detected cluster поглощает почти все сегменты в multi-speaker embedding path.
- Повторная проверка richer smoke после этого сигнала подтверждает, что healthy case не шумит: `output_smoke_duo_rich/` завершается со статусом `completed` и пустым `warnings`.
- Quality summary теперь сохраняется в `job.metadata.diarization_quality`, поэтому калибровочные сравнения можно делать по `job.json`, а не только по полному `diarization_dump.json`.
- Собраны дополнительные calibration fixtures: `sample_data/smoke_duo_imbalanced.wav` и `sample_data/smoke_duo_overlap.wav`, плюс отдельная заметка с наблюдениями в `docs/diarization-calibration.md`.
- По текущей калибровке: balanced fixtures (`smoke_duo`, `smoke_duo_rich`) остаются без warning-ов при `min margin` около `0.25` и `0.11`, а fixtures `imbalanced` и `overlap` стабильно ловятся через `dominant_cluster_share = 0.83`.
- Подтверждены текущие проверки в целевой среде: `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`.
- Реализован M4 exporter layer: `txt`, `md`, `srt`, `json`, baseline `docx`, baseline `pdf`, `summary.md`, `summary.json`.
- Реализован M5 orchestration layer: `batch`, `dir`, `watch` scan, batch reports, stability window, move to `processed/` / `failed/`.
- Local API расширен endpoint-ами `POST /batch` и `POST /watch-folder/scan`.
- Frontend dashboard расширен batch path list и watch-folder scan controls.
- README дополнен backend/frontend запуском и validation командами.
- `POST /jobs` переведён на background execution через bounded `ThreadPoolExecutor`: API сразу возвращает `queued`, а frontend обновляет активные jobs polling-ом.
- Pipeline теперь пишет structured progress events в `job.metadata.events`, `artifacts/events.jsonl` и `artifacts/job.log`: stage, status, message, progress, timestamp.
- Local API отдаёт `GET /jobs/{job_id}/events`, а frontend показывает progress bar и timeline процесса.
- 2026-05-14: проектный baseline изменён на app-first. Canonical product теперь Tauri desktop app; CLI, local API и browser dashboard считаются поддерживающими/dev-интерфейсами.

## In Progress
- App-first hardening: закрепить документацию, агентские правила и модульные границы UI/Tauri/service вокруг desktop app.

## Next
- Продолжить `M3`: добавить более реалистичный multi-speaker fixture и/или сохранить сырой diarization debug artifact, чтобы оценивать качество embedding-based speaker split отдельно от manifest remapping.
- Продолжить `M3`: добавить более реалистичный multi-speaker fixture и richer diagnostics на уровне cluster-distance/quality score, чтобы оценивать качество backend-а на менее синтетическом разговорном аудио.
- Продолжить `M3`: откалибровать warning thresholds на richer fixtures и решить, нужны ли дополнительные quality signals вроде expected-speaker balance checks или cluster drift diagnostics.
- Продолжить `M3`: проверить warning thresholds на 3+ richer fixtures и решить, стоит ли вводить manifest-aware balance checks поверх текущих backend-agnostic quality warnings.
- Продолжить `M3`: проверить duration-aware balance, потому что текущая калибровка покрывает segment-count imbalance, но ещё не ловит сценарии с равным числом turn-ов и сильной асимметрией по длительности.
- Продолжить `M6`: добавить отмену/повтор job и, при необходимости, более granular progress внутри долгого ASR stage.
- Продолжить hardening: улучшить качество DOCX/PDF formatting и добавить реальный smoke через UI на коротком media fixture.
- Добавить app smoke: packaged/dev Tauri app запускает backend, создаёт single-file job и показывает transcript/artifacts.

## Decisions Made
- Плановые артефакты вынесены в `docs/`, так как в репозитории пока нет другой инженерной структуры.
- Single-file pipeline выбран как первый сквозной путь перед batch/watch/service.
- Diarization и alignment с самого начала трактуются как optional-with-fallback, а не как hard blocker для успешного job.
- Для `M2` success-path покрыт через временные фейковые `ffprobe/ffmpeg` в тестах, чтобы не зависеть от системной установки media tools на этой машине.
- Concrete baseline ASR для MVP зафиксирован как whisper-compatible backend с optional runtime import и конфигурируемым model name.
- Frontend для приложения теперь трактуется как UI canonical Tauri app; browser dashboard поверх `mnema serve` остаётся dev/debug режимом.
- Для быстрого пользовательского среза M6/M7 начаты до полного закрытия M4/M5: API и frontend покрывают single-file path, а batch/watch/export остаются в своих milestone.

## Assumptions In Force
- Разработка будет идти на Python 3.11+ под macOS Apple Silicon.
- Основная рабочая среда проекта теперь `.venv` на `/opt/homebrew/bin/python3.11`.
- Реальный ASR smoke run потребует отдельного media fixture и, вероятно, загрузки конкретной whisper model при первом запуске.
- При конфликте CLI/API convenience и app UX приоритет у app UX.

## Commands
```sh
.venv/bin/python -m pytest
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src
.venv/bin/python - <<'PY'
import whisper
print(whisper.__version__)
PY
```

## Current Blockers
- Качество real local diarization пока подтверждено только на synthetic two-speaker fixture; отдельной проверки на живом разговорном multi-speaker аудио ещё нет.
- Optional stack `resemblyzer` тянет внешние warning-и (`scipy.ndimage.morphology`, `pkg_resources` через `webrtcvad`), которые пока не ломают работу, но потребуют отдельной санитарной обработки.
- Frontend зависит от стабильного local service API, поэтому реализацию UI стоит начинать после базового `M6` job lifecycle.

## Audit Log
| Date | Milestone | Files | Commands | Result | Next |
| --- | --- | --- | --- | --- | --- |
| 2026-04-18 | Planning | `README.md`, `task.md`, `decisions.md`, `acceptance_checklist.md`, `docs/plans.md`, `docs/status.md`, `docs/test-plan.md` | `sed -n`, `rg --files`, `ls -la` | plan drafted | Start M1 scaffold |
| 2026-04-18 | M1-M2 | `pyproject.toml`, `configs/*`, `src/mnema/**/*`, `tests/*` | `python3 -m pytest`, `python3 -m ruff check src tests` | pass | Start M3 contracts |
| 2026-04-18 | M3 slice | `src/mnema/asr/transcription_service.py`, `src/mnema/postprocess/transcript_cleaner.py`, `tests/test_pipeline_smoke.py`, `tests/test_cleanup.py` | `python3 -m pytest`, `python3 -m ruff check src tests` | pass | Select concrete ASR backend |
| 2026-04-18 | Environment + M3 baseline | `.venv`, `pyproject.toml`, `src/mnema/asr/*`, `src/mnema/cli/commands.py`, `src/mnema/storage/*`, `tests/test_asr_factory.py`, `tests/test_whisper_backend.py`, `tests/test_run_command.py` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src` | pass | Add transcript metadata and concrete alignment/diarization |
| 2026-04-18 | M3 metadata + smoke | `src/mnema/asr/base.py`, `src/mnema/asr/whisper_backend.py`, `src/mnema/asr/transcription_service.py`, `src/mnema/cli/commands.py`, `configs/lightweight_test.yaml`, `sample_data/smoke_ru.wav` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_test.yaml run sample_data/smoke_ru.wav --out ./output_smoke_manual` | pass | Move to alignment/diarization |
| 2026-04-18 | M3 stable artifacts | `src/mnema/alignment/*`, `src/mnema/diarization/*`, `src/mnema/storage/*`, `src/mnema/cli/commands.py`, `tests/test_alignment_factory.py`, `tests/test_diarization_factory.py`, `tests/test_pipeline_smoke.py`, `tests/test_run_command.py` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src` | pass | Add real multi-speaker path |
| 2026-04-18 | M3 manifest mapping | `src/mnema/diarization/speaker_mapper.py`, `src/mnema/app/models.py`, `src/mnema/cli/commands.py`, `tests/test_speaker_mapper.py`, `tests/test_run_command.py` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src` | pass | Add real multi-speaker path |
| 2026-04-18 | M3 heuristic multi-speaker | `src/mnema/diarization/heuristic_multi_speaker_backend.py`, `src/mnema/diarization/factory.py`, `src/mnema/diarization/speaker_mapper.py`, `src/mnema/cli/commands.py`, `tests/test_diarization_factory.py`, `tests/test_pipeline_smoke.py`, `tests/test_run_command.py` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src` | pass | Add real backend or real fixture |
| 2026-04-18 | M3 sentence-boundary split + real duo smoke | `src/mnema/postprocess/segmenter.py`, `src/mnema/asr/transcription_service.py`, `configs/lightweight_diarization.yaml`, `sample_data/smoke_duo.wav`, `sample_data/smoke_duo_speakers.json`, `tests/test_segmenter.py`, `tests/test_pipeline_smoke.py` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo.wav --speaker-manifest sample_data/smoke_duo_speakers.json --out ./output_smoke_duo_diarization` | pass | Research real diarization backend |
| 2026-04-29 | M3 embedding-based diarization + CLI module entry | `src/mnema/diarization/resemblyzer_backend.py`, `src/mnema/diarization/factory.py`, `src/mnema/cli/main.py`, `tests/test_resemblyzer_backend.py`, `tests/test_diarization_factory.py`, `tests/test_cli.py`, `output_smoke_duo_resemblyzer/` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo.wav --speaker-manifest sample_data/smoke_duo_speakers.json --out ./output_smoke_duo_resemblyzer` | pass | Validate on less synthetic audio and add diarization debug artifacts |
| 2026-04-29 | M3 diarization observability | `src/mnema/storage/paths.py`, `src/mnema/core/job_manager.py`, `src/mnema/cli/commands.py`, `tests/test_job_manager.py`, `tests/test_run_command.py`, `output_smoke_duo_observable/` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo.wav --speaker-manifest sample_data/smoke_duo_speakers.json --out ./output_smoke_duo_observable` | pass | Add richer diarization diagnostics on less synthetic audio |
| 2026-04-29 | M3 mapping diagnostics propagation | `src/mnema/app/models.py`, `src/mnema/diarization/resemblyzer_backend.py`, `src/mnema/diarization/single_speaker_backend.py`, `src/mnema/diarization/heuristic_multi_speaker_backend.py`, `src/mnema/diarization/speaker_mapper.py`, `tests/test_resemblyzer_backend.py`, `tests/test_speaker_mapper.py`, `tests/test_pipeline_smoke.py`, `output_smoke_duo_diagnostics/` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo.wav --speaker-manifest sample_data/smoke_duo_speakers.json --out ./output_smoke_duo_diagnostics` | pass | Add cluster-quality metrics and validate on less synthetic audio |
| 2026-04-29 | M3 cluster-quality diagnostics | `src/mnema/diarization/resemblyzer_backend.py`, `tests/test_resemblyzer_backend.py`, `output_smoke_duo_quality/` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo.wav --speaker-manifest sample_data/smoke_duo_speakers.json --out ./output_smoke_duo_quality` | pass | Compare metrics against less synthetic audio and design warning thresholds |
| 2026-04-29 | M3 warning thresholds + richer fixture + timeline fix | `src/mnema/asr/transcription_service.py`, `src/mnema/diarization/resemblyzer_backend.py`, `tests/test_pipeline_smoke.py`, `tests/test_run_command.py`, `tests/test_resemblyzer_backend.py`, `sample_data/smoke_duo_rich.wav`, `sample_data/smoke_duo_rich_speakers.json`, `output_smoke_duo_rich/` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo_rich.wav --speaker-manifest sample_data/smoke_duo_rich_speakers.json --out ./output_smoke_duo_rich` | pass | Calibrate warning thresholds and consider richer quality signals |
| 2026-04-29 | M3 imbalance warning guardrail | `src/mnema/asr/transcription_service.py`, `tests/test_pipeline_smoke.py`, `output_smoke_duo_rich/` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo_rich.wav --speaker-manifest sample_data/smoke_duo_rich_speakers.json --out ./output_smoke_duo_rich` | pass | Validate thresholds across more varied fixtures |
| 2026-04-29 | M3 quality summary + multi-fixture calibration | `src/mnema/diarization/quality.py`, `src/mnema/asr/transcription_service.py`, `src/mnema/cli/commands.py`, `tests/test_diarization_quality.py`, `tests/test_pipeline_smoke.py`, `tests/test_run_command.py`, `sample_data/smoke_duo_imbalanced.wav`, `sample_data/smoke_duo_overlap.wav`, `docs/diarization-calibration.md`, `output_smoke_duo_baseline_calibrated/`, `output_smoke_duo_rich_calibrated/`, `output_smoke_duo_imbalanced/`, `output_smoke_duo_overlap/` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo.wav --speaker-manifest sample_data/smoke_duo_speakers.json --out ./output_smoke_duo_baseline_calibrated`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo_rich.wav --speaker-manifest sample_data/smoke_duo_rich_speakers.json --out ./output_smoke_duo_rich_calibrated`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo_imbalanced.wav --speaker-manifest sample_data/smoke_duo_imbalanced_speakers.json --out ./output_smoke_duo_imbalanced`, `.venv/bin/python -m mnema.cli.main --config configs/lightweight_diarization.yaml run sample_data/smoke_duo_overlap.wav --speaker-manifest sample_data/smoke_duo_overlap_speakers.json --out ./output_smoke_duo_overlap` | pass | Explore duration-aware balance checks |
| 2026-05-08 | M4-M7 MVP completion slice | `src/mnema/core/processing.py`, `src/mnema/core/batch.py`, `src/mnema/export/writers.py`, `src/mnema/summary/extractive.py`, `src/mnema/service/server.py`, `src/mnema/cli/commands.py`, `tests/test_batch.py`, `tests/test_export_writers.py`, `tests/test_service_api.py`, `frontend/`, `README.md`, `docs/*` | `.venv/bin/python -m pytest -q`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `cd frontend && npm test`, `cd frontend && npm run build`, `cd frontend && npm run e2e` | pass | Add real UI smoke on media fixture and cancel/retry controls |
| 2026-05-08 | Progress observability | `src/mnema/core/job_manager.py`, `src/mnema/core/processing.py`, `src/mnema/storage/paths.py`, `src/mnema/service/server.py`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`, `tests/test_service_api.py` | `.venv/bin/python -m pytest -q`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `cd frontend && npm test && npm run build && npm run e2e` | pass | Validate live progress on real media run |
| 2026-05-14 | App-first baseline + refactor | `AGENTS.md`, `README.md`, `decisions.md`, `docs/*`, `acceptance_checklist.md`, `frontend/src/*`, `frontend/src-tauri/src/*`, `src/mnema/service/*` | `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check src tests`, `.venv/bin/python -m mypy src`, `cd frontend && npm test`, `cd frontend && npm run build`, `cd frontend && npm run tauri:build` | pass | Add clean-machine bundle smoke |

## Smoke / Demo Checklist
- [x] Python project skeleton initializes locally
- [x] CLI help command renders available modes
- [x] Config loads from YAML preset without manual patching
- [x] `run` command creates `job.json` and artifacts workspace
- [x] Host machine has `ffmpeg` and `ffprobe`
- [x] Real ASR smoke run on a short valid media fixture
- [x] Real synthetic two-speaker smoke run with manifest-driven speaker labels
- [x] Local service responds to health/jobs/job/transcript/artifact endpoints
- [x] Frontend dashboard builds and passes unit + Playwright smoke checks
- [x] Export layer writes txt/md/srt/json/docx/pdf and summary artifacts
- [x] Batch, directory, and watch scan paths have tests
- [x] Jobs expose progress events and UI timeline for debugging failures

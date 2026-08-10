# Mnema · visual system handoff

Status: approved identity direction for Issue #55.

Sources: parent #51, screen map #52 (`docs/screen-map.md`), final decision in #54, Tauri bundle contract in `frontend/src-tauri/tauri.conf.json`.

## Fixed direction

- Character: `03 · Редакционный объект`.
- Composition: `B · Редакционное деление`: main object in wide column, stage/context in narrow column.
- Upload: neutral field.
- Processing: large blue progress field with real dynamic data.
- Typography: contrast serif only for large state headings and key numbers; system sans for working UI.
- Density: compact professional tool. Large scale only for state title and key data.
- Geometry: 6–8 px radii. No heavy card stack.
- Liquid Glass: sidebar, toolbar, and system controls only. Working content stays opaque.
- Accent: blue dominates; coral stays rare and decorative.
- Theme delivered here: light. Dark theme is not specified or implemented by this handoff.

## Identity

Chosen mark: `C · Индекс памяти`.

Meaning: one recording becomes a durable document in a personal archive. Three offset sheets form a memory index; coral page corner provides the one distinctive editorial accent. The mark is not a letter `M`, waveform, graph, or progress indicator.

Wordmark: `Mnema` in Didot Regular. Use mark alone for app icon and compact sidebar; use horizontal lockup where at least 160 px width is available. Do not recolor individual sheets or animate the coral corner as data.

Assets:

- `mnema-app-icon.svg` — 1024 × 1024 vector source, full-bleed blue background for platform masking.
- `mnema-app-icon-1024.png` — raster source used by Tauri icon generator.
- `mnema-lockup.svg` — approved horizontal mark + wordmark.
- `frontend/src-tauri/icons/32x32.png` — generated runtime icon.
- `frontend/src-tauri/icons/128x128.png` — generated runtime icon.
- `frontend/src-tauri/icons/128x128@2x.png` — generated 256 px runtime icon.
- `frontend/src-tauri/icons/icon.png` — generated 512 px runtime icon.
- `frontend/src-tauri/icons/icon.icns` — generated macOS bundle icon.

Keep 18% clear space around mark. Do not add a container inside an existing macOS icon mask. At 32 px, preserve page stack and coral corner; remove text lines first if a smaller custom surface is ever needed.

## Tokens

### Color

| Token | Value | Role |
| --- | --- | --- |
| `canvas` | `#F4F1E9` | app background |
| `surface` | `#FFFDF8` | opaque working surface |
| `ink` | `#14203B` | primary text |
| `muted` | `#546078` | secondary text |
| `line` | `#D7D9E0` | separators and quiet borders |
| `blue` | `#183F9B` | primary action, selection, processing field |
| `blue-soft` | `#D9E0F2` | selected/hover support surface |
| `coral` | `#EE6A51` | decorative cut only; never body text or status |
| `success` | `#18794E` | completed/available |
| `warning` | `#8A5900` | needs attention/low confidence |
| `error` | `#B62F27` | failed/unavailable |

Status never depends on color alone: pair color with icon and explicit label. Coral has 2.73:1 contrast on canvas, so it is not a text or control color.

Verified text contrast on `canvas`:

- `ink`: 14.32:1.
- `muted`: 5.60:1.
- `surface` on `blue`: 9.29:1.
- `success`: 4.79:1.
- `warning`: 5.30:1.
- `error`: 5.43:1.

### Type

- Display: `Didot`, fallback `Bodoni 72`, then `Georgia`. Use only at 32 px and above for state headings and key progress numbers.
- UI: `-apple-system`, `BlinkMacSystemFont`, `Helvetica Neue`, `sans-serif`.
- UI sizes: 12 metadata, 14 secondary, 15 body/control, 18 section title.
- Display sizes: 40 state heading, 64–80 key progress number where space allows.
- Body line height: 1.45. Control line height: 1.2.
- No serif in buttons, inputs, queue rows, history rows, errors, or settings.

### Spacing and geometry

- Base unit: 4 px.
- Scale: 4, 8, 12, 16, 24, 32, 48, 64 px.
- Control height: 36 px compact, 44 px primary.
- Radius: 6 px controls, 8 px working surfaces. Pills only for short status labels.
- Border: 1 px `line`. Avoid borders where spacing already separates regions.
- Shadow: sidebar/system chrome only, maximum `0 16px 40px rgba(20,32,59,.10)`. No floating card stack in working area.
- Focus ring: 2 px `blue` with 2 px offset; never remove native keyboard visibility.

## Components

### Primary button

Blue fill, light text, 44 px height, 6 px radius. One primary action per state. Hover darkens blue; pressed shifts down at most 1 px; disabled uses `line`/`muted` and keeps readable label; focus ring remains visible.

### Secondary button

Transparent or `surface`, 1 px `line`, `ink` label, 36–40 px height. Never compete with primary by using coral or equal filled weight.

### File drop surface

Neutral `surface` on `canvas`; no large blue fill. Entire central workspace accepts drop. Default uses quiet border and one compact `Выбрать файлы` button. Drag-over changes border and soft blue background, plus explicit `Отпустите файлы`. Decorative coral cut may enlarge behind empty content but cannot resemble waveform, progress, or file count. Once files are selected, decoration shrinks behind filename/folder/actions.

### Queue item

One 48–56 px row: filename, concise status, optional per-file folder override, and contextual action. Current item uses `blue-soft` and a blue leading rule. `Настроить`, `Обрабатывается`, `Готово`, `Ошибка` each use semantic icon + text. Error action repeats only that file.

### History item

One quiet row, not a card: title/filename, date, destination, status. Batch is one expandable group. Selected row uses `blue-soft`; hover cannot look selected. Search match emphasis uses weight, not coral.

### Processing state

Wide column contains opaque blue field. Real percentage is large contrast-serif data; stage and filename remain system sans. Progress bar is functional and blue/white, never coral. Narrow column carries stage, elapsed/supporting context, and `Новая транскрипция`. Decorative coral cut can cross an unused edge of the field but never tracks progress.

### Result actions

`Открыть Markdown` is primary. `Показать в Finder` and `Новая транскрипция` are secondary. `Ещё` contains diagnostics/intermediate artifacts. Decoration nearly disappears; output file and actions lead hierarchy.

### Settings shell

Sidebar/system chrome may use restrained material blur; settings content uses opaque `surface`. Sections use separators and spacing, not nested cards. `Готово` is the single primary action. Models, updater, API, and diagnostics stay here and appear in workspace only through actionable errors.

## State coverage

| Screen-map state | Required visual treatment |
| --- | --- |
| Launch | neutral drop field; largest allowed decorative cut |
| Drag-over | explicit copy + blue-soft field change |
| One file selected | compact file/folder form; reduced decoration |
| Folder missing | warning icon + label; `Выбрать папку` primary |
| Batch | same file form + narrow queue column |
| Processing | large blue field; real percentage; coral never data |
| Job error | error icon + label; `Повторить` primary |
| Result | decoration almost absent; Markdown action leads |
| Low-confidence diarization | warning icon + honest chronology copy; no false speaker color coding |
| History/search | no decoration; row hierarchy only |
| Settings | no decoration; opaque sections |
| Backend problem | error icon + `Повторить запуск`; diagnostics secondary |
| Model problem | warning/error label + `Открыть настройки моделей` |

## Decorative language

One device only: a coral editorial cut/page corner. Use it at large scale on upload, once on processing, minimally in identity, and nowhere in result/history/settings/diagnostics. It carries no value, duration, stage, confidence, waveform, or status. If it competes with filename, percentage, result, or action, remove it.

## Implementation boundary

This handoff changes identity assets and Tauri icon configuration only. It does not implement React/CSS, alter the screen map, add a dark theme, or change backend/API behavior.

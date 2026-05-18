# AGENTS.md

## Project Direction

- Canonical product: Tauri desktop app in `frontend/src-tauri`.
- Primary user surface: packaged macOS app that starts the local backend itself.
- Supporting surfaces: CLI, local service API, and browser dashboard are development, automation, and debugging interfaces.

## App-First Rule

- New user-facing behavior must be designed and verified through the desktop app flow first.
- Do not treat CLI or API convenience as the main product path when it conflicts with app UX.
- Browser dashboard changes must stay compatible with Tauri runtime assumptions: local API base, no cloud auth, no public URLs, no direct Python internals in UI.

## Change Checklist

- Before code changes, identify whether the app flow, backend API contract, or packaging/runtime setup is affected.
- Keep the Python pipeline behind the local API; do not move speech processing logic into React/Tauri UI code.
- Preserve CLI/API compatibility unless the change explicitly updates those contracts.
- For app-facing work, check frontend tests/build and run a Tauri smoke/build when local prerequisites allow it.

## Refactor Policy

- Prefer small vertical refactor slices with unchanged behavior and tests after each slice.
- Split large files by responsibility: app shell/components/view-model, Tauri commands/settings/backend process, service routes/storage/responses/model runtime.
- Optimize first for maintainability and clear boundaries; do not tune ASR/diarization performance without a measured bottleneck.

# Frontend Plan

## Goal

Frontend is the UI layer for the canonical Tauri desktop app. It gives the user a simple working surface for creating jobs, tracking progress, reading transcripts, checking diagnostics, and downloading artifacts.

The same React client can run in a browser against `transcribe-doc serve`, but that browser mode is for development and diagnostics. Product decisions should assume the packaged Tauri app is the main user surface.

## Product Scope

Desktop app MVP:
- submit a single media file for processing;
- optionally enter a free-form participant hint, for example `Яков и Никита`;
- choose a small set of safe job settings;
- show job list with status, warnings, timestamps, and output paths;
- show transcript as segment rows with speaker labels and timing;
- show word-level data when available;
- show diagnostics and degraded-mode warnings;
- expose links/actions for generated artifacts.

Not in the first app slice:
- transcript editing;
- collaborative editing;
- cloud accounts;
- remote deployment;
- live microphone transcription;
- cloud distribution or auto-updates.

## Architecture

The frontend lives in `frontend/` and talks only to the local service API. Tauri owns desktop shell concerns: starting the backend sidecar, locating app data, and exposing bootstrap settings.

Preferred stack:
- TypeScript;
- React + Vite;
- local API client module;
- component-level tests where useful;
- Playwright smoke tests for the main user flow.

Backend contract:
- `GET /health`;
- `POST /jobs`;
- `GET /jobs`;
- `GET /jobs/{job_id}`;
- `GET /jobs/{job_id}/artifacts`;
- static or streamed artifact download endpoints.

The service remains the owner of filesystem access, job state, pipeline execution, and artifact paths. The frontend renders state; it does not duplicate orchestration.

## UX Direction

The UI should feel like a focused local production tool, not a marketing page.

Primary layout:
- left rail or top bar for jobs and settings;
- main work area for upload, active job state, and transcript viewer;
- diagnostics panel for warnings, diarization quality, and artifact health.

The default workflow should be:
1. choose media file;
2. optionally type who was in the meeting;
3. start job;
4. watch status;
5. inspect transcript;
6. download outputs.

## Desktop Contract

The frontend must preserve app runtime assumptions:
- no hard-coded public URLs;
- API base URL configurable;
- no cloud auth dependency;
- no browser-only filesystem assumptions beyond file upload/download;
- no pipeline code in frontend;
- clean separation between API client, state model, and presentation components.

## Milestone Placement

Frontend implementation follows the canonical desktop path while keeping browser dev mode available.

Planned order:
1. finish core transcript/diarization quality work;
2. implement stable outputs;
3. implement local API job lifecycle;
4. build React UI and browser dev dashboard;
5. package and verify the Tauri desktop app as the main release surface.

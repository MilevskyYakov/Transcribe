# Local API Contract

The canonical app/backend contract for the local desktop API is defined in `src/transcribe_doc/service/contracts.py` and mirrored by `frontend/src/types.ts`.

Backend route handlers should return payloads by constructing the dataclass responses from `contracts.py` and serializing them with `dataclass_payload()` (or `JobResponse.to_payload()` for jobs). Do not assemble new endpoint-specific dictionaries directly in route handlers when a response model already exists.

Frontend code should consume the typed interfaces in `frontend/src/types.ts`. Known diagnostic payloads belong in typed metadata fields, not in generic `Record<string, unknown>` parsing inside view-model code.

## Endpoints

### `GET /health`

Returns `HealthResponse`:

- `status: string`
- `app.output_dir: string`
- `app.temp_dir: string`
- `app.cache_dir: string`
- `media_tools.ffmpeg.available: boolean`
- `media_tools.ffmpeg.path?: string`
- `media_tools.ffprobe.available: boolean`
- `media_tools.ffprobe.path?: string`

### `GET /jobs` and `GET /jobs/:id`

Jobs are `JobResponse` objects:

- `job_id: string`
- `source_paths: string[]`
- `status: queued | processing | completed | completed_with_warnings | failed_partial | failed`
- `detected_language?: string | null`
- `artifacts: ArtifactManifest`
- `metadata: JobMetadataResponse`
- `warnings: string[]`

Known metadata fields include `display_title`, `source_filename`, `execution`, `current_stage`, `last_message`, `progress`, `events`, and `diarization_quality`. Unknown metadata may still be carried for backward compatibility, but app-facing diagnostics should be promoted to explicit fields.

### `GET /jobs/:id/transcript`

Returns `TranscriptResponse`:

- `job: JobResponse | null`
- `segments: TranscriptSegment[]`
- `words: WordToken[]`

### `GET /jobs/:id/artifacts`

Returns `ArtifactsResponse` with `artifacts: ArtifactResponse[]`:

- `name: string`
- `filename: string`
- `size_bytes: number`
- `download_url: string`

### `GET /jobs/:id/events`

Returns `EventsResponse` with `events: JobEventResponse[]`:

- `timestamp: string`
- `stage: string`
- `status: ok | warning | error | string`
- `message: string`
- `progress: number`

### `GET /models`

Returns `ModelsResponse`:

- `current_model: string`
- `models: ModelStatusResponse[]`

Each model has `name`, `status`, and optional metadata such as `label`, `backend`, `language`, `description`, `path`, `size_bytes`, `downloaded_bytes`, `total_bytes`, `progress`, `message`, `updated_at`, `stale_download`, `runtime_name`, and `queue_position`.

## Change rule

When adding or changing an app-facing field:

1. Update `src/transcribe_doc/service/contracts.py`.
2. Update `frontend/src/types.ts` to mirror the contract.
3. Add or update `tests/test_service_api.py` contract coverage.
4. Run `pytest tests/test_service_api.py` and `npm test` in `frontend/`.

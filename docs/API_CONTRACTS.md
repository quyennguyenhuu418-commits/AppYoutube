# API_CONTRACTS

Every active HTTP route in the system. Routes are read from the source;
they are not extracted from documentation.

Format: `METHOD /path` — handler (`file:line`) — request model — response
model — consumer — status.

Status values: `ACTIVE`, `INTERNAL`, `DEPRECATED`.

---

## Health

### `GET /health` — `health()`
- File: `orchestrator/app/main.py`
- Request: —
- Response: `{ status, openai_configured, elevenlabs_configured, cache_mode }`
- Consumer: webapp `api.health()`, ops
- Status: ACTIVE

---

## Jobs (`orchestrator/app/api/jobs.py`)

### `POST /jobs` — `create_job()`
- File: `orchestrator/app/api/jobs.py:58`
- Request: `JobCreateRequest` (`{ topic: str }`)
- Response: `201 JobDetail`
- Consumer: webapp `TopicForm`
- Side effect: creates job record + spawns `BackgroundTask(run_job)`
- Status: ACTIVE

### `GET /jobs` — `list_jobs()`
- File: `orchestrator/app/api/jobs.py`
- Request: —
- Response: `list[JobSummary]`
- Consumer: webapp `JobsList`
- Status: ACTIVE

### `GET /jobs/{job_id}` — `get_job()`
- File: `orchestrator/app/api/jobs.py`
- Request: path param `job_id`
- Response: `JobDetail`
- Consumer: webapp `/jobs/[id]/page.tsx`
- Status: ACTIVE

---

## Assets (`orchestrator/app/api/assets.py`)

### `GET /jobs/{job_id}/artifacts/{name:path}` — `get_artifact()`
- File: `orchestrator/app/api/assets.py:44`
- Request: path params `job_id`, `name` (path-traversal-safe)
- Response: media file stream (mp4, mp3, png, json)
- Consumer: webapp `<VideoPlayer>`, direct browser download
- Status: ACTIVE

---

## Research (`orchestrator/app/api/research.py`)

All routes mounted under `/research`.

### `GET /research/{job_id}/package` — `get_package()`
- File: `orchestrator/app/api/research.py:196`
- Request: path param `job_id`
- Response: `ResearchPackage` (canonical rich)
- Consumer: ops, future webapp pages
- Status: ACTIVE

### `GET /research/{job_id}/sources` — `get_sources()`
- File: `orchestrator/app/api/research.py`
- Request: query `tier?`, `page`, `page_size`
- Response: `SourceResponse` (paginated)
- Status: ACTIVE

### `GET /research/{job_id}/claims` — `get_claims()`
- Request: query `claim_type?`, `certainty?`, `page`, `page_size`
- Response: `ClaimResponse` (paginated)
- Status: ACTIVE

### `GET /research/{job_id}/contradictions` — `get_contradictions()`
- Request: —
- Response: `ContradictionResponse` (currently always empty; see
  `docs/TECHNICAL_DEBT.md` C-001)
- Status: ACTIVE

### `GET /research/{job_id}/quality` — `get_quality()`
- Request: —
- Response: `QualityResponse` (score + warnings)
- Status: ACTIVE

### `POST /research/{job_id}/review/sources/{source_id}` — `review_source()`
- Request: `{ approved: bool, notes: str }`
- Response: updated `Source`
- Side effect: persists to disk
- Status: ACTIVE

### `POST /research/{job_id}/review/claims/{claim_id}` — `review_claim()`
- Request: `{ approved: bool, notes: str }`
- Response: updated `Claim` (rejection sets `SPECULATION` certainty + note)
- Side effect: persists to disk
- Status: ACTIVE

---

## Characters (`orchestrator/app/api/characters.py`)

### `GET /api/characters/{job_id}/package` — `get_package()`
- File: `orchestrator/app/api/characters.py`
- Request: path param `job_id`
- Response: `CharacterSystemPackage`
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/characters` — `list_characters()`
- File: `orchestrator/app/api/characters.py`
- Request: path param `job_id`
- Response: `{ count, characters: list[CharacterInfo] }`
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/characters/{character_id}` — `get_character()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`
- Response: `CharacterDefinition`
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/characters/{character_id}/poses` — `get_poses()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`
- Response: `{ character_id, count, poses: list[PoseDefinition] }`
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/characters/{character_id}/expressions` — `get_expressions()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`
- Response: `{ character_id, count, expressions: list[ExpressionDefinition] }`
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/characters/{character_id}/wardrobes` — `get_wardrobes()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`
- Response: `{ character_id, count, wardrobes: list[WardrobeDefinition] }`
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/characters/{character_id}/assets` — `get_assets()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`
- Response: `CharacterAssetPackage`
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/characters/{character_id}/quality` — `get_quality()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`
- Response: `CharacterQualityScore` (11-dimension)
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/characters/{character_id}/preview` — `get_character_preview()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`
- Response: `image/svg+xml` (generated SVG preview)
- Consumer: UI (character inspection page)
- Status: ACTIVE

### `GET /api/characters/{job_id}/registry` — `get_registry()`
- File: `orchestrator/app/api/characters.py`
- Request: path param `job_id`
- Response: `CharacterRegistry`
- Consumer: UI
- Status: ACTIVE

### `GET /api/characters/{job_id}/preview` — `get_preview()`
- File: `orchestrator/app/api/characters.py`
- Request: path param `job_id`
- Response: `CharacterPreview` summary
- Consumer: UI
- Status: ACTIVE

### `POST /api/characters/{job_id}/characters/{character_id}/approve` — `approve_character()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`; body `approved_by`
- Response: `CharacterDefinition` (updated status=APPROVED)
- Consumer: UI
- Status: ACTIVE

### `POST /api/characters/{job_id}/characters/{character_id}/deprecate` — `deprecate_character()`
- File: `orchestrator/app/api/characters.py`
- Request: path params `job_id`, `character_id`; body `reason`
- Response: `CharacterDefinition` (updated status=DEPRECATED)
- Consumer: UI
- Status: ACTIVE

### `POST /api/characters/{job_id}/generate` — `generate_characters()`
- File: `orchestrator/app/api/characters.py`
- Request: path param `job_id`, query `force: bool`
- Response: `CharacterSystemPackage`
- Consumer: UI (triggers engine from storyboard)
- Status: ACTIVE

---

## Route Inventory Summary

| route | handler | status |
|---|---|---|
| `GET /health` | `health` | ACTIVE |
| `POST /jobs` | `create_job` | ACTIVE |
| `GET /jobs` | `list_jobs` | ACTIVE |
| `GET /jobs/{job_id}` | `get_job` | ACTIVE |
| `GET /jobs/{job_id}/artifacts/{name:path}` | `get_artifact` | ACTIVE |
| `GET /research/{job_id}/package` | `get_package` | ACTIVE |
| `GET /research/{job_id}/sources` | `get_sources` | ACTIVE |
| `GET /research/{job_id}/claims` | `get_claims` | ACTIVE |
| `GET /research/{job_id}/contradictions` | `get_contradictions` | ACTIVE |
| `GET /research/{job_id}/quality` | `get_quality` | ACTIVE |
| `POST /research/{job_id}/review/sources/{source_id}` | `review_source` | ACTIVE |
| `POST /research/{job_id}/review/claims/{claim_id}` | `review_claim` | ACTIVE |
| `GET /story/{job_id}/package` | `get_package` | ACTIVE |
| `GET /story/{job_id}/thesis` | `get_thesis` | ACTIVE |
| `GET /story/{job_id}/angles` | `get_angles` | ACTIVE |
| `GET /story/{job_id}/titles` | `get_titles` | ACTIVE |
| `GET /story/{job_id}/script` | `get_script` | ACTIVE |
| `GET /story/{job_id}/critique` | `get_critique` | ACTIVE |
| `GET /story/{job_id}/quality` | `get_quality` | ACTIVE |
| `POST /story/{job_id}/approve` | `approve_story` | ACTIVE |
| `POST /story/{job_id}/reject` | `reject_story` | ACTIVE |
| `GET /storyboard/{job_id}/package` | `get_package` | ACTIVE |
| `GET /storyboard/{job_id}/beats` | `get_beats` | ACTIVE |
| `GET /storyboard/{job_id}/assets` | `get_assets` | ACTIVE |
| `GET /storyboard/{job_id}/quality` | `get_quality` | ACTIVE |
| `GET /storyboard/{job_id}/continuity` | `get_continuity` | ACTIVE |
| `GET /storyboard/{job_id}/preview` | `get_preview` | ACTIVE |
| `POST /storyboard/{job_id}/approve` | `approve_storyboard` | ACTIVE |
| `POST /storyboard/{job_id}/reject` | `reject_storyboard` | ACTIVE |
| `POST /storyboard/{job_id}/regenerate` | `regenerate_storyboard` | ACTIVE |
| `GET /api/characters/{job_id}/package` | `get_package` | ACTIVE |
| `GET /api/characters/{job_id}/characters` | `list_characters` | ACTIVE |
| `GET /api/characters/{job_id}/characters/{character_id}` | `get_character` | ACTIVE |
| `GET /api/characters/{job_id}/characters/{character_id}/poses` | `get_poses` | ACTIVE |
| `GET /api/characters/{job_id}/characters/{character_id}/expressions` | `get_expressions` | ACTIVE |
| `GET /api/characters/{job_id}/characters/{character_id}/wardrobes` | `get_wardrobes` | ACTIVE |
| `GET /api/characters/{job_id}/characters/{character_id}/assets` | `get_assets` | ACTIVE |
| `GET /api/characters/{job_id}/characters/{character_id}/quality` | `get_quality` | ACTIVE |
| `GET /api/characters/{job_id}/characters/{character_id}/preview` | `get_character_preview` | ACTIVE |
| `GET /api/characters/{job_id}/registry` | `get_registry` | ACTIVE |
| `GET /api/characters/{job_id}/preview` | `get_preview` | ACTIVE |
| `POST /api/characters/{job_id}/characters/{character_id}/approve` | `approve_character` | ACTIVE |
| `POST /api/characters/{job_id}/characters/{character_id}/deprecate` | `deprecate_character` | ACTIVE |
| `POST /api/characters/{job_id}/generate` | `generate_characters` | ACTIVE |

**45 active routes.** (Character routes)

---

## Integration Tests (PROMPT 6.5)

The following HTTP endpoints are now covered by integration tests in
`orchestrator/tests/test_pipeline_integration_65.py`:

| Endpoint | Test | Status |
|---|---|---|
| `POST /jobs` | `test_jobs_create_endpoint` | VERIFIED (200) |
| `GET /api/assets/environments/list` | `test_asset_api_get_environments` | VERIFIED (200) |
| `GET /api/assets/props/list` | `test_asset_api_get_props` | VERIFIED (200) |
| `POST /api/assets/resolve` | `test_asset_api_resolve_asset` | VERIFIED (200) |

---

## Asset System Routes (Prompt 6)

| Method | Route | Source | Status |
|---|---|---|---|
| `GET /api/assets` | `list_assets` | `orchestrator/app/api/assets.py` | ACTIVE |
| `GET /api/assets/{asset_id}` | `get_asset` | `orchestrator/app/api/assets.py` | ACTIVE |
| `GET /api/assets/{asset_id}/versions` | `list_versions` | `orchestrator/app/api/assets.py` | ACTIVE |
| `GET /api/assets/{asset_id}/usage` | `get_usage` | `orchestrator/app/api/assets.py` | ACTIVE |
| `POST /api/assets/resolve` | `resolve_asset` | `orchestrator/app/api/assets.py` | ACTIVE |
| `POST /api/assets/generate` | `generate_asset` | `orchestrator/app/api/assets.py` | ACTIVE |
| `POST /api/assets/{asset_id}/validate` | `validate_asset` | `orchestrator/app/api/assets.py` | ACTIVE |
| `POST /api/assets/{asset_id}/approve` | `approve_asset` | `orchestrator/app/api/assets.py` | ACTIVE |
| `POST /api/assets/{asset_id}/deprecate` | `deprecate_asset` | `orchestrator/app/api/assets.py` | ACTIVE |
| `GET /api/assets/registry` | `get_registry` | `orchestrator/app/api/assets.py` | ACTIVE |
| `GET /api/assets/quality/{asset_id}` | `get_quality` | `orchestrator/app/api/assets.py` | ACTIVE |
| `GET /api/assets/environments/list` | `list_environments` | `orchestrator/app/api/assets.py` | ACTIVE |
| `GET /api/assets/props/list` | `list_props` | `orchestrator/app/api/assets.py` | ACTIVE |

**13 active asset routes.** Total: **58 active routes.**

(POST /jobs, GET environments/props, POST resolve verified at HTTP layer in PROMPT 6.5.)

---

## Naming Consistency

- Singular for path params (`/jobs/{job_id}`), not plural
- Lowercase, hyphenless
- No version prefix (e.g., no `/v1/`)

If a future route breaks these conventions, record it in
`docs/CHANGELOG_INTERNAL.md`.

---

## Voice / TTS / Audio API (PROMPT 8, future)

The Voice / TTS / Audio Intelligence Layer does NOT yet expose HTTP routes. The contracts below are intended for a future webapp integration (not yet implemented).

### `GET /voices`

List all voices registered in the VoiceRegistry. Supports filters by `language`, `status`, `provider`.

- request: query params `language`, `status`, `provider`
- response: `[{ voice_id, name, language, provider, status, ... }]`
- consumer: webapp admin UI (not yet implemented)
- status: INTERNAL (defined as future)

### `GET /voices/{id}`

Lookup a single voice by ID.

- request: `voice_id` (path)
- response: `VoiceDefinition`
- consumer: webapp admin UI
- status: INTERNAL (defined as future)

### `POST /voices/resolve`

Resolve a `NarrationUnit` to a concrete voice + provider. Returns `VoiceResolution` + audit trail.

- request: `{ narration_unit, voice_id? }`
- response: `{ resolved_voice_id, resolved_provider, strategy, fallback_used, mock_used, events[] }`
- consumer: internal orchestrator (currently called by app.voice.resolver)
- status: INTERNAL (defined as future)

### `POST /tts/synthesize`

Synthesize audio for one or more narration units. Returns canonical AudioArtifacts.

- request: `{ units: [NarrationUnit], voice_id?, output_dir? }`
- response: `{ artifacts: { narration_id -> AudioArtifact } }`
- consumer: orchestrator pipeline (s7.5 future stage)
- status: INTERNAL (defined as future)

### `GET /audio/{artifact_id}`

Retrieve canonical AudioArtifact metadata by artifact_id.

- request: `artifact_id` (path)
- response: `AudioArtifact`
- consumer: renderer / AudioLibrary
- status: INTERNAL (defined as future)

### `GET /audio/{artifact_id}/timing`

Retrieve SpeechTiming for a canonical AudioArtifact.

- request: `artifact_id` (path)
- response: `SpeechTiming`
- consumer: renderer / Captions (PROMPT 9)
- status: INTERNAL (defined as future)

###     `POST /audio/validate`

Re-validate an existing AudioArtifact on disk.

- request: `{ artifact_id }`
- response: `{ valid, actual_duration_sec, actual_sample_rate, actual_channels, actual_byte_size, issues[] }`
- consumer: orchestrator / Editorial
- status: INTERNAL (defined as future)

---

## Render Orchestration API (PROMPT 12)

All routes mounted under `/render`. Thin adapter over `RenderOrchestrator`.
Business logic lives in `orchestrator/app/orchestration/orchestrator.py`.

### `POST /render/preflight` — `preflight()`
- File: `orchestrator/app/api/render.py:233`
- Request: `RenderPreflightRequest`
  ```json
  {
    "job_id": "p12_demo_001",
    "project_id": "proj_demo",
    "topic": "...",
    "editorial_project_data": { ... },
    "render_profile_data": { ... },
    "mastering_profile_data": { ... }
  }
  ```
- Response: `RenderPreflightResponse`
  ```json
  {
    "job_id": "...",
    "status": "ok | errors | warnings",
    "errors": [{ "severity": "error", "field": "...", "message": "..." }],
    "warnings": [{ "severity": "warning", "field": "...", "message": "..." }],
    "render_plan_id": "...",
    "render_plan_fingerprint": "...",
    "resolved_asset_count": 0,
    "resolved_audio_count": 0,
    "estimated_duration_sec": null,
    "created_at": "ISO-8601"
  }
  ```
- Error codes: 400 (invalid job_id), 422 (contract validation failure)
- Idempotency: read-only; safe to call repeatedly
- Status: ACTIVE

### `POST /render/finalize` — `finalize()`
- File: `orchestrator/app/api/render.py:347`
- Request: `RenderFinalizeRequest` (same schema as preflight)
- Response: `202 RenderFinalizeResponse`
  ```json
  {
    "job_id": "...",
    "lifecycle": "queued | approved | ...",
    "progress_pct": 0,
    "current_stage": "queued",
    "render_plan_id": null,
    "render_job_id": "...",
    "message": "Render queued. Poll GET /render/{id}/status for progress."
  }
  ```
- Error codes: 400 (invalid job_id), 409 (job already terminal)
- Side effect: enqueues background `RenderOrchestrator.orchestrate()` task
- Idempotency: terminal jobs are refused with 409
- Status: ACTIVE

### `GET /render/{job_id}/status` — `render_status()`
- File: `orchestrator/app/api/render.py:417`
- Request: path param `job_id` (validated against `^[A-Za-z0-9_-]+$`)
- Response: `RenderStatusResponse`
  ```json
  {
    "job_id": "...",
    "project_id": "...",
    "topic": "...",
    "lifecycle": "queued | preparing | preflight | rendering | mastering | qa | finalizing | approved | failed | cancelled",
    "progress_pct": 0..100,
    "current_stage": null,
    "stage_progress": { "preparing": 5, ... },
    "stages": [
      { "name": "preparing", "label": "Preparing", "status": "completed", "started_at": "...", "finished_at": "...", "error": null }
    ],
    "is_terminal": false,
    "error": null,
    "error_stage": null,
    "render_plan_id": null,
    "final_artifact_id": null,
    "qa_report_id": null,
    "final_mp4_path": null,
    "renderer_version": "remotion-X.Y.Z",
    "ffmpeg_version": "ffmpeg-X.Y",
    "created_at": "...",
    "started_at": null,
    "finished_at": null
  }
  ```
- Error codes: 400 (invalid id), 404 (job not found)
- Security: `final_mp4_path` is always `null` (internal path is never leaked)
- State lifecycle: see RenderJob contract in `docs/DATA_CONTRACTS.md`
- Status: ACTIVE

### `GET /render/{job_id}/qa` — `render_qa()`
- File: `orchestrator/app/api/render.py:464`
- Request: path param `job_id`
- Response: `RenderQAReportResponse` (thin transport DTO wrapping canonical `MediaQAReport`)
  ```json
  {
    "report_id": "...",
    "artifact_id": "...",
    "render_profile_id": "...",
    "mastering_profile_id": "...",
    "overall_status": "pass | warn | fail",
    "checks": [
      {
        "check_id": "VIDEO_STREAM | AUDIO_STREAM | DURATION | FPS | RESOLUTION | CODEC | AUDIO_DURATION | LOUDNESS | TRUE_PEAK | DECODE | SYNC | ARTIFACT_INTEGRITY",
        "status": "pass | warn | fail | unavailable",
        "expected": { ... },
        "measured": { ... },
        "tolerance": 0.5,
        "explanation": "..."
      }
    ],
    "warnings": ["..."],
    "failures": ["..."],
    "tool_versions": { "ffmpeg": "...", "ffprobe": "..." },
    "measured_at": "ISO-8601"
  }
  ```
- Error codes: 400, 404, 500
- Source of truth: canonical `MediaQAReport` (P11 §34)
- Status: ACTIVE

### `GET /render/{job_id}/artifact` — `render_artifact()`
- File: `orchestrator/app/api/render.py:534`
- Request: path param `job_id`
- Response: `RenderArtifactResponse` (thin transport DTO; no internal paths exposed)
  ```json
  {
    "artifact_id": "...",
    "project_id": "...",
    "render_plan_id": "...",
    "render_profile_id": "...",
    "mastering_profile_id": "...",
    "qa_report_id": "...",
    "renderer_version": "remotion-X.Y.Z",
    "width": 1280,
    "height": 720,
    "fps": 30.0,
    "video_codec": "h264",
    "audio_codec": "aac",
    "audio_sample_rate_hz": 48000,
    "audio_channels": 2,
    "duration_sec": 60.0,
    "file_size_bytes": 12345678,
    "checksum_sha256": "0123abcd...",
    "loudness_lufs": -16.3,
    "true_peak_dbtp": -9.2,
    "lifecycle_status": "approved",
    "qa_status": "final_approved",
    "video_url": "/render/{job_id}/video",
    "fingerprint": "...",
    "created_at": "ISO-8601"
  }
  ```
- Error codes: 400, 404, 500
- Security: `video_url` is always relative `/render/{job_id}/video`; internal filesystem paths never leaked
- Source of truth: canonical `FinalVideoArtifact` (P11 §4)
- Status: ACTIVE

### `GET /render/{job_id}/video` — `render_video()`
- File: `orchestrator/app/api/render.py:585`
- Request: path param `job_id`
- Response: media stream (`video/mp4`) — only `APPROVED` artifacts are served
- Headers: `Content-Type: video/mp4`, `Content-Disposition: attachment; filename="render-{job_id}.mp4"`, `Accept-Ranges: bytes`, `Content-Length: <bytes>`
- Error codes: 400 (invalid id), 403 (not approved), 404 (not found), 500
- Security: lifecycle MUST be `APPROVED`; qa_status MUST be `FINAL_APPROVED`
- Status: ACTIVE

---

## Render API Route Inventory (PROMPT 12)

| route | handler | status |
|---|---|---|
| `POST /render/preflight` | `preflight` | ACTIVE |
| `POST /render/finalize` | `finalize` | ACTIVE |
| `GET /render/{job_id}/status` | `render_status` | ACTIVE |
| `GET /render/{job_id}/qa` | `render_qa` | ACTIVE |
| `GET /render/{job_id}/artifact` | `render_artifact` | ACTIVE |
| `GET /render/{job_id}/video` | `render_video` | ACTIVE |

**6 active render routes.** Previous total: **58 active routes.** New total: **64 active routes.**



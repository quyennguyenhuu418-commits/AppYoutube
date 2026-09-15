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

---

## Naming Consistency

- Singular for path params (`/jobs/{job_id}`), not plural
- Lowercase, hyphenless
- No version prefix (e.g., no `/v1/`)

If a future route breaks these conventions, record it in
`docs/CHANGELOG_INTERNAL.md`.

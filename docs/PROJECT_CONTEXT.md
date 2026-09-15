# PROJECT_CONTEXT

## Project Purpose

videoAI is an end-to-end AI documentary generator. A user submits a topic; the
system autonomously researches the topic, drafts a thesis and YouTube titles,
writes a narration script, builds a visual storyboard, generates background
imagery, synthesizes narration audio, compiles a strict `SceneDefinition`
JSON, and finally renders an MP4 video plus a 9:16 vertical Short via a
Remotion renderer and FFmpeg.

## Current Product Goal

Ship an MVP that can take a single topic and produce a 2-minute (default
`target_duration_sec = 120`) 1920x1080 documentary MP4 with voiceover,
captions, animated stick-figure characters, props, and background imagery —
plus a Shorts clip. All stages run synchronously in a single FastAPI process
with a file-based job store.

## Current Architecture

Three-tier deployment on a single Windows host:

```
webapp (Next.js 14, port 3000)
   ↓  HTTP /api/jobs
orchestrator (FastAPI, port 8000)
   ↓  sequential stage loop
   ↓   ├─ Research (s1) → Research Intelligence Engine
   ↓   ├─ Thesis (s2)
   ↓   ├─ Titles (s3)
   ↓   ├─ Script (s4)
   ↓   ├─ Storyboard (s5)
   ↓   ├─ Assets (s6) — DALL-E / placeholder
   ↓   ├─ Narration (s7) — ElevenLabs / gTTS
   ↓   ├─ SceneDefinition JSON (s8)
   ↓   ├─ Validate (s9)
   ↓   ├─ Render (s10) — subprocess: `npx tsx src/index.ts`
renderer (Remotion v4) → workspace/{job_id}/output.mp4
   ↓
   └─ Shorts (s11) — FFmpeg 9:16 crop → workspace/{job_id}/shorts/
```

Persistence is a **file-based JSON store** (`orchestrator/app/db/store.py`).
`docker-compose.yml` defines optional `redis` and `postgres:16` services that
are **NOT** used by the code (see `docs/TECHNICAL_DEBT.md` C-006).

## Current Development Phase

**Phase: governance / reconstruction (PROMPT 0.5).** Product code is at
PROMPT-2 maturity (Research Intelligence Engine). The next major subsystem
will be the Script Quality Engine (s2–s5). Before any further product work,
the project requires persistent project-memory and governance artifacts,
which this prompt installs.

## Completed Systems

- **Pipeline foundation** (PROMPT 1) — 11-stage runner, schemas, providers,
  Remotion renderer, Next.js console, file-based job store.
- **Research Intelligence Engine** (PROMPT 2) — rich 17-section
  `ResearchPackage` schema, 13-step engine, hash-keyed 7-day cache, mock
  fixtures, REST inspection API, 34 unit/integration tests.

## Partial Systems

- **Research Engine** — contradiction detection, geography, and quantitative
  steps are **stubs** (see `docs/TECHNICAL_DEBT.md` C-001/C-002 and the
  Research Engine row in `docs/PROJECT_STATE.md`).
- **Renderer audio** — `sfx[]` and `music` fields are validated but no
  component reads them (see `docs/TECHNICAL_DEBT.md` C-004).
- **Renderer character metadata** — `Character.name`, `description`,
  `default_pose`, `Environment.name`, `Environment.mood` are validated but
  never rendered.

## Unverified Systems

- All Python tests (`orchestrator/tests/*.py`) — **WRITTEN, never executed**
  because Python 3.11+ is not installed on the development host. See
  `docs/TEST_STATUS.md`.
- `DuckDuckGoSearchProvider` and `RequestsContentFetchProvider` — declared
  `REAL` in code but never runtime-verified end-to-end.
- Repository git history — repo is **not a git repository**; no `.git/`
  directory exists. See `docs/TECHNICAL_DEBT.md` C-008.

## Next System

**Script Quality Engine** for stages s2–s5 (thesis → titles → script →
storyboard). Mirrors the Research Engine pattern: rich schema, claim/beats
registry, contradiction + uncertainty modeling, quality scoring, hash-keyed
cache, mock fixtures, dedicated REST inspection endpoints.

## Non-Goals (this phase)

- No database migration. No Celery / Redis. No S3 / OSS.
- No story intelligence. No script generation. No storyboard / animation /
  TTS / rendering / Shorts / thumbnail / publishing / analytics feature work
  (existing code stays untouched).
- No git initialization.
- No silent refactor of unrelated modules.

## Reading Order for a New AI Session

1. `docs/PROJECT_CONTEXT.md` (this file)
2. `docs/PROJECT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. The relevant contract doc (`DATA_CONTRACTS.md`, `API_CONTRACTS.md`,
   `PROVIDER_REGISTRY.md`, `PIPELINE_REGISTRY.md`)
5. The actual source code (never trust this doc over code)
6. `docs/TEST_STATUS.md`
7. `docs/TECHNICAL_DEBT.md`
8. `docs/SAFE_CHANGE_RULES.md`

If any doc conflicts with code, **code wins**. Record the conflict in
`docs/TECHNICAL_DEBT.md` and `docs/CHANGELOG_INTERNAL.md`.

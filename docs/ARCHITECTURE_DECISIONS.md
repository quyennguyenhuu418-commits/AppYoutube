# ARCHITECTURE_DECISIONS

Architecture Decision Records (ADR). Each ADR documents one major decision
already supported by the actual code. ADRs are immutable once written;
changes create a new ADR that supersedes the old one.

---

## ADR-001 — Python orchestrator + Remotion renderer (split-runtime)

**Status:** Accepted. Evidence present in current code.

**Context:** A documentary generator must orchestrate long-running LLM/TTS
work and produce frame-accurate video. Node and Python each excel at one
half of this problem.

**Decision:** Python FastAPI orchestrator handles research, LLM calls, TTS,
and produces a strict `SceneDefinition` JSON. The renderer is a separate
Node/Remotion v4 process invoked as a subprocess.

**Consequences:**
- Renderer subprocess failure does not corrupt orchestrator state.
- SceneDefinition JSON is the only cross-runtime contract; both sides must
  keep their copies in sync manually (see
  `docs/TECHNICAL_DEBT.md` C-004/C-005).
- Each runtime version can be upgraded independently.

**Evidence:**
- `orchestrator/app/main.py` (FastAPI entrypoint).
- `orchestrator/app/pipeline/stages/s10_render.py:49` (subprocess spawn).
- `renderer/src/index.ts` (Remotion CLI entrypoint).
- `renderer/package.json` declares `@remotion/* ^4.0`.

---

## ADR-002 — SceneDefinition as renderer boundary

**Status:** Accepted. Evidence: `orchestrator/app/schemas/scene_definition.py:288`.

**Context:** Remotion needs deterministic, frame-accurate input. LLM
output is not directly safe to feed into the renderer.

**Decision:** Stage 8 (`s8_scene_json.py`) produces a strict `SceneDefinition`
JSON validated by Pydantic in stage 9 (`s9_validate.py`). The renderer
loads this JSON and never calls an LLM.

**Consequences:**
- The renderer is fully deterministic and re-renderable.
- LLM output variations are absorbed before reaching the renderer.
- Cross-runtime contract drift is possible; see
  `docs/TECHNICAL_DEBT.md` C-004/C-005 and ADR-001.

**Evidence:**
- `orchestrator/app/pipeline/stages/s8_scene_json.py`.
- `orchestrator/app/pipeline/stages/s9_validate.py:35`.
- `renderer/src/lib/loadScene.ts:55`.

---

## ADR-003 — Provider abstraction via ABCs + factory functions

**Status:** Accepted.

**Context:** The pipeline needs LLM, TTS, image, search, and content-fetch
capabilities but no single vendor should be hard-coded. Tests must run
without paid API keys.

**Decision:** Each capability has an ABC in
`orchestrator/app/providers/base.py:132` and a factory in
`orchestrator/app/providers/{llm,tts,image,research_providers}.py` that
returns the real or mock implementation based on settings.

**Consequences:**
- Adding a new vendor means implementing one ABC and updating one factory.
- Mock implementations are first-class and used by tests.
- The orchestrator code is provider-agnostic.

**Evidence:**
- `orchestrator/app/providers/base.py` (LLMProvider, TTSProvider,
  ImageProvider, SearchProvider, ContentFetchProvider ABCs).
- `orchestrator/app/providers/llm.py:27`
  (`get_llm_provider()` factory).
- `orchestrator/app/providers/tts.py:26`,
  `image.py:24`,
  `research_providers.py` (`get_search_provider`,
  `get_content_fetch_provider`).

---

## ADR-004 — ResearchPackage as canonical research contract

**Status:** Accepted.

**Context:** Stage 1 originally returned a thin `ResearchPackage` (topic +
facts + open questions) that was insufficient to drive a quality
documentary. The new Research Intelligence Engine produces a 17-section
package with sources, claims, contradictions, timeline, geography,
quantitative facts, visual opportunities, story opportunities, synthesis,
and a quality score.

**Decision:** Promote the rich `ResearchPackage` (in
`orchestrator/app/schemas/research_package.py:454`) to the canonical
contract. The thin legacy schema (`research.py:22`) is preserved only as a
compat shim via `ResearchPackage.to_legacy_dict()`.

**Consequences:**
- Downstream stages consume the legacy dict for now; future stages can
  read the rich package directly.
- The legacy schema duplicates field names with the rich schema; future
  cleanup must keep `to_legacy_dict()` as the migration path.

**Evidence:**
- `orchestrator/app/schemas/research_package.py` (17-section schema).
- `orchestrator/app/schemas/research.py` (legacy compat).
- `orchestrator/app/research/engine.py` (engine that produces it).
- `orchestrator/app/pipeline/stages/s1_research.py:76` (writes both files).

---

## ADR-005 — Next.js frontend + FastAPI backend

**Status:** Accepted.

**Context:** The web console must poll job state and stream artifacts
without coupling to Python.

**Decision:** Next.js 14 (App Router) frontend on port 3000 with a rewrite
proxy `/api/* → http://localhost:8000/*`. Backend is FastAPI on port 8000.

**Consequences:**
- No CORS configuration needed in development.
- Single dev-host assumption; deployment to two hosts would require
  reconfiguration.
- The webapp is intentionally thin — all heavy logic lives in the
  orchestrator.

**Evidence:**
- `webapp/next.config.js:15` (rewrite rule).
- `webapp/package.json:25` (Next 14, React 18).
- `webapp/lib/api.ts:56` (typed fetch client).
- `start.bat:32` (launches both processes in separate windows).

---

## ADR-006 — Local file-based job store (no database)

**Status:** Accepted. May be revisited.

**Context:** For an MVP on a single dev host, a JSON file per job is
simpler than provisioning a database.

**Decision:** `orchestrator/app/db/store.py:130` persists jobs as JSON
files under `workspace/{job_id}/job.json`. `docker-compose.yml` defines
optional Redis and PostgreSQL services that are intentionally NOT wired
to the code.

**Consequences:**
- No SQLAlchemy, no migrations directory.
- Not safe for concurrent uvicorn workers writing the same job.
- Future scale-up must either serialize writes or migrate to SQLite/Postgres.

**Evidence:**
- `orchestrator/app/db/store.py:130` (active store).
- `docker-compose.yml:25` (declared but unused services).
- See `docs/TECHNICAL_DEBT.md` C-006.

---

## ADRs deferred

The following would be reasonable ADRs but lack sufficient code evidence
to write authoritatively yet:

- ADR-007 — Quality-gated stages (no current retry-with-quality logic).
- ADR-008 — Research cache invalidation policy (only TTL exists; no
  explicit invalidation).
- ADR-009 — Renderer audio wiring (currently inert; see
  `docs/TECHNICAL_DEBT.md` C-004).

These will be written when the corresponding systems are implemented.

---

## ADR-007 — Story Intelligence Engine (PROMPT 3)

**Problem**: Stages s2-s5 were naive single-LLM-call stubs that generated thesis, titles, script, and storyboard without traceability, scoring, or critique.

**Old architecture**: Each stage called LLM once with a hardcoded prompt. No traceability to research claims, no quality scoring, no hostile critique, no script revision.

**New architecture**: A `StoryEngine` class orchestrates 15 ordered steps that produce a canonical `StoryPackage`. The pipeline stage `s2_thesis` runs the engine. Stages s3-s5 are now read-only adapters that translate `StoryPackage` to legacy JSON files.

**Reason**: Production-grade documentary generation requires traceability (every claim traceable to a source), evaluation (hostile critique catches unsupported claims), and revision (critique → revision instructions → improved script).

**Migration approach**:
- s2 — full engine run, writes story_package.json + legacy thesis.json
- s3, s4, s5 — read story_package.json, write legacy titles/script/storyboard.json
- Downstream stages (s6-s11) unaffected; they still read legacy files

**Compatibility implications**: All legacy contracts preserved via `StoryPackage.to_legacy_*()` bridges. The new story_package.json is canonical and additive.

**Affected components**:
- `app/schemas/story.py` (NEW — 25 Pydantic models)
- `app/story/engine.py` (NEW — 15-step engine)
- `app/story/cache.py` (NEW — content-addressed cache)
- `app/api/story.py` (NEW — 9 REST endpoints)
- `app/pipeline/stages/s2_thesis.py` (REWRITTEN — runs engine)
- `app/pipeline/stages/s3_titles.py` (REWRITTEN — adapter)
- `app/pipeline/stages/s4_script.py` (REWRITTEN — adapter)
- `app/pipeline/stages/s5_storyboard.py` (REWRITTEN — adapter)
- `app/main.py` (MODIFIED — story router mounted)
- `app/core/config.py` (MODIFIED — 7 story settings added)
- `app/providers/mock_llm.py` (MODIFIED — MOCK_STORY_PACKAGE fixture)

## ADR-008 — Storyboard Intelligence Engine (PROMPT 4)

**Problem**: Stages s5 was a thin adapter that wrote a legacy 4-field `Storyboard` schema (`beats: [{summary, environment_id, characters, visual_intent, duration_sec}]`). It had no visual mode selection, no continuity engine, no evidence linking, no camera/motion planning, no asset reuse tracking, no quality scoring. The downstream `s6_assets` only used `environment_id`, and `s8_scene_json` only used `environment_id`, `duration_sec`, and `summary`.

**New architecture**: A `StoryboardEngine` class transforms the canonical `StoryPackage` (FINAL script) into a rich `StoryboardPackage v1` with 24 sections including visual_beats, continuity_state, asset_requirements, camera_plan, motion_plan, transition_plan, text_plan, audio_sync_points, diagram_specs, map_specs, timeline_specs, comparison_specs, data_visualization_specs, scene_definition_candidates, and a 14-axis storyboard_quality_score. Each beat carries purpose, visual_function, visual_mode, composition, characters, environment, props, action, camera plan, motion, transition, source_ids, claim_ids, evidence_trace, asset_requirements, information_alignment, reconstruction_confidence, and an uncertainty_treatment. The engine also bridges to a render-ready `SceneDefinitionCandidate` for each beat, so downstream Character/Asset/Animation systems can be deterministic.

**Reason**: A storyboard is not a list of pictures. It is the executable visual blueprint connecting NARRATION → INFORMATION → STORY → VISUAL COMMUNICATION → CHARACTER → ENVIRONMENT → CAMERA → MOTION → ASSETS → SCENE DEFINITION.

**Migration approach**:
- s5 — now runs the StoryboardEngine, writes both canonical `storyboard_package.json` and legacy `storyboard.json`
- s6_assets / s8_scene_json — continue to read legacy `storyboard.json`; can later read the rich `storyboard_package.json`
- All legacy contracts preserved via the existing `StoryPackage.to_legacy_*()` bridges

**Compatibility implications**: The legacy `Storyboard` schema is preserved. The new `StoryboardPackage` is additive. Future Character/Asset/Animation systems can be implemented on top of the rich package without touching the renderer.

**Affected components**:
- `app/schemas/storyboard.py` (NEW — 30+ Pydantic models, ~700 lines)
- `app/storyboard/engine.py` (NEW — Storyboard Intelligence Engine, ~1900 lines)
- `app/storyboard/cache.py` (NEW — content-addressed cache, ~110 lines)
- `app/storyboard/__init__.py` (NEW — public exports)
- `app/api/storyboard.py` (NEW — 9 REST endpoints)
- `app/api/__init__.py` (existing — storyboard router added)
- `app/main.py` (MODIFIED — storyboard router mounted)
- `app/pipeline/stages/s5_storyboard.py` (REWRITTEN — runs engine)
- `webapp/lib/api.ts` (MODIFIED — added Storyboard TypeScript types)
- `webapp/app/jobs/[id]/page.tsx` (MODIFIED — added View Storyboard link)
- `webapp/app/jobs/[id]/storyboard/page.tsx` (NEW — minimal UI)

---

## ADR-009 — Character System (PROMPT 5)

**Problem**: Storyboard emits `character_requirements` (visual role, color hints, count, reuse policy). `s8_scene_json` was letting the LLM invent `character_id`s at will. There was no canonical Character definition, no version control, no duplicate detection, no registry, no reuse strategy. Stick-figure `renderer/src/components/Character.tsx` was the only character source.

**New architecture**: A `CharacterSystemEngine` class transforms `character_requirements` into a canonical `CharacterSystemPackage v1` containing: 6 character archetypes (HUMAN_MALE/HUMAN_FEMALE/GROUP/EXPERT/NARRATOR/ABSTRACT), deterministic SVG generation (8 renderer-compatible poses × 11 expressions), pose/expression/wardrobe registries, 15-joint skeleton, 11-dimension deterministic quality scoring, character registry with cross-project reuse, duplicate detection via SHA-256 of normalized identity, and SceneDefinition bridges (`to_scene_definition_characters()` and `to_scene_definition_actors()`).

**Reason**: A character is a persistent production entity, not just a PNG. Without canonical character definitions, every stage reinvents characters and continuity breaks.

**Migration approach**:
- Character System emits `character_system_package.json` (canonical) and `characters/` directory
- s6 / s8 read optional canonical IDs if present (additive)
- Existing 8-pose renderer compatibility preserved
- `to_scene_definition_characters()` and `to_scene_definition_actors()` produce backward-compatible dicts

**Compatibility implications**: No breaking changes to existing `SceneDefinition.Character`/`Actor` schemas. New `CharacterDefinition` is additive. Existing renderer still works.

**Affected components**:
- `app/schemas/character.py` (NEW — ~700 lines, Pydantic models)
- `app/character/engine.py` (NEW — CharacterSystemEngine)
- `app/character/svg_generator.py` (NEW — deterministic SVG, validation)
- `app/character/cache.py` (NEW — content-addressed cache)
- `app/api/characters.py` (NEW — 14 REST endpoints)
- `webapp/app/jobs/[id]/characters/page.tsx` (NEW — minimal UI)
- `webapp/lib/api.ts` (MODIFIED — Character TypeScript types)

---

## ADR-010 — Unified Asset Intelligence Layer (PROMPT 6)

**Problem**: Character had a canonical system but Environment/Prop had only legacy `backgrounds/{env_id}.png` PNG generation. `s6` was a PNG generator, `s8` was letting the LLM invent `environment_id` and `prop_id` strings. There was no unified Asset abstraction — Character/Environment/Prop/Diagram/Overlay were 5 unrelated generation paths. No versioning, no reuse detection, no continuity, no canonical registry, no deterministic quality scoring.

**New architecture**: A unified Asset Intelligence Layer with:
- **Single `AssetReference` contract** — the only object passed to the renderer. Carries `asset_id`, `asset_type`, `version`, `variant`, `uri/path`, `format`, `dimensions`, `anchors`, `renderer_hints`, `metadata`.
- **Single canonical resolution path** — `AssetResolver` is the only decision point for reuse vs. generation. No other code decides asset existence.
- **Shared asset lifecycle** — DRAFT → GENERATING → GENERATED → VALIDATED → REVIEW → APPROVED → REJECTED → DEPRECATED → ARCHIVED. Only APPROVED assets are rendered.
- **Asset Registry** with `find_by_role`, `find_by_style`, `find_by_semantic_tags`, `find_reusable`, `find_latest_approved`, `find_similar`, `record_usage`, `approve`, `deprecate`. Supports `GLOBAL_ASSET`, `PROJECT_ASSET`, `SCENE_LOCAL_GENERATED_CANDIDATE`.
- **Deterministic 11-dimension quality scoring** — identity_consistency, semantic_correctness, style_consistency, composition_quality, resolution_quality, format_quality, continuity_readiness, reuse_quality, renderer_compatibility, metadata_completeness, animation_readiness. All scores trace to asset fields.
- **Content-addressed cache** — SHA-256 of (prompt + style + seed + provider_version) is the cache key. Idempotent re-runs hit the cache.
- **Provider abstraction** — `AssetProvider` (generate_image / generate_svg / generate_vector / validate / describe). The engine never knows specific provider business logic.
- **Reuse policies** — REUSE_ALWAYS, REUSE_PREFERRED, REUSE_ALLOWED, SCENE_LOCAL, NEVER_REUSE.
- **Security validation** — Detects scripts, event handlers, external URLs, javascript: URIs, path traversal, unsafe absolute paths, invalid extensions, invalid MIME.

**Reason**: A character is a persistent entity, but so is an environment or a prop. Without a unified abstraction, every subsystem invents its own asset conventions and the system cannot scale to 3D/video/audio/diagram/overlay assets.

**Migration approach**:
- s6_assets.py is **additive** — reads `asset_system_package.json` if present, continues to produce `backgrounds/{env_id}.png` for legacy compat
- s8_scene_json.py is **additive** — prepends canonical asset IDs from registry to LLM prompt, no LLM schema changes
- `AssetReference.to_scene_definition_environment()` produces a 4-key dict compatible with existing `Environment` schema
- No breaking changes to `SceneDefinition`, `CharacterSystemPackage`, `StoryboardPackage`, or any existing API

**Compatibility implications**: All existing schemas preserved. Renderer can opt into richer asset references in PROMPT 7/10.

**Affected components**:
- `app/schemas/asset.py` (NEW — ~700 lines, Asset/Environment/Prop/Registry/Reference/Resolution)
- `app/assets/engine.py` (NEW — AssetSystemEngine + AssetResolver)
- `app/assets/cache.py` (NEW — content-addressed cache)
- `app/assets/security.py` (NEW — shared SVG/path validation)
- `app/assets/provider.py` (NEW — Provider abstraction)
- `app/assets/s6_bridge.py` (NEW — backward-compatible bridge)
- `app/api/assets.py` (NEW — 13 REST endpoints)
- `app/pipeline/stages/s6_assets.py` (MODIFIED — additive)
- `app/pipeline/stages/s8_scene_json.py` (MODIFIED — additive)
- `app/core/paths.py` (MODIFIED — added asset path helpers)
- `webapp/app/jobs/[id]/assets/page.tsx` (NEW — minimal UI)
- `webapp/lib/api.ts` (MODIFIED — Asset TypeScript types)

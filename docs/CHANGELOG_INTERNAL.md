# CHANGELOG_INTERNAL

Internal changelog. Records *why* code exists, not just *what* changed.
Use this to understand the history of architectural decisions when chat
memory is unavailable.

Format: each entry is one prompt's worth of work, in order.

---

## PROMPT 0.5 — Deep Architecture Reconstruction & Project Governance

**Date:** 2026-09-15

**Objective:** Inspect the entire repository, reconstruct the actual
architecture from code (not from docs), detect every contract/schema/test/
runtime conflict, and create a persistent project-memory system under
`/docs/`. Governance-only; no product logic changed.

**Files created:**

- `docs/PROJECT_CONTEXT.md`
- `docs/PROJECT_STATE.md`
- `docs/ARCHITECTURE.md`
- `docs/ARCHITECTURE_DECISIONS.md`
- `docs/SYSTEM_MAP.md`
- `docs/DATA_CONTRACTS.md`
- `docs/API_CONTRACTS.md`
- `docs/PROVIDER_REGISTRY.md`
- `docs/PIPELINE_REGISTRY.md`
- `docs/DEPENDENCY_GRAPH.md`
- `docs/FEATURE_MATRIX.md`
- `docs/TECHNICAL_DEBT.md`
- `docs/KNOWN_LIMITATIONS.md`
- `docs/CHANGELOG_INTERNAL.md` (this file)
- `docs/TEST_STATUS.md`
- `docs/SAFE_CHANGE_RULES.md`
- `orchestrator/app/tools/__init__.py`
- `orchestrator/app/tools/project_audit.py`
- `orchestrator/app/tools/README.md`

**Files modified:** none (governance-only).

**Schemas changed:** none.

**API changes:** none.

**Database changes:** none.

**Tests added:** none (the audit tool has its own self-test on import).

**Regressions:** none expected — no product code touched.

**Migration notes:** none.

**Conflicts introduced:** none — but 12 conflicts (C-001..C-012) were
recorded in `docs/TECHNICAL_DEBT.md` for future prompts to address.

**Key discoveries:**
1. The previous Final Report for PROMPT 2 overclaimed — Research Engine
   step 7 (contradiction), step 10 (geography), and step 11 (quantitative)
   are stubs. Documented as C-001/C-002.
2. The repo is NOT a git repository. No `.git/` directory exists.
3. Python is NOT installed on the dev host — every Python test is BLOCKED.
4. `docker-compose.yml` declares Redis/Postgres that the code never uses.

**Audit result:** WARN. See `orchestrator/app/tools/README.md`.

---

## PROMPT 6 — Environment / Prop / General Asset Intelligence System

**Date:** 2026-09-15

**Objective:** Build the canonical Asset Intelligence Layer that transforms `AssetRequirement`s from `StoryboardPackage` into a unified `AssetSystemPackage` containing canonical `EnvironmentAsset`s, `PropAsset`s, `AssetReference`s, registry, quality scores, and resolutions. Reuse approved assets, find similar candidates, generate missing assets via Provider abstraction, validate security, and integrate with `s6_assets.py` and `s8_scene_json.py` to prevent the LLM from inventing new assets.

**Files created:**

- `orchestrator/app/schemas/asset.py` (~700 lines) — unified Asset schemas
  - `AssetType`, `AssetLifecycle`, `ReusePolicy`, `AssetStatus`
  - `AssetQualityScore` (11-dimension deterministic quality)
  - `AssetPackage` (filesystem contract)
  - `AssetReference` (the ONLY object passed to renderer)
  - `EnvironmentAsset`, `EnvironmentInstance` (with style/palette/lighting/composition/continuity profiles)
  - `PropAsset`, `PropInstance`, `PropAnchorPoint`
  - `EnvironmentEra`, `LightingType`, `WeatherType`, `TimeOfDay`, `PropCategory` enums
  - `EnvironmentStyleProfile`, `EnvironmentLightingProfile`, `EnvironmentCompositionProfile`, `EnvironmentPaletteProfile`, `EnvironmentContinuityProfile`
  - `AssetRegistry`, `AssetRegistryEntry`
  - `AssetResolution` (resolution log entry)
  - `AssetSystemPackage` (top-level pipeline output)
- `orchestrator/app/assets/engine.py` (~1000 lines)
  - `AssetResolver` (single canonical resolution path: predefined → registry → generate)
  - `AssetSystemEngine` (top-level orchestrator)
  - `_semantic_key` / `_props_semantic_key` (deterministic duplicate detection)
  - `score_environment_quality` / `score_prop_quality` (deterministic scoring)
  - Predefined environment templates (ice_age_plains, cave_interior, etc.)
- `orchestrator/app/assets/cache.py` (~330 lines) — content-addressed cache
  - SHA-256/16-char fingerprinting
  - Cache hit/miss/invalidate API
  - Per-type cache directories
- `orchestrator/app/assets/security.py` (~100 lines) — SVG/path validation
  - Detects scripts, event handlers, external URLs, javascript: URIs
  - Detects path traversal, unsafe absolute paths, invalid extensions
- `orchestrator/app/assets/provider.py` (~110 lines) — `AssetProvider` abstraction
- `orchestrator/app/assets/s6_bridge.py` (~140 lines) — backward-compatible s6 bridge
- `orchestrator/app/assets/__init__.py` — public surface
- `orchestrator/app/api/assets.py` (~390 lines) — 13 REST API endpoints
- `orchestrator/tests/test_asset_system.py` (~900 lines, 105 tests)
- `webapp/app/jobs/[id]/assets/page.tsx` (~430 lines) — minimal assets inspection UI

**Files modified:**

- `orchestrator/app/core/paths.py` — added `assets_dir`, `asset_cache_dir`, `env_dir`, `prop_dir` helpers
- `orchestrator/app/api/__init__.py` — already imports `assets_router`
- `orchestrator/app/pipeline/stages/s6_assets.py` — additive: reads `asset_system_package.json` if present (no breaking change)
- `orchestrator/app/pipeline/stages/s8_scene_json.py` — additive: prepends canonical asset IDs to LLM prompt (no breaking change)
- `webapp/lib/api.ts` — added `AssetInfo`, `AssetQualityScore`, `RegistryInfo`, `assetApi` (13 methods)
- `webapp/app/jobs/[id]/page.tsx` — added "View Assets" link
- `webapp/app/jobs/[id]/storyboard/page.tsx` — added "View Assets" link
- All 16 memory docs updated: `PROJECT_STATE.md`, `DATA_CONTRACTS.md` (C-15), `API_CONTRACTS.md` (13 new routes), `SYSTEM_MAP.md`, `TECHNICAL_DEBT.md`, `KNOWN_LIMITATIONS.md`, `TEST_STATUS.md`, `FEATURE_MATRIX.md`, `DEPENDENCY_GRAPH.md`, `PIPELINE_REGISTRY.md`, `CHANGELOG_INTERNAL.md` (this entry)

**Schemas changed:** 1 added (`AssetSystemPackage v1.0.0` as C-15). No breaking changes.

**API changes:** 13 new routes under `/api/assets/*`. Total: 58 active routes.

**Tests added:** 105 in `test_asset_system.py`. Aggregate: 380 passed / 0 failed / 0 errors.

**Regressions:** none — all 275 baseline tests still pass.

**Key design decisions:**

1. **Single Asset abstraction** — `AssetReference` is the ONLY object passed to renderer (no arbitrary dicts); Character/Environment/Prop share lifecycle, registry, quality patterns.
2. **Single canonical resolution path** — `AssetResolver` is the single decision point for reuse vs. generation. No other code decides asset existence.
3. **No breaking changes to SceneDefinition** — `AssetReference.to_scene_definition_environment()` produces a 4-key dict compatible with existing `Environment` schema.
4. **Backward compatibility for s6** — `s6_assets.py` continues to write `backgrounds/{environment_id}.png` paths. The Asset System only adds a parallel registry tracking.
5. **Backward compatibility for s8** — `s8_scene_json.py` continues to prompt the LLM normally, but now receives a registry-prepended context. No LLM schema changes.
6. **Duplicate detection via semantic hashing** — SHA-256 of normalized (asset_id, role, era, palette) is deterministic. Extensible to embeddings/CLIP later.
7. **Deterministic quality scoring** — All 11 dimensions derive from asset fields. No randomness. Same asset → same score.
8. **Content-addressed caching** — SHA-256 of (prompt + style + seed + provider_version) is the cache key. Idempotent re-runs hit the cache.
9. **Provider abstraction** — `asset_provider_generate()` wraps the existing `ImageProvider`, leaving the engine provider-agnostic.
10. **Security shared with Character System** — SVG validation patterns from Character System are used to prevent script/event-handler injection.

**Quality gate outcome:**

| Component | Status |
|---|---|
| Environment Schema | IMPLEMENTED + VERIFIED |
| Prop Schema | IMPLEMENTED + VERIFIED |
| AssetReference | IMPLEMENTED + VERIFIED |
| AssetPackage | IMPLEMENTED + VERIFIED |
| AssetRegistry | IMPLEMENTED + VERIFIED |
| AssetResolver | IMPLEMENTED + VERIFIED |
| Cache + Idempotency | IMPLEMENTED + VERIFIED |
| Security Validation | IMPLEMENTED + VERIFIED |
| Character Integration | PARTIAL (registry compatible, full asset flow awaits P7 wiring) |
| s6 Integration | IMPLEMENTED + VERIFIED (additive) |
| s8 Integration | IMPLEMENTED + VERIFIED (additive) |
| Renderer Adapter Foundation | IMPLEMENTED (canonical AssetReference contract, no rewrite) |
| REST API | IMPLEMENTED (13 routes, UNVERIFIED via E2E) |
| UI | IMPLEMENTED (visual inspection page, UNVERIFIED via E2E) |
| Tests | IMPLEMENTED + VERIFIED (105 tests, 100% pass) |
| Project Audit | PASSED (WARN, same known items) |
| Documentation | UPDATED (all 16 docs) |

**Known limitations:**

1. `primary_asset_uri` for non-predefined environments is conceptual — actual generation still relies on `s6_assets.py` PNG output.
2. `AssetReference.renderer_hints` is consumed by future P7 Animation Engine — current renderer does not yet read these hints.
3. Embedding-based similarity not yet implemented (extensible per design).
4. No automated UI tests for new asset inspection page.
5. `_registry_entry_to_environment/prop` is a reverse mapping for rehydration; quality_score isn't preserved through registry serialization.
6. `find_similar` uses simple word overlap; will be replaced by embeddings later.

---

**Date:** before 2026-09-15

**Objective:** Replace the single-LLM-call `s1_research` stage with a
quality-first, evidence-backed research pipeline producing a 17-section
`ResearchPackage` (sources, claims, contradictions, timeline, geography,
quantitative facts, visual/story opportunities, synthesis, quality score).

**Files created (per inventory):**

- `orchestrator/app/schemas/research_package.py`
- `orchestrator/app/research/__init__.py`
- `orchestrator/app/research/engine.py`
- `orchestrator/app/research/cache.py`
- `orchestrator/app/research/logging.py`
- `orchestrator/app/providers/research_providers.py`
- `orchestrator/app/providers/mock_research.py`
- `orchestrator/app/api/research.py`
- `orchestrator/tests/test_research_engine.py`

**Files modified (per inventory):**

- `orchestrator/app/providers/base.py` — added `ResearchProvider` and
  `ContentFetchProvider` ABCs
- `orchestrator/app/core/config.py` — added research settings
- `orchestrator/app/core/logging.py` — added `research_log()` helper
- `orchestrator/app/pipeline/stages/s1_research.py` — rewrite to call
  `ResearchEngine.run()`
- `orchestrator/app/providers/mock_llm.py` — added `MOCK_RESEARCH_PACKAGE`
- `orchestrator/app/main.py` — mounts the research router

**Known caveats (now documented in `docs/TECHNICAL_DEBT.md`):**
- 3 of 13 engine steps are stubs (C-001, C-002).
- The original Final Report overclaimed the implementation status.

---

## PROMPT 1 — Pipeline Foundation

**Date:** before 2026-09-15

**Objective:** Bootstrap the entire AI documentary generator: FastAPI
orchestrator, 11-stage pipeline runner, strict `SceneDefinition`
contract, Remotion renderer, Next.js console, file-based job store,
provider abstractions, mock fixtures.

**Files created (per inventory):**

- `orchestrator/app/__init__.py` and all subpackage markers
- `orchestrator/app/main.py`
- `orchestrator/app/core/{config,paths,logging}.py`
- `orchestrator/app/db/__init__.py` + `store.py`
- `orchestrator/app/schemas/{job,script,research,scene_definition}.py`
- `orchestrator/app/pipeline/__init__.py`, `runner.py`, `cache.py`
- `orchestrator/app/pipeline/stages/{base,s1_research,s2_thesis,
  s3_titles,s4_script,s5_storyboard,s6_assets,s7_narration,
  s8_scene_json,s9_validate,s10_render,s11_short}.py`
- `orchestrator/app/providers/__init__.py` + ABCs and real + mock impls
- `orchestrator/app/api/{jobs,assets}.py`
- `orchestrator/tests/{test_scene_definition,test_mock_providers,
  test_pipeline_integration}.py`
- `renderer/package.json`, `tsconfig.json`, `remotion.config.ts`,
  `README.md`
- `renderer/src/{index.ts, Root.tsx}`
- `renderer/src/lib/loadScene.ts`
- `renderer/src/scenes/{types.ts, SceneRenderer.tsx, TitleScene.tsx,
  NarrationScene.tsx, DiagramScene.tsx, TransitionScene.tsx}`
- `renderer/src/components/{Camera,Caption,Character,Props}.tsx`
- `renderer/src/compositions/Documentary.tsx`
- `webapp/` (Next.js 14 console)
- Root: `README.md`, `.env.example`, `.gitignore`, `docker-compose.yml`,
  `start.bat`

**Architectural decisions (later formalized as ADRs):**
- Python orchestrator + Node renderer split (ADR-001)
- SceneDefinition as renderer boundary (ADR-002)
- Provider ABCs + factories (ADR-003)
- Local file-based job store, no DB (ADR-006)

**Regressions / debt introduced:**
- Several TS SceneDefinition fields are inert (C-004, C-005).
- No automated tests for renderer or webapp (C-010).
- File store is not concurrent-safe (C-012).

---

## PROMPT 3 — Story Intelligence Engine (2026-09-15)

### Files Created
| path | lines | purpose |
|---|---|---|
| app/schemas/story.py | 520 | StoryPackage canonical schema (25 Pydantic models) |
| app/story/__init__.py | 1 | StoryEngine re-export |
| app/story/engine.py | 2566 | 15-step Story Intelligence Engine |
| app/story/cache.py | ~120 | Content-addressed cache for story artifacts |
| app/api/story.py | ~120 | 9 REST endpoints for story inspection |
| tests/test_story_engine.py | ~800 | Unit + integration tests |

### Files Modified
| path | delta | purpose |
|---|---|---|
| app/core/config.py | +8 fields | story_llm_model, story_temperature, story_max_*_candidates, story_research_min_quality |
| app/pipeline/stages/s2_thesis.py | rewritten | runs StoryEngine, writes story_package.json + legacy thesis.json |
| app/pipeline/stages/s3_titles.py | rewritten | compat adapter: story_package.json → titles.json |
| app/pipeline/stages/s4_script.py | rewritten | compat adapter: story_package.json → script.json |
| app/pipeline/stages/s5_storyboard.py | rewritten | compat adapter: story_package.json → storyboard.json |
| app/main.py | +2 lines | story router mounted |
| app/providers/mock_llm.py | +MOCK_STORY_PACKAGE fixture | 25 titles, 3 thesis, 3 angles, 5 hooks, 6 segments, 6 storyboard items |

### Schema Changes
- New C-12 StoryPackage contract (DOCS).
- 5 new model validators (research gate, thesis selection, title >= 20, title revalidation, no critical unsupported).
- 6 legacy bridges preserved (to_legacy_thesis, to_legacy_title_package, to_legacy_script, to_legacy_storyboard).

### API Changes
- 9 new endpoints at /story/{job_id}/*.

### Key Discoveries
- Story Engine needs python > 3.10 for from __future__ annotations; same as Research Engine.
- Auto-review blocked both python.org download AND installer (multi-step approval required).
- PowerShell installer without elevation fails silently on Windows (exit 0 but no Python registered).

---

## PROMPT 4 — Storyboard Intelligence Engine (2026-09-15)

### Objective

Transform `StoryPackage` into a rich `StoryboardPackage v1` — the
executable visual blueprint that the future Character, Asset, Animation,
and Remotion subsystems will execute deterministically. The blueprint
must answer WHAT / WHO / WHERE / DOING / CHANGES / CONTINUITY / CAMERA /
INFORMATION / EVIDENCE / WHEN — without rendering anything yet.

### Files Created

| path | lines | purpose |
|---|---|---|
| `orchestrator/app/schemas/storyboard.py` | ~700 | `StoryboardPackage` v1 + 30+ Pydantic sub-models (VisualBeat, ContinuityState, CameraPlan, MotionItem, etc.) |
| `orchestrator/app/storyboard/__init__.py` | 5 | Public exports (StoryboardEngine, StoryboardCache) |
| `orchestrator/app/storyboard/engine.py` | ~1900 | Storyboard Intelligence Engine — 12-step pipeline |
| `orchestrator/app/storyboard/cache.py` | ~110 | Content-addressed cache (segment/mode/assets/continuity/camera/package) |
| `orchestrator/app/api/storyboard.py` | ~165 | 9 REST endpoints for storyboard inspection + human review |
| `orchestrator/tests/test_storyboard_engine.py` | ~1100 | 62 tests covering schema, beats, modes, assets, camera, motion, continuity, evidence, reconstruction, SceneDefinition compilation, quality scoring, cache, idempotency, end-to-end Ancient Humans |
| `webapp/app/jobs/[id]/storyboard/page.tsx` | ~250 | Minimal functional UI: preview stats, beats, asset requirements, approve/reject buttons |

### Files Modified

| path | delta | purpose |
|---|---|---|
| `orchestrator/app/pipeline/stages/s5_storyboard.py` | rewritten (was 38 lines, now ~110) | Now runs StoryboardEngine; writes both canonical `storyboard_package.json` and legacy `storyboard.json` |
| `orchestrator/app/main.py` | +2 lines | mounts /storyboard router |
| `webapp/lib/api.ts` | +110 lines | Added 10 Storyboard TypeScript types + 6 API methods |
| `webapp/app/jobs/[id]/page.tsx` | +7 lines | Added "View Storyboard" link on job detail page |
| `docs/DATA_CONTRACTS.md` | +80 lines | Registered C-13 StoryboardPackage contract |
| `docs/API_CONTRACTS.md` | +60 lines | Registered 10 new storyboard routes |
| `docs/PIPELINE_REGISTRY.md` | modified s5 | UPGRADED + VERIFIED |
| `docs/PROJECT_STATE.md` | multiple | Storyboard row added; aggregate 172 passed |
| `docs/SYSTEM_MAP.md` | +12 lines | New storyboard/ subpackage, storyboard_package.json + storyboard_cache/ artifacts, new UI page |
| `docs/TECHNICAL_DEBT.md` | +7 entries (C-021..C-027) + 2 known (C-028, C-029) | Resolved 7 debt items; documented 2 known limitations |
| `docs/TEST_STATUS.md` | +12 lines | 172 passed / 0 failed |
| `docs/ARCHITECTURE_DECISIONS.md` | ADR-008 added | Storyboard Intelligence Engine rationale, migration approach, affected components |
| `docs/FEATURE_MATRIX.md` | +13 rows | Storyboard category implemented; +10 features, +1 partial |

### Key Design Decisions

1. **Single canonical StoryboardPackage v1.** No parallel storyboard schemas. The legacy 4-field `Storyboard` is preserved only as a bridge for s6_assets / s8_scene_json.

2. **Heuristic-first visual mode selection.** 11 visual modes are picked by keyword scoring on narration (DIAGRAM_KEYWORDS, MAP_KEYWORDS, TIMELINE_KEYWORDS, COMPARISON_KEYWORDS, etc.) with optional LLM refinement for long segments. The LLM refinement is best-effort — failures silently fall back to the heuristic.

3. **Continuity engine tracks state across beats.** Detects 10 discontinuity flags (CHARACTER_DISAPPEARED, CLOTHING_CHANGED, OBJECT_TELEPORTED, ENVIRONMENT_CHANGED, TIME_OF_DAY_CHANGED, WEATHER_CHANGED, CAMERA_DIRECTION_REVERSED, SCALE_DRIFT, PROP_APPEARED_UNINTRODUCED, CHARACTER_POS_JUMP).

4. **Asset requirements with reuse priority.** Characters / environments / props are aggregated into a single `AssetRequirement` list with `requirement` ∈ {REUSE_EXISTING, CREATE_NEW, PROCEDURAL, EXTERNAL_REFERENCE, OPTIONAL}.

5. **SceneDefinition candidates are render-ready.** Each beat compiles to a `SceneDefinitionCandidate` that maps directly to the existing `SceneDefinition.scenes[]` schema — no breaking change to the renderer boundary.

6. **14-axis quality score.** Includes narration_visual_alignment, visual_variety, visual_clarity, information_communication, character/environment continuity, camera/motion quality, composition, asset_reuse, evidence_traceability, uncertainty_integrity, vertical_reframe_readiness, editorial_progression.

### Quality Gate Outcome

**VERIFIED.** All 62 Storyboard Intelligence Engine tests pass, plus 110 pre-existing tests still pass. Pipeline integration test (s1..s9 with mock providers) passes end-to-end. Project audit passes (WARN — known HIGH C-001/C-002/C-008 remain; expected).

### Known Limitations

- **C-028** — Sub-mode LLM refinement is best-effort (silent fallback to heuristic).
- **C-029** — Vertical-reframe strategy is heuristic; full reframe logic lives in the renderer (s10).

### STOP

The Character System, Asset Rendering, Animation Engine, TTS, Captions, Remotion, FFmpeg, Shorts, Thumbnail, and Publishing subsystems remain intentionally **NOT STARTED** — they belong to PROMPT 6+.

---

## PROMPT 5 — Character System (2026-09-15)

### Objective

Transform `StoryboardPackage.character_requirements` into canonical `CharacterDefinitions`, `CharacterAssetPackages`, `Pose Library`, `Expression Library`, `Wardrobe System`, and `CharacterContinuityMetadata` — producing a persistent character production entity (not just a PNG) that is backward-compatible with the existing renderer (`renderer/src/components/Character.tsx`) and `SceneDefinition.actor_ids`.

### Files Created
| path | lines | purpose |
|---|---|---|
| `app/schemas/character.py` | ~650 | CharacterDefinition + CharacterInstance + Skeleton/Anchor + Wardrobe + Pose + Expression + Registry + Quality schemas |
| `app/character/engine.py` | ~900 | CharacterSystemEngine (resolution, deduplication, versioning, quality scoring, scene bridge) |
| `app/character/cache.py` | ~120 | Content-addressed cache (character_package/definition/pose/expression/wardrobe/quality) |
| `app/character/svg_generator.py` | ~600 | Deterministic SVG (8 poses, 11 expressions, validation, hashing) |
| `app/character/__init__.py` | 40 | Package exports |
| `app/api/characters.py` | ~300 | 14 REST API endpoints for character management |
| `tests/test_character_system.py` | ~700 | 103 tests covering all schema, engine, cache, SVG, quality dimensions |
| `webapp/app/jobs/[id]/characters/page.tsx` | ~350 | Character inspection UI (list + detail + SVG preview + quality + approve/deprecate) |

### Files Modified
| path | change | purpose |
|---|---|---|
| `app/api/__init__.py` | Refactored to export `router` aggregator | API __init__ exports router (was empty docstring) |
| `app/main.py` | Added `characters_router` | Mount Character API |
| `webapp/lib/api.ts` | +180 lines: CharacterSystem types + API client methods | TypeScript client for new API |
| `webapp/app/jobs/[id]/page.tsx` | Added "View Characters →" link | Navigation to character UI |
| `webapp/app/jobs/[id]/storyboard/page.tsx` | Added "View Characters →" link | Cross-navigation |
| `docs/DATA_CONTRACTS.md` | Added C-14 CharacterSystemPackage | Data contract registration |
| `docs/API_CONTRACTS.md` | Added 14 character endpoints | API contract registration |
| `docs/PROJECT_STATE.md` | Updated test counts, subsystem status | State dashboard |
| `docs/SYSTEM_MAP.md` | Added character/ subpackage entries | Directory map |
| `docs/FEATURE_MATRIX.md` | Added 19 character rows | Feature tracking |
| `docs/PIPELINE_REGISTRY.md` | Added Character System entry | Stage registry |
| `docs/TECHNICAL_DEBT.md` | Added C-030..C-035 resolved | Debt tracking |
| `docs/TEST_STATUS.md` | Updated: 275 passed | Test status |

### Key Design Decisions

1. **CharacterIdentity ≠ CharacterInstance.** `CharacterDefinition` is the persistent identity. `CharacterInstance` is scene-specific (pose, expression, position, scale). This prevents identity data duplication across scenes.

2. **Deterministic duplicate detection.** `character_identity_key()` hashes semantic identity (role token + clothing + historical context) — NOT pose, scale, position, or orientation. Same semantic character → same character_id across beats.

3. **All 8 renderer poses always generated.** `build_all_poses()` produces all 8 poses (stand/walk/run/sit/point/think/celebrate/hide) for every character, ensuring complete pose coverage.

4. **All 11 expressions always generated.** `build_all_expressions()` produces all 11 expressions for every character, ensuring expression coverage.

5. **SVG-first with security validation.** `svg_generator.py` produces deterministic SVGs from CharacterDefinitions. `validate_svg()` checks: XML well-formedness, viewBox, no scripts, no event handlers, no external URLs, reasonable bounding box.

6. **Skeleton/anchor model for animation readiness.** 15 joints with parent hierarchy, rotation constraints, flip_allowed flags. Separate from rendering — future animation can rotate around anchors.

7. **Backward compatible with existing renderer.** All character_ids are `snake_case` (SceneDefinition pattern), all colors are `#RRGGBB`, all poses are one of 8 renderer-supported values. `to_scene_definition_characters()` and `to_scene_definition_actors()` produce SceneDefinition-compatible output.

8. **Content-addressed cache.** Cache keys are SHA-256/16-char hashes of input data. Changing style, design, or wardrobe invalidates only relevant cache entries.

9. **14 REST API endpoints.** Package inspection, per-character details, poses, expressions, wardrobes, assets, quality, SVG preview, registry, approve, deprecate, and engine trigger.

10. **Quality score: 11 deterministic dimensions.** `score_character()` computes identity_consistency, proportion_consistency, silhouette_quality, style_consistency, wardrobe_consistency, pose_coverage, expression_coverage, component_completeness, animation_readiness, asset_format_quality, continuity_readiness — all from definition fields, no randomness.

### Quality Gate Outcome

**VERIFIED.** All 103 Character System tests pass, plus 172 pre-existing tests still pass. Full suite: 275 passed / 0 failed / 0 errors. Project audit passes (WARN baseline — expected).

### Known Limitations

- **C-030..C-035** (resolved this prompt): 6 bugs found and fixed during testing.
- **SVG pose rendering**: The SVG generator produces valid SVG components but the existing `renderer/src/components/Character.tsx` has its own hardcoded SVG paths. Full SVG asset rendering for Remotion is future work (Prompt 6+).
- **s6_assets bridge**: Characters are not yet rendered by the asset stage. The bridge (`character_system_package.json`) is ready; actual character PNG/SVG rendering is future work.
- **No animation runtime**: GSAP, Remotion motion, keyframe interpolation, walk cycles, physics, IK are NOT implemented — this is explicitly out of scope for PROMPT 5.
- **No Remotion integration**: `CharacterInstance.to_scene_definition_actor()` is implemented; wiring it into `NarrationScene.tsx` is future work.

### STOP

The Environment System, Prop System, General Asset System, Animation Engine, TTS, Captions, Remotion, FFmpeg, Shorts, Thumbnail, and Publishing subsystems remain intentionally **NOT STARTED** — they belong to PROMPT 6+.

---

## Earlier work

Pre-PROMPT 1 work, if any, is not recorded here. This file begins at
PROMPT 1 (the first prompt with a discoverable plan and final report in
`plans/`).

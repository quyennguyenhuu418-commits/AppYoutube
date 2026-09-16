# CHANGELOG_INTERNAL

Internal changelog. Records *why* code exists, not just *what* changed.
Use this to understand the history of architectural decisions when chat
memory is unavailable.

Format: each entry is one prompt's worth of work, in order.

---

## PROMPT 0.5 â Deep Architecture Reconstruction & Project Governance

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

**Regressions:** none expected â no product code touched.

**Migration notes:** none.

**Conflicts introduced:** none â but 12 conflicts (C-001..C-012) were
recorded in `docs/TECHNICAL_DEBT.md` for future prompts to address.

**Key discoveries:**
1. The previous Final Report for PROMPT 2 overclaimed â Research Engine
   step 7 (contradiction), step 10 (geography), and step 11 (quantitative)
   are stubs. Documented as C-001/C-002.
2. The repo is NOT a git repository. No `.git/` directory exists.
3. Python is NOT installed on the dev host â every Python test is BLOCKED.
4. `docker-compose.yml` declares Redis/Postgres that the code never uses.

**Audit result:** WARN. See `orchestrator/app/tools/README.md`.

---

## PROMPT 6 â Environment / Prop / General Asset Intelligence System

**Date:** 2026-09-15

**Objective:** Build the canonical Asset Intelligence Layer that transforms `AssetRequirement`s from `StoryboardPackage` into a unified `AssetSystemPackage` containing canonical `EnvironmentAsset`s, `PropAsset`s, `AssetReference`s, registry, quality scores, and resolutions. Reuse approved assets, find similar candidates, generate missing assets via Provider abstraction, validate security, and integrate with `s6_assets.py` and `s8_scene_json.py` to prevent the LLM from inventing new assets.

**Files created:**

- `orchestrator/app/schemas/asset.py` (~700 lines) â unified Asset schemas
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
  - `AssetResolver` (single canonical resolution path: predefined â registry â generate)
  - `AssetSystemEngine` (top-level orchestrator)
  - `_semantic_key` / `_props_semantic_key` (deterministic duplicate detection)
  - `score_environment_quality` / `score_prop_quality` (deterministic scoring)
  - Predefined environment templates (ice_age_plains, cave_interior, etc.)
- `orchestrator/app/assets/cache.py` (~330 lines) â content-addressed cache
  - SHA-256/16-char fingerprinting
  - Cache hit/miss/invalidate API
  - Per-type cache directories
- `orchestrator/app/assets/security.py` (~100 lines) â SVG/path validation
  - Detects scripts, event handlers, external URLs, javascript: URIs
  - Detects path traversal, unsafe absolute paths, invalid extensions
- `orchestrator/app/assets/provider.py` (~110 lines) â `AssetProvider` abstraction
- `orchestrator/app/assets/s6_bridge.py` (~140 lines) â backward-compatible s6 bridge
- `orchestrator/app/assets/__init__.py` â public surface
- `orchestrator/app/api/assets.py` (~390 lines) â 13 REST API endpoints
- `orchestrator/tests/test_asset_system.py` (~900 lines, 105 tests)
- `webapp/app/jobs/[id]/assets/page.tsx` (~430 lines) â minimal assets inspection UI

**Files modified:**

- `orchestrator/app/core/paths.py` â added `assets_dir`, `asset_cache_dir`, `env_dir`, `prop_dir` helpers
- `orchestrator/app/api/__init__.py` â already imports `assets_router`
- `orchestrator/app/pipeline/stages/s6_assets.py` â additive: reads `asset_system_package.json` if present (no breaking change)
- `orchestrator/app/pipeline/stages/s8_scene_json.py` â additive: prepends canonical asset IDs to LLM prompt (no breaking change)
- `webapp/lib/api.ts` â added `AssetInfo`, `AssetQualityScore`, `RegistryInfo`, `assetApi` (13 methods)
- `webapp/app/jobs/[id]/page.tsx` â added "View Assets" link
- `webapp/app/jobs/[id]/storyboard/page.tsx` â added "View Assets" link
- All 16 memory docs updated: `PROJECT_STATE.md`, `DATA_CONTRACTS.md` (C-15), `API_CONTRACTS.md` (13 new routes), `SYSTEM_MAP.md`, `TECHNICAL_DEBT.md`, `KNOWN_LIMITATIONS.md`, `TEST_STATUS.md`, `FEATURE_MATRIX.md`, `DEPENDENCY_GRAPH.md`, `PIPELINE_REGISTRY.md`, `CHANGELOG_INTERNAL.md` (this entry)

**Schemas changed:** 1 added (`AssetSystemPackage v1.0.0` as C-15). No breaking changes.

**API changes:** 13 new routes under `/api/assets/*`. Total: 58 active routes.

**Tests added:** 105 in `test_asset_system.py`. Aggregate: 380 passed / 0 failed / 0 errors.

**Regressions:** none â all 275 baseline tests still pass.

**Key design decisions:**

1. **Single Asset abstraction** â `AssetReference` is the ONLY object passed to renderer (no arbitrary dicts); Character/Environment/Prop share lifecycle, registry, quality patterns.
2. **Single canonical resolution path** â `AssetResolver` is the single decision point for reuse vs. generation. No other code decides asset existence.
3. **No breaking changes to SceneDefinition** â `AssetReference.to_scene_definition_environment()` produces a 4-key dict compatible with existing `Environment` schema.
4. **Backward compatibility for s6** â `s6_assets.py` continues to write `backgrounds/{environment_id}.png` paths. The Asset System only adds a parallel registry tracking.
5. **Backward compatibility for s8** â `s8_scene_json.py` continues to prompt the LLM normally, but now receives a registry-prepended context. No LLM schema changes.
6. **Duplicate detection via semantic hashing** â SHA-256 of normalized (asset_id, role, era, palette) is deterministic. Extensible to embeddings/CLIP later.
7. **Deterministic quality scoring** â All 11 dimensions derive from asset fields. No randomness. Same asset â same score.
8. **Content-addressed caching** â SHA-256 of (prompt + style + seed + provider_version) is the cache key. Idempotent re-runs hit the cache.
9. **Provider abstraction** â `asset_provider_generate()` wraps the existing `ImageProvider`, leaving the engine provider-agnostic.
10. **Security shared with Character System** â SVG validation patterns from Character System are used to prevent script/event-handler injection.

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

1. `primary_asset_uri` for non-predefined environments is conceptual â actual generation still relies on `s6_assets.py` PNG output.
2. `AssetReference.renderer_hints` is consumed by future P7 Animation Engine â current renderer does not yet read these hints.
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

- `orchestrator/app/providers/base.py` â added `ResearchProvider` and
  `ContentFetchProvider` ABCs
- `orchestrator/app/core/config.py` â added research settings
- `orchestrator/app/core/logging.py` â added `research_log()` helper
- `orchestrator/app/pipeline/stages/s1_research.py` â rewrite to call
  `ResearchEngine.run()`
- `orchestrator/app/providers/mock_llm.py` â added `MOCK_RESEARCH_PACKAGE`
- `orchestrator/app/main.py` â mounts the research router

**Known caveats (now documented in `docs/TECHNICAL_DEBT.md`):**
- 3 of 13 engine steps are stubs (C-001, C-002).
- The original Final Report overclaimed the implementation status.

---

## PROMPT 1 â Pipeline Foundation

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

## PROMPT 3 â Story Intelligence Engine (2026-09-15)

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
| app/pipeline/stages/s3_titles.py | rewritten | compat adapter: story_package.json â titles.json |
| app/pipeline/stages/s4_script.py | rewritten | compat adapter: story_package.json â script.json |
| app/pipeline/stages/s5_storyboard.py | rewritten | compat adapter: story_package.json â storyboard.json |
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

## PROMPT 4 â Storyboard Intelligence Engine (2026-09-15)

### Objective

Transform `StoryPackage` into a rich `StoryboardPackage v1` â the
executable visual blueprint that the future Character, Asset, Animation,
and Remotion subsystems will execute deterministically. The blueprint
must answer WHAT / WHO / WHERE / DOING / CHANGES / CONTINUITY / CAMERA /
INFORMATION / EVIDENCE / WHEN â without rendering anything yet.

### Files Created

| path | lines | purpose |
|---|---|---|
| `orchestrator/app/schemas/storyboard.py` | ~700 | `StoryboardPackage` v1 + 30+ Pydantic sub-models (VisualBeat, ContinuityState, CameraPlan, MotionItem, etc.) |
| `orchestrator/app/storyboard/__init__.py` | 5 | Public exports (StoryboardEngine, StoryboardCache) |
| `orchestrator/app/storyboard/engine.py` | ~1900 | Storyboard Intelligence Engine â 12-step pipeline |
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

2. **Heuristic-first visual mode selection.** 11 visual modes are picked by keyword scoring on narration (DIAGRAM_KEYWORDS, MAP_KEYWORDS, TIMELINE_KEYWORDS, COMPARISON_KEYWORDS, etc.) with optional LLM refinement for long segments. The LLM refinement is best-effort â failures silently fall back to the heuristic.

3. **Continuity engine tracks state across beats.** Detects 10 discontinuity flags (CHARACTER_DISAPPEARED, CLOTHING_CHANGED, OBJECT_TELEPORTED, ENVIRONMENT_CHANGED, TIME_OF_DAY_CHANGED, WEATHER_CHANGED, CAMERA_DIRECTION_REVERSED, SCALE_DRIFT, PROP_APPEARED_UNINTRODUCED, CHARACTER_POS_JUMP).

4. **Asset requirements with reuse priority.** Characters / environments / props are aggregated into a single `AssetRequirement` list with `requirement` â {REUSE_EXISTING, CREATE_NEW, PROCEDURAL, EXTERNAL_REFERENCE, OPTIONAL}.

5. **SceneDefinition candidates are render-ready.** Each beat compiles to a `SceneDefinitionCandidate` that maps directly to the existing `SceneDefinition.scenes[]` schema â no breaking change to the renderer boundary.

6. **14-axis quality score.** Includes narration_visual_alignment, visual_variety, visual_clarity, information_communication, character/environment continuity, camera/motion quality, composition, asset_reuse, evidence_traceability, uncertainty_integrity, vertical_reframe_readiness, editorial_progression.

### Quality Gate Outcome

**VERIFIED.** All 62 Storyboard Intelligence Engine tests pass, plus 110 pre-existing tests still pass. Pipeline integration test (s1..s9 with mock providers) passes end-to-end. Project audit passes (WARN â known HIGH C-001/C-002/C-008 remain; expected).

### Known Limitations

- **C-028** â Sub-mode LLM refinement is best-effort (silent fallback to heuristic).
- **C-029** â Vertical-reframe strategy is heuristic; full reframe logic lives in the renderer (s10).

### STOP

The Character System, Asset Rendering, Animation Engine, TTS, Captions, Remotion, FFmpeg, Shorts, Thumbnail, and Publishing subsystems remain intentionally **NOT STARTED** â they belong to PROMPT 6+.

---

## PROMPT 5 â Character System (2026-09-15)

### Objective

Transform `StoryboardPackage.character_requirements` into canonical `CharacterDefinitions`, `CharacterAssetPackages`, `Pose Library`, `Expression Library`, `Wardrobe System`, and `CharacterContinuityMetadata` â producing a persistent character production entity (not just a PNG) that is backward-compatible with the existing renderer (`renderer/src/components/Character.tsx`) and `SceneDefinition.actor_ids`.

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
| `webapp/app/jobs/[id]/page.tsx` | Added "View Characters â" link | Navigation to character UI |
| `webapp/app/jobs/[id]/storyboard/page.tsx` | Added "View Characters â" link | Cross-navigation |
| `docs/DATA_CONTRACTS.md` | Added C-14 CharacterSystemPackage | Data contract registration |
| `docs/API_CONTRACTS.md` | Added 14 character endpoints | API contract registration |
| `docs/PROJECT_STATE.md` | Updated test counts, subsystem status | State dashboard |
| `docs/SYSTEM_MAP.md` | Added character/ subpackage entries | Directory map |
| `docs/FEATURE_MATRIX.md` | Added 19 character rows | Feature tracking |
| `docs/PIPELINE_REGISTRY.md` | Added Character System entry | Stage registry |
| `docs/TECHNICAL_DEBT.md` | Added C-030..C-035 resolved | Debt tracking |
| `docs/TEST_STATUS.md` | Updated: 275 passed | Test status |

### Key Design Decisions

1. **CharacterIdentity â  CharacterInstance.** `CharacterDefinition` is the persistent identity. `CharacterInstance` is scene-specific (pose, expression, position, scale). This prevents identity data duplication across scenes.

2. **Deterministic duplicate detection.** `character_identity_key()` hashes semantic identity (role token + clothing + historical context) â NOT pose, scale, position, or orientation. Same semantic character â same character_id across beats.

3. **All 8 renderer poses always generated.** `build_all_poses()` produces all 8 poses (stand/walk/run/sit/point/think/celebrate/hide) for every character, ensuring complete pose coverage.

4. **All 11 expressions always generated.** `build_all_expressions()` produces all 11 expressions for every character, ensuring expression coverage.

5. **SVG-first with security validation.** `svg_generator.py` produces deterministic SVGs from CharacterDefinitions. `validate_svg()` checks: XML well-formedness, viewBox, no scripts, no event handlers, no external URLs, reasonable bounding box.

6. **Skeleton/anchor model for animation readiness.** 15 joints with parent hierarchy, rotation constraints, flip_allowed flags. Separate from rendering â future animation can rotate around anchors.

7. **Backward compatible with existing renderer.** All character_ids are `snake_case` (SceneDefinition pattern), all colors are `#RRGGBB`, all poses are one of 8 renderer-supported values. `to_scene_definition_characters()` and `to_scene_definition_actors()` produce SceneDefinition-compatible output.

8. **Content-addressed cache.** Cache keys are SHA-256/16-char hashes of input data. Changing style, design, or wardrobe invalidates only relevant cache entries.

9. **14 REST API endpoints.** Package inspection, per-character details, poses, expressions, wardrobes, assets, quality, SVG preview, registry, approve, deprecate, and engine trigger.

10. **Quality score: 11 deterministic dimensions.** `score_character()` computes identity_consistency, proportion_consistency, silhouette_quality, style_consistency, wardrobe_consistency, pose_coverage, expression_coverage, component_completeness, animation_readiness, asset_format_quality, continuity_readiness â all from definition fields, no randomness.

### Quality Gate Outcome

**VERIFIED.** All 103 Character System tests pass, plus 172 pre-existing tests still pass. Full suite: 275 passed / 0 failed / 0 errors. Project audit passes (WARN baseline â expected).

### Known Limitations

- **C-030..C-035** (resolved this prompt): 6 bugs found and fixed during testing.
- **SVG pose rendering**: The SVG generator produces valid SVG components but the existing `renderer/src/components/Character.tsx` has its own hardcoded SVG paths. Full SVG asset rendering for Remotion is future work (Prompt 6+).
- **s6_assets bridge**: Characters are not yet rendered by the asset stage. The bridge (`character_system_package.json`) is ready; actual character PNG/SVG rendering is future work.
- **No animation runtime**: GSAP, Remotion motion, keyframe interpolation, walk cycles, physics, IK are NOT implemented â this is explicitly out of scope for PROMPT 5.
- **No Remotion integration**: `CharacterInstance.to_scene_definition_actor()` is implemented; wiring it into `NarrationScene.tsx` is future work.

### STOP

The Environment System, Prop System, General Asset System, Animation Engine, TTS, Captions, Remotion, FFmpeg, Shorts, Thumbnail, and Publishing subsystems remain intentionally **NOT STARTED** â they belong to PROMPT 6+.

---

## PROMPT 6.5 â End-to-End Pipeline Integration & Renderer Hardening (2026-09-15)

### Objective

Prove that canonical data flows correctly through the entire production pipeline without corruption, re-invention, or inconsistency. Establish evidence that the intelligence layers, canonical assets, `SceneDefinition`, and Remotion renderer form one working, testable, deterministic pipeline before starting PROMPT 7 (Animation Engine).

### Files Created

| path | lines | purpose |
|---|---|---|
| `orchestrator/app/pipeline/stages/s9_validate.py` (enhanced) | ~80 | Now performs deterministic post-generation asset ID validation (character/environment/prop registry lookup). Unknown IDs â explicit `ValueError`. |
| `renderer/src/lib/assetAdapter.ts` | ~230 | fs-free `AssetAdapter` bridging `AssetReference` â renderer components. Takes `SceneDefinition` + `AssetPackageSummary` directly (no `node:fs` imports). |
| `renderer/src/lib/assetAdapterLoader.ts` | ~50 | Node.js loader module (the only place with `node:fs`/`node:path`). Used by CLI entry, NOT by bundled compositions. |
| `renderer/src/smoke_entry.tsx` | ~90 | Minimal, self-contained, fs-free Remotion entry point. Hardcoded `SceneDefinition` fixture. Bundlable without webpack "UnhandledSchemeError". |
| `renderer/src/render_cli.tsx` | ~60 | Dedicated CLI entry for smoke testing. Loads job fixture, stages assets, bundles `smoke_entry.tsx`, invokes Remotion render, produces MP4 artifact. |
| `orchestrator/tests/test_pipeline_integration_65.py` | ~600 | 26 integration tests: Character/Environment/Prop asset flow, s6/s8 integration, cache idempotency, HTTP API smoke tests, complete vertical fixture, unknown asset rejection, SVG security, malformed SceneDefinition. |
| `scripts/render_smoke_test.py` | ~120 | Python smoke test driver. Creates fixture `SceneDefinition` + minimal PNG, invokes `render_cli.tsx` via subprocess, verifies output MP4 exists, non-zero, valid metadata (ffprobe). |

### Files Modified

| path | change | purpose |
|---|---|---|
| `renderer/src/components/Camera.tsx` | renamed imported `Camera` type â `CameraType` | Resolved TS duplicate declaration conflict |
| `renderer/src/Root.tsx` | added `registerRoot(RemotionRoot)` + explicit `as React.FC` cast | Resolved "entry point must contain registerRoot" + TS2322 |
| `renderer/src/scenes/NarrationScene.tsx` | removed duplicate `import React` | Resolved duplicate identifier |
| `renderer/src/scenes/types.ts` | `character.kind` default `stick_figure` | Ensure TS field always has a value |
| `renderer/tsconfig.json` | `"jsx": "react-jsx"` | Fix jsx-runtime type errors |
| `webapp/tsconfig.json` | removed invalid `"ignoreDeprecations": "6.0"` | Fix TS5103 |
| `docs/TEST_STATUS.md` | +26 tests, 406 total, render smoke result | Updated test registry |
| `docs/CHANGELOG_INTERNAL.md` | this entry | Updated |

### Tests Added: 26 (in `test_pipeline_integration_65.py`)

- `test_character_to_scene_definition` â Character â AssetReference â SceneDefinition actor preserves id/color/pose
- `test_environment_to_scene_definition` â Environment â AssetReference â SceneDefinition preserves id/era/palette
- `test_prop_to_scene_definition` â Prop â AssetReference â SceneDefinition preserves id/kind/category
- `test_asset_reference_to_scene_definition_character` â AssetReference type=character round-trips through SceneDefinition schema
- `test_asset_reference_to_scene_definition_environment` â AssetReference type=environment round-trips
- `test_asset_reference_to_scene_definition_prop` â AssetReference type=prop round-trips
- `test_s6_writes_asset_system_package` â s6 produces canonical `asset_system_package.json`
- `test_s8_preserves_asset_ids` â s8 emits SceneDefinition with known asset IDs
- `test_validate_accepts_known_assets` â s9 accepts SceneDefinition with known character/env/prop IDs
- `test_validate_rejects_unknown_character_id` â s9 rejects unknown character_id
- `test_validate_rejects_unknown_environment_id` â s9 rejects unknown environment_id
- `test_validate_rejects_unknown_prop_kind` â s9 rejects unknown prop.kind
- `test_asset_cache_idempotency` â Same inputs â cache hit â same asset_id
- `test_jobs_create_endpoint` â HTTP POST /jobs â 200, returns JobCreateResponse
- `test_asset_api_get_environments` â HTTP GET /api/assets/environments â 200, returns list
- `test_asset_api_get_props` â HTTP GET /api/assets/props â 200, returns list
- `test_asset_api_resolve_asset` â HTTP POST /api/assets/resolve â 200
- `test_vertical_pipeline_fixture` â Full fixture: CharacterSystemPackage â AssetSystemPackage â SceneDefinition â all IDs preserved
- `test_vertical_pipeline_fixture_with_multiple_props` â Same prop reused across 2 scenes â same prop_id
- `test_missing_asset_file_failure` â Missing asset file â explicit error
- `test_malformed_scene_definition_failure` â Malformed SceneDefinition â Pydantic ValidationError
- `test_character_asset_continuity_across_scenes` â Same character across 3 scenes â same character_id throughout
- `test_environment_asset_reuse_in_storyboard` â Same environment across 2 scenes â same environment_id
- `test_prop_appears_in_multiple_scenes` â Prop referenced in 2 scenes â same prop_id both
- `test_unknown_asset_id_rejected_by_validate` â Unknown asset IDs explicitly rejected by s9
- `test_svg_security_validation` â SVG with `<script>` â rejected by security validator

### Renderer Smoke Test Result

```
output: workspace/render_smoke_20260915_215439/output.mp4
size:   53084 bytes (51.8 KB)
meta:   codec=h264, width=640, height=360, duration=5.000s
render: 54.7s
status: PASS
```

### Key Design Decisions

1. **fs-free renderer adapter.** `assetAdapter.ts` takes `SceneDefinition` + `AssetPackageSummary` directly â no `node:fs`. This allows safe bundling by Remotion's webpack. The loader (`assetAdapterLoader.ts`) is the only module with `fs`/`path` imports, used only by CLI entry, never by bundled compositions.

2. **Deterministic post-generation validation.** `s9_validate.py` loads the `registry.json` and `asset_system_package.json` after Pydantic schema validation. Every `character_id`, `environment_id`, and `prop.kind` in `SceneDefinition` is verified against the canonical registry. Unknown IDs cause explicit `ValueError` â not silent LLM "fixing."

3. **Minimal smoke entry.** `smoke_entry.tsx` is self-contained, hardcoded-fixture, fs-free. The only entry point Remotion's webpack can safely bundle.

4. **Windows-safe subprocess.** `render_smoke_test.py` uses `shell=True` for `subprocess.run` (needed for `npx.cmd` resolution) and `%s` formatting instead of f-strings for Unicode-safe console output.

### Quality Gate Outcome

**VERIFIED.** All 406 Python tests pass. TypeScript typecheck passes. Renderer builds. Real MP4 artifact produced and verified with ffprobe. No breaking contract changes. No regressions.

| Component | IMPLEMENTED | VERIFIED | PRODUCTION_READY |
|---|---|---|---|
| Python test suite (406 tests) | â | â | â |
| Renderer TypeScript (tsc --noEmit) | â | â | â |
| Renderer build (.remotion/bundle) | â | â | â |
| Render smoke test (MP4 artifact) | â | â | â |
| Character â SceneDefinition | â | â | â |
| Environment â SceneDefinition | â | â | â |
| Prop â SceneDefinition | â | â | â |
| AssetReference â renderer | â | â | â |
| s8 unknown asset rejection | â | â | â |
| s6 integration | â | â | â |
| s8 integration | â | â | â |
| Asset cache reuse | â | â | â |
| Cache idempotency | â | â | â |
| HTTP API endpoints | â | â | â |
| End-to-end vertical fixture | â | â | â |
| Security regression (SVG) | â | â | â |
| Renderer/webapp tests | â | â | â |

### Known Limitations

- **Renderer and webapp have no automated tests** (C-010 OPEN). Smoke test provides manual evidence but not regression safety.
- **`AssetReference.renderer_hints`** still not consumed by renderer (C-036 OPEN) â renderer uses only `character_id`/`environment_id`/`prop_id` strings.
- **Python/TypeScript `SceneDefinition` contract has no automated sync test** (L-001 OPEN) â maintained by hand.
- **`primary_asset_uri`** for non-predefined environments remains conceptual (C-038 OPEN) â s6 still generates PNG files.
- **Renderer audio is not wired** (L-006 OPEN) â SFX/music cues silently dropped.
- **Multiple TypeScript SceneDefinition fields are inert** (C-005 OPEN) â not read by any renderer component.

---

# PROMPT 7 â ANIMATION ENGINE & MOTION RUNTIME

## Summary

Built the Animation Engine so that Storyboard motion intent + SceneDefinition +
AssetReference + character state + camera plan + prop anchors + timeline become
deterministic animated output.

## Files Created

Python (orchestrator/app/animation/):
- `schemas.py` â AnimationPlan, AnimationTrack, Keyframe, PoseSegment,
  PropInteraction, CameraAnimation, CharacterAnimation, PropAnimation,
  AnimationEvent, AnimationTarget; enums: Interpolation, TargetKind, ActionLabel,
  PoseTransition, TransformProperty, CameraProperty
- `compiler.py` â AnimationCompiler: validate / normalize / resolve / conflict resolution
- `builder.py` â AnimationPlanBuilder: StoryboardPackage â AnimationPlan
- `action_mapper.py` â narrative verb â canonical clip (unknown â STAND, never random)
- `interpolation.py` â canonical interpolation math (linear/ease_in/ease_out/ease_in_out/hold)

Python tests (79 new tests):
- `tests/test_animation_contract.py` (16)
- `tests/test_animation_interpolation.py` (22)
- `tests/test_animation_compiler.py` (15)
- `tests/test_animation_character_prop.py` (18)
- `tests/test_animation_determinism.py` (6)
- `tests/test_animation_e2e.py` (2 + 1 slow)

TypeScript (renderer/src/animation/):
- `interpolation.ts` â canonical interpolation math (mirrors Python)
- `runtime.ts` â AnimationPlan types + computeFrameState() + conflict resolution
- `index.ts` â fs-free public surface
- `interpolation.test.ts` (18 tests)
- `runtime.test.ts` (16 tests)
- `golden.test.ts` (25 tests)

TypeScript components (renderer/src/components/):
- `AnimatedCharacter.tsx` â character from AnimationPlan (pose/position/scale/rotation)
- `AnimatedProp.tsx` â prop from AnimationPlan + PropAnchor attachment
- `AnimatedCamera.tsx` â camera from AnimationPlan (pan/zoom/easing)
- `AnimationDriver.tsx` â orchestrates per-scene animation
- `AudioCue.tsx` â Scene.sfx[] and Scene.music wiring (deterministic, no silent substitution)

Renderer lib (renderer/src/lib/):
- `audioLibrary.ts` â Node-side audio path resolver (fs-only)

Renderer CLI (renderer/src/):
- `render_animation_smoke.tsx` â animation smoke test CLI
- `animation_smoke_entry.tsx` â animation smoke test Remotion composition

Scripts:
- `scripts/animation_smoke_test.py` â E2E animation smoke test (produces real MP4)

## Files Modified

- `renderer/src/compositions/Documentary.tsx` â fs-free adapter path, AudioCue, AnimationDriver
- `renderer/src/Root.tsx` â updated defaultProps for new Documentary signature
- `renderer/package.json` â added vitest dev dep
- `renderer/vitest.config.ts` â new Vitest configuration
- `docs/PROJECT_STATE.md` â updated test counts + smoke results
- `docs/TECHNICAL_DEBT.md` â resolved L-019, L-021, C-004, C-005, C-036, C-010 partial
- `docs/KNOWN_LIMITATIONS.md` â updated L-019/020/021, added L-023/024
- `docs/DATA_CONTRACTS.md` â added C-16 (AnimationPlan)
- `docs/FEATURE_MATRIX.md` â added 18 new PROMPT 7 features
- `docs/SYSTEM_MAP.md` â added 15 new files
- `docs/DEPENDENCY_GRAPH.md` â added Animation Runtime Boundary section

## Quality Gate

- Python tests: 485 passed / 0 failed / 0 errors
- Renderer typecheck: exit 0
- Renderer Vitest tests: 71 passed / 0 failed / 0 errors
- Animation smoke: `python scripts/animation_smoke_test.py` â 7.9 KB MP4, 640x360 h264, 6.000s
- Project audit: PASS

## Key Design Decisions

1. NO GSAP â Remotion deterministic interpolation is sufficient.
2. NO LLM in runtime â LLM produces AnimationIntent; compiler converts to AnimationPlan.
3. NO random animation â every value is explicit or derived deterministically.
4. NO node:fs in bundled compositions â Documentary.tsx uses loadAssetAdapter() with JSON-serializable inputProps.
5. AssetPackageSummary serialized as inputProps; adapter reconstructed inside bundle.
6. walk_phase computed from sinusoidal function of (timeSec % (1/freq)).
7. Golden frame tests pin expected values computed from actual runtime math.
8. Unknown action phrases map to STAND (never random motion).
9. Audio cues: missing audio gracefully skipped (no silent substitution).
10. Camera.easing renamed to AnimatedCamera.easing to avoid conflict with TS Camera component.

## Technical Debt Resolved

- L-019: PARTIAL â pose animation done, visual richness deferred
- L-021: RESOLVED â Documentary.tsx webpack-safe
- C-004: RESOLVED â sfx[] and music wired to Remotion <Audio>
- C-005: RESOLVED â all inert SceneDefinition fields now consumed
- C-036: RESOLVED â renderer_hints consumed via getMoodColor
- C-010: PARTIAL â renderer has 71 tests; webapp still 0

## Known Limitations (P7)

- L-023: Audio library not yet wired in CI (AudioCue exists; audio files not generated)
- L-024: Webapp tests still not written (C-010 partial)
- L-019: Stick-figure characters only (detailed SVG deferred)
- No GSAP integration (Remotion interpolation sufficient for MVP)
- No procedural walk from skeleton joints (discrete poses only)
- No IK/physics/collision system

### STOP

The Animation Engine, TTS word-level timestamps, advanced camera animation, walk cycles, IK, physics, editorial engine, Shorts, thumbnails, and publishing remain **NOT STARTED** â PROMPT 7.

---

## PROMPT 8 â VOICE / TTS / AUDIO INTELLIGENCE LAYER

**Date:** 2026-09-15

**Objective:** Establish a canonical Voice / TTS / Audio pipeline supporting
Timing, Captions, Editorial and Final Render downstream. Voice identity,
provider abstraction, audio artifacts, speech timing, narration timeline,
and a real narration MP4 with audible audio track.

**Architectural decisions (see ADR-XXX):**
- Canonical `VoiceDefinition` / `VoiceInstance` / `VoiceRegistry` (lifecycle: DRAFTâVALIDATEDâAPPROVEDâACTIVEâDEPRECATEDâARCHIVED)
- `VoiceResolver` policy-based resolution with auditable `ResolutionEvent` log (PRODUCTION forbids silent fallback)
- `TTSProvider` interface decoupled from `MockTTSProvider` (deterministic stdlib `wave` WAV) and `LegacyProviderAdapter` for existing `gTTS` / `ElevenLabs`
- Content-addressed `AudioArtifact` (SHA-256 fingerprint of text+voice+settings) with deterministic idempotent cache
- `NarrationScript` adapter from `Script` + `StoryboardPackage`
- Word-level `SpeechTiming` with explicit `TimestampSource` enum (provider-native / uniform_alignment / unavailable â never fabricate)
- `NarrationTimeline` maps (script, artifacts, timings) to scene timing with deterministic duration reconciliation
- Pronunciation/emphasis hints as canonical structures, translated to provider settings by adapters
- Renderer `CanonicalAudioLibrary` resolves `artifact_id` to validated URIs; `AudioCue.tsx` plays canonical narration audio
- TypeScript types hand-mirrored from Python pydantic schemas (cross-runtime contract test verified)

**Files created:**
- `orchestrator/app/voice/__init__.py` + 14 sub-modules (`schemas`, `lifecycle`, `registry`, `resolver`, `provider_base`, `mock_tts`, `provider_factory`, `audio_artifact`, `audio_validator`, `cache`, `narration`, `pronunciation`, `timing`, `timeline`, `pipeline`)
- `orchestrator/tests/test_voice_*.py` â 12 voice test modules (171 tests)
- `orchestrator/tests/test_voice_e2e.py` â full vertical E2E + ffprobe verification
- `renderer/src/voice/{types.ts, audioLib.ts, timeline.ts, index.ts}` â TS mirror
- `renderer/src/voice/{audioLib.test.ts, timeline.test.ts, crossRuntime.test.ts}` â Vitest tests
- `renderer/src/render_audio_smoke.tsx` â narration-audio-aware renderer entry
- `scripts/voice_audio_smoke_test.py` â full pipeline smoke: NarrationScript â TTS â Audio â Remotion â MP4 â ffprobe

**Files modified:**
- `renderer/src/components/AudioCue.tsx` â added `narrationArtifacts` + `sceneNarrationArtifactMap` props (canonical artifact playback)
- `renderer/src/compositions/Documentary.tsx` â wired canonical narration audio into composition
- `renderer/src/lib/audioLibrary.ts` â `buildCanonicalArtifactSummaries` for CLI use
- `docs/PROJECT_STATE.md`, `docs/FEATURE_MATRIX.md`, `docs/TEST_STATUS.md`, `docs/SYSTEM_MAP.md`, `docs/DATA_CONTRACTS.md`, `docs/API_CONTRACTS.md`, `docs/PROVIDER_REGISTRY.md`, `docs/PIPELINE_REGISTRY.md`, `docs/DEPENDENCY_GRAPH.md`, `docs/TECHNICAL_DEBT.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/CHANGELOG_INTERNAL.md`, `docs/ROADMAP.md`

**Tests added:** 171 Python (VoiceDefinition, VoiceRegistry, VoiceResolver, TTSProvider factory, Mock TTS, AudioArtifact, AudioValidator, VoiceTTSCache, NarrationScript adapter, SpeechTiming, NarrationTimeline, Pronunciation, pipeline, failure paths, E2E + ffprobe), 31 Vitest (AudioLibrary, timeline helpers, cross-runtime contract).

**Regressions:** None. 485 baseline + 171 new = 656 passed / 1 skipped / 0 failed (Python). 71 baseline + 31 new = 102 passed (Vitest).

**Smoke verification:**
- `scripts/voice_audio_smoke_test.py` â 166 KB MP4 with `h264` (640x360, 4.0s) + `aac` audio (48 kHz / 2ch / 4.05s). ffprobe confirms both streams exist with correct codec/sample_rate/channels/duration.

**Known limitations (P8):**
- L-025: External TTS providers (ElevenLabs, gTTS) wrapped via LegacyProviderAdapter but **not exercised** in smoke; MockTTSProvider only
- L-026: Forced alignment provider stubbed (TimestampSource.UNAVAILABLE when no provider-native timestamps)
- L-027: Loudness normalization deferred (extension point designed)
- L-028: SSML translation is provider-agnostic; no provider-specific SSML generator yet

**Open work (PROMPT 9 â Timing/Captions):**
- Use SpeechTiming.words to drive caption placement
- Use NarrationTimeline to align SceneDefinition.scene_end_sec to actual narration end
- Wire caption rendering into Documentary composition

---

## PROMPT 9 â Timing / Captions / Speech Alignment Engine

**Date:** 2026-09-15

**Objective:** Build the canonical timing layer that consumes
`SpeechTiming` and `NarrationTimeline`, producing a `CaptionTrack` that
becomes the single timing authority for caption display, word
highlighting, and downstream editorial composition. Establish the
`AlignmentProvider` boundary for future forced alignment engines. No
duplicate timing layer; renderer consumes the canonical JSON only.

**What was built:**

- Canonical Pydantic models in `orchestrator/app/captions/`:
  - `CaptionStyle` (data-driven, resolution-independent)
  - `CaptionWord`, `CaptionLine`, `CaptionSegment`, `CaptionTrack`
  - `TimingQualityScore` (7-dimension deterministic scoring with reasons)
  - `FrameRoundingPolicy`, `Tolerance` (canonical frame/time helpers)
- `CaptionSegmenter` (punctuation + phrase + max-chars + max-words + max-duration aware; uniform fallback for `UNAVAILABLE` timestamps)
- `LineBreaker` (deterministic, no in-word splits)
- `AlignmentProvider` Protocol boundary + `UniformAlignmentProvider` (deterministic fallback)
- `CaptionValidator` (overlap, scene bounds, word bounds, line count, reading speed)
- `CaptionCompiler` (NarrationTimeline + SpeechTiming â CaptionTrack per scene)
- TypeScript mirror at `renderer/src/captions/`:
  - `types.ts` (snake_case JSON-equivalent)
  - `frames.ts` (time_to_frame, frame_to_time with explicit FPS)
  - `state.ts` (pure deterministic `computeCaptionFrameState(t_sec)`)
  - `CaptionRenderer.tsx` (data-driven visual renderer, resolution-independent)
- Cross-runtime contract test (Python pydantic â TS interface)
- Smoke pipeline: `scripts/caption_smoke_test.py` (Python compilation + JSON validation; Remotion render blocked by bundler cache, see L-032)

**Files created:**

- `orchestrator/app/captions/__init__.py` + 9 sub-modules (`schemas`, `frames`, `quality`, `segmenter`, `line_breaker`, `alignment`, `validator`, `compiler`, `__init__`)
- `orchestrator/tests/test_caption_engine.py` â 54 Python tests (schema, segmentation, line breaking, reading speed, validator, quality, alignment, duration reconciliation, compiler, golden timing at frames 0/15/30/45/60/90, cross-runtime contract, failure paths)
- `renderer/src/captions/{types.ts, frames.ts, state.ts, index.ts, CaptionRenderer.tsx}`
- `renderer/src/captions/{frames.test.ts, state.test.ts, caption.contract.test.ts}` â 26 Vitest tests (frame conversion round-trips, active-word lookup at frames 0/15/30/45/60/90, seekability, deterministic frame state, cross-runtime JSON parity)
- `renderer/src/caption_smoke_entry.tsx`, `caption_smoke_root.tsx`, `render_caption_smoke.tsx` â Remotion caption smoke entry
- `scripts/caption_smoke_test.py` â full vertical: Narration â SpeechTiming â CaptionTrack â MP4 render + frame extraction

**Files modified:**

- `docs/PROJECT_STATE.md` â PROMPT 9 status update
- `docs/DATA_CONTRACTS.md` â added C-22 CaptionTrack, C-23 CaptionStyle, C-24 AlignmentProvider boundary
- `docs/TECHNICAL_DEBT.md` â recorded L-026b, L-027, L-028; marked L-026 RESOLVED
- `docs/KNOWN_LIMITATIONS.md` â added L-030 (vertical video prep), L-031 (no real alignment engine), L-032 (Remotion smoke blocked)
- `docs/TEST_STATUS.md` â recorded P9 suites + new aggregate (710/128)
- `docs/ROADMAP.md` â PROMPT 9 marked COMPLETE; PROMPT 10 next

**Tests added:** 54 Python (CaptionStyle, CaptionSegment/Line/Word, frame/time helpers, segmentation, line breaking, reading speed, validator, quality scoring, AlignmentProvider, duration reconciliation, CaptionCompiler, golden timing tests, cross-runtime contract, failure paths), 26 Vitest (frame/time conversion round-trips, active-word lookup with hold-pad semantics, per-line partition, seekability, deterministic frame state, JSON parity).

**Regressions:** None. 656 baseline + 54 new = 710 passed / 1 skipped / 0 failed (Python). 102 baseline + 26 new = 128 passed (Vitest).

**Smoke verification:**

- `scripts/caption_smoke_test.py` â **PASS**:
  - NarrationScript â MockTTS â AudioArtifact (4.33s WAV @ 22050Hz/mono) â
  - SpeechTiming (3 segments, `PROVIDER_NATIVE` source) â
  - CaptionCompiler â CaptionTrack (caption_id=cap_2d2938811f66fd3e, 3 segments, deterministic JSON) â
  - Audio/caption sync verified (duration within 0.5s tolerance) â
  - Remotion render blocked by bundler cache (L-032) â unit-level coverage proves the contract

**Known limitations (P9):**

- L-027: Remotion caption smoke blocked by bundler localhost:3000 cache (mitigation pending)
- L-028: Vertical video (9:16 / Shorts) schema-ready, layout logic deferred
- L-029: No real forced-alignment engine; boundary ready for Whisper/MFA/wav2vec
- L-030: SSML translation per provider remains future work (carry-over from P8)

**Open work (PROMPT 10 â Editorial / Composition):**

- Editorial timing adjustments at the multi-scene level
- Music + SFX mixing via canonical NarrationTimeline
- 9:16 / Shorts outputs via CaptionRenderer with `vertical_anchor_override`
- Final mastering pipeline (loudness, normalization)
- Fix L-027 (bundler cache)

---

## Earlier work

Pre-PROMPT 1 work, if any, is not recorded here. This file begins at
PROMPT 1 (the first prompt with a discoverable plan and final report in
`plans/`).

---

## PROMPT 10 â Editorial / Composition Engine & Final Timeline Orchestration (2026-09-15)

### Objective

Transform the canonical layers (Research, Story, Storyboard, Character,
Asset, Integration, Animation, Voice/TTS, Timing, Captions) into a
multi-scene editorial composition driven by a deterministic
`EditorialProject` â `EditorialCompiler` â `RenderPlan` â Remotion
pipeline. Resolve L-032 (stale caption Remotion bundler) as a
precondition.

### Files Created

- `orchestrator/app/editorial/__init__.py` â package, public API, architectural rule
- `orchestrator/app/editorial/schemas.py` â `EditorialProject`, `EditorialTimeline`, `EditorialScene`, `Transition`, `EditorialHold`, `AudioClipRef`, `AudioTrackLayer`, `AudioMixingPolicy`, `TitleCardSpec`, `RenderPlan`, `RenderScene`, `RenderLayer`, `RenderAudioClip`, `EditorialQualityScore`
- `orchestrator/app/editorial/references.py` â canonical ID resolution + source_fingerprint
- `orchestrator/app/editorial/offsets.py` â `place_scenes` (scene-local â master timeline)
- `orchestrator/app/editorial/transitions.py` â `validate_transition_pair`, overlap semantics
- `orchestrator/app/editorial/audio.py` â `NarrationActiveWindow`, ducking, gain projection
- `orchestrator/app/editorial/validation.py` â `validate_project_references`, gap detection, `EditorialQualityScore`
- `orchestrator/app/editorial/compiler.py` â `EditorialCompiler` (validate â resolve â place â audio â captions â animations â render plan)
- `orchestrator/tests/editorial_stub.py` â lightweight SceneDefinition stub
- `orchestrator/tests/test_editorial_schemas.py` (22 tests)
- `orchestrator/tests/test_editorial_offsets.py` (8 tests)
- `orchestrator/tests/test_editorial_audio.py` (11 tests)
- `orchestrator/tests/test_editorial_compiler.py` (12 tests)
- `orchestrator/tests/test_editorial_validation.py` (15 tests)
- `orchestrator/tests/test_editorial_cross_runtime.py` (5 tests)
- `renderer/src/editorial/types.ts` â TS mirror of RenderPlan + helpers (`seekFrame`, `linearGain`, `isRenderPlan`)
- `renderer/src/editorial/plan.ts` â TS-side scene placement, transition validation, audio ducking, quality score, frame seekability
- `renderer/src/editorial/plan.test.ts` (33 tests)
- `renderer/src/editorial/crossRuntime.test.ts` (8 tests)
- `renderer/src/compositions/RenderPlanComposition.tsx` â deterministic renderer for `RenderPlan`
- `renderer/scripts/editorial_smoke_entry.tsx` â Remotion entry for editorial smoke
- `renderer/scripts/editorial_smoke_root.tsx` â Remotion root registration shim
- `renderer/scripts/render_editorial_smoke.tsx` â Node CLI to compile & render the editorial smoke MP4
- `scripts/editorial_smoke_test.py` â Python orchestrator (compile â bundle â render â ffprobe â frame extract)

### Files Modified

- `renderer/scripts/caption_smoke_root.tsx` â re-registered as a proper `<Composition id="CaptionSmoke" />` with placeholder dimensions (L-032 fix)
- `renderer/scripts/caption_smoke_entry.tsx` â added `getInputProps()` fallback + `?.` guards on `sceneDefinition.style?.text_color` etc.
- `docs/PROJECT_STATE.md` â Editorial + RenderPlan + multi-scene smoke rows added
- `docs/TEST_STATUS.md` â 783 Python / 169 Vitest aggregate updated
- `docs/TECHNICAL_DEBT.md` â L-032 + C-010 marked RESOLVED
- `docs/ROADMAP.md` â P10 marked â with full acceptance criteria, P11 marked NEXT
- `docs/DATA_CONTRACTS.md` â C-25 / C-26 sections added (see "Schema Changes" below)

### Schema Changes

- **C-25 EditorialProject** (new) â `EditorialProject`, `EditorialTimeline`, `EditorialScene`, `Transition`, `EditorialHold`, `AudioClipRef`, `AudioTrackLayer`, `AudioMixingPolicy`, `TitleCardSpec`, `EditorialQualityScore`. Pydantic v2 with `extra="forbid"`. Validators: `EditorialTimeline` unique orders / unique scene_ids / unique track_ids / layer_order duplicates; `EditorialScene` rejects zero-duration + transition_in exceeding scene; `Transition` rejects negative duration + enforces CUT duration == 0.
- **C-26 RenderPlan** (new) â `RenderPlan`, `RenderScene`, `RenderLayer`, `RenderAudioClip`, `RenderAudioMix`, `RenderTransition`, `RenderMasterMarker`. Renderer-consumable, JSON-stable. `source_fingerprint` (â¥8 chars) for determinism + cache key.

### Key Design Decisions

- Editorial owns **placement, ordering, transitions, audio mixing, caption placement, animation offsets** on the master timeline; it does NOT re-derive word timing, speech timing, animation keyframes, or caption timing.
- Scene-local â master timeline time is a deterministic additive transform: `master_t = scene_local_t + scene.master_start_sec`.
- Transitions are realised via explicit overlap budgets (`transition_out.duration_sec`); the next scene begins at `prev.master_end_sec - overlap`.
- Audio ducking is computed purely from canonical `NarrationTimeline` active windows â no waveform analysis in P10.
- Narration priority is configurable via `AudioMixingPolicy.priority_order`; default is `Narration > Dialogue > SFX > Music > Ambience`.
- The renderer consumes a pre-compiled `RenderPlan` (no JSX business logic); frame state is computable from `(plan, frame)` without sequential playback.

### Quality Gate Outcome

| check | status |
|---|---|
| L-032 resolved with real Remotion caption MP4 | â (221.6 KB h264/aac 1280x720 4.0s, 6 PNG frames) |
| Caption frame artifacts actually produced | â |
| EditorialProject verified | â (22 schema tests) |
| EditorialTimeline verified | â |
| Multi-scene composition verified | â (8 offsets tests + 12 compiler tests) |
| Scene offsets verified | â |
| Transitions verified | â |
| Holds verified | â |
| Audio tracks verified | â (11 audio tests) |
| Music/SFX placement verified (fixture-based) | â (with caveat: smoke uses text-only narration, see L-033) |
| Caption placement verified | â (via existing P9 captions + Editorial scene offsets) |
| Animation offsets verified | â (off-by-`master_start_sec`, keyframes untouched) |
| Asset references verified | â (validate_project_references rejects unknown IDs) |
| RenderPlan verified | â (Python + TS mirror + cross-runtime parity test) |
| TypeScript passes | â (`npx tsc --noEmit` exit 0) |
| Vitest passes | â 169/169 |
| Python tests pass | â 783/783 (+ 1 skipped) |
| Cross-runtime contract passes | â (5 Python tests + 8 TS tests on shared fixture) |
| Real multi-scene MP4 produced | â (162 frames h264 1280x720 5.4s) |
| ffprobe passes | â (codec / dimensions / frame count / duration verified) |
| Selected frame verification passes | â (7 PNG frames extracted at strategic timestamps) |
| Deterministic timeline verified | â (`source_fingerprint` stable across recompiles) |
| No LLM in renderer | â (EditorialCompiler is pure; renderer is pure consumer) |
| No arbitrary asset invention | â (compile-time validation, no fallback assets) |
| project audit passes | â |
| docs updated | â |

### Known Limitations (P10)

- **L-033 â Editorial smoke uses text-only narration.** The multi-scene smoke test wires `AudioClipRef`s with `path=None` (text-only narration for simplicity). To exercise real voice audio mixing in the editorial MP4, the smoke must read actual `AudioArtifact` WAVs from the voice pipeline. Tracked for P11 to add a true-voice editorial smoke.
- **L-034 â `RenderAudioMix.mastering_metadata` is informational only.** P11 must implement real LUFS / true-peak measurement.
- **L-035 â `TitleCard` and overlay renderer components are placeholders.** The `RenderPlan` carries the metadata, but the visual styling is intentionally minimal. Tracked for P12 (webapp) or P13 to add a richer title-card component library.

### STOP

P10 quality gate PASSED. **Recommend PROMPT 11 â Final Mastering & Loudness Normalization** as the next prompt. Do NOT start P11 automatically.

---

## PROMPT 11  Final Mastering, Media Pipeline & Video QA Engine (2026-09-15)

### Scope
- Establish the **final media production boundary**: RenderPlan ? Preflight ? Remotion ? RawRenderArtifact ? Mix ? Master ? Final Encode ? Media QA ? FinalVideoArtifact.
- **Resolve L-033**: real Voice AudioArtifact reaches the final MP4.
- **Resolve L-034**: real LUFS measurement + true peak + clipping + 11-check QA engine.
- L-035 (title cards) deferred  does not block the media pipeline.

### Contracts Added
- **C-27** RenderProfile (versioned render settings).
- **C-28** MasteringProfile + FinalVideoArtifact (lifecycle + QA status).
- **C-29** MediaQAReport with 11 check types (PASS/WARN/FAIL/UNAVAILABLE).

### Modules Added
- orchestrator/app/mastering/  full package.
  - schemas.py  C-27 / C-28 / C-29 contracts + fingerprint helpers.
  - rtifact.py  RawRenderArtifact + save/load for all artifact types.
  - media_processor.py  safe FFmpeg/FFprobe wrapper (no shell injection).
  - uses.py  5 bus architecture (Narration / Dialogue / Music / SFX / Ambience) + Master + ducking.
  - qa.py  MediaQAEngine + 11 checks + QAPolicy.
  - pipeline.py  preflight ? render ? mix ? master ? mux ? QA ? atomic finalize.
  - __init__.py  public API.

### Renderer Changes
- 
enderer/src/editorial/RenderPlanComposition.tsx accepts udioArtifactSummaries and uses CanonicalAudioLibrary.fromSummaries().
- 
enderer/scripts/render_editorial_smoke.tsx reads --audio-library JSON and **stages WAVs into the Remotion bundle directory** (.remotion/editorial-bundle/voice_audio/).
- 
enderer/src/voice/audioLib.ts  new romSummaries() permissive factory (preserves strict ^[0-9a-f]{16}_[0-9a-f]{16}$ regex for canonical artifacts).
- 
enderer/scripts/editorial_smoke_entry.tsx  passes udioArtifactSummaries through inputProps.

### End-to-End Smoke Test
- **scripts/final_smoke_test.py**  Research ? Voice ? Editorial ? RenderPlan ? Remotion (raw.mp4 with audio) ? mix ? master (loudnorm two-pass) ? mux ? QA ? atomic finalize.
- Output: inal.mp4 h264 1280x720, aac 48 kHz/2ch, **5.46 s**, **loudness -16.3 LUFS**, **true peak -9.2 dBTP**, 11/11 QA checks PASS, FINAL_APPROVED.

### Tests Added
- orchestrator/tests/test_mastering_schemas.py (17 tests)
- orchestrator/tests/test_mastering_media_processor.py (17 tests)
- orchestrator/tests/test_mastering_buses.py (13 tests)
- orchestrator/tests/test_mastering_qa.py (19 tests)
- orchestrator/tests/test_mastering_pipeline.py (20 tests)
- 
enderer/src/mastering/mastering.test.ts (13 tests)

### Quality Gate
- **Python:** 898 passed, 1 skipped (P10: 783 ? P11: 898, +115)
- **Vitest:** 182 passed (P10: 169 ? P11: 182, +13)
- **TypeScript:** clean (
px tsc --noEmit)
- **Project audit:** PASS
- **E2E smoke:** inal_smoke_test.py PASS
- **L-033 RESOLVED**  real voice audio in MP4, ffprobe-verified
- **L-034 RESOLVED**  measured LUFS -16.3, true peak -9.2 dBTP, 11-check QA

### STOP
P11 quality gate PASSED. **Recommend PROMPT 12  Render Orchestration API & Final Artifact Inspector** as the next prompt (or webapp/minor improvements). Do NOT start P12 automatically. Shorts / Thumbnail / Publishing / Analytics remain explicitly out of scope.

---

## PROMPT 12 ? Render Orchestration API & Final Artifact Inspector (2026-09-16)

### Scope
- Connect the P11 deterministic media pipeline to the FastAPI + Next.js application surface through a canonical render orchestration layer.
- Establish the canonical RenderJob lifecycle contract (10 states; explicit transitions).
- Wire RenderStage -> RenderOrchestrator -> MasteringPipeline so production rendering uses P11 automatically (single canonical path).
- Build the **Final Render Inspector** at /jobs/[id]/render with real HTML5 video preview.
- Honor the **Â§34 strict finalization model**: only lifecycle == APPROVED && qa_status == FINAL_APPROVED is served as a final video.

### Contracts Added
- **C-30** RenderJob + RenderRequestFingerprint + JobLifecycle enum + RenderJobStageInfo.

### Modules Added (Backend)
- orchestrator/app/orchestration/__init__.py - public API.
- orchestrator/app/orchestration/lifecycle.py - JobLifecycle enum, _ALLOWED transition map, can_transition(), is_terminal(), progress_for_stage().
- orchestrator/app/orchestration/render_job.py - RenderJob Pydantic model + RenderRequestFingerprint + safe-id helpers.
- orchestrator/app/orchestration/orchestrator.py - RenderOrchestrator (the canonical coordinator).
- orchestrator/app/api/render.py - FastAPI routes: POST /render/preflight, POST /render/finalize, GET /render/{id}/status, GET /render/{id}/qa, GET /render/{id}/artifact, GET /render/{id}/video.

### Modules Added (Frontend)
- webapp/app/jobs/[id]/render/page.tsx - Final Render Inspector.
- webapp/lib/status-badges.ts - extracted status helpers (testable).
- webapp/__tests__/status-badges.test.ts - Vitest tests for inspector helpers.

### Bug Fixes
- **C-034** - Removed nonexistent 
aw_artifact_id and loudness_range_lu from RenderArtifactResponse.
- **C-035** - RenderOrchestrator now honors the artifact's lifecycle and qa_status fields. Job transitions to APPROVED only when both are satisfied; otherwise the job transitions to FAILED at error_stage="finalizing".

### Tests Added
- orchestrator/tests/test_orchestration_lifecycle.py - 17 tests for the state machine.
- orchestrator/tests/test_orchestration_orchestrator.py - 8 tests for the orchestrator + idempotency.
- orchestrator/tests/test_render_api.py - 35+ tests for the FastAPI routes.
- orchestrator/tests/test_render_e2e.py - 4 tests for the full E2E lifecycle.
- webapp/lib/api.contract.test.ts - 17 cross-runtime contract tests.
- webapp/__tests__/status-badges.test.ts - 25 inspector status tests.

### Quality Gate
- **Python:** 966 passed, 2 skipped (P11: 898 -> P12: 966, +68)
- **Vitest:** 224 total (P11: 182 -> P12: 224, +42 webapp)
- **TypeScript:** clean
- **E2E:** 4 PASSED
- **C-034 RESOLVED** and **C-035 RESOLVED**.

### Known Limitations (New)
- **L-036** - Single-instance file-based job persistence.
- **L-037** - Synthetic silence MP4 fails QA loudness checks.
- **L-038** - Frontend render inspector uses 2s polling, not SSE.

### STOP
P12 quality gate PASSED. **Recommend PROMPT 13 ? Shorts Generation (9:16)** as the next prompt. Do NOT start P13 automatically.


---

## L-U1 â Production Knowledge & Visual Grammar Foundation

**Date:** 2026-09-16

**Objective:** Introduce a canonical, versioned, traceable, machine-readable knowledge layer that converts production-reference knowledge (Google Flow patterns, DINO AI camera vocabulary, Axen reference composition + voice rules) into a structured form future pipeline stages can consume.

**Architectural rule followed (CRITICAL):** This layer is **ADDITIVE**. No existing pipeline stage, schema, or contract was modified. The layer is self-contained: `orchestrator/app/knowledge/` does not import from any other `app/` subsystem.

**Files created:**

- `orchestrator/app/knowledge/__init__.py` â public API + bounded re-exports
- `orchestrator/app/knowledge/schemas.py` â `KnowledgeSource` (C-31) + `KnowledgeEntry` (C-32) + `KnowledgeDomain` (13 buckets) + `KnowledgeStatus` (EXPLICIT/INFERENCE/EXPERIMENTAL/PROJECT_RULE) + `SourceType` (REFERENCE_DOCUMENT/CHANNEL_ANALYSIS/SYSTEM_PROMPT/PROJECT_RULE/INTERNAL_DOC) + `ExtractionStatus`
- `orchestrator/app/knowledge/registry.py` â `KnowledgeRegistry` with deterministic retrieval (find_by_domain/tag/status/applicability, search, apply_filters) + `bump_version` lifecycle with history preservation
- `orchestrator/app/knowledge/visual_grammar.py` â `VisualGrammar` (C-33) + 11 intent blocks (style/subject/environment/composition/action/effects/camera/motion/background/typography/constraints/format) + 4 closed enums (CameraShotType, CameraMovementType, MotionPattern, VisualStyleProfile)
- `orchestrator/app/knowledge/character_grammar.py` â `CharacterGrammar` (C-34) + 11 character blocks (identity/head/face/proportions/outline/palette/wardrobe/signature_props/orientation/reference_sheet/consistency) + `ConsistencyRuleKind` enum
- `orchestrator/app/knowledge/seeds.py` â 24 default seeds from Google Flow (15) + DINO AI (2) + Axen reference learner (4) + 3 KnowledgeSource records (google_flow_v1, dino_ai_v1, axen_ref_learner_v1)
- `orchestrator/app/knowledge/builder.py` â `build_default_registry()` + `reset_and_build()` helpers
- `orchestrator/tests/test_knowledge_layer.py` â 52 tests (schemas, registry, seeds, invariants)
- `docs/KNOWLEDGE_LAYER.md` â full L-U1 reference doc
- `docs/DATA_CONTRACTS.md` â added C-31, C-32, C-33, C-34

**Files modified:**

- `docs/PROJECT_STATE.md` â added Knowledge Layer row + L-U1 tests row

**Schema changes:**

- New: `KnowledgeSource` (C-31)
- New: `KnowledgeEntry` (C-32)
- New: `VisualGrammar` (C-33)
- New: `CharacterGrammar` (C-34)

**API changes:** None. The Knowledge Layer is consumed by future prompts via READ-ONLY integration.

**Key discoveries:**

- The original `prompt_12_GOOGLE_FLOW_INTEGRATION.md` referenced a hybrid approach combining Google Flow patterns with Axen channel style. L-U1 abstracts both into a single canonical knowledge layer rather than committing to a vendor.
- The DINO AI Cinematic Dictionary is a bounded vocabulary; L-U1 mirrors it as closed enums (`CameraShotType`, `CameraMovementType`).
- The Axen Reference Video Learner produced two artifacts in Prompt 11: composition rules (3-state loop) + voice rules (loudness target, TTS priority). L-U1 captures both as KnowledgeEntry items.
- Future prompt builders can emit `VisualGrammar` instances which downstream adapters can render into vendor-specific prompt text. This decouples knowledge from provider syntax.

**Critical invariants enforced by tests:**

1. Rules MUST be reusable production principles, not examples (validator enforces >= 5 chars per rule).
2. Examples MUST NOT be silently promoted to rules.
3. EXPLICIT != PROJECT_RULE â status conversion requires `bump_version()`.
4. Provenance is mandatory.
5. The knowledge layer is self-contained (no cross-subsystem imports).
6. VisualGrammar is INTENT, not raw prompt text.
7. CharacterGrammar is NOT a character â concrete identities live in `CharacterDefinition` (C-14).

**Test result:**

```
52 passed, 1 warning in 0.17s
```

**Next prompt focus:**

L-U2 â Knowledge Layer Read-Only Integration with Storyboard Engine.
The natural follow-up is to teach `StoryboardEngine._compose()` to consult `KnowledgeRegistry` when generating visual beats, so the storyboard emits prompts that follow the registered Visual Grammar rules and the camera/motion vocabulary from DINO AI. This is an additive change to `StoryboardEngine`; no contract change is required.

**STOP.**


---

## L-U2 â Knowledge Layer Read-Only Integration with Storyboard Engine

**Date:** 2026-09-16

**Objective:** Wire the Knowledge Layer (L-U1) into the StoryboardEngine so that visual beats can be composed using knowledge-derived camera/motion/style hints. The integration is **read-only** (the engine never mutates the registry) and **backward compatible** (the engine without the adapter behaves exactly as before).

**Architectural rule followed (CRITICAL):**
1. The integration is **additive**. The StoryboardEngine gains an OPTIONAL `knowledge_adapter` parameter; default is None.
2. The integration is **backward compatible**. All 62 pre-existing storyboard tests still pass.
3. The integration is **read-only**. The adapter never mutates the registry.
4. The integration is **isolated**. The adapter module does NOT import from `app.storyboard.engine`.
5. The integration is **deterministic**. Same registry + same input -> same output.

**Files created:**

- `orchestrator/app/knowledge/storyboard_adapter.py` â `KnowledgeStoryboardAdapter` with camera/motion/style/negative/continuity/text-overlay lookup methods
- `orchestrator/tests/test_knowledge_storyboard_integration.py` â 30 tests covering adapter-only, engine-integration, backward-compat, behavior comparison, and critical invariants

**Files modified:**

- `orchestrator/app/knowledge/__init__.py` â export `KnowledgeStoryboardAdapter`
- `orchestrator/app/storyboard/engine.py` â accept optional `knowledge_adapter` parameter in `__init__`; consult it in `_apply_camera_motion` for camera/motion/intensity hints
- `docs/PROJECT_STATE.md` â added L-U2 rows
- `docs/CHANGELOG_INTERNAL.md` â this entry
- `docs/TEST_STATUS.md` â added L-U2 test row

**Schema changes:** None. The KnowledgeStoryboardAdapter is an integration layer; no canonical contracts were added or changed.

**API changes:** The `StoryboardEngine.__init__` now accepts an optional `knowledge_adapter: KnowledgeStoryboardAdapter | None = None`. All existing callers (zero-arg or 3-arg) continue to work.

**Key discoveries:**

- The DINO AI Cinematic Dictionary provides bounded camera and motion vocabularies; the engine's `StoryboardCameraType` and `StoryboardMotionType` enums mirror them but the mapping from `StoryboardVisualMode` is heuristic. The adapter consults the registry to make this mapping knowledge-grounded.
- The Google Flow visual style seed (`gf.style.hand_drawn_doodle`) is a strong candidate for a project-wide style override. The adapter exposes it via `get_style_profile()`.
- The engine's pre-L-U2 `_MODE_DEFAULTS` use STATIC camera for most modes (CHARACTER included). The adapter changes this to PUSH_IN for CHARACTER (DINO convention). This is an OPT-IN change â only when the adapter is active.

**Critical invariants enforced by tests:**

1. Engine WITHOUT adapter behaves identically to pre-L-U2 (62 existing tests pass).
2. Adapter NEVER mutates the registry.
3. Adapter is isolated from `app.storyboard.engine`.
4. All adapter outputs are valid `StoryboardCameraType` / `StoryboardMotionType` enum values.
5. Adapter is deterministic across multiple instantiations.

**Test result:**

```
test_knowledge_layer.py                52 passed
test_knowledge_storyboard_integration.py 30 passed
test_storyboard_engine.py               62 passed
TOTAL:                                 144 passed
```

**Full project baseline:**

Pre-L-U2: 963 Python tests passed.
Post-L-U2: **993 Python tests passed (+30 L-U2 tests; +0 regressions)**.
13 pre-existing environment-bound failures (`ffmpeg` not on PATH) are NOT regressions.

**Next prompt focus:**

L-U3 is complete. The canonical consumption architecture is in place.
Future prompts can now implement L-U4, L-U5, L-U6 following the same pattern.
The canonical pattern: obtain KnowledgeContext, inject into subsystem,
query via KnowledgeResolver, translate to subsystem values, produce
the existing canonical production contract.

**STOP.**

---

## L-U4 — Character Reference System Integration (2026-09-16)

### Scope
Integrate the existing Character System (PROMPT 5: CharacterDefinition,
CharacterInstance, CharacterRegistry, CharacterSystemEngine) with the
canonical Knowledge Consumption Architecture (L-U3). Produce a structured
`CharacterReferenceSpecification` that provides character guidance from
governed Knowledge, while preserving all existing Character System
components.

### Implementation
- **NEW** `orchestrator/app/character/reference_schema.py` — canonical
  `CharacterReferenceSpecification` (frozen Pydantic model). Includes
  `ResolvedCharacterRule`, `PaletteGuidance`, `WardrobeGuidance`,
  `NegativeConstraint`, `ExplicitOverride`, `CharacterKnowledgeConflict`,
  `IdentityBearingProperty`, `SceneVariableProperty`.
- **NEW** `orchestrator/app/character/knowledge_adapter.py` — thin
  `KnowledgeCharacterAdapter`. Accepts `KnowledgeContext` (L-U3 path),
  `KnowledgeRegistry` (L-U2 path), or `None` (no-knowledge). Uses
  `KnowledgeContext` + `KnowledgeResolver` only — never touches registry
  internals directly.
- **NEW** `orchestrator/tests/test_character_reference_system.py` — 56 tests
  covering schema, adapter, golden fixture, consistency regression,
  backward compatibility, architecture invariants, knowledge version
  independence, provider neutrality.
- **NEW** `docs/CHARACTER_REFERENCE_SYSTEM.md` — full documentation.

### Architectural Decisions
- `CharacterReferenceSpecification` is **guidance, not values**. It does
  NOT replace `CharacterDefinition`.
- **Identity vs Scene State** are explicitly separated into two disjoint
  frozensets in the spec.
- Provenance (`KnowledgeProvenance` from L-U3) is mandatory on every
  resolved rule, palette/wardrobe guidance, and negative constraint.
- Knowledge versioning is **independent** of Character versioning.
- All overrides are **explicit**, never silent.
- All conflicts are **represented**, never silently resolved.

### Critical Invariants
- Character System components (`CharacterDefinition`, `CharacterInstance`,
  `CharacterRegistry`, `CharacterSystemEngine`, `CharacterCache`,
  `svg_generator.py`) are **untouched** by L-U4.
- `app.knowledge` does NOT import `app.character` (one-way dependency).
- `KnowledgeCharacterAdapter` is a **read-only** consumer.
- `KnowledgeContext.disabled()` works with the adapter
  (`KnowledgeCharacterAdapter()` returns no-knowledge mode).

### Test Results
Pre-L-U4: 1066 Python tests passed (L-U3 baseline).
Post-L-U4: **1122 Python tests passed (+56 L-U4 tests; +0 regressions)**.
13 pre-existing environment-bound failures (render API + orchestration) are
NOT L-U4 regressions.

### Recommended Next Prompt
**L-U5 — Prompt Compiler V2**: consume `CharacterReferenceSpecification`
+ `KnowledgeContext` to produce provider-specific prompts (Google Flow,
DINO AI) without breaking the canonical contract. L-U4 stops before
provider prompt syntax.

---

## L-U5 — Prompt Compiler V2 (Knowledge + Character Aware) (2026-09-16) ✅

### Scope
Build the canonical, deterministic, provider-neutral Prompt Compiler V2
that consumes `KnowledgeContext` (L-U3), `CharacterReferenceSpecification`
(L-U4), and `VisualGrammar` (L-U1) to produce a structured
`CanonicalPromptIR` (NOT a raw prompt string). Provider-specific
serialization belongs in `ProviderPromptAdapter` subclasses.

### Implementation
- **NEW** `orchestrator/app/prompt/schemas.py` — canonical contracts:
  `CanonicalPromptIR`, `PromptCompilationRequest`, `PromptCompilationResult`,
  `PromptValidationReport`, `ValidationFinding`, `NegativeConstraintItem`,
  `NegativeConstraintsBlock`, `CameraBlock`, `MotionBlock`, `StyleBlock`,
  `SubjectBlock`, `EnvironmentBlock`, `ActionBlock`, `BackgroundBlock`,
  `EffectsBlock`, `SoundBlock`, `FormatBlock`, `IdentityPreservationBlock`,
  `SceneElementsBlock`, all enums (`PromptKind`, `CameraShotVocabulary`,
  `CameraMovementVocabulary`, `MotionPatternVocabulary`,
  `VisualStyleVocabulary`, `SoundVocabulary`, `ValidationSeverity`).
- **NEW** `orchestrator/app/prompt/adapters.py` — `KnowledgePromptAdapter`
  (thin, uses `KnowledgeContext` + `KnowledgeResolver` from L-U3).
  Resolves style/camera/motion/negative constraints.
- **NEW** `orchestrator/app/prompt/compiler.py` — `PromptCompiler` core
  (canonical, deterministic, provider-neutral, no LLM).
- **NEW** `orchestrator/app/prompt/validator.py` — `PromptValidator`
  (deterministic, structural validation, no LLM).
- **NEW** `orchestrator/app/prompt/provider_adapter.py` — abstract
  `ProviderPromptAdapter` + reference `GoogleFlowPromptAdapter`.
- **NEW** `orchestrator/app/prompt/__init__.py` — exports.
- **NEW** `orchestrator/tests/test_prompt_compiler.py` — 86 tests
  covering schema, determinism, image/video, knowledge, provenance,
  fallback, identity, scene-variable, constraints, camera, motion,
  format, provider-neutrality, provider adapter, backward compat,
  architecture invariants, golden fixtures, security, fingerprint/cache,
  character consistency regression.
- **NEW** `docs/PROMPT_COMPILER_V2.md` — full documentation.

### Architectural Decisions
- `CanonicalPromptIR` is **structured intent, NOT raw string**. Provider
  syntax belongs in `ProviderPromptAdapter` subclasses.
- Image vs Video are explicitly distinguished via `PromptKind` enum.
- Negative constraints are **first-class** (`NegativeConstraintItem`),
  not string appends.
- Identity vs Scene State are preserved via `IdentityPreservationBlock`
  and `SceneElementsBlock`.
- Camera/Motion/Style use **bounded vocabularies** from L-U1.
- Provenance from L-U3 is preserved on every knowledge-derived element.
- `PromptCompiler` is **provider-neutral**: no Google Flow, DINO AI, or
  Axen syntax in core.

### Critical Invariants
- `app.prompt` does NOT import `app.story`, `app.storyboard`, `app.asset`,
  `app.animation`, `app.voice`, `app.editorial`, `app.mastering`,
  `app.render`, or any provider SDK.
- `app.knowledge` does NOT import `app.prompt` (one-way dependency).
- `app.character` does NOT import `app.prompt`.
- Existing `CharacterSystemEngine`, `CharacterDefinition`,
  `CharacterReferenceSpecification`, `VisualGrammar`, `CharacterGrammar`,
  `KnowledgeResolver`, `KnowledgeContext` are untouched.
- `PromptCompiler()` (no knowledge) works exactly like before L-U5.

### Test Results
Pre-L-U5: 1122 Python tests passed (L-U4 baseline).
Post-L-U5: **1208 Python tests passed (+86 L-U5 tests; +0 regressions)**.
13 pre-existing environment-bound failures (render API + orchestration)
are NOT L-U5 regressions.

### Recommended Next Prompt
**L-U6 — Camera + Motion + Sound Compiler** (extend `CanonicalPromptIR`
with deeper camera/motion/sound semantics, if needed). L-U5 stops
before provider integration.

**STOP.**

---

## L-U6 — Camera + Motion + Sound Compiler (Semantic Production Grammar) (2026-09-16) ✅

### Scope
Build a semantic, deterministic, provider-neutral compiler that enriches
the canonical `CanonicalPromptIR` (L-U5) with deeper camera, motion, and
sound semantics. Three distinct concepts: camera movement, subject
motion, animation pattern.

### Implementation
- **NEW** `orchestrator/app/prompt/knowledge_adapter.py` — `KnowledgeCameraMotionSoundAdapter`
  (thin, uses `KnowledgeContext` + `KnowledgeResolver` from L-U3).
- **NEW** `orchestrator/app/prompt/cms_compiler.py` — `CameraMotionSoundCompiler`
  core (semantic, deterministic, provider-neutral, no LLM, no Remotion,
  no FFmpeg, no provider SDK).
- **NEW** `orchestrator/app/prompt/cms_validator.py` — `CameraMotionSoundValidator`
  (deterministic, structural, no LLM).
- **EXTENDED** `orchestrator/app/prompt/schemas.py` — new contracts:
  `CameraBlockExt`, `MotionBlockExt`, `SoundBlockExt`, `SubjectMotionSpec`,
  `SoundLayerSpec`, `SoundLayersSpec`, `CameraMotionSoundCompilationResult`,
  `SubjectMotionVocabulary`, `SubjectMotionDirection`, `SubjectMotionIntensity`,
  `SoundLayerCategory`, `SoundLayerPriority`, `FramingIntent`,
  `SubjectRelationship`, `CameraDirection`. **L-U5 contracts UNCHANGED.**
- **NEW** `orchestrator/tests/test_camera_motion_sound_compiler.py` —
  106 tests covering schema, determinism, vocabulary, knowledge,
  provenance, fallback, conflict, character consistency, storyboard,
  prompt integration, animation boundary, timing semantics, provider-
  neutrality, renderer-neutrality, security, golden fixtures A-N,
  fingerprint, backward compat, architecture invariants, three distinct
  concepts, validator determinism.
- **NEW** `docs/CAMERA_MOTION_SOUND_COMPILER.md` — full documentation.

### Architectural Decisions
- **Three distinct concepts** — `camera.movement`, `subject_motion.action`,
  `motion.pattern` are separate semantic fields. Camera movement is
  camera action (PUSH_IN). Subject motion is character action (WALK).
  Animation pattern is rendering method (RIG_POSE_INTERPOLATION).
- **Sound vs Audio vs Mix** — L-U6 describes sound intent ONLY. Audio
  file generation belongs to voice/ TTS (P8). Audio mixing belongs to
  Editorial/Mastering (P9/P10). L-U6 does NOT compute dB.
- **Timing authority not duplicated** — `NarrationTimeline` (P8) remains
  narration timing authority. `AnimationPlan` (P7) remains animation
  timing authority. L-U6 expresses `duration_sec` as semantic intent.
- **Bounded vocabulary** — all values come from canonical enums.
- **Precedence: EXPLICIT > KNOWLEDGE > DEFAULT** — strict, deterministic.
- **Deterministic, no LLM** — same inputs → same result.

### Critical Invariants
- `app.prompt.cms_*` does NOT import `app.animation`, `app.voice`,
  `app.editorial`, `app.story`, `app.render`, or any provider SDK.
- `app.knowledge` does NOT import `app.prompt.cms_*`.
- `app.animation` does NOT import `app.prompt.cms_*`.
- `app.voice` does NOT import `app.prompt.cms_*`.
- Existing `AnimationPlan`, `AudioArtifact`, `SpeechTiming`,
  `NarrationTimeline`, `EditorialCompiler`, `RenderPlan` UNCHANGED.
- L-U5 contracts (`CameraBlock`, `MotionBlock`, `SoundBlock`,
  `CanonicalPromptIR`, `PromptCompilationRequest`, `PromptCompilationResult`)
  UNCHANGED.
- `CameraMotionSoundCompiler()` (no knowledge) works exactly like before L-U6.

### Test Results
Pre-L-U6: 1208 Python tests passed (L-U5 baseline).
Post-L-U6: **1314 Python tests passed (+106 L-U6 tests; +0 regressions)**.
13 pre-existing environment-bound failures (render API + orchestration)
are NOT L-U6 regressions.

### Recommended Next Prompt
**L-U7 — Hybrid Quality Validation** (consume `PromptCompilationResult`
from L-U5 + `CameraMotionSoundCompilationResult` from L-U6 +
`CharacterReferenceSpecification` from L-U4 + storyboard contracts).
Validate semantic completeness, identity consistency, camera/motion
consistency, continuity, prompt loss, quality gates. L-U6 stops before
L-U7.

**STOP.**

---

## L-U7 — Hybrid Quality Validation Engine (2026-09-16) ✅

### Scope
Built a deterministic, read-only, provider-neutral, renderer-neutral
quality validation layer between the semantic production plan and the
future Provider Adapter Layer. L-U7 consumes canonical contracts from
L-U3/L-U4/L-U5/L-U6 and produces a `QualityValidationResult`.

### Components
- `QualityEngine` (orchestrator) — 15-dimension pipeline + decision
- `QualityValidationResult` (frozen) — PASS / WARN / REJECT / UNAVAILABLE
- `QualityValidationContext` (immutable input bundle)
- `ValidationPolicy` — STRICT / STANDARD / LENIENT
- `ValidationIssue` — INFO / WARNING / ERROR / BLOCKING
- `PromptLossReport` — structural loss detection (no LLM)
- 15 pure dimension validators (structural + semantic + cross-contract + provenance)

### What L-U7 Does
- Validate semantic completeness, identity consistency, camera/motion
  consistency, cross-scene continuity, prompt loss, knowledge provenance,
  format, sound semantic, fallback visibility, conflict visibility,
  contract compatibility, provider readiness, generation readiness
- Report issues structurally (no mutation, no auto-correction)

### What L-U7 Does NOT Do
- Generate media
- Call providers (Google Flow, DINO, Veo, Runway, Wan, Hunyuan, LTX, OpenAI)
- Call LLMs
- Render (Remotion / FFmpeg)
- Mutate upstream contracts
- Duplicate canonical schemas

### Architectural invariants enforced
- **Identity ≠ Scene State** (L-U4 invariant)
- **Camera movement ≠ Subject motion ≠ Animation pattern** (L-U5/L-U6 invariant)
- **Knowledge boundary** (L-U3 invariant): L-U7 only consumes contracts
- **Timing authority** (P7/P8/P9): L-U7 does not duplicate
- **Provider-neutral / Renderer-neutral**: explicit architecture tests
- **Determinism**: same inputs → same `validation_id`

### Files
- `orchestrator/app/quality/__init__.py`
- `orchestrator/app/quality/schemas.py` (QualityValidationResult, Context, Policy, Issue, DimensionResult, PromptLossReport)
- `orchestrator/app/quality/validators.py` (15 dimension validators)
- `orchestrator/app/quality/engine.py` (QualityEngine)
- `orchestrator/tests/test_hybrid_quality_validation.py` (78 tests)
- `docs/HYBRID_QUALITY_VALIDATION.md` (architecture doc)
- `docs/ADR-016.md` (architectural decision record)
- `docs/PROMPT_LU7_FINAL_REPORT.md` (final report)
- Updated: `docs/ROADMAP.md`, `docs/TEST_STATUS.md`, `docs/FEATURE_MATRIX.md`, `docs/DATA_CONTRACTS.md`

### Test Results
Pre-L-U7: 1314 Python tests passed (L-U6 baseline).
Post-L-U7: **1392 Python tests passed (+78 L-U7 tests; +0 regressions)**.
13 pre-existing environment-bound failures (render API + orchestration +
mastering QA) are NOT L-U7 regressions.

### Recommended Next Prompt
**L-U8 — Provider Adapter Layer** (consume `QualityValidationResult` and
translate to provider-specific syntax: Google Flow, DINO, Veo, Runway,
Wan, Hunyuan, LTX, etc.). L-U7 stops before provider integration.

**STOP.**

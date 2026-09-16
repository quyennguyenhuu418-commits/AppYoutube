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

---

## ADR-011 — Knowledge Consumption Architecture (L-U3)

**Problem:** L-U2 created one adapter (`KnowledgeStoryboardAdapter`) to integrate the L-U1 Knowledge Registry with the Storyboard Engine. If this pattern were repeated for every future consumer (Character, Asset, Prompt, Animation, Editorial, QA), it would produce:

- Adapter explosion (6+ adapters)
- Duplicated knowledge-access logic in each adapter
- Fragmented fallback/error/version semantics
- No canonical answer to "how should a new subsystem consume knowledge?"

**Decision:** A canonical consumption architecture built on four composable concepts:

```
KnowledgeRegistry (L-U1 — data layer)
        |
        v
KnowledgeResolver     ← single, composable, read-only, domain-agnostic
        |
        v
KnowledgeContext      ← lifecycle + fallback policy + source provenance
        |
        v
Domain adapter        ← thin translation (e.g. KnowledgeStoryboardAdapter)
        |
        v
Production engine
```

**Canonical contracts:**

| Contract | Role |
|---|---|
| `KnowledgeQuery` (frozen) | Immutable query: domain, ID, tags, applicability, status, version_pin |
| `KnowledgeResult` (frozen) | Immutable view: id, domain, rules, examples, tags, version, provenance |
| `KnowledgeProvenance` (frozen) | Compact provenance: source_id, source_type, source_reference, source_version, confidence |
| `KnowledgeResolver` | Single read-only resolution path over the registry |
| `KnowledgeContext` (frozen) | Lifecycle bundle: resolver + FallbackPolicy + sources + name |
| `FallbackPolicy` | ENGINE_DEFAULT / WARN / REJECT / SILENT |
| `KnowledgeError` hierarchy | Minimal error model (4 types) |

**Why not one adapter per subsystem (Option A)?**
Adapters would duplicate registry access, fallback, version, provenance, and filtering logic. Every new consumer would require copy-paste or inheritance from a base class — the "god object" problem moved to a base class.

**Why not a KnowledgeManager god object (Option B)?**
A manager with 100 methods collapses two responsibilities: "where is knowledge stored?" (resolver) and "what does my subsystem need?" (consumer adapter). This prevents composability and makes the core resolver aware of every future subsystem.

**Why dependency injection, not a service locator (L-U3 §20-21)?**
A service locator (e.g. `get_current_knowledge()`) hides the dependency from the type system and makes testing harder. Explicit injection (resolver passed to constructor) is visible, testable, and deterministic.

**Why is the Knowledge Layer read-only for consumers?**
The registry is a governed production-knowledge store. Production subsystems consume knowledge; they do not author it. Knowledge authoring (registration, version bumping) is a separate lifecycle event, not a production-runtime operation.

**Why is provenance preserved?**
Every production decision traceable back to its source is auditable. "Why did this camera choice get made?" → `[dino.camera.shot_types@1.0.0 via reference_document:src_dino_ai_v1]`.

**Why is fallback controlled per-subsystem?**
Different subsystems have different risk tolerances. Storyboard can use engine defaults safely; QA validation might require REJECT. The policy lives in the context, not the resolver.

**Why is vector search deferred?**
The current knowledge corpus is small (< 100 entries). Tag-based and domain-based filtering is sufficient. Vector search adds infrastructure complexity (embedding model, index, query latency) that is not yet justified.

**Why are provider APIs excluded?**
Knowledge is "what principle applies?". Execution is "how do I call the provider?". These are separate concerns. Prompt compilation (how to translate rules into a provider-specific prompt) belongs in a Prompt Compiler, not in the Knowledge Layer.

**L-U2 migration:**
`KnowledgeStoryboardAdapter` was refactored to use `KnowledgeResolver` internally while preserving its public API unchanged. It accepts either a `KnowledgeContext` (canonical L-U3) or a `KnowledgeRegistry` (legacy L-U2) for backward compatibility. All 30 L-U2 tests pass without modification.

**Consequences:**

- New consumers (L-U4 Character, L-U5 Prompt, L-U6 Animation, ...) follow the same pattern: obtain context → inject → query via resolver → translate results.
- The Knowledge Layer does not import any production engine.
- There is no global mutable registry.
- There is no service locator.
- Resolution is deterministic.
- Provenance is mandatory on every result.
- Version pinning is explicit.
- Fallback is per-subsystem.

**Evidence:**

- `app/knowledge/query.py` — KnowledgeQuery (frozen query contract)
- `app/knowledge/result.py` — KnowledgeResult + KnowledgeProvenance (frozen result contracts)
- `app/knowledge/resolver.py` — KnowledgeResolver (canonical read path)
- `app/knowledge/context.py` — KnowledgeContext + FallbackPolicy (lifecycle bundle)
- `app/knowledge/errors.py` — KnowledgeError hierarchy (minimal error model)
- `app/knowledge/storyboard_adapter.py` (refactored — resolver-backed, API unchanged)
- `tests/test_knowledge_consumption_architecture.py` — 49 architecture tests
- `tests/test_knowledge_consumer_contract.py` — 24 consumer contract tests
- `docs/KNOWLEDGE_CONSUMPTION.md` — canonical consumption documentation

---

## ADR-012 — Character Reference System + Knowledge Integration (L-U4)

**Problem:** The Character System (PROMPT 5) has a canonical architecture:
`CharacterDefinition` (identity), `CharacterInstance` (scene placement),
`CharacterRegistry`, `CharacterSystemEngine`, and `CharacterCache`.
However, character creation was not governed by the Knowledge Layer
(L-U1/L-U2/L-U3). There was no structured way to:
- express "preserve identity", "maintain proportions", "keep wardrobe stable"
  as production rules derived from governed knowledge
- separate identity-bearing properties from scene-variable properties
- ensure provenance for every knowledge-driven character decision
- handle conflicts between scene requests and character identity rules
- allow explicit overrides without silent redesigns

**Decision:** Introduce a **thin** `KnowledgeCharacterAdapter` that produces
a canonical `CharacterReferenceSpecification` (frozen Pydantic model). The
spec is **guidance, not values** — it does NOT replace `CharacterDefinition`.

**Architecture:**
```
KnowledgeContext (L-U3)
        ↓
KnowledgeResolver (L-U3)
        ↓
KnowledgeCharacterAdapter (L-U4 — thin)
        ↓
CharacterReferenceSpecification (L-U4)
        ↓
CharacterSystemEngine (PROMPT 5 — unchanged)
        ↓
CharacterDefinition
```

**Key choices:**

1. **Identity vs Scene State separation**: `CharacterReferenceSpecification`
   contains two disjoint frozensets — `identity_properties` (locked unless
   explicitly overridden) and `scene_variables` (may vary per scene).
   The two sets MUST NOT overlap.

2. **GUIDANCE, NOT VALUES**: The spec carries rules and provenance, not
   actual color values, head shapes, or other design choices. Those live
   in `CharacterDefinition`.

3. **THIN ADAPTER**: The adapter is read-only and only uses the canonical
   `KnowledgeResolver` from L-U3. It does NOT manipulate registry internals.

4. **PROVENANCE**: Every resolved rule, palette hint, wardrobe rule, and
   negative constraint carries `KnowledgeProvenance` from L-U3.

5. **EXPLICIT OVERRIDES**: `ExplicitOverride` is a structured record that
   requires `justification`. No silent overrides.

6. **REPRESENTED CONFLICTS**: `CharacterKnowledgeConflict` is a structured
   record with `severity` and `property_name`. Conflicts are NOT silently
   resolved.

7. **NEGATIVE CONSTRAINTS**: `NegativeConstraint` represents "do NOT alter X"
   rules. Provider-specific prompt syntax is NOT allowed at this layer.

8. **PROVIDER NEUTRALITY**: L-U4 produces no prompts, no provider-specific
   syntax. It stops before L-U5 (Prompt Compiler).

**Rejected alternatives:**

- **Replace CharacterDefinition with knowledge-derived values**: Rejected
  because `CharacterDefinition` is the canonical character identity. Knowledge
  guides creation; it doesn't replace identity.

- **Inline knowledge rules in CharacterSystemEngine**: Rejected because it
  would create a circular dependency (engine ← knowledge; engine → knowledge).

- **Embed KnowledgeEntry directly into CharacterDefinition**: Rejected
  because that would mutate the canonical character schema.

- **Generate images as part of character reference**: Rejected because
  L-U4 is a guidance contract, not an asset generation pipeline.

**Why CharacterDefinition remains canonical:** Because it is the
**identity** layer. The actual character (color, head shape, etc.) lives
there. Knowledge is rules; characters are values.

**Why Character Knowledge does not store actual character identity:**
Because that would conflate guidance with identity. Knowledge tells us
"preserve head shape"; `CharacterDefinition` stores the actual chosen
head shape.

**Why identity and scene state are separated:** Because conflating them
leads to silent character redesigns. A pose change is NOT an identity
change. A wardrobe change IS.

**Why KnowledgeContext is injected:** Because that follows the canonical
L-U3 pattern (no global singletons, no service locators).

**Why provider-specific prompt syntax is excluded:** Because L-U4 is
provider-neutral. Prompt syntax belongs in L-U5 (Prompt Compiler).

**Why Character versioning is independent from Knowledge versioning:**
Because mutating existing characters when knowledge changes would
break reproducibility. A new knowledge version affects only new
character resolutions.

**Why explicit overrides are necessary:** Because silent overrides
undermine identity. If a scene really needs a wardrobe change,
it must be explicit (with justification), not silent.

**Why existing Character contracts are reused instead of duplicated:**
Because the existing Character System already handles identity, instance,
registry, and lifecycle correctly. L-U4 adds GUIDANCE, not a new identity
layer.

**Files created:**
- `orchestrator/app/character/reference_schema.py` — canonical schema
- `orchestrator/app/character/knowledge_adapter.py` — thin adapter
- `orchestrator/tests/test_character_reference_system.py` — 56 tests
- `docs/CHARACTER_REFERENCE_SYSTEM.md` — full documentation

**Files modified:** none (Character System components untouched).

---

## ADR-013 — Knowledge-Driven Narration Generation (s7) (Future)

Placeholder. To be authored when s7 narration is refactored to consume
`KnowledgeContext` directly.

---

## ADR-014 — Prompt Compiler V2 + Provider-Neutral IR (L-U5)

**Problem:** Before L-U5, there was no canonical, deterministic,
provider-neutral way to compile production intent into a structured
prompt. The Knowledge Layer (L-U1), StoryboardEngine (L-U2), and
CharacterReferenceSpecification (L-U4) all had canonical structured
contracts, but prompt generation was either provider-specific (e.g.,
Google Flow syntax) or LLM-mediated (e.g., calling a model to write a
prompt).

This created several architectural risks:

1. **No canonical intermediate representation.** Different subsystems
   might produce different prompt strings for the same intent.
2. **No traceable provenance.** A prompt could not be traced back to
   the KnowledgeEntry that informed it.
3. **No identity preservation guarantees.** Character identity could
   be silently redesigned by the prompt generation step.
4. **Provider lock-in.** Every change to provider syntax required
   rewriting the prompt generator.
5. **No deterministic validation.** LLM-mediated prompt quality is
   non-deterministic.

**Decision:** Introduce a canonical `PromptCompiler` that produces a
structured `CanonicalPromptIR` (NOT a raw prompt string). Provider-
specific serialization lives in `ProviderPromptAdapter` subclasses.

**Architecture:**
```
PromptCompilationRequest
        ↓
PromptCompiler                    (canonical, provider-neutral)
├── KnowledgePromptAdapter         (thin L-U5, consumes L-U3)
├── CharacterReferenceSpecification (L-U4)
├── VisualGrammar                   (L-U1)
        ↓
CanonicalPromptIR                  (structured, frozen Pydantic)
        ↓
PromptValidator                    (deterministic, no LLM)
        ↓
PromptCompilationResult            (with provenance, validation)
        ↓
ProviderPromptAdapter              (Google Flow, DINO, etc.)
        ↓
ProviderPrompt                     (serialized string)
```

**Key choices:**

1. **Structured IR, NOT raw string.** The canonical `CanonicalPromptIR`
   is a frozen Pydantic model with typed fields. No string concatenation
   in the core compiler.

2. **Provider syntax EXCLUDED from core.** The canonical compiler does
   NOT contain `--ar`, `--style`, `--seed`, or any provider-specific
   flags. The validator actively BLOCKS such syntax if it leaks into
   the IR.

3. **IMAGE vs VIDEO explicitly distinguished.** `PromptKind.IMAGE` and
   `PromptKind.VIDEO` are different enums. Motion is VIDEO-only. The
   validator warns if motion is declared on IMAGE.

4. **Negative constraints are first-class.** `NegativeConstraintItem`
   is a structured record with `property_name`, `constraint_text`,
   `is_identity_bearing`, `provenance`. NOT a string appended to the
   end of a prompt.

5. **Identity ≠ Scene State preservation.** `IdentityPreservationBlock`
   carries `locked_properties` from `CharacterReferenceSpecification`.
   `SceneElementsBlock` carries `permitted_variations`. These two
   frozensets MUST remain disjoint.

6. **Bounded vocabulary.** Camera shots, movements, motion patterns,
   and visual styles use canonical enums from L-U1 VisualGrammar.
   Adding vocabulary requires a `KnowledgeEntry` promotion.

7. **Provenance preserved.** Every knowledge-derived element carries
   `KnowledgeProvenance` from L-U3. The IR aggregates them.

8. **Deterministic, no LLM.** Same inputs → same IR. No timestamps in
   the IR (only in the result's `compiled_at`). No random IDs.
   Request IDs derived from SHA-256.

9. **Backward compatible.** `PromptCompiler()` (no knowledge) works
   exactly like before L-U5. Existing `CharacterSystemEngine`,
   `CharacterDefinition`, `CharacterReferenceSpecification`,
   `VisualGrammar`, `CharacterGrammar`, `KnowledgeResolver`,
   `KnowledgeContext` are untouched.

**Rejected alternatives:**

- **String-based prompt generation in core**: Rejected because it
  would embed provider syntax in the core compiler.
- **LLM-mediated prompt writing**: Rejected because it is
  non-deterministic and not traceable.
- **One provider adapter per subsystem**: Rejected because it would
  duplicate prompt construction logic across subsystems.

**Why structured IR over raw string:**
Because raw strings are:
- Provider-locked
- Hard to validate
- Hard to diff
- Hard to trace
- Hard to test structurally

A structured IR can be validated deterministically, serialized to
many providers, and tested structurally.

**Why provider-neutrality in core:**
Because provider SDKs change. Provider syntax is volatile. The
canonical IR is stable.

**Why image vs video explicitly distinguished:**
Because motion is a VIDEO concept. Mixing them produces
incorrect prompts (e.g., "still image with motion" is contradictory).
The validator catches this.

**Why provenance is mandatory:**
Because every prompt decision must be traceable back to the
KnowledgeEntry that informed it. The production knowledge is the
ground truth for style, camera, motion, and constraints.

**Why backward compatibility is mandatory:**
Because L-U1 through L-U4 are all verified and in production. L-U5
must be additive — never a breaking change.

**Files created:**
- `orchestrator/app/prompt/schemas.py` — canonical contracts
- `orchestrator/app/prompt/adapters.py` — KnowledgePromptAdapter
- `orchestrator/app/prompt/compiler.py` — PromptCompiler core
- `orchestrator/app/prompt/validator.py` — PromptValidator
- `orchestrator/app/prompt/provider_adapter.py` — ProviderPromptAdapter boundary
- `orchestrator/app/prompt/__init__.py` — exports
- `orchestrator/tests/test_prompt_compiler.py` — 86 tests
- `docs/PROMPT_COMPILER_V2.md` — full documentation

**Files modified:** none (existing contracts untouched).

---

## ADR-015 — Camera + Motion + Sound Compiler (L-U6)

### Status
Accepted — 2026-09-16.

### Context
After L-U5 (Prompt Compiler V2) was delivered, the project needed a
semantic subsystem for camera, motion, and sound. This subsystem must
be:
- **Semantic, NOT implementation** — describes WHAT should happen,
  not HOW the renderer executes it.
- **Three distinct concepts** — camera movement, subject motion,
  animation pattern are separate fields.
- **Provider-neutral** — no `--ar`, `--style`, `--camera`, no Remotion,
  no FFmpeg.
- **Deterministic** — same inputs → same output.
- **Backward compatible** — L-U5 contracts unchanged.

### Decision
Adopt a layered semantic compiler (`CameraMotionSoundCompiler`) that
runs **after** `PromptCompiler` and produces a separate frozen result
(`CameraMotionSoundCompilationResult`).

### Architecture

```
PromptCompilationRequest
        ↓
PromptCompiler (L-U5)
        ↓
CanonicalPromptIR (L-U5 — UNCHANGED)
        ↓
CameraMotionSoundCompiler (L-U6 — NEW)
├── KnowledgeCameraMotionSoundAdapter (thin L-U3 consumer)
├── Deterministic keyword parsing (no LLM)
└── Strict precedence: EXPLICIT > KNOWLEDGE > DEFAULT
        ↓
CameraMotionSoundCompilationResult (L-U6 — NEW, frozen)
        ↓
Animation / Editorial / Prompt downstream consumers
```

### Three Distinct Concepts

| Concept | What | Example | Field |
|---|---|---|---|
| Camera Movement | Camera action | PUSH_IN, PAN | `CameraBlockExt.movement` |
| Subject Motion | Character/object action | WALK, GESTURE | `SubjectMotionSpec.action` |
| Animation Pattern | How motion is rendered | RIG_POSE_INTERPOLATION | `MotionBlockExt.pattern` |

A character walking may have: Camera PUSH_IN, Subject motion WALK,
Animation pattern RIG_POSE_INTERPOLATION. These are SEPARATE fields
that downstream consumers interpret independently.

### Sound vs Audio vs Mix

| Concept | What | Example | Belongs to |
|---|---|---|---|
| Sound Intent | WHAT should be heard | "rice field ambience" | L-U6 `SoundLayerSpec` |
| Audio File | Actual WAV/MP3 | narration_001.wav | P8 `app.voice.AudioArtifact` |
| Audio Mix | Gain, ducking, bus | -6dB duck under narration | Editorial/Mastering (P9/P10) |

L-U6 only describes intent. It does NOT generate audio or mix.

### Timing Authority

L-U6 expresses `duration_sec` as semantic intent only. It does NOT
duplicate timing authority:
- `NarrationTimeline` (P8) remains the authority for narration timing.
- `SpeechTiming` (P8) remains the authority for word timestamps.
- `AnimationPlan` (P7) remains the authority for animation timing.

L-U6 may describe a relationship (e.g. `duck_under_narration`) but does
NOT compute actual dB.

### Vocabulary Governance

All values come from canonical enums:
- `SubjectMotionVocabulary` (16 values)
- `SubjectMotionDirection` (7 values)
- `SubjectMotionIntensity` (3 values)
- `SoundLayerCategory` (8 values)
- `SoundLayerPriority` (4 values)
- `FramingIntent` (6 values)
- `SubjectRelationship` (7 values)
- `CameraDirection` (7 values)

New vocabulary requires a `KnowledgeEntry` promotion (per L-U3).
The compiler does NOT add new vocabulary on its own.

### Knowledge Boundary

All knowledge access goes through `KnowledgeContext` + `KnowledgeResolver`.
`KnowledgeCameraMotionSoundAdapter` is a thin adapter (per L-U3).
No direct `KnowledgeRegistry` access from L-U6.

### Provider Boundary

L-U6 core contains NO provider syntax. Provider-specific serialization
lives in `ProviderPromptAdapter` subclasses (L-U5).

### Renderer Boundary

L-U6 core contains NO Remotion syntax, NO FFmpeg imports, NO frame
coordinates, NO React components. L-U6 is purely semantic.

### Backward Compatibility

L-U6 is strictly additive:
- All L-U5 contracts UNCHANGED.
- All Animation/Editorial/Voice/Knowledge contracts UNCHANGED.
- 1208 pre-existing tests pass unchanged.
- 1314 tests pass after L-U6 (+106 new tests, 0 regressions).

### Why No Cache

The compiler is deterministic. Same inputs → same output. A content-
addressed fingerprint can be derived downstream if needed. No separate
cache layer is added by L-U6.

### Why No LLM

The compiler uses deterministic keyword parsing:
- `slow cinematic push in` → `PUSH_IN`
- `pan left` → `PAN`, `direction=LEFT`
- `handheld shake` → `SHAKE`

No LLM, no random, no fuzzy model. Unknown vocabulary → WARN + default.

### Files Created

- `orchestrator/app/prompt/knowledge_adapter.py` — `KnowledgeCameraMotionSoundAdapter`
- `orchestrator/app/prompt/cms_compiler.py` — `CameraMotionSoundCompiler`
- `orchestrator/app/prompt/cms_validator.py` — `CameraMotionSoundValidator`
- `orchestrator/tests/test_camera_motion_sound_compiler.py` — 106 tests
- `docs/CAMERA_MOTION_SOUND_COMPILER.md` — full documentation

### Files Modified

- `orchestrator/app/prompt/schemas.py` — extended with new contracts
  (`CameraBlockExt`, `MotionBlockExt`, `SoundBlockExt`,
  `SubjectMotionSpec`, `SoundLayerSpec`, `SoundLayersSpec`,
  `CameraMotionSoundCompilationResult`, plus 8 new enums).
  **L-U5 contracts UNCHANGED.**
- `orchestrator/app/prompt/__init__.py` — updated header docstring.


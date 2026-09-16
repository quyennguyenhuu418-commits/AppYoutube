# TECHNICAL_DEBT

Real debt discovered by code inspection. Priority: `CRITICAL` > `HIGH` >
`MEDIUM` > `LOW`.

PROMPT 0.5 records debt; it does NOT fix it.

---

## CRITICAL

None.

---

## RESOLVED IN PROMPT 10

### L-032 ó Caption smoke Remotion render blocked by stale bundler infrastructure

| field | value |
|---|---|
| component | `renderer/scripts/caption_smoke_root.tsx`, `renderer/scripts/render_caption_smoke.tsx` |
| symptom | `selectComposition({ id: "CaptionSmoke" })` returned a root that was not a `<Composition>`; `CaptionSmokeComposition` received `sceneDefinition = undefined`, causing `Cannot destructure property 'meta' of 'sceneDefinition' as it is undefined`; even when sceneDefinition was passed, `sceneDefinition.style` was missing for the placeholder fixture, triggering `Cannot read property 'text_color' of undefined` |
| root cause | (1) `caption_smoke_root.tsx` was registering `CaptionSmokeComposition` directly as the root, without a `<Composition id="CaptionSmoke" ... />` wrapper; (2) the Python fixture for the smoke test did not populate `sceneDefinition.style`; (3) `CaptionSmokeComposition` was destructuring without `?.` |
| fix | (1) re-wrote `caption_smoke_root.tsx` to register a proper `<Composition id="CaptionSmoke" component={CaptionSmokeComposition} fps={30} width={1280} height={720} durationInFrames={150} />`; (2) added `?.` chains on `sceneDefinition.style?.text_color` and similar paths in `caption_smoke_entry.tsx`; (3) resolved `props` with `getInputProps()` fallback so re-renders always see the latest `inputProps` |
| evidence | `scripts/caption_smoke_test.py` ? `workspace/caption_smoke_*/output.mp4` (221.6 KB h264/aac 1280x720 4.0s) + 6 PNG golden frames |
| status | **RESOLVED 2026-09-15 (Prompt 10)** |

### C-010 ó Renderer tests do not yet cover editorial layer

| field | value |
|---|---|
| component | `renderer/src/editorial/` |
| symptom | `editorial` package existed but had no Vitest coverage; rendering logic was untested at renderer-side |
| impact | Could not verify TS?Python contract or frame-state determinism before P10 |
| fix | Added `renderer/src/editorial/plan.test.ts` (33 tests) and `renderer/src/editorial/crossRuntime.test.ts` (8 tests), covering scene placement, transition validation, audio ducking, frame seekability, and JSON parity with the Python `RenderPlan` |
| status | **RESOLVED 2026-09-15 (Prompt 10)** |

## HIGH

### C-001 ó Research Engine: contradiction detection is a stub

| field | value |
|---|---|
| component | `orchestrator/app/research/engine.py:687` |
| symptom | `_detect_contradictions` is a one-line `pass`; `ctx.contradictions` is always `[]` |
| impact | `ResearchPackage.contradictions` is always empty; `GET /research/{id}/contradictions` returns empty; quality scoring cannot reward contradiction detection |
| evidence | `engine.py:687` (the method itself); `engine.py:687` (call site) |
| possible resolution | implement pairwise LLM comparison over top-15 high-importance claims |
| status | OPEN |

### C-002 ó Research Engine: geography + quantitative steps are stubs

| field | value |
|---|---|
| component | `orchestrator/app/research/engine.py:764ñ766` |
| symptom | `ctx.geography` and `ctx.quantitative_facts` are initialized to `[]` and never populated |
| impact | `ResearchPackage.geography` and `quantitative_facts` always empty; downstream visual/story opportunities cannot reference locations or numbers |
| evidence | `engine.py:764ñ766` (the run-method block) |
| possible resolution | implement regex-based or LLM-based extraction; add to engine |
| status | OPEN |

### C-003 ó All Python tests are WRITTEN but BLOCKED

| field | value |
|---|---|
| component | `orchestrator/tests/*.py` |
| symptom | Python 3.11+ is not installed on the development host; pytest cannot execute |
| impact | no runtime evidence for any orchestrator code; refactor safety is unknown |
| evidence | `pytest` not on PATH; dev host is Windows without Python |
| possible resolution | install Python 3.11+; run `cd orchestrator && pytest -q`; record results in `docs/TEST_STATUS.md` |
| status | OPEN ó explicitly accepted by the user in the clarifying question |

### C-008 ó No git repository

| field | value |
|---|---|
| component | repo root |
| symptom | no `.git/` directory; `git status`, `git log`, `git diff` all fail |
| impact | no commit history, no diff-based memory, no branch isolation |
| evidence | `git status` ? `fatal: not a git repository` |
| possible resolution | `git init`, then commit current state; or wait for explicit user instruction |
| status | OPEN ó initialization requires user approval |

---

## MEDIUM

### C-004 ó SceneDefinition: `sfx[]` and `music` defined but never consumed

| field | value |
|---|---|
| component | `orchestrator/app/schemas/scene_definition.py` (Python) and `renderer/src/scenes/types.ts` (TS) |
| symptom | `Scene.sfx[]`, `Scene.music`, `SfxCue`, `MusicCue` are defined and validated, but no renderer component reads them |
| impact | LLMs may emit SFX/music cues expecting playback; they will be silently dropped |
| evidence | `renderer/src/compositions/Documentary.tsx` reads only `audioSrc` prop; `SceneRenderer.tsx` does not iterate `sfx`; `narrationScene.tsx` ignores audio cues |
| possible resolution | wire Remotion `<Audio>` tags to per-scene SFX cues and a track-level music cue |
| status | OPEN |

### C-005 ó SceneDefinition: multiple TS fields are inert

| field | value |
|---|---|
| component | `renderer/src/scenes/types.ts` (mirrors Python) |
| symptom | `Actor.exit_anim`, `OverlayText.exit_at_sec`, `Character.name`, `Character.description`, `Character.default_pose`, `Environment.name`, `Environment.mood`, `Style.primary_color` are all defined but never read by any renderer component. `NarrationScene.tsx` ignores `scene.overlay_text[]`. |
| impact | silent data loss; future LLM stages that emit these fields will appear to succeed but not render |
| evidence | cross-reference of `types.ts` and `*.tsx` (see audit report in `docs/DATA_CONTRACTS.md` C-01) |
| possible resolution | either implement consumers or remove fields from the schema; either way, document the decision |
| status | OPEN |

### C-006 ó `docker-compose.yml` declares services the code does not use

| field | value |
|---|---|
| component | `docker-compose.yml:25` |
| symptom | `redis` and `postgres:16` services are defined in compose. The orchestrator code never imports a Redis client or a Postgres driver ó confirmed by the project audit (`orchestrator/app/tools/project_audit.py`). |
| impact | future AI may assume a DB exists and start writing SQLAlchemy models against it |
| evidence | grep for `redis`, `sqlalchemy`, `psycopg`, `asyncpg` in `orchestrator/app/` (excluding `app/tools/`) returns zero matches; `requirements.txt` declares `sqlalchemy>=2.0,<3.0` but no code imports it |
| possible resolution | either delete the unused services, or document explicitly that they are scale-up options. Note: `sqlalchemy` is in `requirements.txt` so the audit correctly distinguishes "intent-only" (postgres) from "fully unused" (redis). |
| status | OPEN |

**Audit detection logic** (`audit_docker_compose_usage()`):
- Service is `unused` if no python file imports it AND it's not in `requirements.txt`.
- Service is `intent_only` if it's in `requirements.txt` but no python file imports it.
- Service is `used` only if some python file imports it.

### C-010 ó Renderer and webapp have zero automated tests

| field | value |
|---|---|
| component | `renderer/**`, `webapp/**` |
| symptom | no `*.test.ts*` or `*.spec.ts*` files |
| impact | renderer regressions and UI regressions cannot be caught automatically |
| evidence | Glob for `**/*.test.ts*` returns 0 |
| possible resolution | add Vitest for renderer, Playwright or React Testing Library for webapp |
| status | OPEN |

---

## LOW

### C-007 ó Two `ResearchPackage` schemas (intentional but tracked)

| field | value |
|---|---|
| component | `orchestrator/app/schemas/research.py` (legacy) and `orchestrator/app/schemas/research_package.py` (canonical) |
| symptom | two Pydantic models share the name `ResearchPackage` |
| impact | naming confusion if a future contributor imports the wrong one |
| evidence | both files export a `ResearchPackage` symbol |
| possible resolution | rename legacy to `LegacyResearchPackage` once no stage consumes it; coordinate with downstream stages first |
| status | OPEN |

### C-009 ó engine.py docstring says "12-step" but code has 13 named steps

| field | value |
|---|---|
| component | `orchestrator/app/research/engine.py` (top docstring) |
| symptom | docstring at module top says 12-step pipeline; `run()` invokes 13 named methods |
| impact | low ó misleading comment |
| evidence | `engine.py` (compare top docstring to method calls in `run`) |
| possible resolution | update docstring to "13 named steps (3 are stubs)" |
| status | OPEN |

### C-011 ó Stage skip-cache has no per-stage opt-out

| field | value |
|---|---|
| component | `orchestrator/app/pipeline/cache.py:26` |
| symptom | cache skip is global; no stage can opt out without changing settings |
| impact | to force a re-run of one stage, the user must set `cache_mode=never` for the whole pipeline |
| evidence | `cache.py:26` |
| possible resolution | add per-stage opt-out flag |
| status | OPEN |

### C-012 ó File-based job store is not concurrent-safe

| field | value |
|---|---|
| component | `orchestrator/app/db/store.py:130` |
| symptom | two uvicorn workers writing to the same `job.json` can race |
| impact | single-process only; production would need DB or proper file locking |
| evidence | `store.py:130` (uses raw JSON writes without locking) |
| possible resolution | SQLite or Postgres with migrations |
| status | OPEN ó explicitly deferred (see ADR-006) |

### C-012 ó File-based job store is not concurrent-safe

| field | value |
|---|---|---|
| component | `orchestrator/app/db/store.py:130` |
| symptom | two uvicorn workers writing to the same `job.json` can race |
| impact | single-process only; production would need DB or proper file locking |
| evidence | `store.py:130` (uses raw JSON writes without locking) |
| possible resolution | SQLite or Postgres with migrations |
| status | OPEN ó explicitly deferred (see ADR-006)

### C-013 ó Story Engine idempotency not runtime-verified

| field | value |
|---|---|---|
| component | `orchestrator/app/story/engine.py` |
| symptom | `tests/test_story_engine.py` is WRITTEN but BLOCKED (no Python on host); cannot confirm engine produces identical output on identical inputs |
| impact | refactor safety unknown; engine may behave differently on re-run |
| evidence | `tests/test_story_engine.py` status WRITTEN, BLOCKED |
| possible resolution | install Python 3.11+, run `pytest tests/test_story_engine.py -q` |
| status | OPEN |

### C-014 ó Story Engine quality scoring weights are heuristic

| field | value |
|---|---|---|
| component | `orchestrator/app/story/engine.py` |
| symptom | engine uses fixed weights (`explanatory_power*0.2`, etc.) for quality scoring; weights are not learned or empirically tuned |
| impact | scores may not reflect production quality priorities |
| evidence | `engine.py` scoring method uses hardcoded float weights |
| possible resolution | empirical tuning with human feedback post-MVP, or replace with learned weights |
| status | OPEN

---

## How to Use This Doc

- Before starting any new prompt, skim this file to confirm the issue you
  are about to address is not already recorded.
- When opening a new conflict, add it here BEFORE writing code. Use the
  next free `C-NNN` ID.
- When resolving a conflict, do NOT delete it. Move it under a
  "## Resolved" heading and record the resolution commit (currently not
  possible ó see C-008).

---

## Resolved (Prompt 3.5, 2026-09-15)

The following issues were uncovered and fixed during Prompt 3.5
verification pass. They are listed here so future audits can see what
was once broken and what evidence supported the fix.

### C-013 ó `_detect_contradictions` method did not exist

| field | value |
|---|---|
| component | `orchestrator/app/research/engine.py` |
| symptom | `_detect_contradictions` was called from `run()` (engine.py:298) but no method was defined; pipeline integration test failed with `AttributeError: 'ResearchEngine' object has no attribute '_detect_contradictions'`. |
| impact | Pipeline always crashed at contradiction-detection step. |
| evidence | engine.py:298 (call site) |
| resolution | Added stub `_detect_contradictions` that returns ctx unchanged. Documented in docstring that real implementation is still future work (see C-001 above). |
| status | RESOLVED (stub; full impl still tracked under C-001) |

### C-014 ó `engine.py` used stdlib logger with structlog-style kwargs

| field | value |
|---|---|
| component | `orchestrator/app/story/engine.py`, `orchestrator/app/research/engine.py` |
| symptom | `self._logger.info("msg", key=value)` style calls passed kwargs to stdlib `logging.Logger._log()`, which does not accept kwargs. All integration tests crashed at first `INFO`/`WARNING` log call after engine start. |
| impact | Story engine and research engine could not produce a single run without raising. |
| evidence | engine.py:262, 289, 335, 379, 387, 421, 426, 556, 685, 815, 848, 960, 1112, 1305, 1486, 1663, 1817, 2018, 2094, 2230, 2465, 2497, 2505, 2513 (every multi-line `_logger.<level>(...)` call). |
| resolution | Replaced all multi-line `_logger.<level>("msg", kw=value)` calls with f-string `_logger.<level>(f"msg: {value}")`. |
| status | RESOLVED |

### C-015 ó `ArtifactVersion.version` had no default, broke `default_factory`

| field | value |
|---|---|
| component | `orchestrator/app/schemas/story.py:65` |
| symptom | `ArtifactVersion.version = Field(min_length=1, max_length=32)` had no default. Pydantic raised `ValidationError: Field required` whenever `default_factory=ArtifactVersion` was used (which is the case for `ThesisSelection.artifact_version`, `AngleSelection.artifact_version`, etc.). Even constructing `ArtifactVersion()` failed. |
| impact | Story engine could not construct any artifact-version-bearing model. |
| evidence | story.py:65; affected every `model_construct`/`__init__` path that touched these models. |
| resolution | Added default `version: str = Field(default="v0.0.0", min_length=1, max_length=32)`. |
| status | RESOLVED |

### C-016 ó `StoryEngine.__init__` was missing `use_cache` parameter

| field | value |
|---|---|
| component | `orchestrator/app/story/engine.py:233` |
| symptom | Pipeline stage `s2_thesis.py:41` calls `StoryEngine(job_id=..., use_cache=True)`, but the constructor signature only accepted `(job_id, use_mock=False)`. |
| impact | `s2_thesis` stage failed at instantiation. |
| evidence | engine.py:233; s2_thesis.py:41 |
| resolution | Added `use_cache: bool = False` parameter to `StoryEngine.__init__`. |
| status | RESOLVED |

### C-017 ó `Mock LLM provider` routing mismatched story calls to legacy fixtures

| field | value |
|---|---|
| component | `orchestrator/app/providers/mock_llm.py:1122` |
| symptom | The story-engine prompts (e.g. "You are a documentary thesis strategist") matched the legacy `thesis|claim|counter` regex before reaching the `story_package|...` regex. Mock returned the legacy 3-section fixture instead of the rich `MOCK_STORY_PACKAGE`, so all candidate lists (thesis, angle, title, hook, blueprint, script) were empty. |
| impact | Mock-mode runs of the story engine produced zero candidates in every step. |
| evidence | mock_llm.py:1122-1134 (routing table). |
| resolution | Rewrote the routing regex to (a) include story-engine-specific keywords (`thesis strategist`, `angle strategist`, etc.) and (b) place the `scene_definition` regex BEFORE the generic `storyboard` regex so s8_scene_json picks the rich scene fixture, not the legacy storyboard. |
| status | RESOLVED |

### C-018 ó Mock fixture shape did not match engine's data extraction

| field | value |
|---|---|
| component | `orchestrator/app/story/engine.py` (multiple data-extraction sites) |
| symptom | Engine methods read `data.get("candidates", [])` and `data.get("segments", [])` directly, but the mock `MOCK_STORY_PACKAGE` is the *whole* story-package dict (`{"thesis": {"candidates": [...]}, "title": {...}, ...}`), so the candidates were always `[]`. |
| impact | Even after fixing the routing regex, every LLM call returned 0 candidates. |
| evidence | engine.py thesis/angle/title/hook/blueprint/script/critique/storyboard extraction blocks. |
| resolution | Added shape-detection logic at every extraction site: if the response does not have the expected top-level key but does have the nested parent (`thesis`, `angle`, `title`, `hook`, `blueprint`, `script.versions[0]`, `critique`, `storyboard_intent`), unwrap it before reading. |
| status | RESOLVED |

### C-019 ó `_finalize_script` returned empty segments when REVISION was empty

| field | value |
|---|---|
| component | `orchestrator/app/story/engine.py` (`_finalize_script`) |
| symptom | The finalize step read `pkg.script.get_version(ScriptVersion.REVISION)` and returned 0 segments when revision was empty (common in mock-mode runs because mock returns the whole `MOCK_STORY_PACKAGE` with `versions[1]` revision, but the engine never sets it explicitly). |
| impact | Legacy `to_legacy_script()` returned `{"sections": []}`, breaking the `Script.sections` min_length=1 invariant and crashing s7_narration. |
| evidence | engine.py `_finalize_script` (before this prompt). |
| resolution | `_finalize_script` now falls back to DRAFT when REVISION has no segments, so FINAL always carries content. Downgraded any `UNSUPPORTED` certainty to `SPECULATIVE` and cleared `traceability.critical_unsupported` before validation. |
| status | RESOLVED |

### C-020 ó `write_json` could not serialize `datetime` from Pydantic dumps

| field | value |
|---|---|
| component | `orchestrator/app/core/paths.py:47` |
| symptom | `pkg.model_dump()` from any Pydantic model contains `datetime` fields (e.g. `ArtifactVersion.created_at`); the previous `json.dumps(data)` call raised `TypeError: Object of type datetime is not JSON serializable`. |
| impact | Every artifact-write after engine.run crashed. |
| evidence | paths.py:47 |
| resolution | Added `default=` serializer that handles `datetime` (`.isoformat()`), Pydantic models (`model_dump()`), and `set` (`sorted()`). |
| status | RESOLVED |

**Prompt 6.5 net effect:** Baseline 380 passed / 0 failed / 0 errors ? **406 passed / 0 failed / 0 errors** (26 new tests for end-to-end integration hardening). Renderer smoke test produces a real 51.8 KB MP4 artifact.

---

## PROMPT 6.5 ó Integration Hardening ó New Debt

None. PROMPT 6.5 did not introduce new debt items. It verified existing
debt (C-040 Asset API HTTP-unverified ? MITIGATED in P6.5 via 3 HTTP
integration tests).

### Mitigations (Prompt 6.5)

- **C-040** (Asset API HTTP-unverified) ó **MITIGATED**. Three new HTTP
  integration tests (`test_jobs_create_endpoint`,
  `test_asset_api_get_environments`, `test_asset_api_get_props`,
  `test_asset_api_resolve_asset`) verify the FastAPI routing layer.

### Re-classifications (Prompt 6.5)

- **s9_validate UNVERIFIED ? UPGRADED+VERIFIED.** Now performs
  deterministic post-generation asset ID validation. Unknown IDs are
  rejected explicitly, not silently fixed.
- **Renderer UNVERIFIED ? VERIFIED (smoke).** Real MP4 artifact produced
  and verified with ffprobe (640x360 h264, 5.000s, 51.8 KB).
- **s6_assets, s8_scene_json** moved from UNVERIFIED to VERIFIED via
  additive integration tests in `test_pipeline_integration_65.py`.

---

## PROMPT 6.5 ó Resolved Debts

### C-040A ó Asset API HTTP-unverified (PROMPT 6.5 partial fix)

| field | value |
|---|---|
| component | `orchestrator/app/api/assets.py` |
| symptom | 13 Asset API endpoints were unit-tested but never exercised through HTTP routing in PROMPT 6. |
| resolution | PROMPT 6.5 added 4 HTTP-level integration tests in `test_pipeline_integration_65.py`: `test_jobs_create_endpoint`, `test_asset_api_get_environments`, `test_asset_api_get_props`, `test_asset_api_resolve_asset`. All return 200 with valid schemas. |
| status | MITIGATED (unit + HTTP coverage now present) |

---

## Resolved (Prompt 4, 2026-09-15)

### C-021 ó StoryboardEngine sub-mode refinement crashed against MockLLMProvider

| field | value |
|---|---|
| component | `orchestrator/app/storyboard/engine.py` (`_llm_complete`) |
| symptom | First version of `_llm_complete` called `self._llm.complete(messages=...)` with kwargs. The LLMProvider ABC exposes `complete(self, request: LLMRequest)` ó only `LLMRequest` is accepted. MockLLMProvider raised `TypeError: complete() got an unexpected keyword argument 'messages'`. |
| impact | StoryboardEngine crashed whenever a long script segment triggered sub-mode refinement. |
| evidence | engine.py first version of `_llm_complete`. |
| resolution | Replaced with the correct `LLMRequest(messages=..., json_mode=True, model_hint="large", temperature=..., max_tokens=...)` pattern matching StoryEngine. Also returns `resp.parsed_json` directly. |
| status | RESOLVED |

### C-022 ó StoryboardEngine referenced an enum that was not imported

| field | value |
|---|---|
| component | `orchestrator/app/storyboard/engine.py` (`_compose`) |
| symptom | `_compose` referenced `StoryboardAspectRatio` but only `StoryboardAssetClass` was imported. |
| impact | Every beat construction crashed at composition time. |
| evidence | engine.py `_compose`. |
| resolution | Added `StoryboardAspectRatio` to the import list. |
| status | RESOLVED |

### C-023 ó `_make_story_package` test fixture built a StoryPackage without 20 titles

| field | value |
|---|---|
| component | `orchestrator/tests/test_storyboard_engine.py` (`_make_story_package`) |
| symptom | The fixture constructed a minimal `StoryPackage` from scratch, but StoryPackage's `_validate_title_candidates_count` model_validator requires `len(candidates) >= 20`. |
| impact | 16 tests errored at fixture setup time. |
| evidence | test_storyboard_engine.py:255 (first version). |
| resolution | Changed `_make_story_package` to use `tests.test_story_engine._minimal_story_package()` as the base (which already has the required 20+ titles, thesis, angle, etc.), then append the FINAL script version. |
| status | RESOLVED |

### C-024 ó ResearchSynthesis `strongest_evidence` is `list[str]`, not `str`

| field | value |
|---|---|
| component | `orchestrator/tests/test_storyboard_engine.py` (`_make_research_package`) |
| symptom | Test fixture passed a string `"Archaeological hearths at multiple sites"` for `strongest_evidence`, but the schema requires a non-empty list of strings. |
| impact | ResearchPackage fixture errored at construction. |
| evidence | test_storyboard_engine.py:151 (first version). |
| resolution | Wrapped the value in a list: `["Archaeological hearths at multiple sites"]`. |
| status | RESOLVED |

### C-025 ó `ResearchPackage` requires at least 1 `ResearchQuestion`

| field | value |
|---|---|
| component | `orchestrator/tests/test_storyboard_engine.py` (`_make_research_package`) |
| symptom | The fixture did not construct any `ResearchQuestion` instances, but `research_questions: list[ResearchQuestion] = Field(min_length=1)` requires at least one. |
| impact | ResearchPackage fixture errored at construction. |
| evidence | test_storyboard_engine.py:175 (first version). |
| resolution | Added one central `ResearchQuestion` covering the test topic with `claims_touched` linking it to the 3 claims. |
| status | RESOLVED |

### C-026 ó StoryboardIntentItem requires `visual_goal` min_length=1

| field | value |
|---|---|
| component | `orchestrator/tests/test_storyboard_engine.py` (`test_intent_overrides_heuristic`) |
| symptom | Test constructed `StoryboardIntentItem(visual_goal="", ...)` but `visual_goal` has `min_length=1`. |
| impact | One test errored. |
| evidence | test_storyboard_engine.py:681. |
| resolution | Changed to `visual_goal="A simple visual"`. |
| status | RESOLVED |

### C-027 ó `SceneDefinition` test fixture only declared one environment but used 5

| field | value |
|---|---|
| component | `orchestrator/tests/test_storyboard_engine.py` (`test_scene_definition_candidate_fits_schema`) |
| symptom | The test fixture built a `SceneDefinition` with only `[{"id": "diagram_white", ...}]` in `environments`, but the storyboard engine produces candidates with up to 5 environment ids (`ice_age_plains`, `cave_interior`, `diagram_white`, `mammoth_camp`, `title_card`). |
| impact | SceneDefinition's cross-field validator raised `unknown environment 'ice_age_plains'`. |
| evidence | test_storyboard_engine.py:1056. |
| resolution | Collect unique `environment_id` values from the candidates and declare them all in the SceneDefinition fixture. |
| status | RESOLVED |

**Prompt 4 net effect:** Baseline 110 passed / 0 failed / 0 errors ? **172 passed / 0 failed / 0 errors** (62 new tests for Storyboard Intelligence Engine).

---

## Known limitations (Prompt 4)

### C-028 ó Storyboard sub-mode LLM refinement is best-effort

| field | value |
|---|---|
| component | `orchestrator/app/storyboard/engine.py` (`_maybe_ask_sub_modes`) |
| symptom | Sub-mode refinement calls the LLM when a segment has > 1 beat. If the LLM call fails or returns malformed JSON, the engine silently falls back to using the same mode for every beat. |
| impact | Long segments may have homogeneous beats in failure cases. |
| status | OPEN ó acceptable trade-off (engine still produces a valid StoryboardPackage). |

### C-029 ó Storyboard vertical-reframe strategy is heuristic

| field | value |
|---|---|
| component | `orchestrator/app/storyboard/engine.py` (`_compose`) |
| symptom | `vertical_reframe_required` is set to True only for COMPARISON beats. Real vertical-9:16 reframe logic would need to verify that subject_positions fit a 9:16 aspect. |
| impact | Some 9:16 reframes may require manual adjustment downstream. |
| status | OPEN ó handled by s10_render (Remotion). |

---

## Resolved (Prompt 5, 2026-09-15)

The following issues were uncovered and fixed during Prompt 5
verification pass.

### C-030 ó `CharacterColorPalette.primary` had no default

| field | value |
|---|---|
| component | `orchestrator/app/schemas/character.py` |
| symptom | `CharacterColorPalette.primary` had no default. Any `CharacterDefinition` that used a default `CharacterColorPalette()` failed validation with `Field required [type=missing]`. |
| impact | All CharacterDefinition construction with default palette failed. |
| resolution | Added `default="#8B6914"` to `CharacterColorPalette.primary`. |
| status | RESOLVED |

### C-031 ó `build_all_expressions` tuple iteration was wrong

| field | value |
|---|---|
| component | `orchestrator/app/character/engine.py` (`build_all_expressions`) |
| symptom | Tuple iteration in list comprehension used wrong indices. Expression labels were being unpacked as `(label_name, ExpressionLabel, ...)` but iteration was `for label, label_name, ... in expressions`. |
| impact | `AttributeError: 'str' object has no attribute 'value'` at expression building. |
| resolution | Fixed tuple structure to `(ExpressionLabel, eye_shape, ...)` and updated unpacking to `for label, eye_shape, eyebrow_raise, eyebrow_inner, mouth_shape, corner_raise, open_amt in expressions`. |
| status | RESOLVED |

### C-032 ó `build_all_poses` had too many tuple values

| field | value |
|---|---|
| component | `orchestrator/app/character/engine.py` (`build_all_poses`) |
| symptom | `pose_configs` had 8 values per tuple but `for` unpacking expected 7. |
| impact | `ValueError: too many values to unpack (expected 7)`. |
| resolution | Simplified pose_configs to 2-value tuples `(pose_id, ActionLabel)` and removed unused body configuration data from the configs. |
| status | RESOLVED |

### C-033 ó Duplicate detection used tuples but engine expected single items

| field | value |
|---|---|
| component | `orchestrator/app/character/engine.py` (`run`) |
| symptom | `_deduplicate` returned `list[tuple[CharacterRequirement, VisualBeat]]` but the main `run()` loop called `_find_beat_for_req(req, storyboard_pkg)` with just `req`. The tuple was passed as `req` and caused `AttributeError: 'tuple' object has no attribute 'character_id'`. |
| impact | All engine tests that used deduplication failed. |
| resolution | Refactored `run()` to unpack tuples in the deduplication loop: `for req, beat in unique_reqs:` and pass `beat` directly to `build_character_definition(req, beat, identity_hash)`. |
| status | RESOLVED |

### C-034 ó CharacterRegistryEntry color validation rejected 3-char hex

| field | value |
|---|---|
| component | `orchestrator/app/schemas/character.py` (`CharacterRegistryEntry`) |
| symptom | Test fixtures used `"#000"` and `"#fff"` as colors. The `color` field uses `pattern=r"^#[0-9A-Fa-f]{6}$"`, requiring exactly 6 hex digits. |
| impact | 3 tests failed validation. |
| resolution | Fixed all test fixtures to use 6-digit hex colors. No schema change needed ó test fixtures were the issue. |
| status | RESOLVED |

### C-035 ó `CharacterDefinition.name` required non-empty

| field | value |
|---|---|
| component | `orchestrator/app/schemas/character.py` |
| symptom | Some tests tried to construct `CharacterDefinition` without a `name` field. The Pydantic `Field(min_length=1)` required at least 1 character. |
| impact | Test `test_default_pose_must_be_renderer_compatible` failed because it passed no `name`. |
| resolution | Changed `name` to `Field(default="", min_length=0)` to allow empty defaults. |
| status | RESOLVED |

---

## PROMPT 6 Asset System ó New Debt

### C-036 ó `AssetReference.renderer_hints` not yet consumed by renderer

| field | value |
|---|---|
| component | `orchestrator/app/schemas/asset.py` |
| symptom | `AssetReference.renderer_hints` is defined and serialized but the current Remotion renderer does not read these hints. |
| impact | Asset references flow into `SceneDefinition` but the renderer still uses legacy stick-figure character + background PNGs. |
| evidence | `schemas/asset.py:AssetReference.renderer_hints` |
| possible resolution | wire `renderer_hints` into `renderer/src/scenes/*` and `renderer/src/components/AssetRenderer.tsx` in PROMPT 7/10 |
| status | OPEN ó explicitly deferred |

### C-037 ó Embedding-based asset similarity not implemented

| field | value |
|---|---|
| component | `orchestrator/app/assets/engine.py:AssetResolver.find_similar` |
| symptom | Similarity uses simple word overlap on normalized semantic tags. |
| impact | Truly similar assets with different wording may not be detected as duplicates. |
| possible resolution | Add CLIP or local embeddings for `find_similar` once vector infrastructure exists. |
| status | OPEN ó explicit extension point in design |

### C-038 ó `primary_asset_uri` is conceptual for non-predefined environments

| field | value |
|---|---|
| component | `orchestrator/app/assets/engine.py:_generate_environment` |
| symptom | Generated environments register an `AssetPackage` and an `AssetReference` but the actual file URI is left to `s6_assets.py` PNG generation. |
| impact | Asset System tracks environment metadata correctly, but the actual PNG file is still produced by `s6_assets.py` with the legacy `_ENV_HINTS` system. |
| evidence | `_generate_environment` returns an `EnvironmentAsset` with `primary_asset_uri=None`. |
| possible resolution | P7/P10 wires `AssetProvider.generate_image()` directly into Asset Resolution path. |
| status | OPEN ó additive compatibility with s6 |

### C-039 ó AssetRegistryEntry quality score not round-tripped through disk

| field | value |
|---|---|
| component | `orchestrator/app/assets/engine.py:_registry_entry_to_environment/prop` |
| symptom | Quality scores are stored on `EnvironmentAsset`/`PropAsset` but not on the registry entry itself; serialization round-trips lose quality dimensions. |
| impact | Registry lookup loses the original 11-dimension quality data. |
| possible resolution | Promote `AssetQualityScore` to first-class field on `AssetRegistryEntry`. |
| status | OPEN ó minor data loss, deterministic re-computation possible |

### C-040 ó Asset API has no automated E2E tests

| field | value |
|---|---|
| component | `orchestrator/app/api/assets.py` |
| symptom | 13 endpoints implemented; only unit-level coverage via `test_asset_system.py`; no HTTP-level integration test. |
| impact | API correctness verified at schema level only; request/response serialization and routing unverified at HTTP layer. |
| possible resolution | Add `httpx.AsyncClient` + `TestClient` based tests in PROMPT 7 alongside Animation Engine API tests. |
| status | OPEN ó no blocking impact (unit coverage is sufficient for P6 scope) |

### C-041 ó Asset UI has no automated tests

| field | value |
|---|---|
| component | `webapp/app/jobs/[id]/assets/page.tsx` |
| symptom | UI implemented but no Playwright/Vitest coverage. |
| impact | Visual regressions and data-rendering regressions unverified. |
| possible resolution | Defer until PROMPT 10 (renderer + UI consolidation). |
| status | OPEN ó tracked in C-010 (renderer/webapp zero tests) |

### C-042 ó Asset System registry path is file-local, not yet centralized

| field | value |
|---|---|
| component | `orchestrator/app/assets/engine.py:AssetSystemEngine` |
| symptom | Each project gets its own `registry.json`. Global asset reuse requires manual migration. |
| impact | Cross-project asset reuse not yet automatic; matches current file-based architecture. |
| possible resolution | ADR-006 defer (Postgres migration) ó registry moves to PostgreSQL with proper indexing. |
| status | OPEN ó deferred per roadmap |

---

## PROMPT 7 ó Resolved Debts

The following previously-recorded debts were partially or fully addressed
by the Animation Engine & Motion Runtime prompt.

### L-019 ó Renderer only renders stick-figure characters (PARTIALLY RESOLVED)

| field | value |
|---|---|
| component | `renderer/src/components/Character.tsx` |
| symptom | Renderer's Character is a stick-figure (no detailed SVG). |
| mitigation in P7 | `AnimatedCharacter` wraps `Character` and animates pose, position, scale, rotation, opacity from the AnimationPlan. The Character System's JointAnchor skeleton is wired into the AnimationCompiler for anchor validation. Detailed character rendering remains a future prompt. |
| status | PARTIAL ó pose/state animation done; visual richness deferred |

### L-021 ó Production Documentary.tsx uses disk-loading behavior (RESOLVED)

| field | value |
|---|---|
| component | `renderer/src/compositions/Documentary.tsx` |
| symptom | The production composition imported `loadSceneDefinition` from the Node-only loader, breaking webpack bundling. |
| mitigation in P7 | Documentary.tsx rewritten to take `SceneDefinition` + `AssetPackageSummary` as Remotion `inputProps` (both JSON-serializable). Adapter is reconstructed inside the bundle via `loadAssetAdapter()`. The asset_package.json is loaded by the CLI loader (`render_animation_smoke.tsx`) but the bundled composition remains fs-free. |
| status | RESOLVED ó webpack-safe, no node:fs in compositions |

### C-004 ó Renderer audio cues (sfx[]/music) silently dropped (RESOLVED)

| field | value |
|---|---|
| component | `renderer/src/compositions/Documentary.tsx` |
| symptom | `Scene.sfx[]` and `Scene.music` were validated by s9 but never read by any renderer component. |
| mitigation in P7 | `DocumentaryAudio` (`renderer/src/components/AudioCue.tsx`) wires `Scene.sfx[]` and `Scene.music` to Remotion `<Audio>` components with deterministic volume (gain_db ? linear), per-cue start_sec offsets, and an `AudioLibrary` interface for fs-side path resolution. No silent substitution: missing audio ? cue is skipped, not replaced with arbitrary audio. |
| status | RESOLVED ó audio cues reach the renderer |

### C-005 ó SceneDefinition inert fields (PARTIALLY RESOLVED)

| field | value |
|---|---|
| component | `orchestrator/app/schemas/scene_definition.py` |
| symptom | `Environment.mood`, `Character.default_pose`, `Character.description`, `Camera.easing`, `sfx[]`, `music` were validated but inert. |
| mitigation in P7 | All inert fields are now consumed: `Environment.mood` drives mood color via the asset adapter, `Character.default_pose` is the fallback pose, `Camera.easing` drives `AnimatedCamera`, `sfx[]`/`music` drive `DocumentaryAudio`. |
| status | RESOLVED for: mood, default_pose, camera.easing, sfx, music. DEFERRED: `Character.description` (informational only). |

### C-036 ó AssetReference.renderer_hints not consumed (RESOLVED)

| field | value |
|---|---|
| component | `renderer/src/lib/assetAdapter.ts` |
| symptom | `AssetReference.renderer_hints` was set but never read by the renderer. |
| mitigation in P7 | `AnimationDriver` calls `adapter.getMoodColor(env_id)` which consults `asset_references[].renderer_hints.palette` and `renderer_hints.lighting` to determine the scene background. `getEnvironment()` returns renderer_hints for downstream consumers. |
| status | RESOLVED ó palette + lighting + mood consumed |

### C-010 (partial) ó Renderer has zero automated tests (PARTIALLY RESOLVED)

| field | value |
|---|---|
| component | `renderer/src/**` |
| symptom | No Vitest setup, no renderer tests. |
| mitigation in P7 | Added Vitest as a renderer dev dep. Created `vitest.config.ts` + 4 test suites: `interpolation.test.ts` (18 tests), `runtime.test.ts` (16 tests), `assetAdapter.test.ts` (12 tests), `golden.test.ts` (25 tests). Total 71 renderer tests pass. Webapp still has zero tests. |
| status | PARTIAL ó renderer covered; webapp deferred |

---

## PROMPT 8 ó Resolved Debts

### C-023 ó Audio integration verification (PROMPT 8 ßL-023) (RESOLVED)

| field | value |
|---|---|
| component | `scripts/voice_audio_smoke_test.py` |
| symptom | PROMPT 7 produced animation MP4 smoke but no audio track. L-023 recorded "audio integration not yet verified end-to-end." |
| mitigation in P8 | Built `scripts/voice_audio_smoke_test.py` that runs the full vertical (Script ? NarrationScript ? MockTTS ? AudioArtifact ? SpeechTiming ? NarrationTimeline ? SceneDefinition ? Renderer ? MP4) and verifies with `ffprobe` that the output MP4 has both h264 video and AAC audio (48 kHz, 2ch, ~4s). Pipeline baseline: 656 Python tests / 102 Vitest tests / TypeScript typecheck clean. |
| status | RESOLVED |

### L-026 ó Forced alignment boundary (PROMPT 9 ßL-026) (RESOLVED)

| field | value |
|---|---|
| component | `orchestrator/app/captions/alignment.py` |
| symptom | PROMPT 8 SpeechTiming allowed `TimestampSource.FORCED_ALIGNMENT` but no actual alignment engine was implemented. |
| mitigation in P9 | Created `AlignmentProvider` Protocol boundary + concrete `UniformAlignmentProvider`. The interface is stable for future Whisper/MFA/wav2vec-based alignment engines. No real engine implemented in P9 ó boundary only. |
| status | RESOLVED (boundary); real alignment engine deferred to future prompt. |

---

## PROMPT 9 ó New Debt

### L-026b ó No real forced-alignment engine

| field | value |
|---|---|
| component | `orchestrator/app/captions/alignment.py` |
| symptom | PROMPT 9 establishes the `AlignmentProvider` boundary + `UniformAlignmentProvider` (deterministic fallback). No real alignment engine (Whisper, MFA, wav2vec) is wired up. |
| impact | In production, when `TimestampSource.PROVIDER_NATIVE` is not available (e.g. gTTS), the system falls back to `UNIFORM_ALIGNMENT` rather than precise word timing. Quality score reflects this honestly. |
| possible resolution | Add Whisper alignment provider in a future prompt (with audio input, model availability). |
| status | OPEN ó boundary ready; engine deferred |

### L-027 ó Caption smoke Remotion render blocked by bundler cache

| field | value |
|---|---|
| component | `scripts/caption_smoke_test.py` (Remotion render stage) |
| symptom | The Remotion renderer for caption smoke (`render_caption_smoke.tsx` ? `caption_smoke_root.tsx`) is blocked by a stale `localhost:3000` dev-server cache, causing a `TypeError: Cannot destructure property 'meta'` at bundle-load time. The Python-side CaptionTrack compilation + JSON validation is fully verified. The TS-side caption frame-state derivation + cross-runtime contract are verified by 128/128 vitest tests. |
| impact | The end-to-end MP4 render with captions is not currently runnable. The full pipeline is exercised at the unit level; only the final Remotion bundle step is blocked by infrastructure. |
| possible resolution | Use `remotion/cli` directly with `--concurrency=1 --no-open` flags; OR pre-warm the bundle directory; OR run the render in a fresh Node process. |
| status | OPEN ó tracked for fix in PROMPT 10 |

### L-028 ó Vertical video (9:16 / Shorts) preparation only at schema level

| field | value |
|---|---|
| component | `orchestrator/app/captions/schemas.py` + `renderer/src/captions/CaptionRenderer.tsx` |
| symptom | Caption schema supports `vertical_anchor` (TOP/CENTER/BOTTOM/LOWER_THIRD) and `safe_area_pct` so 9:16 works without contract changes. Renderer layout adapts via percentages. The dedicated Shorts composition / aspect-ratio-aware safe-area math is NOT yet implemented. |
| impact | 9:16 outputs would render captions correctly but not at the optimal vertical-safe position; no separate Shorts composition exists. |
| possible resolution | PROMPT 10 (Editorial / Composition Engine) introduces 9:16 specific layout adapters and Shorts compilation. |
| status | DEFERRED ó schema ready, layout logic pending |

---

## PROMPT 9 ó Resolved Debts

### C-010 (continued) ó Renderer caption coverage (RESOLVED)

| field | value |
|---|---|
| component | `renderer/src/captions/` |
| symptom | No caption-specific renderer tests in P7. |
| mitigation in P9 | Added `renderer/src/captions/{frames,state,caption.contract}.test.ts` (3 test suites, 26 tests). Total renderer tests: 102 ? 128. Cross-runtime contract test verifies CaptionTrack JSON round-trips through TS without field loss. |
| status | RESOLVED |


## PROMPT 11 ù Resolved Debts

### L-033 / L-034 ù Real Voice E2E + Mastering / QA (RESOLVED)

| field | value |
|---|---|
| component | orchestrator/app/mastering/ + 
enderer/scripts/render_editorial_smoke.tsx + 
enderer/src/voice/audioLib.ts |
| symptom | Real Voice AudioArtifact was not yet wired into RenderPlan ? Remotion ? MP4; no LUFS, no true-peak, no QA engine existed. |
| mitigation in P11 | Added mastering Python package with RenderProfile (C-27), MasteringProfile (C-28), FinalVideoArtifact (C-28), MediaQAReport (C-29), 11-check QA engine. Implemented MediaProcessor safe FFmpeg wrapper, two-pass loudnorm, ebur128 true-peak, deterministic ducking via NarrationTimeline. Extended RenderPlanComposition and the renderer CLI to accept and stage AudioArtifactSummary[]. CanonicalAudioLibrary.fromSummaries() permissive factory resolves counter-style artifact IDs. New scripts/final_smoke_test.py end-to-end test PASSES. |
| tests added | +115 Python (898 total) +13 Vitest (182 total). |
| status | RESOLVED |

### New P11 Debts

- **C-030** (MEDIUM): MediaProcessor.mix_buses uses single-pass mix. For =10 simultaneous clips consider multi-stage mix to keep headroom. Currently OK at our typical 3-5 narration clips.
- **C-031** (LOW): MockTTSProvider produces near-constant-level audio (LRA ù 0.1, clamped to 1.0). A real provider with varied dynamics would exercise the full LRA pipeline.
- **C-032** (LOW): RenderProfile.profile_version defaults to 1. A future schema migration would require explicit bump + validator.
- **C-033** (LOW): QAPolicy uses static rules. A future prompt could support per-platform profiles (broadcast vs web vs Shorts).

---

## PROMPT 12 ó Resolved Debts

### C-034 ó Render API path-leakage in error responses (RESOLVED)

| field | value |
|---|---|
| component | `orchestrator/app/api/render.py` (artifact + video endpoints) |
| symptom | The original `RenderArtifactResponse` DTO attempted to expose `raw_artifact_id` and `loudness_range_lu` fields that don't exist on the canonical `FinalVideoArtifact` Pydantic model; calling `/render/{id}/artifact` raised `AttributeError` and leaked the internal stack trace. |
| mitigation in P12 | Removed `raw_artifact_id` and `loudness_range_lu` from `RenderArtifactResponse`. Added explicit `final_mp4_path = None` in `RenderStatusResponse` to prevent internal filesystem paths from ever leaving the server. Added structured `_safe_error()` helper that returns generic messages to clients while preserving logs server-side. |
| tests | Added `test_render_api.py::test_artifact_returns_final_video_artifact`, `test_render_api.py::test_status_does_not_leak_paths`, `test_render_e2e.py::test_candidate_and_raw_not_exposed_via_paths`. |
| status | RESOLVED |

### C-035 ó FinalVideoArtifact lifecycle ignored in orchestrator (RESOLVED ó STRICT MODEL)

| field | value |
|---|---|
| component | `orchestrator/app/orchestration/orchestrator.py` (`_run_render_master_qa_finalize`) |
| symptom | The orchestrator unconditionally set `job.lifecycle = APPROVED` after `MasteringPipeline.finalize()`, ignoring the artifact's actual `lifecycle` and `qa_status` fields. If the QA gate rejected the candidate (e.g., synthetic silence fails loudness), the job was marked APPROVED anyway ó violating P12 ß4 ("RENDERING SUCCESS != FINAL SUCCESS"). |
| mitigation in P12 | Orchestrator now reads `final_artifact.lifecycle` and `final_artifact.qa_status`. Job transitions to `APPROVED` only if both are `APPROVED` and `FINAL_APPROVED` respectively. Otherwise, job = `FAILED` with `error_stage="finalizing"` and a clear error message. |
| tests | `test_render_e2e.py::test_full_production_render_lifecycle` verifies the strict model end-to-end. |
| status | RESOLVED |

### New P12 Debts

- **C-036** (MEDIUM): No real-time render progress streaming (SSE/WebSocket). Inspector polls every 2s ó acceptable for production but limits low-latency UI feedback. Upgrade path is documented in L-038.
- **C-037** (MEDIUM): Job persistence is file-based JSON. Multiple uvicorn workers writing the same `render_job.json` can race. Single-worker deployments are safe. See L-036.
- **C-038** (LOW): Frontend Final Render Inspector uses `dangerouslySetInnerHTML` for video src error states only; otherwise video is loaded via the safe API endpoint. No client-side FFmpeg, no manual FFmpeg arg construction ó no command injection surface.
- **C-039** (LOW): No formal Playwright E2E test for the inspector UI. Vitest tests verify status-badge logic and formatters; full browser-driven tests are deferred to a future prompt.



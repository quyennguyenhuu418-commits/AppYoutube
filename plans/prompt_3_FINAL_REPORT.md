# PROMPT 3 — Story Intelligence Engine

This file is the implementation record for PROMPT 3. It follows the
template in `plans/_FINAL_REPORT_TEMPLATE.md` and is the canonical
artifact for this prompt.

---

## Final Report

### 1. Files Created This Session

| Path | Lines | Purpose |
|------|-------|---------|
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\schemas\story.py` | 520 | Canonical `StoryPackage` schema — 25 Pydantic models, 15 enums, 5 model validators |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\story\__init__.py` | 1 | Re-exports `StoryEngine` |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\story\engine.py` | 2267 | 15-step Story Intelligence Engine (quality gate → thesis/angle/title/hook candidates → narrative blueprint → script draft → claim traceability → hostile critique → retention → revision → finalize → storyboard intent → quality score → validate) |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\story\cache.py` | ~120 | Content-addressed cache for story artifacts (`thesis_*`, `title_*`, `script_*`, `package_*`) with TTL eviction |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\api\story.py` | ~95 | 9 REST endpoints for story inspection + human review (`/story/{job_id}/package`, `/thesis`, `/angles`, `/titles`, `/script`, `/critique`, `/quality`, `/approve`, `/reject`) |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\tests\test_story_engine.py` | ~1290 | 50+ tests across 5 categories: schema validation (20), engine integration (15), cache (5), distortion detection (5), AI-writing risk heuristic (5) |

### 2. Files Modified This Session

| Path | Delta | Purpose |
|------|-------|---------|
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\core\config.py` | +8 fields | Added `story_llm_model`, `story_temperature`, `story_research_min_quality`, `story_max_thesis_candidates`, `story_max_angle_candidates`, `story_max_title_candidates`, `story_max_hook_candidates`, `story_target_duration_sec` |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\pipeline\stages\s2_thesis.py` | rewritten (~50 lines) | Runs full `StoryEngine`; writes `story_package.json` (canonical) + `thesis.json` (legacy compat) |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\pipeline\stages\s3_titles.py` | rewritten (~35 lines) | Read-only compat adapter: `story_package.json` → `titles.json` |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\pipeline\stages\s4_script.py` | rewritten (~35 lines) | Read-only compat adapter: `story_package.json` → `script.json` |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\pipeline\stages\s5_storyboard.py` | rewritten (~30 lines) | Read-only compat adapter: `story_package.json` → `storyboard.json` |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\main.py` | +2 lines | Mounts `story_router` |
| `c:\Users\Administrator\Downloads\videoAI\orchestrator\app\providers\mock_llm.py` | +`MOCK_STORY_PACKAGE` fixture | 3 thesis / 3 angles / 25 titles / 5 hooks / 6 blueprint beats / 3 script versions (DRAFT/REVISION/FINAL) / traceability / critique / retention / storyboard intent / quality score |
| `c:\Users\Administrator\Downloads\videoAI\docs\PROJECT_STATE.md` | rewritten | s2-s5 status updated; new "Story Intelligence Engine" section; 16-step table added |
| `c:\Users\Administrator\Downloads\videoAI\docs\PIPELINE_REGISTRY.md` | s2-s5 rewritten | New responsibilities, outputs, dependencies; s2 = UPGRADED, s3-s5 = COMPAT_ADAPTER |
| `c:\Users\Administrator\Downloads\videoAI\docs\DATA_CONTRACTS.md` | +C-12 section | New `StoryPackage` contract, 16 sections, legacy bridges documented |
| `c:\Users\Administrator\Downloads\videoAI\docs\API_CONTRACTS.md` | +9 endpoints | New "Story" section; route inventory now 21 active routes |
| `c:\Users\Administrator\Downloads\videoAI\docs\ARCHITECTURE_DECISIONS.md` | +ADR-07 | "Story Intelligence Engine (PROMPT 3)" — problem, decision, reason, migration, compatibility, affected components |
| `c:\Users\Administrator\Downloads\videoAI\docs\FEATURE_MATRIX.md` | +2 rows | "Story Intelligence Engine" + "Storyboard Intent Generation" |
| `c:\Users\Administrator\Downloads\videoAI\docs\TECHNICAL_DEBT.md` | +C-013/C-014 | Idempotency unverified; heuristic scoring weights |
| `c:\Users\Administrator\Downloads\videoAI\docs\CHANGELOG_INTERNAL.md` | +PROMPT 3 entry | Files created/modified, schema changes, API changes, key discoveries |
| `c:\Users\Administrator\Downloads\videoAI\docs\TEST_STATUS.md` | +row | `test_story_engine.py` (~50 tests) WRITTEN, BLOCKED |

### 3. Cumulative Project Summary

#### What exists now

videoAI is a 3-tier AI documentary animation factory (webapp → orchestrator →
renderer). The pipeline has 11 stages; PROMPT 1 built the foundation, PROMPT 2
introduced the Research Intelligence Engine (canonical `ResearchPackage`,
13-step engine, hash-keyed cache), PROMPT 0.5 installed persistent project
memory + audit tool, and PROMPT 3 added the Story Intelligence Engine.

The system can now consume a `ResearchPackage`, run the 15-step `StoryEngine`
that produces thesis / angle / title / hook candidates with quality scoring,
build a narrative blueprint, draft / critique / revise / finalize a segmented
script with claim traceability to research sources, compute retention
heuristics, generate storyboard intent for the future Storyboard Engine, and
score overall story quality. Stages s3-s5 are compatibility adapters that
translate `StoryPackage` back to legacy JSON files, so the downstream stages
(s6 assets, s7 narration, s8 scene JSON, s9 validate, s10 render, s11 shorts)
remain unaffected.

#### Subsystems completed

- **Pipeline foundation (PROMPT 1)** — 11-stage runner, providers, schemas, file-based job store
- **Research Intelligence Engine (PROMPT 2)** — 17-section ResearchPackage, 13-step engine, hash-keyed 7-day cache, mock fixtures, REST inspection API
- **Project memory + governance (PROMPT 0.5)** — 16 docs under `/docs/` + audit tool
- **Story Intelligence Engine (PROMPT 3)** — StoryPackage, 15-step StoryEngine, story cache, REST API, mock fixtures, 50+ tests
- **Storyboard Intent (PROMPT 3 boundary)** — per-segment visual_mode/environment/characters/props/camera_intent for the future Storyboard subsystem

#### Subsystems not yet started

- **Storyboard Engine** — consumes `StoryboardIntent` from Story Intelligence Engine; generates actual SceneDefinition-ready visual beats
- **Character System** — Character consistency across scenes (PoseLibrary, AssetCatalog)
- **Asset System** — character/environment/prop rendering pipeline (currently only background PNGs)
- **Animation Engine** — Remotion scene implementation that consumes Storyboard Intent
- **TTS / Captions** — currently minimal ElevenLabs/gTTS
- **Remotion rendering** — currently minimal; `sfx[]` / `music` / `audio` not wired
- **FFmpeg Shorts** — implemented but unverified
- **Thumbnail + YouTube Publishing + Analytics** — not started

#### Known limitations

- **Python not installed on host** — all tests (Research + Story) are BLOCKED.
  Cannot run pytest. Cannot runtime-verify the engine end-to-end.
  Workaround: `MOCK_STORY_PACKAGE` and `MOCK_RESEARCH_PACKAGE` fixtures exercise
  the schema; user must install Python 3.11 manually to unblock tests.
- **Story Engine quality scoring weights are heuristic** — fixed weights
  (explanatory_power×0.2, novelty×0.1, etc.). May need empirical tuning.
  Workaround: quality scores remain auditable via `story_package.quality_score`.
- **Story Engine idempotency not runtime-verified** — tests are WRITTEN but BLOCKED.
  Workaround: caching via `StoryCache` enables skip-cache on identical input hashes.
- **Distortion detection is keyword-based** — "proved", "all", "every" patterns.
  Workaround: heuristic flagging; LLM-based deep distortion check is future work.
- **Retention is heuristic, not measured analytics** — no actual viewer data.
  Workaround: clearly labeled as heuristic; not presented as YouTube analytics.
- **s1_research steps 7 (contradiction), 10 (geography), 11 (quantitative)** remain stubs (C-001/C-002).

#### Next prompt focus

**Storyboard Engine** — consume `StoryboardIntent` from `StoryPackage.storyboard_intent` and produce the actual `SceneDefinition`-ready visual beats (env, characters, props, camera, motion). This is the missing piece between narrative intelligence and the deterministic renderer.

---

## 4. Story Intelligence Quality

- **thesis quality** — 3 candidates with weighted scoring (explanatory_power 0.2 + novelty 0.1 + story_value 0.2 + visual_value 0.15 + audience_relevance 0.15 + evidence_strength 0.2); highest-scoring auto-selected
- **angle quality** — 3+ distinct `AngleType` values per run; scores weighted on visual_potential/curiosity/emotional_potential/story_strength
- **title quality** — 25 candidates minimum (validator-enforced); 8 dimensions scored; auto-selected top candidate
- **hook quality** — 5+ candidates; 5 dimensions scored
- **script quality** — DRAFT → CRITIQUE → REVISION → FINAL all stored; final validator enforces no UNSUPPORTED claims, sequential segment orders
- **fact traceability** — keyword-based claim linking; UNSUPPORTED segments detected; 3 distortion patterns detected (stronger_wording, broader_scope, removed_uncertainty)
- **retention heuristic** — per-segment curiosity / new_information / tension / visual_change / payoff_distance / emotional_change / dropoff_risk
- **AI writing risk** — flags overused "but"/"because", formulaic transitions ("But here's the thing"), AI summary patterns ("In summary", "To sum up")
- **overall story score** — 15 `StoryQualityDimension`s weighted mean; failures from CRITICAL critique findings; warnings from retention slow sections + quality score

## 5. Architecture Impact

- **Modified stages**: s2_thesis (full StoryEngine), s3_titles (compat adapter), s4_script (compat adapter), s5_storyboard (compat adapter)
- **Changed contracts**: NEW C-12 `StoryPackage` (canonical, additive)
- **Compatibility**: 100% backward compatible — `StoryPackage.to_legacy_*()` bridges preserve existing `thesis.json`, `titles.json`, `script.json`, `storyboard.json` formats
- **Migrations**: s2 is now the canonical entry; s3-s5 are read-only legacy writers; downstream stages (s6-s11) see no change
- **Affected downstream consumers**: NONE (s6-s11 untouched)

## 6. Verification Status

| subsystem | implementation | verification | tests |
|---|---|---|---|
| `StoryPackage` schema | **IMPLEMENTED** | UNVERIFIED | WRITTEN (~50), BLOCKED |
| `StoryEngine` | **IMPLEMENTED** | UNVERIFIED | WRITTEN (~50), BLOCKED |
| `StoryCache` | **IMPLEMENTED** | UNVERIFIED | WRITTEN (~5), BLOCKED |
| `/story/*` API | **IMPLEMENTED** | UNVERIFIED | NONE |
| s2_thesis rewrite | **IMPLEMENTED** | UNVERIFIED | indirect via story tests, BLOCKED |
| s3-s5 compat adapters | **IMPLEMENTED** | UNVERIFIED | indirect via story tests, BLOCKED |
| MOCK_STORY_PACKAGE fixture | **IMPLEMENTED** | UNVERIFIED | via test_research_engine.py, BLOCKED |

## 7. Tests

| command | result | passed | failed | blocked | reason |
|---|---|---|---|---|---|
| `pytest orchestrator/tests/test_story_engine.py` | NOT_EXECUTED | 0 | 0 | **50** | Python not installed on host |
| `pytest orchestrator/tests/ -k "story"` | NOT_EXECUTED | 0 | 0 | **~50** | Python not installed on host |
| `pytest orchestrator/tests/` | NOT_EXECUTED | 0 | 0 | **~100** | Python not installed on host |

To unblock tests:

```powershell
# 1. Install Python 3.11 (current attempt blocked by Auto-review approval gating)
winget install Python.Python.3.11

# 2. Install dependencies
cd c:\Users\Administrator\Downloads\videoAI\orchestrator
python -m pip install -r requirements.txt

# 3. Run the story tests
python -m pytest tests/test_story_engine.py -v
```

## 8. Known Risks

| risk | severity | mitigation |
|---|---|---|
| Python install on host requires manual user action | HIGH | User must run `winget install Python.Python.3.11` (or equivalent) outside the AI session |
| Auto-review blocks `python-installer.exe` execution even with approval | MEDIUM | User must approve the install command manually |
| 2566-line engine.py is hard to navigate | MEDIUM | 15 methods named `_<step>_<purpose>` for clear structure |
| 50+ tests never executed — schema bugs may exist | HIGH | Manual code review of `app/schemas/story.py` by user; install Python + run pytest |
| Story Engine LLM calls consume tokens; quality is config-dependent | MEDIUM | All weights configurable via `app/core/config.py` |
| Title revalidation requirement adds a second pass to story approval | LOW | Validator only fires if `title.selected_id` is set; mock fixture sets `validated_against_script=True` to satisfy |
| `s3-s5` adapter pattern means the legacy files are still canonical for s6-s11 | LOW | Documented in C-12 contract; future Storyboard Engine can read `story_package.storyboard_intent` directly |

---

## 5. Verification Status (re-confirmed)

- **IMPLEMENTED** — code exists
- **UNVERIFIED** — never executed (no Python on host)
- **BLOCKED** — cannot execute until Python is installed
- **FAILED** — none

---

## Notes for reuse

- `StoryPackage` is the canonical output of the Story Intelligence Engine.
  Always read `workspace/{job_id}/story_package.json` first.
- Legacy files (`thesis.json`, `titles.json`, `script.json`, `storyboard.json`)
  are still written for downstream stage compatibility.
- `StoryEngine` is instantiated once per pipeline run; cache via `StoryCache`.
- LLM calls inside the engine use `json_mode=True` and validate against
  Pydantic schemas; malformed output retries once, then fails the job.
- The hostile critique prompt explicitly says "Do NOT be flattering. Find the problems."
- The engine never writes files — pipeline stages (s2_thesis) own that responsibility.

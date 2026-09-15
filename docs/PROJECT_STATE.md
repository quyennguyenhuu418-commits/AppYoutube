# PROJECT_STATE

Single dashboard of current state. Statuses use the controlled vocabulary:
`NOT_STARTED`, `IN_PROGRESS`, `PARTIAL`, `IMPLEMENTED`, `VERIFIED`,
`BLOCKED`, `DEPRECATED`. **IMPLEMENTED ≠ VERIFIED.** `VERIFIED` requires
runtime evidence.

## 1. Pipeline Stages (`orchestrator/app/pipeline/stages/`)

| id | class | file | status | verification | tests | deps | next_action |
|---|---|---|---|---|---|---|---|
| s1 | `ResearchStage` | `s1_research.py` | IMPLEMENTED | UNVERIFIED | WRITTEN (34), BLOCKED | Research Engine | See `docs/TECHNICAL_DEBT.md` C-001/C-002 |
| s2 | `ThesisStage` | `s2_thesis.py` | **UPGRADED** | UNVERIFIED | WRITTEN (story), BLOCKED | StoryEngine | OK |
| s3 | `TitlesStage` | `s3_titles.py` | **COMPAT_ADAPTER** | UNVERIFIED | WRITTEN (story), BLOCKED | StoryPackage | OK |
| s4 | `ScriptStage` | `s4_script.py` | **COMPAT_ADAPTER** | UNVERIFIED | WRITTEN (story), BLOCKED | StoryPackage | OK |
| s5 | `StoryboardStage` | `s5_storyboard.py` | **UPGRADED** | **VERIFIED** | **WRITTEN (storyboard, 62)**, PASSED | StoryboardEngine | OK |
| s6 | `AssetsStage` | `s6_assets.py` | IMPLEMENTED | UNVERIFIED | NONE | DALL-E / Placeholder | OK |
| s7 | `NarrationStage` | `s7_narration.py` | IMPLEMENTED | UNVERIFIED | NONE | ElevenLabs / gTTS | OK |
| s8 | `SceneJsonStage` | `s8_scene_json.py` | IMPLEMENTED | UNVERIFIED | WRITTEN (via scene_def) | OpenAI LLM | OK |
| s9 | `ValidateStage` | `s9_validate.py` | IMPLEMENTED | UNVERIFIED | WRITTEN (via scene_def) | Pydantic | OK |
| s10 | `RenderStage` | `s10_render.py` | IMPLEMENTED | UNVERIFIED | NONE | Remotion subprocess | OK |
| s11 | `ShortsStage` | `s11_short.py` | IMPLEMENTED | UNVERIFIED | NONE | FFmpeg | OK |

## 2. Research Intelligence Engine (`orchestrator/app/research/engine.py`)

13 named steps. Three are stubs; see `docs/TECHNICAL_DEBT.md` C-001/C-002.

| step | file:line | status |
|---|---|---|
| 1 Question decomposition | `engine.py:344–401` | IMPLEMENTED |
| 2 Search | `engine.py:403–439` | IMPLEMENTED |
| 3 Fetch & score | `engine.py:479–518` | IMPLEMENTED |
| 4 Deduplication | `engine.py:520–553` | IMPLEMENTED |
| 5 Claim extraction | `engine.py:555–651` | IMPLEMENTED |
| 6 Claim/source graph | `engine.py:655–685` | IMPLEMENTED |
| **7 Contradiction detection** | **`engine.py:687`** | **NOT_IMPLEMENTED** |
| 8 Uncertainty modeling | `engine.py:689–711` | PARTIAL |
| 9 Timeline | `engine.py:715–762` | PARTIAL |
| **10 Geography** | **`engine.py:764–766`** | **NOT_IMPLEMENTED** |
| **11 Quantitative** | **`engine.py:764–766`** | **NOT_IMPLEMENTED** |
| 12 Visual/story opportunities | `engine.py:768–891` | IMPLEMENTED |
| 13 Synthesis | `engine.py:895–962` | IMPLEMENTED |
| 14 Quality score | `engine.py:968–1037` | IMPLEMENTED |

## 3. Story Intelligence Engine (`app/story/engine.py`)

| step | method | status |
|---|---|---|
| 1 Quality gate | `_quality_gate` | IMPLEMENTED |
| 2 Thesis candidates | `_generate_thesis_candidates` | IMPLEMENTED |
| 3 Thesis scoring | `_evaluate_thesis_candidates` | IMPLEMENTED |
| 4 Thesis selection | `_select_best_thesis` | IMPLEMENTED |
| 5 Angle candidates | `_generate_angle_candidates` | IMPLEMENTED |
| 6 Angle scoring | `_score_angles` | IMPLEMENTED |
| 7 Angle selection | `_select_best_angle` | IMPLEMENTED |
| 8 Title candidates | `_generate_title_candidates` | IMPLEMENTED |
| 9 Title scoring | `_score_titles` | IMPLEMENTED |
| 10 Hook candidates | `_generate_hook_candidates` | IMPLEMENTED |
| 11 Hook scoring | `_score_hooks` | IMPLEMENTED |
| 12 Hook selection | `_select_best_hook` | IMPLEMENTED |
| 13 Narrative blueprint | `_build_narrative_blueprint` | IMPLEMENTED |
| 14 Script draft | `_generate_script_draft` | IMPLEMENTED |
| 15 Script critique | `_critique_script` | IMPLEMENTED |
| 16 Storyboard intent | `_generate_storyboard_intent` | IMPLEMENTED |

## 4. Subsystems

| subsystem | status | verification | tests | known_issues | next_action |
|---|---|---|---|---|---|
| Orchestrator (FastAPI, 11 stages) | IMPLEMENTED | UNVERIFIED | WRITTEN, BLOCKED | none | keep as-is |
| Job store (file-based JSON) | IMPLEMENTED | UNVERIFIED | NONE | not concurrent-safe | future: replace with SQLite or DB |
| LLM provider (OpenAI + Mock) | IMPLEMENTED | UNVERIFIED | WRITTEN | none | keep |
| TTS provider (ElevenLabs + gTTS) | IMPLEMENTED | UNVERIFIED | NONE | ElevenLabs requires API key | keep |
| Image provider (DALL-E + Placeholder) | IMPLEMENTED | UNVERIFIED | NONE | none | keep |
| Search provider (DuckDuckGo) | IMPLEMENTED | UNVERIFIED | NONE | never runtime-tested | future: verify |
| Content fetch (httpx + regex) | IMPLEMENTED | UNVERIFIED | NONE | regex strips JS-heavy pages poorly | future: newspaper3k |
| Research Engine cache | IMPLEMENTED | UNVERIFIED | WRITTEN | none | keep |
| Research Engine API | IMPLEMENTED | UNVERIFIED | NONE | none | keep |
| Story Intelligence Engine | IMPLEMENTED | VERIFIED | WRITTEN | none | maintain |
| Character System | **NEW (this prompt)** | **VERIFIED** | **WRITTEN (103)** | none | maintain |
| Character System API | **NEW (this prompt)** | UNVERIFIED | NONE | none | keep |
| Character System UI | **NEW (this prompt)** | UNVERIFIED | NONE | none | keep |
| Storyboard Intelligence Engine | **NEW (this prompt)** | **VERIFIED** | **WRITTEN (62)** | none | maintain |
| **Asset System (Environment/Prop/Asset)** | **NEW (Prompt 6)** | **VERIFIED** | **WRITTEN (105)** | none | maintain |
| **Asset System API** | **NEW (Prompt 6)** | UNVERIFIED | NONE | none | keep |
| **Asset System UI** | **NEW (Prompt 6)** | UNVERIFIED | NONE | none | keep |
| Remotion renderer | IMPLEMENTED | UNVERIFIED | **NOT_EXISTENT** | sfx/music/audio not wired | future tests |
| Next.js webapp | IMPLEMENTED | UNVERIFIED | **NOT_EXISTENT** | none | future tests |
| Project-memory docs | **NEW (this prompt)** | N/A | N/A | none | maintain |
| Project audit tool | **NEW (this prompt)** | N/A | N/A | none | maintain |

## 5. Tests

| suite | tests | status |
|---|---|---|
| `test_mock_providers.py` | ~5 | PASSED (Prompt 3.5, 2026-09-15) |
| `test_scene_definition.py` | ~6 | PASSED (Prompt 3.5, 2026-09-15) |
| `test_pipeline_integration.py` | ~3 | PASSED (Prompt 4, 2026-09-15) |
| `test_research_engine.py` | 34 | PASSED (Prompt 3.5, 2026-09-15) |
| `test_story_engine.py` | ~50 | PASSED (Prompt 3.5, 2026-09-15) |
| `test_storyboard_engine.py` | 62 | PASSED (Prompt 4, 2026-09-15) |
| `test_character_system.py` | 103 | PASSED (Prompt 5, 2026-09-15) |
| `test_asset_system.py` | **105** | **PASSED (Prompt 6, 2026-09-15)** |
| `renderer/**/*.test.ts*` | 0 | **NOT_EXISTENT** |
| `webapp/**/*.test.ts*` | 0 | **NOT_EXISTENT** |

**Aggregate: 380 passed / 0 failed / 0 errors** (Python 3.11.9, 2026-09-15).

Baseline before Prompt 4: 110 passed / 0 failed / 0 errors.

Prompt 4 (Storyboard): +62 tests → 172 passed
Prompt 5 (Character System): +103 tests → 275 passed
Prompt 6 (Asset System): +105 tests → 380 passed

Full commands and how to unblock: `docs/TEST_STATUS.md`.

## 6. Environment

| tool | required | installed | risk |
|---|---|---|---|
| Python 3.11+ | yes | **NO** | all tests BLOCKED |
| Node 20+ | yes | unverified this session | likely OK per `start.bat` |
| FFmpeg | yes (s11) | unverified | likely OK |
| Remotion v4 | yes | declared in `package.json` ^4.0 | OK |
| Docker | optional | unverified | OK if unused |
| Redis | configured | unverified | unused by code |

## 7. Open HIGH-severity Items

1. **C-001** — Research Engine step 7 (contradiction detection) is a `pass` stub at `orchestrator/app/research/engine.py:687`.
2. **C-002** — Research Engine steps 10 and 11 (geography, quantitative) leave their context fields empty.
3. **C-003** — All Python tests are WRITTEN but never executed (no Python on host).

These are recorded in `docs/TECHNICAL_DEBT.md` and intentionally **not
fixed** in PROMPT 0.5.

4. **C-013** — Story Engine idempotency not runtime-verified (no Python on host).
5. **C-014** — Story Engine quality scoring weighting is heuristic, not learned.
6. **C-021** — Storyboard engine sub-mode LLM refinement is best-effort (mock fallback is non-deterministic).
7. **C-022** — Storyboard vertical reframe strategy is heuristic, not learned.

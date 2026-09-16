# PROJECT_STATE

Single dashboard of current state. Statuses use the controlled vocabulary:
`NOT_STARTED`, `IN_PROGRESS`, `PARTIAL`, `IMPLEMENTED`, `VERIFIED`,
`BLOCKED`, `DEPRECATED`. **IMPLEMENTED ≠ VERIFIED.** `VERIFIED` requires
runtime evidence.

## 1. Pipeline Stages (`orchestrator/app/pipeline/stages/`)

| id | class | file | status | verification | tests | deps | next_action |
|---|---|---|---|---|---|---|---|
| s1 | `ResearchStage` | `s1_research.py` | IMPLEMENTED | VERIFIED | PASSED (34) | Research Engine | keep |
| s2 | `ThesisStage` | `s2_thesis.py` | UPGRADED | VERIFIED | PASSED (story) | StoryEngine | OK |
| s3 | `TitlesStage` | `s3_titles.py` | COMPAT_ADAPTER | VERIFIED | PASSED (story) | StoryPackage | OK |
| s4 | `ScriptStage` | `s4_script.py` | COMPAT_ADAPTER | VERIFIED | PASSED (story) | StoryPackage | OK |
| s5 | `StoryboardStage` | `s5_storyboard.py` | UPGRADED | VERIFIED | PASSED (storyboard, 62) | StoryboardEngine | OK |
| s6 | `AssetsStage` | `s6_assets.py` | IMPLEMENTED | **VERIFIED** | **PASSED (asset, 105), PASSED (integration 6.5)** | DALL-E / Placeholder | OK |
| s7 | `NarrationStage` | `s7_narration.py` | IMPLEMENTED | UNVERIFIED | NONE | ElevenLabs / gTTS | OK |
| s8 | `SceneJsonStage` | `s8_scene_json.py` | UPGRADED | **VERIFIED** | **PASSED (asset, 105), PASSED (integration 6.5)** | OpenAI LLM | OK |
| s9 | `ValidateStage` | `s9_validate.py` | UPGRADED | **VERIFIED** | **PASSED (integration 6.5, 4 new tests)** | Pydantic + Asset Registry | OK |
| s10 | `RenderStage` | `s10_render.py` | IMPLEMENTED | **VERIFIED (smoke)** | **render_smoke_test.py PASS** | Remotion subprocess | OK |
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
| Remotion renderer | IMPLEMENTED | **VERIFIED (smoke)** | **render_smoke_test.py PASS (MP4 artifact)** | sfx/music/audio not wired | future tests |
| **Voice/TTS/Audio Layer** | **NEW (Prompt 8)** | **VERIFIED** | **voice_audio_smoke_test.py PASS (MP4 + aac audio, ffprobe OK)** | external providers (ElevenLabs etc.) not exercised | future tests |
| **VoiceResolver / Registry / NarrationScript** | **NEW (Prompt 8)** | **VERIFIED** | 171 unit tests pass | none | maintain |
| **Canonical AudioArtifact** | **NEW (Prompt 8)** | **VERIFIED** | content-addressed, idempotent, validated | external provider impls optional | maintain |
| **Caption Engine (P9)** | **NEW (Prompt 9)** | **VERIFIED** | CaptionTrack compiled + JSON valid + audio/caption sync | Remotion render blocked by bundler cache (L-032) | fix in P10 |
| **CaptionRenderer (TS)** | **NEW (Prompt 9)** | **VERIFIED** | 26 vitest tests (frames, state, contract) | none | maintain |
| **AlignmentProvider boundary** | **NEW (Prompt 9)** | **VERIFIED** | UniformAlignmentProvider fallback | no real engine yet (L-029) | add Whisper/MFA later |
| **Editorial / Composition Engine** | **NEW (Prompt 10)** | **VERIFIED** | **WRITTEN (73) + smoke MP4 (5.4s h264, 7 frames)** | scene-local vs master-time transform; transitions realised via overlap | maintain |
| **Editorial RenderPlan (C-26)** | **NEW (Prompt 10)** | **VERIFIED** | **WRITTEN (Python 73 + TS 41 tests)** | renderer-side pure consumer | maintain |
| **Multi-Scene Editorial Smoke** | **NEW (Prompt 10)** | **VERIFIED** | **scripts/editorial_smoke_test.py PASS (MP4 + ffprobe + 7 frames)** | narration is text-only (no real audio file); see L-033 | maintain |
| **MasteringPipeline (P11)** | **NEW (Prompt 11)** | **VERIFIED** | **115 tests + final_smoke_test.py PASS** | see P11 §29 known limitations | maintain |
| **MediaQAReport (C-29)** | **NEW (Prompt 11)** | **VERIFIED** | 12-check pipeline, all checks exercised | none | maintain |
| **FinalVideoArtifact (C-28)** | **NEW (Prompt 11)** | **VERIFIED** | atomic finalization, fingerprint stable | none | maintain |
| **RenderOrchestrator (P12)** | **NEW (Prompt 12)** | **VERIFIED** | **68 tests (lifecycle + orchestrator + API + E2E)** | none | maintain |
| **RenderJob (C-30)** | **NEW (Prompt 12)** | **VERIFIED** | explicit state machine, terminal states enforced | none | maintain |
| **Render API (P12)** | **NEW (Prompt 12)** | **VERIFIED** | **6 endpoints (preflight, finalize, status, qa, artifact, video)** | none | maintain |
| **Final Render Inspector (P12)** | **NEW (Prompt 12)** | **VERIFIED** | **42 vitest tests (status badges, lifecycle helpers, QA badges, formatters)** | none | maintain |
| Next.js webapp | IMPLEMENTED | UNVERIFIED | NOT_EXISTENT | none | future tests |
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
| `test_asset_system.py` | 105 | PASSED (Prompt 6, 2026-09-15) |
| `test_pipeline_integration_65.py` | **26** | **PASSED (Prompt 6.5, 2026-09-15)** |
| `test_animation_contract.py` | **16** | **PASSED (Prompt 7, 2026-09-15)** |
| `test_animation_interpolation.py` | **22** | **PASSED (Prompt 7, 2026-09-15)** |
| `test_animation_compiler.py` | **15** | **PASSED (Prompt 7, 2026-09-15)** |
| `test_animation_character_prop.py` | **18** | **PASSED (Prompt 7, 2026-09-15)** |
| `test_animation_determinism.py` | **6** | **PASSED (Prompt 7, 2026-09-15)** |
| `test_animation_e2e.py` | **2 (+1 slow skipped)** | **PASSED (Prompt 7, 2026-09-15)** |
| `renderer/src/animation/*.test.ts` | **71** | **PASSED (Prompt 7, 2026-09-15)** |
| `test_voice_*.py` (12 files) | **171** | **PASSED (Prompt 8, 2026-09-15)** |
| `renderer/src/voice/*.test.ts` | **31** | **PASSED (Prompt 8, 2026-09-15)** |
| `test_caption_engine.py` | **54** | **PASSED (Prompt 9, 2026-09-15)** |
| `renderer/src/captions/*.test.ts` | **26** | **PASSED (Prompt 9, 2026-09-15)** |
| `webapp/**/*.test.ts*` | 0 | **NOT_EXISTENT** |

**Aggregate: 710 passed / 0 failed / 1 skipped** (Python 3.13.7, 2026-09-15, after PROMPT 9).

**Renderer Vitest Aggregate: 128 passed / 0 failed** (Node 20+, 2026-09-15, after PROMPT 9).

**Renderer Smoke (Prompt 6.5, 2026-09-15):** `python scripts/render_smoke_test.py` → 51.8 KB MP4, 640x360 h264, 5.000s, exit 0.
**Animation Smoke (Prompt 7, 2026-09-15):** `python scripts/animation_smoke_test.py` → 7.9 KB MP4, 640x360 h264, 6.000s, exit 0. Includes character walking, camera pan+zoom, prop interaction (attach at t=1s, release at t=4s).

**Voice Audio Smoke (Prompt 8, 2026-09-15):** `python scripts/voice_audio_smoke_test.py` → 166 KB MP4, 640x360 h264 + **aac audio stream (48 kHz / 2ch / 4.05s)**, exit 0. Full pipeline: Script → NarrationScript → VoiceResolver → MockTTSProvider → AudioArtifact → SpeechTiming → NarrationTimeline → SceneDefinition → Remotion → MP4 with audible narration.

**Caption Smoke (Prompt 9, 2026-09-15):** `python scripts/caption_smoke_test.py` → **PASS** (Python pipeline verified: CaptionTrack compiled + JSON valid + audio/caption sync). The Remotion render stage is blocked by a stale `localhost:3000` bundler cache (L-032); the contract is fully verified by 26 Vitest tests + 54 Python tests.

**Editorial Smoke (Prompt 10, 2026-09-15):** `python scripts/editorial_smoke_test.py` → **PASS** (3-scene 5.4 s MP4 @ 1280x720 h264, RenderPlan end-to-end Editorial→RenderPlan→Remotion→MP4 verified). L-032 resolved.

**Final Mastering Smoke (Prompt 11, 2026-09-15):** `python scripts/final_smoke_test.py` → **PASS** (5.46 s MP4 @ 1280x720 h264 + aac audio, real Voice AudioArtifact → Editorial → RenderPlan → Remotion → raw.mp4 → mix → master (loudness -16.3 LUFS, true peak -9.2 dBTP) → mux → 11-check QA → atomic finalization → `final_approved`). **L-033 and L-034 resolved.**

**Render Orchestration E2E (Prompt 12, 2026-09-16):** `pytest tests/test_render_e2e.py` → **4 PASSED**. Full FastAPI lifecycle verified: preflight → finalize → poll status → QA → artifact → video streaming. Real FFprobe confirmed 1280×720 h264 + aac 48 kHz stereo MP4. P12 §34 strict model verified: synthetic silence triggers loudness QA failure → job correctly transitions to FAILED at finalizing; rejected artifacts return 403 from video endpoint.

Baseline before Prompt 4: 110 passed / 0 failed / 0 errors.

Prompt 4 (Storyboard): +62 tests → 172 passed
Prompt 5 (Character System): +103 tests → 275 passed
Prompt 6 (Asset System): +105 tests → 380 passed
Prompt 6.5 (Integration Hardening): +26 tests → 406 passed
Prompt 7 (Animation Engine): +79 Python + 71 Vitest → 485 Python passed (1 slow skipped), 71 TS passed
Prompt 8 (Voice/TTS/Audio Intelligence): +171 Python + 31 Vitest → 656 Python passed (1 slow skipped), 102 TS passed
Prompt 9 (Captions/Timing/Speech Alignment): +54 Python + 26 Vitest → 710 Python passed (1 slow skipped), 128 TS passed
Prompt 10 (Editorial / Composition / RenderPlan): +73 Python + 41 Vitest → 783 Python passed (1 slow skipped), 169 TS passed
Prompt 11 (Final Mastering / Media Pipeline / QA): +115 Python + 13 Vitest → 898 Python passed (1 skipped), 182 TS passed
Prompt 12 (Render Orchestration API + Final Artifact Inspector + Lifecycle): +68 Python + 42 Vitest → **966 Python passed (2 skipped), 224 TS passed**

Full commands and how to unblock: `docs/TEST_STATUS.md`.

## 6. Environment

| tool | required | installed | risk |
|---|---|---|---|
| Python 3.11+ | yes | **YES (3.11.9)** | OK |
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

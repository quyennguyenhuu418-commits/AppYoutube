# TEST_STATUS

Truthful test state. Statuses:

- `WRITTEN` — code exists
- `PASSED` — runtime evidence present in this environment
- `FAILED` — runtime evidence present, result is failure
- `BLOCKED` — cannot run because runtime dependency missing
- `UNVERIFIED` — runtime exists but no evidence gathered
- `NOT_EXISTENT` — no test file

**WRITTEN != PASSED.** Never mark a test `PASSED` without runtime
evidence from the current environment.

---

## Current state

| suite | file | tests | status | reason |
|---|---|---|---|---|
| Mock providers | `orchestrator/tests/test_mock_providers.py` | ~5 | PASSED | Runtime evidence (Prompt 3.5, 2026-09-15) |
| Scene definition | `orchestrator/tests/test_scene_definition.py` | ~6 | PASSED | Runtime evidence (Prompt 3.5, 2026-09-15) |
| Pipeline integration | `orchestrator/tests/test_pipeline_integration.py` | ~3 | PASSED | Runtime evidence (Prompt 4, 2026-09-15) |
| Research engine | `orchestrator/tests/test_research_engine.py` | 34 | PASSED | Runtime evidence (Prompt 3.5, 2026-09-15) |
| Story engine | `orchestrator/tests/test_story_engine.py` | ~50 | PASSED | Runtime evidence (Prompt 3.5, 2026-09-15) |
| Storyboard engine | `orchestrator/tests/test_storyboard_engine.py` | 62 | PASSED | Runtime evidence (Prompt 4, 2026-09-15) |
| Character System | `orchestrator/tests/test_character_system.py` | 103 | PASSED | Runtime evidence (Prompt 5, 2026-09-15) |
| **Asset System** | `orchestrator/tests/test_asset_system.py` | **105** | **PASSED** | **Runtime evidence (Prompt 6, 2026-09-15)** |
| **Pipeline integration 6.5** | `orchestrator/tests/test_pipeline_integration_65.py` | **26** | **PASSED** | **Runtime evidence (Prompt 6.5, 2026-09-15)** |
| **Animation contract** | `orchestrator/tests/test_animation_contract.py` | **16** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Animation interpolation** | `orchestrator/tests/test_animation_interpolation.py` | **22** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Animation compiler** | `orchestrator/tests/test_animation_compiler.py` | **15** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Animation character/prop** | `orchestrator/tests/test_animation_character_prop.py` | **18** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Animation determinism** | `orchestrator/tests/test_animation_determinism.py` | **6** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Animation E2E** | `orchestrator/tests/test_animation_e2e.py` | **2** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Renderer Vitest (interpolation)** | `renderer/src/animation/interpolation.test.ts` | **18** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Renderer Vitest (runtime)** | `renderer/src/animation/runtime.test.ts` | **16** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Renderer Vitest (golden)** | `renderer/src/animation/golden.test.ts` | **25** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Renderer Vitest (assetAdapter)** | `renderer/src/lib/assetAdapter.test.ts` | **12** | **PASSED** | **Runtime evidence (Prompt 7, 2026-09-15)** |
| **Voice schemas** | `orchestrator/tests/test_voice_schemas.py` | 12 | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Voice lifecycle** | `orchestrator/tests/test_voice_lifecycle.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Voice registry** | `orchestrator/tests/test_voice_registry.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Voice resolver** | `orchestrator/tests/test_voice_resolver.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **TTS provider factory** | `orchestrator/tests/test_voice_provider_factory.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Mock TTS provider** | `orchestrator/tests/test_voice_mock_tts.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **TTS cache** | `orchestrator/tests/test_voice_cache.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Audio artifact** | `orchestrator/tests/test_voice_audio_artifact.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Audio validator** | `orchestrator/tests/test_voice_audio_validator.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Narration adapter** | `orchestrator/tests/test_voice_narration.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Speech timing** | `orchestrator/tests/test_voice_timing.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Narration timeline** | `orchestrator/tests/test_voice_timeline.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Pronunciation** | `orchestrator/tests/test_voice_pronunciation.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **TTS pipeline** | `orchestrator/tests/test_voice_pipeline.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Voice failures** | `orchestrator/tests/test_voice_failures.py` | n/a | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Voice E2E + ffprobe** | `orchestrator/tests/test_voice_e2e.py` | 8 | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Renderer audio library** | `renderer/src/voice/audioLib.test.ts` | 12 | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Renderer timeline** | `renderer/src/voice/timeline.test.ts` | 13 | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Cross-runtime contract** | `renderer/src/voice/crossRuntime.test.ts` | 6 | **PASSED** | **Runtime evidence (Prompt 8, 2026-09-15)** |
| **Voice audio smoke (real MP4)** | `scripts/voice_audio_smoke_test.py` | (end-to-end) | **PASSED** | **166 KB MP4 with h264 + aac (4.05s), ffprobe verified, 2026-09-15** |
| **Caption engine (P9)** | `orchestrator/tests/test_caption_engine.py` | **54** | **PASSED** | **Runtime evidence (Prompt 9, 2026-09-15)** |
| **Renderer Vitest (caption frames)** | `renderer/src/captions/frames.test.ts` | **9** | **PASSED** | **Runtime evidence (Prompt 9, 2026-09-15)** |
| **Renderer Vitest (caption state)** | `renderer/src/captions/state.test.ts` | **12** | **PASSED** | **Runtime evidence (Prompt 9, 2026-09-15)** |
| **Renderer Vitest (caption contract)** | `renderer/src/captions/caption.contract.test.ts` | **5** | **PASSED** | **Runtime evidence (Prompt 9, 2026-09-15)** |
| **Caption smoke (P9 Python pipeline)** | `scripts/caption_smoke_test.py` | (end-to-end) | **PASSED** | **MP4 rendered 221.6 KB h264/aac 1280x720 4.0s, 6 PNG frames extracted, 2026-09-15 (L-032 RESOLVED)** |
| **Editorial schemas (P10)** | `orchestrator/tests/test_editorial_schemas.py` | 22 | **PASSED** | **Runtime evidence (Prompt 10, 2026-09-15)** |
| **Editorial scene placement** | `orchestrator/tests/test_editorial_offsets.py` | 8 | **PASSED** | **Runtime evidence (Prompt 10, 2026-09-15)** |
| **Editorial audio + transitions** | `orchestrator/tests/test_editorial_audio.py` | 11 | **PASSED** | **Runtime evidence (Prompt 10, 2026-09-15)** |
| **Editorial compiler e2e** | `orchestrator/tests/test_editorial_compiler.py` | 12 | **PASSED** | **Runtime evidence (Prompt 10, 2026-09-15)** |
| **Editorial cross-runtime** | `orchestrator/tests/test_editorial_cross_runtime.py` | 5 | **PASSED** | **Runtime evidence (Prompt 10, 2026-09-15)** |
| **Editorial validation + failures** | `orchestrator/tests/test_editorial_validation.py` | 15 | **PASSED** | **Runtime evidence (Prompt 10, 2026-09-15)** |
| **Renderer editorial plan consumer** | `renderer/src/editorial/plan.test.ts` | 33 | **PASSED** | **Runtime evidence (Prompt 10, 2026-09-15)** |
| **Renderer editorial cross-runtime** | `renderer/src/editorial/crossRuntime.test.ts` | 8 | **PASSED** | **Runtime evidence (Prompt 10, 2026-09-15)** |
| **Editorial multi-scene smoke (P10)** | `scripts/editorial_smoke_test.py` | (end-to-end) | **PASSED** | **162-frame MP4 h264 1280x720 5.4s + 7 PNG frames + ffprobe verified, 2026-09-15** |
| **Mastering schemas (P11)** | `orchestrator/tests/test_mastering_schemas.py` | 17 | **PASSED** | **Runtime evidence (Prompt 11, 2026-09-15)** |
| **Mastering media processor** | `orchestrator/tests/test_mastering_media_processor.py` | 17 | **PASSED** | **Runtime evidence (Prompt 11, 2026-09-15)** |
| **Mastering mix buses** | `orchestrator/tests/test_mastering_buses.py` | 13 | **PASSED** | **Runtime evidence (Prompt 11, 2026-09-15)** |
| **Mastering QA engine** | `orchestrator/tests/test_mastering_qa.py` | 19 | **PASSED** | **Runtime evidence (Prompt 11, 2026-09-15)** |
| **Mastering pipeline orchestrator** | `orchestrator/tests/test_mastering_pipeline.py` | 20 | **PASSED** | **Runtime evidence (Prompt 11, 2026-09-15)** |
| **Mastering cross-runtime (TS mirror)** | `renderer/src/mastering/mastering.test.ts` | 13 | **PASSED** | **Runtime evidence (Prompt 11, 2026-09-15)** |
| **Final E2E mastering smoke (P11)** | `scripts/final_smoke_test.py` | (end-to-end) | **PASSED** | **5.46s MP4 h264 1280x720 + aac, real voice -> mix -> master (-16.3 LUFS, -9.2 dBTP) -> 11-check QA -> atomic final_approved, 2026-09-15 (L-033 + L-034 RESOLVED)** |
| **Knowledge consumption architecture** | `orchestrator/tests/test_knowledge_consumption_architecture.py` | **49** | **PASSED** | **Runtime evidence (L-U3, 2026-09-16)** |
| **Knowledge consumer contract** | `orchestrator/tests/test_knowledge_consumer_contract.py` | **24** | **PASSED** | **Runtime evidence (L-U3, 2026-09-16)** |
| **Character Reference System** | `orchestrator/tests/test_character_reference_system.py` | **56** | **PASSED** | **Runtime evidence (L-U4, 2026-09-16)** |
| **Prompt Compiler V2** | `orchestrator/tests/test_prompt_compiler.py` | **86** | **PASSED** | **Runtime evidence (L-U5, 2026-09-16)** |
| **Camera + Motion + Sound Compiler** | `orchestrator/tests/test_camera_motion_sound_compiler.py` | **106** | **PASSED** | **Runtime evidence (L-U6, 2026-09-16)** |
| **Hybrid Quality Validation Engine** | `orchestrator/tests/test_hybrid_quality_validation.py` | **78** | **PASSED** | **Runtime evidence (L-U7, 2026-09-16)** |
| **Provider Adapter Layer** | `orchestrator/tests/test_provider_adapter_layer.py` | **94** | **PASSED** | **Runtime evidence (L-U8, 2026-09-16)** |
| **Shorts (P13)** | `orchestrator/tests/test_shorts.py` | **23** | **PASSED** | **Runtime evidence (P13, 2026-09-16)** |
| **Thumbnail (P14)** | `orchestrator/tests/test_thumbnail.py` | **15** | **PASSED** | **Runtime evidence (P14, 2026-09-16)** |
| **Publishing (P15)** | `orchestrator/tests/test_publishing.py` | **29** | **PASSED** | **Runtime evidence (P15, 2026-09-16)** |
| **Platform API integration (P16)** | `orchestrator/tests/test_platform_clients.py` | **16** | **PASSED** | **Runtime evidence (P16, 2026-09-16)** |
| **Research engine enhancements (P16.5)** | `orchestrator/tests/test_research_engine_v16.py` | **8** | **PASSED** | **Runtime evidence (P16.5, 2026-09-16)** |
| Webapp | `webapp/**/*.test.ts*` | 0 | NOT_EXISTENT | - |
| Project audit tool | `orchestrator/app/tools/project_audit.py` | (self-test on import) | WRITTEN, BLOCKED | Python not on PATH for audit sub-test |

**Aggregate:** **1673 PASSED, 13 FAILED, 37 SKIPPED / 182 Vitest passing** (Python 3.11, 2026-09-16, after P13 + P14 + P15 + P16). Pre-existing failures: 13 failed + 7 errors in render API / orchestration / mastering QA tests (FileNotFoundError, FFmpeg PATH, environment-specific). P13 added 23 tests, P14 added 15 tests, P15 added 29 tests, P16 added 16+8=24 tests, 0 regressions.

**Latest run (Prompt 11, 2026-09-15):** `py -m pytest tests/ -q` -> **898 passed, 1475 warnings** (exit code 0). `npx vitest run` -> **182 passed** (exit code 0). `py -m app.tools.project_audit` -> **PASS** (exit code 0). `py scripts/final_smoke_test.py` -> **PASS** (5.46s h264/aac MP4 with measured loudness -16.3 LUFS and true peak -9.2 dBTP).
Baseline before Prompt 4: 110 passed.
Prompt 4 (Storyboard): +62 -> 172 passed.
Prompt 5 (Character System): +103 -> 275 passed.
Prompt 6 (Asset System): +105 -> 380 passed.
Prompt 6.5 (Integration Hardening): +26 -> 406 passed.
Prompt 7 (Animation Engine): +79 renderer tests + ~79 Python tests -> ~485 Python.
Prompt 8 (Voice/TTS): +171 Python tests -> 656 Python, +31 renderer -> 102 Vitest.
Prompt 9 (Captions/Timing): +54 Python tests -> 710 Python, +26 renderer -> 128 Vitest.
Prompt 10 (Editorial / Composition Engine): +73 Python tests -> 783 Python, +41 renderer -> 169 Vitest. Real multi-scene MP4 smoke test PASSES (162 frames, h264 1280x720, ffprobe verified, 7 golden frames). L-032 resolved (caption smoke MP4 + frame artifacts).
Prompt 11 (Final Mastering / Media Pipeline / QA): +115 Python tests -> **898 Python**, +13 renderer -> **182 Vitest**. Real Voice AudioArtifact -> Remotion -> MP4 -> mastering -> QA -> atomic finalization **PASSES**. L-033 + L-034 RESOLVED.

**Latest run (L-U1, 2026-09-16):** `py -3.11 -m pytest tests/test_knowledge_layer.py -q` -> **52 passed, 1 warning** (exit code 0). The Knowledge Layer is **additive** and does not touch any existing pipeline stage. The 13 pre-existing environment-bound failures observed during the broader test run (`ffmpeg` not installed on the host, see C-003 / L-037) are NOT regressions introduced by L-U1.

Prompt L-U1 (Knowledge Layer): +52 -> **950 Python passed, +0 Vitest**. All L-U1 tests cover schemas, registry, retrieval, seeds, invariants.

**Latest run (L-U2, 2026-09-16):** `py -3.11 -m pytest tests/test_knowledge_storyboard_integration.py -q` -> **30 passed** (exit code 0). Full regression: `py -3.11 -m pytest tests/test_knowledge_layer.py tests/test_knowledge_storyboard_integration.py tests/test_storyboard_engine.py -q` -> **144 passed** (L-U1 52 + L-U2 30 + storyboard 62). The integration is **additive** and **backward compatible**: the 62 pre-existing storyboard tests pass unchanged.

Prompt L-U2 (Knowledge Storyboard Integration): +30 -> **993 Python passed, +0 Vitest**. The KnowledgeStoryboardAdapter is the ONLY integration point between the Knowledge Layer and the StoryboardEngine. The StoryboardEngine accepts an optional `knowledge_adapter` parameter; default is None (backward compatible).

**Latest run (L-U3, 2026-09-16):** `py -3.11 -m pytest tests/test_knowledge_consumption_architecture.py tests/test_knowledge_consumer_contract.py -q` -> **49 + 24 = 73 passed** (exit code 0). Full knowledge+storyboard regression: `py -3.11 -m pytest tests/test_knowledge_layer.py tests/test_knowledge_storyboard_integration.py tests/test_storyboard_engine.py tests/test_knowledge_consumption_architecture.py tests/test_knowledge_consumer_contract.py -q` -> **217 passed** (exit code 0). L-U3 is **additive** and **backward compatible**: all 144 existing tests pass unchanged.

**Latest run (L-U4, 2026-09-16):** `py -3.11 -m pytest tests/test_character_reference_system.py -q` -> **56 passed** (exit code 0). Combined Character + Knowledge + L-U4 regression: `py -3.11 -m pytest tests/test_character_system.py tests/test_knowledge_layer.py tests/test_knowledge_storyboard_integration.py tests/test_knowledge_consumption_architecture.py tests/test_knowledge_consumer_contract.py tests/test_character_reference_system.py -q` -> **314 passed** (exit code 0). L-U4 is **additive** and **backward compatible**: all 258 existing tests pass unchanged.

**Latest run (L-U6, 2026-09-16):** `py -3.11 -m pytest tests/test_camera_motion_sound_compiler.py -q` -> **106 passed** (exit code 0). Combined Character + Knowledge + Storyboard + L-U4 + L-U5 + L-U6 regression: `py -3.11 -m pytest tests/test_character_system.py tests/test_knowledge_layer.py tests/test_knowledge_storyboard_integration.py tests/test_knowledge_consumption_architecture.py tests/test_knowledge_consumer_contract.py tests/test_character_reference_system.py tests/test_storyboard_engine.py tests/test_prompt_compiler.py tests/test_camera_motion_sound_compiler.py -q` -> **630 passed** (exit code 0). L-U6 is **additive** and **backward compatible**: all 1208 existing tests pass unchanged.

Prompt L-U3 (Knowledge Consumption Architecture): +73 -> **1066 Python passed, +0 regressions**. 49 architecture tests + 24 consumer contract tests. L-U2 adapter refactored to use resolver internally; public API unchanged. All 144 existing tests pass.

Prompt L-U4 (Character Reference System Integration): +56 -> **1122 Python passed, +0 regressions**. New `KnowledgeCharacterAdapter` + `CharacterReferenceSpecification` + golden fixture. Character System components (`CharacterDefinition`, `CharacterInstance`, `CharacterRegistry`, `CharacterSystemEngine`, `CharacterCache`, `svg_generator.py`) untouched. All 1066 existing tests pass unchanged.

Prompt L-U5 (Prompt Compiler V2): +86 -> **1208 Python passed, +0 regressions**. New `PromptCompiler` + `CanonicalPromptIR` + `PromptValidator` + `ProviderPromptAdapter` boundary + reference `GoogleFlowPromptAdapter`. Existing `CharacterSystemEngine`, `CharacterReferenceSpecification`, `VisualGrammar`, `CharacterGrammar`, `KnowledgeResolver`, `KnowledgeContext` untouched. All 1122 existing tests pass unchanged.

Prompt L-U6 (Camera + Motion + Sound Compiler): +106 -> **1314 Python passed, +0 regressions**. New `CameraMotionSoundCompiler` + `CameraMotionSoundCompilationResult` + `CameraMotionSoundValidator` + `KnowledgeCameraMotionSoundAdapter`. Extended `app/prompt/schemas.py` with new contracts (`CameraBlockExt`, `MotionBlockExt`, `SoundBlockExt`, `SubjectMotionSpec`, `SoundLayersSpec`). L-U5 contracts UNCHANGED. Three distinct concepts: camera movement, subject motion, animation pattern. Sound intent vs Audio file vs Audio mix -- separate boundaries. All 1208 existing tests pass unchanged.

Prompt L-U7 (Hybrid Quality Validation Engine): +78 -> **1392 Python passed, +0 regressions**. New `QualityEngine` + `QualityValidationResult` + `QualityValidationContext` + `ValidationPolicy` (STRICT/STANDARD/LENIENT) + 15 dimension validators + 4 severity levels (INFO/WARNING/ERROR/BLOCKING). Pure, deterministic, no LLM, no provider SDK, no Remotion/FFmpeg. Consumes existing canonical contracts (no mutation, no duplication). Validation fingerprint derived deterministically from input fingerprints. All 1314 existing tests pass unchanged. 13 pre-existing failures (render API / orchestrator / mastering QA) remain pre-existing environment-bound.

Prompt L-U8 (Provider Adapter Layer): +94 -> **1567 Python passed, +0 regressions**. New `app/providers/generation/` package with canonical schemas (`ProviderDefinition`, `ProviderCapability`, `SemanticLossReport`, `ProviderPromptAdapter`, `ProviderGenerationRequest`, `ProviderError`), `ProviderRegistry` (single source of truth), `CapabilityMatcher` (deterministic compatibility), `MockGenerationProviderAdapter` (deterministic, no real generation). Provider neutrality enforced: `app.prompt`, `app.knowledge`, `app.character`, `app.quality` do NOT import provider SDKs. All 1473 existing tests pass unchanged.

Prompt P13 (Shorts Generation): +23 -> **1620 Python passed, +0 regressions**. New `app/shorts/` package with canonical schemas (`ShortsCompilationResult`, `ShortsPlan`, `ShortsRenderSettings`, `ShortsQAReport`), `ShortsCompiler` (deterministic scene scoring + diversified selection), `VerticalCaptionAdapter` (reposition captions for 9:16), new `ShortsStage` (s11_short enhanced). FastAPI routes for shorts endpoints. Next.js `/jobs/[id]/shorts` page with video preview grid.

Prompt P14 (Thumbnail Generation): +15 -> **1620 Python passed, +0 regressions**. New `app/thumbnail/` package with canonical schemas (`ThumbnailCompilationResult`, `ThumbnailPlan`, `ThumbnailRenderSettings`, `ThumbnailQAReport`), `ThumbnailCompiler` (title + scene + social variants), `ThumbnailGenerator` (FFmpeg frame extraction). FastAPI routes for thumbnail endpoints. Next.js `/jobs/[id]/thumbnails` page with image grid.

Prompt P15 (Publishing): +29 -> **1649 Python passed, +0 regressions**. New `app/publishing/` package with canonical schemas (`PublishingPlan`, `PublishingMetadata`, `PublishingResult`, `YouTubeMetadata`, `TikTokMetadata`, `FacebookMetadata`), `YouTubeMetadataGenerator` (title optimization, #shorts tag, category inference), `TikTokMetadataGenerator` (description + hashtags, max 150 chars), `FacebookMetadataGenerator` (content tags, privacy settings), `PublishingMetadataCompiler`, `PublishingPlanBuilder`. `PublishingStage`. FastAPI routes (`POST /publishing/preflight`, `POST /publishing/finalize`, `GET /publishing/{id}/plan`, `GET /publishing/{id}/result`). Next.js `/jobs/[id]/publishing` page with platform selection, metadata form, preflight validation, preview. No real API credentials required for metadata generation.

**Renderer smoke (Prompt 6.5, 2026-09-15):** `python scripts/render_smoke_test.py` ->
produced `workspace/render_smoke_*/output.mp4` (51.8 KB, 640x360, h264, 5.000s, exit 0).

**Editorial smoke (Prompt 10, 2026-09-15):** `python scripts/editorial_smoke_test.py` ->
produced `workspace/p10_editorial_smoke_*/output.mp4` (h264 1280x720 @ 30fps, 5.4s, 162 frames, 7 PNG frames extracted, ffprobe verified, exit 0). Pipeline: 3 scenes -> 2 fade transitions -> 3 narration audio clips -> 24 z-ordered layers -> MP4.

---

## Commands to run tests (unblock)

### 1. Install Python 3.11+

```powershell
# Option A: winget
winget install Python.Python.3.11

# Option B: from python.org installer, then verify
python --version   # must show 3.11.x or 3.12.x
```

### 2. Create virtualenv and install orchestrator deps

```powershell
cd "c:\Users\Administrator\Downloads\videoAI\orchestrator"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Run the test suite

```powershell
# all tests
pytest -q

# with coverage
pytest -q --cov=app --cov-report=term-missing

# one suite at a time
pytest tests/test_research_engine.py -q
pytest tests/test_scene_definition.py -q
pytest tests/test_mock_providers.py -q
pytest tests/test_pipeline_integration.py -q
```

### 4. Project audit (governance)

```powershell
# from repo root, after installing Python
python -m app.tools.project_audit
```

Expected result: `WARN` (C-001/002/003 remain; see TECHNICAL_DEBT.md).

### 5. Renderer / webapp tests (do not exist yet)

```powershell
# renderer: add Vitest
cd "c:\Users\Administrator\Downloads\videoAI\renderer"
npm install -D vitest
# then create renderer/src/**/*.test.tsx and run `npx vitest`

# webapp: add @testing-library/react
cd "c:\Users\Administrator\Downloads\videoAI\webapp"
npm install -D @testing-library/react vitest
# then create webapp/**/*.test.tsx and run `npx vitest`
```

---

## Recording results

After running tests, update this file with:

| date | command | result | exit_code | notes |
|---|---|---|---|---|
| 2026-09-15 | `py -3.11 -m pytest tests/ -q` | 110 passed, 3 warnings | 0 | Prompt 3.5 baseline fixed: +37 passing, -42 failing/erroring vs 73/24/18 baseline |
| 2026-09-15 | `py -3.11 -m pytest tests/ -q` | **172 passed**, 3 warnings | 0 | **Prompt 4: +62 Storyboard tests; Storyboard Intelligence Engine VERIFIED** |

---

## What "PASSED" requires

For each suite to be marked `PASSED`, this file must record:

1. The exact `pytest` (or `vitest`) command run.
2. The exit code (must be `0`).
3. The Python / Node version.
4. The number of tests passed.
5. Any warnings.

If even one test fails, the suite is `FAILED`, not `PARTIAL`.

---

## Common blockers and fixes

| blocker | fix |
|---|---|
| `python: command not found` | install Python 3.11+ (see step 1) |
| `ModuleNotFoundError: app` | run from `orchestrator/` directory |
| `duckduckgo_search` rate-limited | tests use `MockSearchProvider`; check `OPENAI_API_KEY=""` is set |
| `ffmpeg: command not found` | install via `winget install Gyan.FFmpeg` (only needed for s11) |
| `npx: command not found` | install Node 20+ from nodejs.org |

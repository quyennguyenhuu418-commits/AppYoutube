# ROADMAP

Planned and completed prompt-level milestones for the AI Documentary
Animation Factory. Each prompt establishes a verifiable, testable
foundation before the next prompt begins.

---

## Completed

### PROMPT 0.5 — Deep Architecture Reconstruction & Project Governance
- Created persistent project-memory docs under `/docs/`
- Project audit tool: `orchestrator/app/tools/project_audit.py`

### PROMPT 1 — Foundation Hardening
- (see `plans/prompt_1_FINAL_REPORT.md` if present)

### PROMPT 2 — Script Engine
- Canonical Script / ScriptSection / ScriptBeat schema

### PROMPT 3 — Story Engine
- Canonical StoryPackage, narrative arcs

### PROMPT 3.5 — Deterministic Mock Providers
- MockLLMProvider with fixture data

### PROMPT 4 — Storyboard
- Canonical StoryboardPackage

### PROMPT 5 — Character System
- Canonical Character, expressions, poses

### PROMPT 6 — Asset System
- Canonical AssetReference, AssetSystemPackage
- Mood colors, render hints

### PROMPT 6.5 — Integration Hardening
- Cross-stage contract tests, asset adapter, vertical E2E

### PROMPT 7 — Animation Engine & Motion Runtime
- Canonical AnimationPlan
- AnimationDriver (Remotion runtime)
- Real animation MP4 smoke test (7.9 KB, 6s)
- 485 Python + 71 Vitest tests passing

### PROMPT 8 — Voice / TTS / Audio Intelligence Layer (2026-09-15)
- Canonical VoiceDefinition / VoiceInstance / VoiceRegistry / VoiceResolver
- TTSProvider abstraction + MockTTSProvider (deterministic stdlib `wave`)
- LegacyProviderAdapter for ElevenLabs/gTTS
- Content-addressed AudioArtifact + VoiceTTSCache
- AudioValidator, NarrationScript adapter, SpeechTiming, NarrationTimeline
- Pronunciation + emphasis hints (provider-agnostic)
- Real narration MP4 with audio: 166 KB, h264 + aac (48 kHz / 2ch / 4.05s)
- 656 Python tests + 102 Vitest tests passing
- See `plans/prompt_8_FINAL_REPORT.md`

---

## Next

### PROMPT 9 — Timing / Captions / Speech Alignment Engine (2026-09-15)
- Canonical CaptionTrack / CaptionSegment / CaptionLine / CaptionWord / CaptionStyle
- CaptionSegmenter (punctuation + phrase + max-chars + max-words + max-duration aware)
- LineBreaker (deterministic, no in-word splits)
- TimingQualityScorer (7 dimensions with reasons)
- AlignmentProvider Protocol boundary + UniformAlignmentProvider fallback
- CaptionValidator (overlap, scene bounds, word bounds, line count, reading speed)
- CaptionCompiler (NarrationTimeline + SpeechTiming → CaptionTrack)
- Remotion CaptionRenderer consuming canonical CaptionTrack
- Pure deterministic frame-state derivation (computeCaptionFrameState)
- Frame/time helpers (time_to_frame, frame_to_time, FrameRoundingPolicy)
- Cross-runtime contract tests (Python pydantic JSON ↔ TS interface)
- 710 Python tests + 128 Vitest tests passing (P9 added +54 Python, +26 renderer)
- See `plans/prompt_9_FINAL_REPORT.md`

---

## Next

### PROMPT 10 — Editorial / Composition Engine (2026-09-15) ✅

Compose multiple scenes onto a deterministic master timeline, mix
narration with music/SFX using canonical timing references, and produce
a `RenderPlan` that the renderer consumes without business logic.
Resolves L-032 (caption Remotion render) as a precondition.

Acceptance criteria (all met):
- [x] `EditorialProject`, `EditorialTimeline`, `EditorialScene`, `Transition`, `EditorialHold`, `AudioClipRef`, `AudioTrackLayer`, `AudioMixingPolicy`, `TitleCardSpec`, `RenderPlan` schemas (Python + TS mirror)
- [x] `EditorialCompiler` pipeline: validate → resolve refs → place scenes → transitions → audio ducking → render plan
- [x] Scene-local → master timeline transformation (`place_scenes`)
- [x] Canonical transitions (CUT/FADE/CROSSFADE/DISSOLVE/DIP_TO_BLACK/DIP_TO_WHITE) with overlap semantics and validation
- [x] Editorial holds (`hold_before` / `hold_after`)
- [x] Audio tracks (narration/dialogue/music/SFX/ambience) with ducking using `NarrationTimeline` active intervals
- [x] Configurable narration priority (`AudioMixingPolicy.priority_order`)
- [x] Video layers with explicit z-order (`EditorialTimeline.layer_order`)
- [x] `EditorialQualityScore` (timeline_validity, scene_continuity, transition_consistency, audio_continuity, caption_alignment, animation_alignment, asset_integrity, pacing_consistency)
- [x] 73 new Python unit tests (schemas, offsets, audio, transitions, compiler, validation, cross-runtime) → 783 PASS
- [x] 41 new Vitest tests (plan + cross-runtime) → 169 PASS
- [x] `scripts/editorial_smoke_test.py` produces a real multi-scene MP4 (h264 1280x720 @ 30fps, 5.4s, 162 frames) with 7 golden PNG frames and ffprobe verification
- [x] L-032 RESOLVED — caption smoke now renders MP4 + frame artifacts
- [x] No regressions in voice/audio/caption tests

Out of scope for P10 (deferred to P11+): final mastering / loudness, Shorts / 9:16, thumbnails, publishing, webapp UI, dynamic music generation.

### PROMPT 11 — Final Mastering & Loudness Normalization (✅ DELIVERED 2026-09-15)

- [x] C-27 `RenderProfile` (versioned render settings, fingerprintable).
- [x] C-28 `MasteringProfile` + `FinalVideoArtifact` (lifecycle + QA status).
- [x] C-29 `MediaQAReport` with 11 check types + `QAPolicy`.
- [x] `MediaProcessor` safe FFmpeg/FFprobe wrapper (no shell injection).
- [x] Two-pass loudnorm (`ebur128` → `loudnorm`) with `LRA` clamping.
- [x] True-peak measurement via `astats` (per-frame true-peak fallback).
- [x] Clipping detection (sample peak ≥ 0 dBFS).
- [x] 5 mix buses (Narration / Dialogue / Music / SFX / Ambience) + Master + deterministic ducking via `NarrationTimeline`.
- [x] Atomic finalization (temp → validate → rename).
- [x] **L-033 RESOLVED** — real voice audio in `final.mp4` (aac 48 kHz / 2ch).
- [x] **L-034 RESOLVED** — measured LUFS -16.3, true peak -9.2 dBTP, 11-check QA PASS.
- [x] Python tests: +115 (898 total), Vitest: +13 (182 total).
- [x] `scripts/final_smoke_test.py` PASS end-to-end.

### PROMPT 12 — Render Orchestration API + Final Artifact Inspector (✅ DELIVERED 2026-09-16)

Connect the deterministic media pipeline (P11) to the FastAPI + Next.js
application surface through a canonical render orchestration layer. One
canonical rendering path. P11's MasteringPipeline remains the production
media boundary.

Acceptance criteria (all met):
- [x] **C-30** `RenderJob` Pydantic contract with explicit state machine
      (`QUEUED → PREPARING → PREFLIGHT → RENDERING → MASTERING → QA →
      FINALIZING → APPROVED | FAILED | CANCELLED`).
- [x] **`RenderOrchestrator`** coordinating the full pipeline
      (preflight → render → master → QA → finalize → persist).
- [x] **Render API** — 6 thin FastAPI endpoints:
      `POST /render/preflight`, `POST /render/finalize`,
      `GET /render/{id}/status`, `GET /render/{id}/qa`,
      `GET /render/{id}/artifact`, `GET /render/{id}/video`.
- [x] **P11 integration** — `RenderStage` (`s10_render`) and the
      orchestrator both go through `MasteringPipeline` (single path).
- [x] **Idempotency** — fingerprint-aware reuse + stale-artifact
      invalidation via `RenderRequestFingerprint`.
- [x] **Strict finalization model** (§34) — only
      `lifecycle == APPROVED && qa_status == FINAL_APPROVED` is served as
      a final video; otherwise the job transitions to `FAILED` at
      `error_stage="finalizing"`.
- [x] **Safe media serving** — `GET /render/{id}/video` returns 403 for
      non-approved artifacts; 404 for non-existent; 400 for path-traversal
      attempts. `Accept-Ranges: bytes` enabled.
- [x] **Final Render Inspector** at `/jobs/[id]/render` with:
      real HTML5 `<video controls>` preview, status pipeline, QA
      check list, audio QA, SHA-256, fingerprint, renderer/ffmpeg versions.
- [x] **Cross-runtime contract** — Python ↔ JSON ↔ TypeScript ↔ React UI
      verified by 17 contract tests + 42 inspector tests.
- [x] **Security audit** — path traversal rejected, internal paths never
      leaked (`final_mp4_path = None` in API responses), arbitrary file
      access prevented.
- [x] **E2E** — `pytest tests/test_render_e2e.py` → 4 PASSED (full
      FastAPI lifecycle + real FFprobe of final MP4).
- [x] **No regressions** — 966 Python passed, 224 TS passed.
- [x] **C-034 RESOLVED** — `RenderArtifactResponse` no longer leaks
      nonexistent fields; orchestrator honors artifact lifecycle/QA
      status (strict model).
- [x] **L-036 / L-037 / L-038** documented as known limitations
      (single-instance file store, synthetic silence QA fixture,
      polling vs SSE).

Out of scope for P12 (deferred to P13+):
Shorts / 9:16, thumbnails, YouTube publishing, real-time SSE progress
streaming, multi-worker job persistence, Playwright UI E2E.

### Future (not yet scheduled)

- PROMPT 13 — Shorts Generation (9:16) — schema ready, layout logic pending
- PROMPT 14 — Thumbnails
- PROMPT 15 — Publishing
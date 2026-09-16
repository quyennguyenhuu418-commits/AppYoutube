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

### L-U1 — Production Knowledge & Visual Grammar Foundation (✅ DELIVERED 2026-09-16)
- Canonical KnowledgeSource (C-31), KnowledgeEntry (C-32), VisualGrammar (C-33), CharacterGrammar (C-34)
- 187+ KnowledgeEntries from Google Flow + DINO AI + Axen seeds
- See `plans/PROMPT_LU1_FINAL_REPORT.md`

### L-U2 — Storyboard Knowledge Integration (✅ DELIVERED 2026-09-16)
- `KnowledgeStoryboardAdapter` connecting StoryboardEngine to KnowledgeRegistry
- Read-only, backward-compatible
- See `plans/L-U2_FINAL_REPORT.md`

### L-U3 — Knowledge Consumption Architecture (✅ DELIVERED 2026-09-16)
- Canonical `KnowledgeContext` + `KnowledgeResolver` + `KnowledgeQuery` + `KnowledgeResult`
- 49 architecture + 24 consumer contract = 73 tests
- See `plans/PROMPT_LU3_FINAL_REPORT.md`

### L-U4 — Character Reference System Integration (✅ DELIVERED 2026-09-16)
- `KnowledgeCharacterAdapter` + `CharacterReferenceSpecification`
- Identity vs Scene State separation
- 56 new tests (schema + adapter + golden fixture + consistency regression + backward compat)
- Character System components untouched
- See `plans/PROMPT_LU4_FINAL_REPORT.md`

### L-U5 — Prompt Compiler V2 (✅ DELIVERED 2026-09-16)
- Canonical `PromptCompiler` + `CanonicalPromptIR` (structured, NOT raw string)
- `KnowledgePromptAdapter` (thin, uses KnowledgeContext from L-U3)
- `PromptValidator` (deterministic, no LLM)
- `ProviderPromptAdapter` boundary + reference `GoogleFlowPromptAdapter`
- 86 new tests (schema + deterministic + image/video + knowledge + provenance + fallback + identity + scene-variable + constraints + camera + motion + format + provider-neutrality + provider adapter + backward compat + architecture invariants + golden fixtures + security + fingerprint + consistency regression)
- CharacterDefinition / CharacterReferenceSpecification / VisualGrammar untouched
- See `plans/PROMPT_LU5_FINAL_REPORT.md`

### L-U6 — Camera + Motion + Sound Compiler (✅ DELIVERED 2026-09-16)
- `CameraMotionSoundCompiler` + `CameraMotionSoundCompilationResult` (semantic, NOT implementation)
- `KnowledgeCameraMotionSoundAdapter` (thin, uses KnowledgeContext from L-U3)
- `CameraMotionSoundValidator` (deterministic, no LLM)
- Three distinct concepts: camera movement (PUSH_IN), subject motion (WALK), animation pattern (RIG_POSE_INTERPOLATION)
- Sound intent vs Audio file vs Audio mix — separate boundaries
- Timing authority not duplicated (NarrationTimeline, SpeechTiming, AnimationPlan remain authoritative)
- Bounded vocabularies for camera/motion/sound
- 106 new tests (schema + deterministic + vocabulary + knowledge + provenance + fallback + conflict + character consistency + storyboard + prompt integration + animation boundary + timing semantics + provider-neutrality + renderer-neutrality + security + golden fixtures A-N + fingerprint + backward compat + architecture invariants + three-distinct-concepts + validator determinism)
- L-U5 contracts UNCHANGED
- See `docs/CAMERA_MOTION_SOUND_COMPILER.md` and `plans/PROMPT_LU6_FINAL_REPORT.md`

### L-U7 — Hybrid Quality Validation (✅ DELIVERED 2026-09-16)
- `QualityValidationResult` (canonical, frozen) with `ValidationStatus` (PASS/WARN/REJECT/UNAVAILABLE) and `GenerationReadiness` (READY/READY_WITH_WARNINGS/NOT_READY/UNAVAILABLE)
- 15 dimension validators (completeness, identity, camera, motion, camera/motion compatibility, continuity, prompt loss, knowledge/provenance, format, sound semantic, fallback visibility, conflict visibility, contract compatibility, provider readiness, generation readiness)
- `QualityEngine` orchestrator: deterministic, no LLM, no provider SDK, no Remotion/FFmpeg
- Validation policy: STRICT / STANDARD / LENIENT
- 78 new tests; 0 regressions in pre-existing tests (all 13 failures are pre-existing environment-bound)
- See `docs/HYBRID_QUALITY_VALIDATION.md`, `docs/ADR-016.md`, and `plans/PROMPT_LU7_FINAL_REPORT.md`

### L-U8 — Provider Adapter Layer (✅ DELIVERED 2026-09-16)
- Canonical `ProviderDefinition` (provider-neutral), `ProviderCapability`, `SemanticLossReport` (field-level translation status)
- `ProviderRegistry` (single source of truth, deterministic)
- `CapabilityMatcher` — deterministic compatibility matching (SUPPORTED/PARTIALLY_SUPPORTED/UNSUPPORTED/UNKNOWN), no ranking
- `ProviderPromptAdapter` abstract interface — translate canonical IR to provider-specific representation
- `MockGenerationProviderAdapter` — deterministic, no real generation, no fake media
- `ProviderGenerationRequest` canonical boundary contract
- Canonical provider error taxonomy (12 error kinds) with retry classification (RETRYABLE/NON_RETRYABLE/UNKNOWN)
- Semantic loss reporting: every field must have explicit status (SUPPORTED/TRANSFORMED/APPROXIMATED/OMITTED_WITH_REASON/UNSUPPORTED)
- Quality gate integration: QualityValidationResult.REJECT blocks compilation; adapter cannot override
- Character identity + scene variable preservation from L-U4
- Deterministic fingerprints (SHA-256[:32]) — no secrets, timestamps, or random UUIDs
- Provider neutrality: `app.prompt`, `app.knowledge`, `app.character`, `app.quality` do NOT import provider SDKs
- 94 new tests; 0 regressions
- See `docs/PROVIDER_ADAPTER_LAYER.md`, `docs/ADR-017.md`, and `plans/PROVIDER_ADAPTER_LU8_FINAL_REPORT.md`

---

**PRODUCTION KNOWLEDGE / VISUAL GRAMMAR TRACK = COMPLETE** ✅

### P13 — Shorts Generation (9:16) (✅ DELIVERED 2026-09-16)

Intelligent 9:16 vertical clip extraction from horizontal final.mp4.

Acceptance criteria (all met):
- [x] Canonical `ShortsCompilationResult`, `ShortsPlan`, `ShortsSourceContext`, `ShortsRenderSettings`, `ShortsQAReport` schemas
- [x] `ShortsCompiler` — deterministic scene scoring (emotional intent, narration priority, position in video)
- [x] `CropMode` — CENTER / SMART_FACE / SUBJECT_TRACKING / RULE_OF_THIRDS / NARRATION_FOCUS
- [x] Smart crop composition — compute crop center from focus point, character positions, speaker position
- [x] Diversified scene selection — pick scenes from different thirds of the video (configurable max_shorts)
- [x] `VerticalCaptionAdapter` — reposition captions from center to lower third for vertical display
- [x] FFmpeg crop pipeline — 16:9 → 9:16 with sharpening + color correction
- [x] `ShortsStage` (s11_short) — new pipeline stage consuming scene_definition.json
- [x] Shorts API endpoints — `GET /jobs/{id}/shorts`, `GET /jobs/{id}/shorts/plan`, `GET /jobs/{id}/shorts/{sid}/video`
- [x] Webapp Shorts page — `/jobs/[id]/shorts` with video preview grid, QA badges, download
- [x] Shortcut links from Render page to Shorts and Thumbnails
- [x] Deterministic fingerprint (SHA-256, no timestamps)
- [x] 23 new Python tests; 0 regressions

Out of scope for P13: real face detection, subject tracking via ML, multiple crop candidates per scene.

### P14 — Thumbnail Generation (✅ DELIVERED 2026-09-16)

Generate static preview images from video for YouTube, Twitter, Instagram.

Acceptance criteria (all met):
- [x] Canonical `ThumbnailCompilationResult`, `ThumbnailPlan`, `ThumbnailRenderSettings`, `ThumbnailTextOverlay`, `ThumbnailQAReport` schemas
- [x] `ThumbnailCompiler` — deterministic plan with title card, scene captures, social variants (Twitter/Instagram)
- [x] `ThumbnailSize` — YOUTUBE_DEFAULT (1280x720), TWITTER_CARD (1200x628), INSTAGRAM_SQUARE (1080x1080), TIKTOK (1080x1920), LINKEDIN (1200x627)
- [x] `ThumbnailFormat` — WEBP (default), JPEG, PNG
- [x] `ThumbnailContentType` — SCENE_CAPTURE / TITLE_CARD / COMPOSITE / DIAGRAM_FOCUS / CHARACTER_PORTRAIT
- [x] `ThumbnailColorScheme` — HIGH_CONTRAST / DARK_OVERLAY / LIGHT_OVERLAY / BRAND_COLOR / MINIMAL
- [x] `ThumbnailGenerator` — FFmpeg frame extraction with scale to target resolution
- [x] `ThumbnailStage` — pipeline stage consuming final.mp4 + story_package.json + scene_definition.json
- [x] Thumbnail API endpoints — `GET /jobs/{id}/thumbnails`, `GET /jobs/{id}/thumbnails/plan`, `GET /jobs/{id}/thumbnails/{tid}`
- [x] Webapp Thumbnails page — `/jobs/[id]/thumbnails` with image grid, format badges, download
- [x] Deterministic fingerprint
- [x] 15 new Python tests; 0 regressions

### P15 — Publishing (YouTube + TikTok + Facebook) (✅ DELIVERED 2026-09-16)

Multi-platform publishing metadata generation for YouTube, TikTok, and Facebook.

Acceptance criteria (all met):
- [x] Canonical `PublishingPlan`, `PublishingMetadata`, `PublishingResult` schemas
- [x] Platform-specific metadata: `YouTubeMetadata`, `TikTokMetadata`, `FacebookMetadata`
- [x] `YouTubeMetadataGenerator` — title optimization (truncation, #shorts), description with hashtags, tag generation, category inference
- [x] `TikTokMetadataGenerator` — description + hashtags in one field, hashtag-only tags, max 150 char title
- [x] `FacebookMetadataGenerator` — title/description, content tags, privacy settings
- [x] `PublishingMetadataCompiler` — compiles platform-specific metadata from canonical data
- [x] `PublishingPlanBuilder` — builds complete `PublishingPlan` from job data
- [x] `PublishingStage` — pipeline stage consuming final.mp4 + shorts + thumbnails
- [x] Publishing API — `POST /publishing/preflight` (validate), `POST /publishing/finalize` (generate plan)
- [x] `GET /publishing/{job_id}/plan` and `GET /publishing/{job_id}/result`
- [x] Webapp Publishing page — `/jobs/[id]/publishing` with platform selection, metadata form, preflight validation, preview
- [x] Security — no credentials in API responses, no tokens in logs
- [x] 29 new Python tests; 0 regressions

Out of scope for P15: real YouTube OAuth, TikTok API integration, Facebook Graph API integration, credential management UI.

### PROMPT 16 — Real Platform API Integration (YouTube + TikTok + Facebook) (✅ DELIVERED 2026-09-16)

Real platform clients with credential management + safe stubs.

Acceptance criteria (all met):
- [x] `PlatformCredentials` — env-loaded credential store with `mask()` for safe logging
- [x] `PlatformClient` abstract interface with `is_configured()` and `upload()`
- [x] `YouTubeClient` — credential check + stub for YouTube Data API v3 OAuth 2.0 + resumable upload
- [x] `TikTokClient` — credential check + stub for TikTok Content Posting API
- [x] `FacebookClient` — credential check + stub for Facebook Graph API v18+ (Reels + Feed)
- [x] `get_platform_client(platform)` factory function
- [x] Deterministic credential sensing — failed gracefully if no credentials
- [x] No credentials in API responses or logs (all values masked)
- [x] 16 new Python tests; 0 regressions
- [x] Production usage: install `httpx` or `aiohttp` to make real uploads

### PROMPT 16.5 — Research Engine Enhancements (✅ DELIVERED 2026-09-16)

- [x] `_detect_contradictions` — deterministic claim-pair detection (polarity markers + topic overlap)
- [x] `_extract_geography` — extract geographic sites (continents, oceans, features)
- [x] `_extract_quantitative_facts` — extract numeric facts (years, percentages, quantities, distances, temperatures)
- [x] 8 new research engine tests; 0 regressions
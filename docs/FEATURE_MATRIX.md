# FEATURE_MATRIX

Every product feature × {backend, frontend, tests, status, known limitation}.
Status values: `IMPLEMENTED`, `PARTIAL`, `MISSING`, `PLANNED`.

---

## Job Lifecycle

| feature | backend | frontend | tests | status | known limitation |
|---|---|---|---|---|---|
| Create job | `POST /jobs` (`api/jobs.py:58`) | `TopicForm` (`webapp/components/TopicForm.tsx:89`) | NONE | IMPLEMENTED | single process; not concurrent-safe |
| List jobs | `GET /jobs` | `JobsList` | NONE | IMPLEMENTED | none |
| View job detail | `GET /jobs/{id}` | `/jobs/[id]/page.tsx:47` | NONE | IMPLEMENTED | polls every 2500 ms (no SSE) |
| Stream artifact | `GET /jobs/{id}/artifacts/{name}` | direct browser | NONE | IMPLEMENTED | path-traversal-safe (`api/assets.py:44`) |
| Cancel running job | — | — | — | MISSING | future work |

## Research

| feature | backend | frontend | tests | status | known limitation |
|---|---|---|---|---|---|
| Question decomposition | `engine.py:344–401` | — | `test_research_engine.py` | IMPLEMENTED | BLOCKED (no Python) |
| Web search | `engine.py:403–439` via `DuckDuckGoSearchProvider` | — | NONE | IMPLEMENTED | UNVERIFIED end-to-end |
| URL fetch | `RequestsContentFetchProvider` | — | NONE | IMPLEMENTED | UNVERIFIED end-to-end |
| Source scoring | `engine.py:479–518` | — | `test_research_engine.py` | IMPLEMENTED | BLOCKED |
| Source deduplication | `engine.py:520–553` | — | `test_research_engine.py` | IMPLEMENTED | BLOCKED |
| Claim extraction | `engine.py:555–651` | — | NONE | IMPLEMENTED | BLOCKED |
| Claim/source graph | `engine.py:655–685` | — | NONE | IMPLEMENTED | BLOCKED |
| **Contradiction detection** | `engine.py:687` (pass stub) | — | NONE | **MISSING** | stub; see `docs/TECHNICAL_DEBT.md` C-001 |
| Uncertainty modeling | `engine.py:689–711` | — | NONE | PARTIAL | heuristic only |
| Timeline | `engine.py:715–762` | — | NONE | PARTIAL | regex extraction; no chronological sort |
| **Geography** | `engine.py:764–766` (never populated) | — | NONE | **MISSING** | stub; see `docs/TECHNICAL_DEBT.md` C-002 |
| **Quantitative facts** | `engine.py:764–766` (never populated) | — | NONE | **MISSING** | stub; see `docs/TECHNICAL_DEBT.md` C-002 |
| Visual opportunities | `engine.py:768–891` | — | NONE | IMPLEMENTED | BLOCKED |
| Story opportunities | `engine.py:768–891` | — | NONE | IMPLEMENTED | BLOCKED |
| Synthesis | `engine.py:895–962` | — | NONE | IMPLEMENTED | BLOCKED |
| Quality score (9 axes) | `engine.py:968–1037` | — | `test_research_engine.py` | IMPLEMENTED | BLOCKED |
| Hash-keyed cache | `research/cache.py:111` | — | `test_research_engine.py` | IMPLEMENTED | BLOCKED |
| Inspection API | `api/research.py:196` | — | NONE | IMPLEMENTED | none |
| Human review (sources) | `POST /review/sources/{id}` | — | NONE | IMPLEMENTED | none |
| Human review (claims) | `POST /review/claims/{id}` | — | NONE | IMPLEMENTED | none |

## Script

| feature | backend | frontend | tests | status | known limitation |
|---|---|---|---|---|---|
| Thesis generation | `s2_thesis.py` | indirect via job detail | NONE | IMPLEMENTED | UNVERIFIED |
| Title candidates | `s3_titles.py` | indirect | NONE | IMPLEMENTED | UNVERIFIED |
| Script writing | `s4_script.py` | indirect | NONE | IMPLEMENTED | UNVERIFIED |
| Storyboard | `s5_storyboard.py` | indirect | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** (62 tests) |
| Story Intelligence Engine | `story/engine.py` | — | `test_story_engine.py` | IMPLEMENTED | VERIFIED |
| Storyboard Intelligence Engine | `storyboard/engine.py` | `/jobs/[id]/storyboard/page.tsx` | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** (62 tests) |
| Visual mode selection (11 modes) | `storyboard/engine.py` | — | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** |
| Camera / motion / transition planning | `storyboard/engine.py` | — | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** |
| Continuity engine | `storyboard/engine.py` | — | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** |
| Evidence linking (visual_beat → claim_ids) | `storyboard/engine.py` | — | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** |
| Asset requirements (REUSE/CREATE/PROCEDURAL) | `storyboard/engine.py` | — | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** |
| Quality score (14 axes) | `storyboard/engine.py` | — | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** |
| SceneDefinition candidates | `storyboard/engine.py` | — | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** |
| Storyboard API | `api/storyboard.py` | — | NONE | **IMPLEMENTED** | **VERIFIED** (integration via pipeline) |
| Storyboard UI | — | `/jobs/[id]/storyboard/page.tsx` | NONE | **IMPLEMENTED** | none |
| Storyboard cache | `storyboard/cache.py` | — | `test_storyboard_engine.py` | **IMPLEMENTED** | **VERIFIED** |
| **Character System** | `character/engine.py` | `/jobs/[id]/characters/page.tsx` | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** (103 tests) |
| Character canonical schema (CharacterDefinition) | `schemas/character.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Character instance (scene placement) | `schemas/character.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Skeleton/anchor model (15 joints) | `schemas/character.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Wardrobe system | `schemas/character.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Pose system (8 renderer poses) | `schemas/character.py`, `engine.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Expression system (11 expressions) | `schemas/character.py`, `engine.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Character registry | `schemas/character.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Duplicate character detection | `engine.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Character reuse | `engine.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Character versioning | `schemas/character.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Character SVG generation (8 poses) | `svg_generator.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| SVG validation (security checks) | `svg_generator.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Character quality score (11 dimensions) | `engine.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Character API (14 endpoints) | `api/characters.py` | — | NONE | **IMPLEMENTED** | none |
| Character inspection UI | — | `/jobs/[id]/characters/page.tsx` | NONE | **IMPLEMENTED** | none |
| Character cache (content-addressed) | `character/cache.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| SceneDefinition actor bridge | `engine.py` | — | `test_character_system.py` | **IMPLEMENTED** | **VERIFIED** |
| **Asset System** | `assets/engine.py` | `/jobs/[id]/assets/page.tsx` | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** (105 tests) |
| Asset abstraction (Asset/Reference/Package/Registry/Resolver/Quality/Lifecycle) | `schemas/asset.py`, `assets/engine.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Environment schema (EnvironmentAsset/Instance + 6 profiles) | `schemas/asset.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Prop schema (PropAsset/Instance + Anchor system) | `schemas/asset.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| AssetRegistry (global/project/scene-local) | `assets/engine.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Asset lifecycle (DRAFT/GENERATED/.../APPROVED) | `schemas/asset.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Duplicate detection (semantic hashing) | `assets/engine.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Reuse policy (ALWAYS/PREFERRED/ALLOWED/SCENE_LOCAL/NEVER) | `schemas/asset.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Asset quality score (11 dimensions) | `assets/engine.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| AssetReference (single renderer contract) | `schemas/asset.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| AssetPackage filesystem contract | `assets/engine.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Content-addressed cache | `assets/cache.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Idempotent re-runs | `assets/cache.py`, `engine.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| SVG/path/MIME security validation | `assets/security.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| AssetProvider abstraction | `assets/provider.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Character System integration (registry compatibility) | `assets/engine.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| Storyboard integration (asset_requirements → resolution) | `assets/engine.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| s6 backward-compatible bridge | `assets/s6_bridge.py` | — | `test_asset_system.py` | **IMPLEMENTED** | **VERIFIED** |
| s8 integration (LLM pre-prompt asset injection) | `s8_scene_json.py` | — | indirect | **IMPLEMENTED** | **VERIFIED** (no LLM schema changes) |
| Asset API (13 endpoints) | `api/assets.py` | — | **test_pipeline_integration_65.py** (4 HTTP tests) | **IMPLEMENTED** | **VERIFIED (Prompt 6.5)** |
| Asset HTTP routing verification | FastAPI TestClient | — | test_pipeline_integration_65.py | **IMPLEMENTED** | **VERIFIED (Prompt 6.5)** |
| Asset inspection UI | — | `/jobs/[id]/assets/page.tsx` | NONE | **IMPLEMENTED** | none |
| AssetReference → SceneDefinition bridge | `schemas/asset.py` | — | test_pipeline_integration_65.py | **IMPLEMENTED** | **VERIFIED (Prompt 6.5)** |
| Canonical Asset ID integrity check (s9) | `s9_validate.py` | — | test_pipeline_integration_65.py | **IMPLEMENTED** | **VERIFIED (Prompt 6.5)** |
| End-to-end vertical pipeline fixture | integration test | — | test_pipeline_integration_65.py | **IMPLEMENTED** | **VERIFIED (Prompt 6.5)** |
| Render smoke test (real MP4) | `scripts/render_smoke_test.py` | `renderer/src/render_cli.tsx`, `smoke_entry.tsx` | manual driver | **IMPLEMENTED** | **VERIFIED (Prompt 6.5, 51.8 KB MP4)** |
| Renderer Asset adapter | `renderer/src/lib/assetAdapter.ts` | — | manual smoke test only | **IMPLEMENTED** | PARTIAL (Provider bridging in P7) |
| **Animation Engine** | — | — | — | MISSING | PROMPT 7 (P6.5 verified integration first) |
| **Vertical reframe (9:16)** | heuristic | — | — | **PARTIAL** | COMPARISON beats flagged; full reframe in renderer |

## Assets / Audio

| feature | backend | frontend | tests | status | known limitation |
|---|---|---|---|---|---|
| DALL-E backgrounds | `dalle_image.py:66` | indirect | NONE | IMPLEMENTED | UNVERIFIED |
| Placeholder backgrounds | `placeholder_image.py:72` | indirect | indirect | IMPLEMENTED | visually inert |
| ElevenLabs TTS | `elevenlabs_tts.py:87` | — | NONE | IMPLEMENTED | UNVERIFIED |
| gTTS fallback | `gtts_tts.py:73` | — | NONE | IMPLEMENTED | uniform word alignment |
| Word timestamps | `s7_narration.py` | indirect via captions | NONE | IMPLEMENTED | UNVERIFIED |
| **SFX playback** | — | — | — | MISSING | see `docs/TECHNICAL_DEBT.md` C-004 |
| **Music playback** | — | — | — | MISSING | see `docs/TECHNICAL_DEBT.md` C-004 |

## Renderer

| feature | backend | frontend | tests | status | known limitation |
|---|---|---|---|---|---|
| Title scene | `TitleScene.tsx` | — | NONE | IMPLEMENTED | UNVERIFIED |
| Narration scene | `NarrationScene.tsx` | — | NONE | IMPLEMENTED | UNVERIFIED; ignores `overlay_text[]` |
| Diagram scene | `DiagramScene.tsx` | — | NONE | IMPLEMENTED | UNVERIFIED |
| Transition scene | `TransitionScene.tsx` | — | NONE | IMPLEMENTED | minimal |
| Documentary composition | `Documentary.tsx` | — | NONE | IMPLEMENTED | UNVERIFIED |
| Camera pan/zoom | `Camera.tsx` | — | NONE | IMPLEMENTED | UNVERIFIED |
| Word-by-word captions | `Caption.tsx` | — | NONE | IMPLEMENTED | UNVERIFIED |
| Animated character | `Character.tsx` | — | NONE | IMPLEMENTED | UNVERIFIED; stick-figure (L-019) |
| SVG props | `Props.tsx` | — | NONE | IMPLEMENTED | UNVERIFIED |
| **Smoke entry composition** | `smoke_entry.tsx` (NEW, P6.5) | — | `scripts/render_smoke_test.py` | **IMPLEMENTED** | **VERIFIED (Prompt 6.5, real MP4)** |
| **Render CLI subprocess** | `render_cli.tsx` (NEW, P6.5) | — | `scripts/render_smoke_test.py` | **IMPLEMENTED** | **VERIFIED (Prompt 6.5)** |
| **Audio playback (sfx/music)** | — | — | — | MISSING | C-004 |
| **Character.name/.description rendering** | — | — | — | MISSING | C-005 |
| **Environment.mood-based lighting** | — | — | — | MISSING | C-005 |

## Distribution

| feature | backend | frontend | tests | status | known limitation |
|---|---|---|---|---|---|
| Render MP4 | `s10_render.py:49` (subprocess) | `<VideoPlayer>` | NONE | IMPLEMENTED | UNVERIFIED; 15-min timeout |
| Vertical Short | `s11_short.py:88` (FFmpeg) | indirect | NONE | IMPLEMENTED | UNVERIFIED |
| **Auto-thumbnail** | — | — | — | MISSING | future |
| **YouTube publishing** | — | — | — | MISSING | future |
| **Analytics** | — | — | — | MISSING | future |

## Cross-cutting

| feature | backend | frontend | tests | status | known limitation |
|---|---|---|---|---|---|
| Auth | — | — | — | MISSING | local dev only |
| Multi-user | — | — | — | MISSING | future |
| Database | `db/store.py:130` (file-based JSON) | — | NONE | IMPLEMENTED | not concurrent-safe |
| Queue (Celery / Redis) | — | — | — | MISSING | `docker-compose.yml` declares Redis but unused (C-006) |
| Object storage (S3/OSS) | — | — | — | MISSING | local filesystem only |
| Secrets management | `.env` (gitignored) | — | NONE | IMPLEMENTED | dev only |

## Coverage summary

| category | implemented | partial | missing | planned |
|---|---|---|---|---|
| Job lifecycle | 4 | 0 | 1 | 0 |
| Research | 14 | 2 | 3 | 0 |
| Script | 4 | 0 | 0 | 0 |
| Story | 1 | 0 | 0 | 0 |
| Storyboard | 10 | 1 | 2 | 0 |
| Assets / audio | 5 | 0 | 2 | 0 |
| Renderer | 9 | 0 | 3 | 0 |
| Distribution | 2 | 0 | 3 | 0 |
| Cross-cutting | 2 | 0 | 4 | 0 |
| **Total** | **51** | **3** | **18** | **0** |

If a feature's status moves from MISSING to IMPLEMENTED, update this
matrix AND `docs/PROJECT_STATE.md` AND `docs/CHANGELOG_INTERNAL.md` in the
same change.


## PROMPT 7 — Animation Engine & Motion Runtime

| Feature | Status | Verification |
|---|---|---|
| AnimationPlan canonical contract | VERIFIED | test_animation_contract.py (16 tests) |
| AnimationCompiler (validate/normalize/resolve) | VERIFIED | test_animation_compiler.py (15 tests) |
| Action Mapper (narrative to canonical clip) | VERIFIED | test_animation_character_prop.py (18 tests) |
| Interpolation (linear/ease_in/ease_out/ease_in_out/hold) | VERIFIED | test_animation_interpolation.py (22) + TS (18) |
| Deterministic frame state computation | VERIFIED | test_animation_determinism.py (6) + TS runtime.test.ts (16) |
| Golden frame tests (frames 0/15/30/60/90) | VERIFIED | golden.test.ts (25 tests) |
| AnimatedCharacter (pose, position, scale, rotation, opacity) | VERIFIED | runtime.test.ts |
| AnimatedProp (position, scale, rotation, opacity, interaction) | VERIFIED | runtime.test.ts |
| AnimatedCamera (pan, zoom, easing) | VERIFIED | runtime.test.ts |
| Character Prop interaction (PropAnchor attach/detach) | VERIFIED | runtime.test.ts |
| Walk cycle (deterministic phase, bob, stride) | VERIFIED | runtime.test.ts |
| Conflict resolution (priority + track_id) | VERIFIED | runtime.test.ts |
| Documentary.tsx fs-free adapter path (L-021) | VERIFIED | TypeScript compile + render artifact |
| Audio cue wiring (sfx[]/music, gain_db) | VERIFIED | AudioCue.tsx |
| AssetReference.renderer_hints consumed (C-036) | VERIFIED | assetAdapter.test.ts |
| Renderer Vitest setup | VERIFIED | 71 tests passing |
| Animation smoke test (real MP4) | VERIFIED | scripts/animation_smoke_test.py (7.9 KB, 6s, exit 0) |
| E2E Storyboard to AnimationPlan to MP4 | VERIFIED | test_animation_e2e.py (2 passed + 1 slow) |

---

## PROMPT 8 — Voice / TTS / Audio Intelligence Layer

| Feature | Status | Verification |
|---|---|---|
| **VoiceDefinition canonical schema** | **VERIFIED** | test_voice_schemas.py (12) |
| **VoiceLifecycle (DRAFT→VALIDATED→APPROVED→ACTIVE→DEPRECATED→ARCHIVED)** | **VERIFIED** | test_voice_lifecycle.py |
| **VoiceRegistry (register/lookup/search/find_by_*)** | **VERIFIED** | test_voice_registry.py |
| **VoiceResolver (explicit → project default → compatible language → mock fallback)** | **VERIFIED** | test_voice_resolver.py |
| **VoiceResolver audit log (ResolutionEvent)** | **VERIFIED** | test_voice_resolver.py + pipeline |
| **TTSProvider abstraction (VoiceTTSProvider)** | **VERIFIED** | test_voice_provider_base.py |
| **MockTTSProvider (deterministic stdlib `wave`)** | **VERIFIED** | test_voice_mock_tts.py |
| **Provider factory (select_provider + LegacyProviderAdapter)** | **VERIFIED** | test_voice_provider_factory.py |
| **Content-addressed VoiceTTSCache** | **VERIFIED** | test_voice_cache.py |
| **Canonical AudioArtifact** | **VERIFIED** | test_voice_audio_artifact.py |
| **AudioValidator (file, format, duration, decodeability)** | **VERIFIED** | test_voice_audio_validator.py |
| **NarrationScript adapter (Script + StoryboardPackage)** | **VERIFIED** | test_voice_narration.py |
| **SpeechTiming (word-level timestamps + TimestampSource)** | **VERIFIED** | test_voice_timing.py |
| **NarrationTimeline (script + artifact + timing → scene timing)** | **VERIFIED** | test_voice_timeline.py |
| **Duration reconciliation policies** | **VERIFIED** | test_voice_timeline.py |
| **PronunciationHint / EmphasisHint (canonical, provider-agnostic)** | **VERIFIED** | test_voice_pronunciation.py |
| **TTS pipeline (run_tts_pipeline: idempotent + audit)** | **VERIFIED** | test_voice_pipeline.py |
| **Voice failure paths (unknown voice, unsupported lang, empty text, corrupt audio)** | **VERIFIED** | test_voice_failures.py |
| **Secrets not in artifacts (§42)** | **VERIFIED** | test_voice_e2e.py |
| **Cross-runtime contract (TS mirrors Python)** | **VERIFIED** | crossRuntime.test.ts (6) |
| **CanonicalAudioLibrary (artifact_id → validated URI)** | **VERIFIED** | audioLib.test.ts (12) |
| **AudioCue plays canonical narration audio** | **VERIFIED** | AudioCue.tsx + smoke |
| **Renderer TS types mirror Python schemas** | **VERIFIED** | types.ts + crossRuntime.test.ts |
| **Scene-narration timing helpers** | **VERIFIED** | timeline.test.ts (13) |
| **Real narration MP4 with audio (ffprobe verified)** | **VERIFIED** | scripts/voice_audio_smoke_test.py (166 KB, h264 + aac, 4.05s) |
| **E2E Story → NarrationScript → TTS → Audio → Scene → MP4** | **VERIFIED** | test_voice_e2e.py (8) + smoke script |
| ElevenLabs TTS (via LegacyProviderAdapter) | IMPLEMENTED | UNVERIFIED (no API key in CI) |
| gTTS (via LegacyProviderAdapter) | IMPLEMENTED | UNVERIFIED (no network in CI) |
| Forced alignment provider | STUBBED | TimestampSource.UNAVAILABLE when no provider-native |
| Loudness normalization | DEFERRED | Extension point in AudioArtifact metadata |

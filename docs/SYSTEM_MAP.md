# SYSTEM_MAP

A directory tour of the actual codebase. All entries cite `file:line` so a
future AI can verify.

## Repository Root

```
c:\Users\Administrator\Downloads\videoAI\
├── README.md                      Chinese project docs (348 lines)
├── .env.example                   60 lines — documented env vars
├── .gitignore                     51 lines — Python/Node/IDE ignores
├── docker-compose.yml             25 lines — optional redis + postgres (UNUSED)
├── start.bat                      32 lines — Windows launcher (webapp + orchestrator)
├── orchestrator/                  Python backend
├── renderer/                      Remotion v4 renderer
├── webapp/                        Next.js 14 console
├── workspace/                     Per-job artifacts (gitignored)
├── plans/                         Plan and final-report files
└── docs/                          Project-memory governance docs (NEW)
```

## orchestrator/ (Python, FastAPI)

Entry point: `orchestrator/app/main.py` (FastAPI app).

```
orchestrator/
├── requirements.txt               21 lines — fastapi, uvicorn, pydantic, openai, httpx, gtts, pydub, duckduckgo-search, bs4, pytest
├── pyproject.toml                 40 lines — ruff config (line-length=100, py311)
├── pytest.ini                     3 lines — testpaths=tests, asyncio_mode=auto
├── app/
│   ├── __init__.py                Package marker
│   ├── main.py                    FastAPI app, mounts jobs + research + assets routers
│   ├── core/
│   │   ├── config.py              120 lines — Pydantic Settings
│   │   ├── paths.py               50 lines — job_dir, stage_path, atomic write_json
│   │   └── logging.py             50 lines — configure_logging, get_logger
│   ├── db/
│   │   └── store.py               130 lines — file-based JSON job store
│   ├── schemas/
│   │   ├── job.py                 53 lines — JobStatus, StageStatus, JobCreateRequest
│   │   ├── script.py              61 lines — Thesis, TitlePackage, Script, Storyboard
│   │   ├── research.py            22 lines — legacy ResearchPackage (compat)
│   │   ├── research_package.py    454 lines — canonical 17-section ResearchPackage
│   │   └── scene_definition.py    288 lines — strict renderer contract
│   ├── pipeline/
│   │   ├── runner.py              83 lines — STAGES list, run_job()
│   │   ├── cache.py               26 lines — should_skip()
│   │   └── stages/
│   │       ├── base.py            26 lines — Stage ABC, StageContext
│   │       ├── s1_research.py     76 lines — ResearchStage (calls Research Engine)
│   │       ├── s2_thesis.py       57 lines — ThesisStage
│   │       ├── s3_titles.py       52 lines — TitlesStage
│   │       ├── s4_script.py       64 lines — ScriptStage
│   │       ├── s5_storyboard.py   70 lines — StoryboardStage
│   │       ├── s6_assets.py       92 lines — AssetsStage (DALL-E / placeholder)
│   │       ├── s7_narration.py    52 lines — NarrationStage (TTS)
│   │       ├── s8_scene_json.py   132 lines — SceneJsonStage (LLM emits SceneDefinition)
│   │       ├── s9_validate.py     35 lines — ValidateStage (Pydantic)
│   │       ├── s10_render.py      49 lines — RenderStage (subprocess)
│   │       └── s11_short.py       88 lines — ShortsStage (FFmpeg 9:16)
│   ├── providers/
│   │   ├── base.py                132 lines — ABCs (LLM, TTS, Image, Search, Fetch) — LEGACY (P8: superseded by app.voice.provider_base)
│   │   ├── llm.py                 27 lines — get_llm_provider()
│   │   ├── openai_llm.py          103 lines — OpenAI GPT provider
│   │   ├── mock_llm.py            617 lines — MockLLMProvider with fixtures
│   │   ├── tts.py                 26 lines — get_tts_provider() — LEGACY
│   │   ├── elevenlabs_tts.py      87 lines — ElevenLabs provider — LEGACY wrapped by LegacyProviderAdapter
│   │   ├── gtts_tts.py            73 lines — Google TTS provider — LEGACY wrapped by LegacyProviderAdapter
│   ├── voice/  (NEW, PROMPT 8 — canonical Voice/TTS/Audio Intelligence Layer)
│   │   ├── __init__.py            public API
│   │   ├── schemas.py             Pydantic models: VoiceDefinition, VoiceInstance, VoiceRegistryEntry, NarrationScript, AudioArtifact, SpeechTiming, NarrationTimeline
│   │   ├── lifecycle.py           VoiceLifecycleStatus + transitions
│   │   ├── registry.py            VoiceRegistryManager (register/lookup/search/find_by_*/transition)
│   │   ├── resolver.py            VoiceResolver (policy-based, audit log)
│   │   ├── provider_base.py       VoiceTTSProvider abstract interface + errors
│   │   ├── mock_tts.py            MockTTSProvider (deterministic stdlib wave)
│   │   ├── provider_factory.py    select_provider + LegacyProviderAdapter
│   │   ├── audio_artifact.py      AudioArtifact creation + SHA-256 fingerprint
│   │   ├── audio_validator.py     AudioValidator (file/format/duration/decodeability)
│   │   ├── cache.py               VoiceTTSCache (content-addressed)
│   │   ├── narration.py           build_narration_script adapter
│   │   ├── pronunciation.py       PronunciationHint + EmphasisHint (canonical)
│   │   ├── timing.py              build_speech_timing (word timestamps)
│   │   ├── timeline.py            build_timeline + reconcile_duration
│   │   └── pipeline.py            run_tts_pipeline (high-level orchestrator)
│   │   ├── image.py               24 lines — get_image_provider()
│   │   ├── dalle_image.py         66 lines — DALL-E 3 provider
│   │   ├── placeholder_image.py   72 lines — deterministic PNG fallback
│   │   ├── research_providers.py  200 lines — DuckDuckGo + httpx fetch
│   │   └── mock_research.py       140 lines — Mock search + fetch
│   ├── research/
│   │   ├── __init__.py            12 lines — exports ResearchEngine, ResearchContext, ResearchCache, ResearchLogger
│   │   ├── engine.py              1114 lines — 13-step engine
│   │   ├── cache.py               111 lines — SHA-256/16-char keys, TTL eviction
│   │   └── logging.py             174 lines — JSON event log helpers
│   ├── story/
│   │   ├── engine.py              ~2700 lines — 16-step Story Intelligence Engine
│   │   └── cache.py               ~110 lines — content-addressed cache
│   ├── storyboard/                (NEW, PROMPT 4)
│   │   ├── engine.py              ~1900 lines — Storyboard Intelligence Engine (visual decomposition, beats, camera, motion, transition, continuity, evidence, quality)
│   │   └── cache.py               ~110 lines — content-addressed cache (segment/mode/assets/continuity/camera/package)
│   ├── character/                 (NEW, PROMPT 5)
│   │   ├── engine.py              ~900 lines — CharacterSystemEngine (resolution, deduplication, versioning, quality scoring)
│   │   ├── cache.py              ~120 lines — content-addressed cache (character_package/definition/pose/expression/wardrobe/quality)
│   │   └── svg_generator.py       ~600 lines — deterministic SVG (8 poses, 11 expressions, validation)
│   ├── assets/                   (NEW, PROMPT 6) — Environment/Prop/Asset Unified Intelligence
│   │   ├── engine.py             ~1000 lines — AssetSystemEngine + AssetResolver (single canonical resolution path)
│   │   ├── cache.py              ~330 lines — content-addressed cache (SHA-256/16-char fingerprint)
│   │   ├── security.py           ~100 lines — SVG validation, path traversal, MIME checks
│   │   ├── provider.py           ~110 lines — AssetProvider abstraction (generate_image/generate_svg/validate/describe)
│   │   └── s6_bridge.py          ~140 lines — backward-compatible bridge for s6_assets.py
│   ├── api/
│   │   ├── jobs.py                58 lines — POST /jobs, GET /jobs, GET /jobs/{id}
│   │   ├── research.py            196 lines — /research/{id}/package|sources|claims|contradictions|quality, /review/*
│   │   ├── story.py               ~115 lines — /story/{id}/package|thesis|angles|titles|script|critique|quality|approve|reject
│   │   ├── storyboard.py          (NEW) — /storyboard/{id}/package|beats|assets|quality|continuity|preview|approve|reject|regenerate
│   │   ├── assets.py              44 lines — GET /jobs/{id}/artifacts/{name} (artifact streaming)
│   │   ├── assets.py              (NEW, PROMPT 6) — /api/assets/* — 13 routes for asset registry/resolution/quality/approve/deprecate
│   │   └── characters.py          (NEW, PROMPT 5) — /api/characters/{job_id}/* — 14 character routes
│   └── tools/                     Project audit tool
│       ├── __init__.py            Package marker
│       ├── project_audit.py       Non-destructive audit
│       └── README.md              How to run
└── tests/
    ├── __init__.py                Package marker
    ├── test_mock_providers.py     71 lines — fixture + JSON round-trip
    ├── test_scene_definition.py   87 lines — contiguity, refs, timing, enums
    ├── test_pipeline_integration.py  57 lines — full s1–s9 against mocks
    ├── test_research_engine.py    806 lines — 34 tests covering Engine + schema
    ├── test_story_engine.py      ~300 lines — story + script schema + engine
    ├── test_storyboard_engine.py ~1100 lines — 62 tests for Storyboard Intelligence Engine
    ├── test_character_system.py  ~700 lines — 103 tests for Character System
    ├── test_asset_system.py      ~900 lines — 105 tests for Asset System
    └── test_pipeline_integration_65.py  ~600 lines (NEW, PROMPT 6.5) — 26 integration tests (vertical slice, character/env/prop flow, s6/s8, cache idempotency, HTTP API, failure paths, SVG security)
```

Top-level scripts/ directory (NEW, PROMPT 6.5):

```
scripts/
└── render_smoke_test.py  ~120 lines — real renderer smoke test driver
```

## renderer/ (Remotion v4 + TypeScript)

Entry point: `renderer/src/index.ts` (CLI).

```
renderer/
├── package.json                  25 lines — @remotion/* ^4.0, react, remotion
├── remotion.config.ts            5 lines — JPEG output, overwrite, concurrency=1
├── tsconfig.json                 20 lines — ES2022, strict, jsx=react-jsx, noUnusedLocals=false
├── README.md                     31 lines — developer docs
└── src/
    ├── index.ts                  112 lines — CLI: loads job, runs renderMedia → MP4
    ├── Root.tsx                  63 lines — composition registry (with registerRoot, PROMPT 6.5)
    ├── lib/
    │   ├── loadScene.ts          55 lines — loadSceneDefinition(jobDir)
    │   ├── assetAdapter.ts       ~230 lines (NEW, PROMPT 6.5) — fs-free AssetReference → renderer adapter
    │   ├── assetAdapterLoader.ts ~50 lines (NEW, PROMPT 6.5) — Node.js loader (the only module with fs/path)
    │   ├── audioLibrary.ts      ~60 lines (NEW, PROMPT 7) — Node-side audio path resolver (fs-only)
    ├── voice/  (NEW, PROMPT 8)
    │   ├── types.ts             ~250 lines — TypeScript mirror of Python pydantic schemas
    │   ├── audioLib.ts          ~150 lines — CanonicalAudioLibrary (artifact_id → validated URI)
    │   ├── timeline.ts          ~60 lines — NarrationTimeline helpers (scene offsets, active entry)
    │   ├── index.ts             ~10 lines — public exports
    ├── animation/
    │   ├── interpolation.ts     ~120 lines (NEW, PROMPT 7) — canonical interpolation math (linear/ease_in/ease_out/ease_in_out/hold)
    │   ├── runtime.ts           ~350 lines (NEW, PROMPT 7) — AnimationPlan types + computeFrameState + conflict resolution
    │   ├── index.ts            ~10 lines (NEW, PROMPT 7) — fs-free public surface
    │   ├── interpolation.test.ts  ~200 lines (NEW, PROMPT 7) — 18 tests
    │   ├── runtime.test.ts       ~300 lines (NEW, PROMPT 7) — 16 tests
    │   └── golden.test.ts        ~200 lines (NEW, PROMPT 7) — 25 golden frame tests
    ├── compositions/
    │   └── Documentary.tsx       ~95 lines — main composition (PROMPT 7: uses AnimationDriver, DocumentaryAudio, fs-free adapter)
    ├── render_cli.tsx            ~60 lines (NEW, PROMPT 6.5) — dedicated CLI entry for smoke testing (uses assetAdapterLoader)
    ├── render_animation_smoke.tsx ~100 lines (NEW, PROMPT 7) — animation smoke test CLI (loads plan + adapter + renders)
    ├── smoke_entry.tsx           ~90 lines (NEW, PROMPT 6.5) — minimal fs-free Remotion entry for smoke testing
    ├── animation_smoke_entry.tsx ~70 lines (NEW, PROMPT 7) — animation smoke test Remotion composition
    ├── scenes/
    │   ├── types.ts              150 lines — TS mirror of Python SceneDefinition
    │   ├── SceneRenderer.tsx     49 lines — kind → component switch
    │   ├── TitleScene.tsx        32 lines
    │   ├── NarrationScene.tsx    85 lines — character actors + word captions
    │   ├── DiagramScene.tsx      67 lines — props + overlay
    │   └── TransitionScene.tsx   49 lines — opacity fade
    └── components/
        ├── Camera.tsx            56 lines — pan/zoom wrapper
        ├── AnimatedCamera.tsx    ~80 lines (NEW, PROMPT 7) — camera from AnimationPlan (pan/zoom/easing)
        ├── AnimatedCharacter.tsx ~90 lines (NEW, PROMPT 7) — character from AnimationPlan (pose/position/scale/rotation)
        ├── AnimatedProp.tsx     ~80 lines (NEW, PROMPT 7) — prop from AnimationPlan (position/anchor attachment)
        ├── AnimationDriver.tsx ~150 lines (NEW, PROMPT 7) — orchestrates AnimatedCharacter/AnimatedProp/AnimatedCamera per scene
        ├── AudioCue.tsx       ~110 lines (NEW, PROMPT 7) — Scene.sfx[] and Scene.music wired to Remotion <Audio>
        ├── Caption.tsx           71 lines — word-by-word highlight
        ├── Character.tsx         129 lines — stick-figure SVG (8 poses)
        └── Props.tsx             137 lines — 12 SVG prop renderers
```

## webapp/ (Next.js 14 + React 18)

Entry point: `webapp/app/page.tsx`.

```
webapp/
├── package.json                  25 lines — next ^14.1, react ^18.2
├── next.config.js                15 lines — rewrite /api/* → :8000
├── tailwind.config.ts            19 lines — color palette
├── postcss.config.js             6 lines
├── tsconfig.json                 16 lines — @/* path alias, strict
└── app/
    ├── globals.css               9 lines — Tailwind base, dark theme
    ├── layout.tsx                16 lines — root layout
    ├── page.tsx                  14 lines — home with TopicForm
    └── jobs/
        ├── page.tsx              25 lines — JobsList
        └── [id]/page.tsx         47 lines — detail page, polls every 2500ms
└── components/
    ├── TopicForm.tsx             89 lines — form + 4 example topics
    ├── JobsList.tsx              36 lines
    ├── StageTimeline.tsx         154 lines — 11-stage ordered list
    └── VideoPlayer.tsx           5 lines — <video controls>
└── lib/
    └── api.ts                    56 lines — typed fetch client
```

## workspace/ (per-job artifacts, gitignored)

```
workspace/
└── {job_id}/
    ├── job.json                  JobDetail snapshot
    ├── research.json             legacy ResearchPackage (compat)
    ├── research_package.json     canonical ResearchPackage
    ├── research_cache/           SHA-256/16-char-keyed cache entries
    ├── research.log              JSON event log
    ├── thesis.json
    ├── titles.json
    ├── script.json
    ├── storyboard.json
    ├── storyboard_package.json  (PROMPT 4) — canonical StoryboardPackage v1
    ├── storyboard_cache/        (PROMPT 4) — SHA-256/16-char-keyed cache entries
    ├── character_system_package.json (PROMPT 5) — canonical CharacterSystemPackage
    ├── character_cache/        (PROMPT 5) — SHA-256/16-char-keyed cache entries
    ├── asset_system_package.json  (PROMPT 6) — canonical AssetSystemPackage (Environment/Prop/Asset)
    ├── asset_cache/            (PROMPT 6) — content-addressed cache (asset_type/asset_id/version)
    ├── registry.json           (PROMPT 6) — AssetRegistry (cross-project asset index)
    ├── scenes/                   LLM-emitted intermediate scene data
    ├── backgrounds/              PNG backgrounds from s6
    ├── characters/            (PROMPT 5) — per-character SVG asset packages
    ├── environments/          (PROMPT 6) — per-environment asset packages
    ├── props/                 (PROMPT 6) — per-prop asset packages
    ├── narration.mp3             s7 TTS output
    ├── narration.words.json      s7 word timestamps
    ├── scene_definition.json     s8 strict contract output
    ├── output.mp4                s10 render result
    └── shorts/
        └── short.mp4             s11 vertical clip
```

## plans/ and docs/

- `plans/_FINAL_REPORT_TEMPLATE.md` (63 lines) — template appended to every plan.
- `docs/PROJECT_CONTEXT.md` (NEW).
- `docs/PROJECT_STATE.md` (NEW).
- `docs/ARCHITECTURE.md` (NEW).
- `docs/ARCHITECTURE_DECISIONS.md` (NEW).
- `docs/SYSTEM_MAP.md` (NEW, this file).
- `docs/DATA_CONTRACTS.md` (NEW).
- `docs/API_CONTRACTS.md` (NEW).
- `docs/PROVIDER_REGISTRY.md` (NEW).
- `docs/PIPELINE_REGISTRY.md` (NEW).
- `docs/DEPENDENCY_GRAPH.md` (NEW).
- `docs/FEATURE_MATRIX.md` (NEW).
- `docs/TECHNICAL_DEBT.md` (NEW).
- `docs/KNOWN_LIMITATIONS.md` (NEW).
- `docs/CHANGELOG_INTERNAL.md` (NEW).
- `docs/TEST_STATUS.md` (NEW).
- `docs/SAFE_CHANGE_RULES.md` (NEW).

## Notes for AI Sessions

- The repo is **not a git repository**. Do not run `git log`, `git diff`,
  or similar commands; they will fail. See `docs/TECHNICAL_DEBT.md` C-008.
- Python is **not installed** on the development host. Tests are BLOCKED.
  See `docs/TEST_STATUS.md`.
- `docker-compose.yml` declares services the code does not use. See
  `docs/TECHNICAL_DEBT.md` C-006.

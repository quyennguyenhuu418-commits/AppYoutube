

## PROMPT 7 — Animation System

New files added to the system map:

Python (orchestrator):
    app/animation/
        __init__.py            — public surface (re-exports)
        schemas.py             — canonical animation schemas
        compiler.py            — validate / normalize / resolve
        builder.py             — StoryboardPackage -> AnimationPlan
        action_mapper.py       — narrative verb -> canonical clip
        interpolation.py       — canonical interpolation math

TypeScript (renderer):
    src/animation/
        interpolation.ts        — canonical interpolation math (mirrors Python)
        runtime.ts            — AnimationPlan types + computeFrameState
        index.ts             — fs-free public surface
    src/components/
        AnimatedCharacter.tsx  — animated character from AnimationPlan
        AnimatedProp.tsx       — animated prop from AnimationPlan
        AnimatedCamera.tsx      — animated camera from AnimationPlan
        AnimationDriver.tsx    — orchestrates per-scene animation
        AudioCue.tsx           — Scene.sfx[] and Scene.music wiring
    src/lib/
        audioLibrary.ts        — Node-side audio path resolver (fs-only)

Renderer CLI:
    src/render_animation_smoke.tsx   — animation smoke test CLI
    src/animation_smoke_entry.tsx    — animation smoke test Remotion composition

New reverse-dependencies (PROMPT 7):
    animation_plan.json     produced by: AnimationPlanBuilder  consumed by: renderer (via inputProps)
    CharacterSystemPackage consumed by: AnimationCompiler (anchor validation)

## Animation Runtime Boundary

    orchestrator: AnimationPlanBuilder --> AnimationPlan (JSON)
                           AnimationCompiler (validate)
    renderer (bundle): loadAssetAdapter() --> AssetAdapter
                             computeFrameState() --> CharacterFrameState
                             AnimatedCharacter --> Character (SVG)
                             AnimatedProp --> PropRenderer
                             AnimatedCamera --> Camera wrapper
                             DocumentaryAudio --> Remotion <Audio>
# DEPENDENCY_GRAPH

Cross-system dependencies. Edges represent "X produces artifact consumed
by Y". Only include edges actually present in code.

## Stage-to-Stage Artifact Flow

```mermaid
flowchart LR
    subgraph S1toS5["Research & Script"]
        s1[s1_research]:::partial --> s2[s2_thesis]
        s2 --> s3[s3_titles]
        s1 --> s3
        s3 --> s4[s4_script]
        s4 --> s5[s5_storyboard]
        s1 --> s5
    end
    subgraph S6toS9["Assets & Scene Definition"]
        s5 --> s6[s6_assets]
        s5 --> s8[s8_scene_json]
        s5 --> AssetEngine["AssetSystem (P6)"]
        AssetEngine --> s6
        AssetEngine --> s8
        s6 --> s8
        s4 --> s7[s7_narration]
        s7 --> s8
        s8 --> s9[s9_validate]
        s9 -.retry once.-> s8
    end
    subgraph S10toS11["Render & Shorts"]
        s9 --> s10[s10_render]
        s10 --> s11[s11_short]
    end
    classDef partial fill:#ffc,stroke:#660
```

## Data Contract Flow

```mermaid
flowchart LR
    JobDetail["JobDetail (job.json)"] --> s1
    ResearchPkg["ResearchPackage (research_package.json)"]
    ResearchPkg -.to_legacy_dict.-> Legacy["ResearchPackage legacy (research.json)"]
    Legacy --> s2
    s2 --> Thesis["Thesis (thesis.json)"]
    Thesis --> s3
    s3 --> TitlePkg["TitlePackage (titles.json)"]
    TitlePkg --> s4
    Thesis --> s4
    s4 --> Script["Script (script.json)"]
    Script --> s5
    Script --> s7
    Thesis --> s5
    ResearchPkg --> s5
    s5 --> Storyboard["Storyboard (storyboard.json)"]
    s5 --> SBpkg["StoryboardPackage (storyboard_package.json)"]
    Storyboard --> s6
    Storyboard --> s8
    Script --> s8
    s7 --> Words["WordTimestamps (narration.words.json)"]
    Words --> s8
    SBpkg --> AssetEngine["AssetSystem (P6)"]
    AssetEngine --> AssetPkg["AssetSystemPackage (asset_system_package.json)"]
    AssetPkg -.prepend canonical IDs.-> s8
    AssetPkg -.additive.-> s6
    s8 --> SceneDef["SceneDefinition (scene_definition.json)"]
    SceneDef --> s9
    s9 --> s10
    s10 --> MP4["output.mp4"]
    MP4 --> s11
    s11 --> Short["shorts/short.mp4"]
```

## Module-level Imports

Source: `orchestrator/app/pipeline/runner.py`.

```mermaid
flowchart LR
    Runner["runner.run_job"]
    Runner --> S1["s1_research.ResearchStage"]
    Runner --> S2["s2_thesis.ThesisStage"]
    Runner --> S3["s3_titles.TitlesStage"]
    Runner --> S4["s4_script.ScriptStage"]
    Runner --> S5["s5_storyboard.StoryboardStage"]
    Runner --> S6["s6_assets.AssetsStage"]
    Runner --> S7["s7_narration.NarrationStage"]
    Runner --> S8["s8_scene_json.SceneJsonStage"]
    Runner --> S9["s9_validate.ValidateStage"]
    Runner --> S10["s10_render.RenderStage"]
    Runner --> S11["s11_short.ShortsStage"]
    Runner --> Store["db.store"]
    Runner --> Base["stages.base.StageContext"]
```

## Provider Dependencies

```mermaid
flowchart LR
    S1 --> RE["research.ResearchEngine"]
    RE --> LLM["providers.LLMProvider"]
    RE --> Search["providers.SearchProvider"]
    RE --> Fetch["providers.ContentFetchProvider"]
    RE --> Cache["research.ResearchCache"]
    RE --> Log["research.ResearchLogger"]
    S2 --> LLM
    S3 --> LLM
    S4 --> LLM
    S5 --> LLM
    S6 --> Img["providers.ImageProvider"]
    S7 --> TTS["providers.TTSProvider"]
    S8 --> LLM
    S9 --> Schema["schemas.SceneDefinition"]
    S10 --> Node["npx tsx (subprocess)"]
    S11 --> FFmpeg["system ffmpeg"]
    Character["character.CharacterSystemEngine"] --> SB["schemas.StoryboardPackage"]
    Character --> SD["schemas.SceneDefinition"]
    Character --> Cache["character.CharacterCache"]
    CharRef["character.CharacterReferenceSpecification"] --> KCtx["knowledge.KnowledgeContext"]
    CharRef --> KRes["knowledge.KnowledgeResolver"]
    CharAdapter["character.KnowledgeCharacterAdapter"] --> CharRef
    CharAdapter --> KCtx
    CharAdapter --> KRes
    CharAdapter --> SB
    Prompt["prompt.PromptCompiler"] --> CharRef
    Prompt --> KCtx
    Prompt --> KRes
    Prompt --> VG["knowledge.VisualGrammar"]
    PromptAdapter["prompt.KnowledgePromptAdapter"] --> KCtx
    PromptAdapter --> KRes
    PromptAdapter --> Prompt
    PromptVal["prompt.PromptValidator"] --> Prompt
    CMS["prompt.CameraMotionSoundCompiler"] --> KCtx
    CMS --> KRes
    CMS --> CharRef
    CMS --> Prompt
    CMSAdapter["prompt.KnowledgeCameraMotionSoundAdapter"] --> KCtx
    CMSAdapter --> KRes
    CMSAdapter --> CMS
    CMSVal["prompt.CameraMotionSoundValidator"] --> CMS
    ProviderAdapter["prompt.ProviderPromptAdapter"] --> Prompt
    ProviderAdapter -.-> "ADAPTED, NOT IMPORTED"| GoogleFlow["prompt.GoogleFlowPromptAdapter (reference)"]
    AssetSys["assets.AssetSystemEngine"] --> SB
    AssetSys --> CharPkg["schemas.CharacterSystemPackage"]
    AssetSys --> AssetRef["schemas.AssetReference"]
    AssetSys --> AssetCache["assets.AssetCache"]
    AssetSys --> AssetSec["assets.security"]
    AssetSys --> AssetProv["assets.provider"]
```

## Cross-Runtime Boundary

```mermaid
flowchart LR
    Python["Python orchestrator"] -- scene_definition.json + asset_system_package.json + narration.mp3 --> Node["Remotion renderer (Node)"]
    Node -- output.mp4 --> Python
```

This is the **single cross-runtime contract** in the system. Any change to
`SceneDefinition` is a breaking change unless coordinated with the TS
mirror (`renderer/src/scenes/types.ts`).

### Asset Adapter (PROMPT 6.5)

```mermaid
flowchart LR
    AssetRef["AssetReference (Python schema)"] --> SceneDef["SceneDefinition (cross-runtime)"]
    SceneDef --> AssetAdapter["assetAdapter.ts (fs-free)"]
    AssetAdapter --> Renderer["renderer components"]
```

`assetAdapter.ts` is the fs-free bridge between `AssetReference` and
renderer components. It is safe to import from Remotion compositions
because it does not pull in `node:fs`. The Node.js-side loader
(`assetAdapterLoader.ts`) is used exclusively by `render_cli.tsx`.

## Cycle Detection

No import cycles detected in the orchestrator. The pipeline is a strict
DAG by construction (runner iterates `STAGES` linearly).

## Reverse-Dependencies (consumers)

| contract | produced by | consumed by |
|---|---|---|
| `research.json` (legacy) | s1 | s2, s3, s4, s5 |
| `research_package.json` (canonical) | s1 | `/research/*` API only (downstream stages do not yet consume it) |
| `thesis.json` | s2 | s3, s4 |
| `titles.json` | s3 | s4, webapp |
| `script.json` | s4 | s5, s7, s8 |
| `storyboard.json` | s5 | s6, s8 |
| `storyboard_package.json` | s5 | Character System (PROMPT 5), `/storyboard/*` API |
| `character_system_package.json` | CharacterSystemEngine | `/api/characters/*` API, future: s8 bridge |
| `narration.mp3` | s7 | s10, webapp |
| `narration.words.json` | s7 | s8 (word-by-word captions) |
| `asset_system_package.json` | AssetSystemEngine (P6) | s6 bridge, s8 asset injection, `/api/assets/*` API |
| `registry.json` | AssetSystemEngine (P6) | s9 validate (P6.5 asset integrity check) |
| `scene_definition.json` | s8, s9 (with asset integrity check) | s10 |
| `output.mp4` | s10 (verified smoke MP4 in P6.5) | s11, webapp |
| `shorts/short.mp4` | s11 | webapp |

---

## PROMPT 8 -- Voice / TTS / Audio Intelligence Layer

New files added to the system map:

Python (orchestrator):
    app/voice/
        __init__.py            -- public surface
        schemas.py             -- VoiceDefinition / NarrationScript / AudioArtifact / SpeechTiming / NarrationTimeline
        lifecycle.py           -- VoiceLifecycleStatus + transitions
        registry.py            -- VoiceRegistryManager
        resolver.py            -- VoiceResolver (policy + audit log)
        provider_base.py       -- VoiceTTSProvider interface + errors
        mock_tts.py            -- MockTTSProvider (deterministic stdlib wave)
        provider_factory.py    -- select_provider + LegacyProviderAdapter
        audio_artifact.py      -- AudioArtifact creation + SHA-256 fingerprint
        audio_validator.py     -- AudioValidator
        cache.py               -- VoiceTTSCache (content-addressed)
        narration.py           -- build_narration_script adapter
        pronunciation.py       -- PronunciationHint + EmphasisHint
        timing.py              -- build_speech_timing
        timeline.py            -- build_timeline + reconcile_duration
        pipeline.py            -- run_tts_pipeline

TypeScript (renderer):
    src/voice/
        types.ts               -- canonical types mirroring Python
        audioLib.ts            -- CanonicalAudioLibrary
        timeline.ts            -- scene-timing helpers
        index.ts               -- public exports
    src/render_audio_smoke.tsx -- narration audio smoke renderer

Scripts:
    scripts/voice_audio_smoke_test.py -- full vertical: TTS -> Remotion -> MP4 -> ffprobe

Tests:
    orchestrator/tests/test_voice_*.py -- 13 voice test modules (171 tests)
    orchestrator/tests/test_voice_e2e.py -- 8 E2E tests including ffprobe
    renderer/src/voice/*.test.ts -- 31 Vitest tests

Dependencies (new):
  * No new external runtime dependencies (stdlib `wave` only)
  * `ffprobe` (PATH) required for audio verification in smoke test

Producer/Consumer graph:
  Script -> build_narration_script -> NarrationScript
  NarrationScript -> VoiceResolver -> VoiceResolution
  VoiceResolution -> VoiceTTSProvider.synthesize() -> VoiceTTSResponse
  VoiceTTSResponse + voice -> write_audio_artifact() -> AudioArtifact
  AudioArtifact -> apply_validation_to_artifact() -> AudioArtifact (validated)
  Provider word_timestamps -> build_speech_timing() -> SpeechTiming
  (NarrationScript, AudioArtifact, SpeechTiming) -> build_timeline() -> NarrationTimeline
  NarrationTimeline -> renderer/voice/timeline.ts (scene offset helpers)
  NarrationTimeline -> renderer/voice/audioLib.ts (CanonicalAudioLibrary)
  CanonicalAudioLibrary -> AudioCue.tsx -> Remotion <Audio> -> MP4 audio stream
  MP4 -> ffprobe (stream + codec + duration verification)

No breaking changes to existing dependencies.


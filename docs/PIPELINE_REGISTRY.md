# PIPELINE_REGISTRY

Canonical stage registry. Source: `orchestrator/app/pipeline/runner.py`.
All 11 stages run sequentially in a single process.

Status values: `IMPLEMENTED`, `PARTIAL`, `NOT_IMPLEMENTED`.
Verification: `VERIFIED`, `UNVERIFIED`, `BLOCKED`.

---

## s1 — Research

| field | value |
|---|---|
| stage_id | `s1_research` |
| file | `orchestrator/app/pipeline/stages/s1_research.py` |
| class | `ResearchStage` |
| responsibility | run `ResearchEngine`, write `research.json` + `research_package.json` |
| input | `{ topic }` from `JobCreateRequest` |
| output | `workspace/{job_id}/research.json` (legacy), `research_package.json` (canonical) |
| dependencies | `ResearchEngine`, `LLMProvider`, `SearchProvider`, `ContentFetchProvider`, `ResearchCache` |
| cache | content-addressed via `ResearchCache` (SHA-256/16-char, TTL default 7d) |
| retry | none (cache hit short-circuits) |
| side effects | writes 2 JSON files + `research_cache/` + `research.log` |
| status | IMPLEMENTED |
| verification | UNVERIFIED (no Python on host; cannot execute) |
| tests | WRITTEN (34) in `test_research_engine.py`, BLOCKED |
| known issues | steps 7, 10, 11 are stubs (see `docs/TECHNICAL_DEBT.md` C-001/C-002) |
| next_action | future: implement contradiction detection + geography + quantitative |

---

## s2 — Thesis

| field | value |
|---|---|
| stage_id | `s2_thesis` |
| file | `orchestrator/app/pipeline/stages/s2_thesis.py:57` |
| class | `ThesisStage` |
| responsibility | run full Story Intelligence Engine, write story_package.json + legacy thesis.json |
| input | `research_package.json` (canonical) |
| output | `workspace/{job_id}/story_package.json` (canonical), `thesis.json` (legacy compat) |
| dependencies | `StoryEngine`, `LLMProvider`, `ResearchPackage` |
| cache | stage skip-cache (file-exists check) |
| retry | none |
| status | UPGRADED |
| verification | UNVERIFIED |
| tests | NONE |
| next_action | OK — see `docs/TECHNICAL_DEBT.md` C-013/C-014 |

---

## s3 — Titles

| field | value |
|---|---|
| stage_id | `s3_titles` |
| file | `orchestrator/app/pipeline/stages/s3_titles.py:52` |
| class | `TitlesStage` |
| responsibility | read story_package.json, write legacy titles.json (compat adapter) |
| input | `story_package.json` (canonical) |
| output | `workspace/{job_id}/titles.json` (`TitlePackage`) |
| dependencies | `StoryPackage` |
| status | COMPAT_ADAPTER |
| verification | UNVERIFIED |
| tests | NONE |
| next_action | OK |

---

## s4 — Script

| field | value |
|---|---|
| stage_id | `s4_script` |
| file | `orchestrator/app/pipeline/stages/s4_script.py:64` |
| class | `ScriptStage` |
| responsibility | read story_package.json, write legacy script.json (compat adapter) |
| input | `story_package.json` (canonical) |
| output | `workspace/{job_id}/script.json` (`Script`) |
| dependencies | `StoryPackage` |
| status | COMPAT_ADAPTER |
| verification | UNVERIFIED |
| tests | NONE |
| next_action | OK |

---

## s5 — Storyboard

| field | value |
|---|---|
| stage_id | `s5_storyboard` |
| file | `orchestrator/app/pipeline/stages/s5_storyboard.py:70` |
| class | `StoryboardStage` |
| responsibility | runs Storyboard Intelligence Engine → canonical `StoryboardPackage`; bridges to legacy `Storyboard` |
| input | `story_package.json` (canonical), `research_package.json` (canonical, optional) |
| output | `workspace/{job_id}/storyboard_package.json` (canonical), `storyboard.json` (legacy compat) |
| dependencies | `StoryboardEngine`, `StoryPackage`, `ResearchPackage` |
| cache | stage skip-cache (file-exists check) |
| retry | none |
| status | UPGRADED |
| verification | VERIFIED (62 unit tests + pipeline integration test, Prompt 4) |
| tests | WRITTEN (`tests/test_storyboard_engine.py`, 62 tests) |
| next_action | OK |

---

## s6 — Assets

| field | value |
|---|---|
| stage_id | `s6_assets` |
| file | `orchestrator/app/pipeline/stages/s6_assets.py:92` |
| class | `AssetsStage` |
| responsibility | generate background PNG per unique environment via DALL-E / placeholder; **additive: now also reads `asset_system_package.json` if present** |
| input | `storyboard.json`, `character_system_package.json`, `asset_system_package.json` (optional, additive) |
| output | `workspace/{job_id}/backgrounds/{environment_id}.png`, `asset_system_package.json` (canonical) |
| dependencies | `ImageProvider`, `assets.AssetSystemEngine` (additive) |
| status | IMPLEMENTED |
| verification | VERIFIED (additive integration tested in `test_asset_system.py`) |
| tests | `test_asset_system.py::test_s6_bridge_*` |
| next_action | P7 — wire AssetProvider.generate_image() into Asset Resolution path (C-038) |

---

## s7 — Narration

| field | value |
|---|---|
| stage_id | `s7_narration` |
| file | `orchestrator/app/pipeline/stages/s7_narration.py:52` |
| class | `NarrationStage` |
| responsibility | TTS synthesize narration; emit audio + word timestamps |
| input | `script.json` |
| output | `workspace/{job_id}/narration.mp3`, `narration.words.json` |
| dependencies | `TTSProvider` |
| status | IMPLEMENTED |
| verification | UNVERIFIED |
| tests | NONE |
| next_action | none |

---

## s8 — SceneDefinition JSON

| field | value |
|---|---|
| stage_id | `s8_scene_json` |
| file | `orchestrator/app/pipeline/stages/s8_scene_json.py:132` |
| class | `SceneJsonStage` |
| responsibility | LLM emits strict `SceneDefinition` JSON via the canonical schema; **additive: now prepends canonical asset IDs from `asset_system_package.json` to the LLM prompt** |
| input | `storyboard.json`, `script.json`, `narration.words.json`, `asset_system_package.json` (optional, additive) |
| output | `workspace/{job_id}/scene_definition.json` |
| dependencies | `LLMProvider`, `SceneDefinition` schema, `assets.AssetSystemEngine` (additive) |
| status | IMPLEMENTED |
| verification | VERIFIED (additive integration tested in `test_asset_system.py`) |
| tests | `test_asset_system.py::test_s8_*` |
| next_action | none |

---

## s9 — Validate

| field | value |
|---|---|
| stage_id | `s9_validate` |
| file | `orchestrator/app/pipeline/stages/s9_validate.py:35` |
| class | `ValidateStage` |
| responsibility | Pydantic `SceneDefinition` validation; on failure re-runs s8 once |
| input | `scene_definition.json` |
| output | validated `SceneDefinition` (also written back) |
| dependencies | Pydantic v2 |
| status | IMPLEMENTED |
| verification | UNVERIFIED |
| tests | indirect via `test_scene_definition.py` |
| next_action | none |

---

## s10 — Render

| field | value |
|---|---|
| stage_id | `s10_render` |
| file | `orchestrator/app/pipeline/stages/s10_render.py:49` |
| class | `RenderStage` |
| responsibility | invoke Remotion renderer as subprocess |
| input | `scene_definition.json`, `narration.mp3` |
| output | `workspace/{job_id}/output.mp4` |
| dependencies | `npx`, Node 20+, FFmpeg (transitively) |
| timeout | 900 s (15 min) |
| retry | none |
| status | IMPLEMENTED |
| verification | UNVERIFIED |
| tests | NONE |
| next_action | none |

---

## s11 — Shorts

| field | value |
|---|---|
| stage_id | `s11_short` |
| file | `orchestrator/app/pipeline/stages/s11_short.py:88` |
| class | `ShortsStage` |
| responsibility | FFmpeg extracts 9:16 vertical clip from most narratively dense scene |
| input | `output.mp4` |
| output | `workspace/{job_id}/shorts/short.mp4` |
| dependencies | system FFmpeg |
| status | IMPLEMENTED |
| verification | UNVERIFIED |
| tests | NONE |
| next_action | none |

---

## Character System (PROMPT 5 — OUTSIDE PIPELINE STAGES)

| field | value |
|---|---|
| subsystem | `CharacterSystem` |
| file | `orchestrator/app/character/` |
| responsibility | transform `StoryboardPackage.character_requirements` → `CharacterSystemPackage` (canonical characters, poses, expressions, wardrobes, SVG assets) |
| input | `workspace/{job_id}/storyboard_package.json` |
| output | `workspace/{job_id}/character_system_package.json` + `character_cache/` |
| dependencies | `StoryboardPackage`, `SceneDefinition` (for bridge), `CharacterCache` |
| cache | content-addressed via `CharacterCache` (SHA-256/16-char, TTL default 7d) |
| status | IMPLEMENTED |
| verification | VERIFIED (103 tests passing) |
| tests | WRITTEN (103) in `test_character_system.py`, PASSED |
| API | `GET/POST /api/characters/{job_id}/*` (14 endpoints) |
| UI | `webapp/app/jobs/[id]/characters/page.tsx` |
| next_action | none |

---

## Stage-level Cache Policy

Source: `orchestrator/app/pipeline/cache.py:26`. The `should_skip()`
function returns `True` when the stage's output file exists and
`settings.cache_mode != 'never'`. There is no per-stage opt-out; cache
mode is global.

| cache_mode | skip-if-exists | use case |
|---|---|---|
| `reuse` (default) | yes | dev iteration |
| `never` | no | force full re-run |

## Stage-level Retry Policy

There is **no per-stage retry**. The runner captures the first exception
and marks the job `failed` (`runner.py:83`). `s9_validate` is the only
stage with an internal retry — it re-runs s8 once on validation failure.

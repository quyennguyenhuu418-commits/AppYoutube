# DATA_CONTRACTS

Canonical registry of every cross-system data contract. Two contracts may
not share a canonical definition. Versions are bumped on breaking changes;
non-breaking additions do not bump versions.

Status values: `CANONICAL`, `LEGACY_COMPAT`, `INTERNAL`.

---

## C-01 — `SceneDefinition`

| field | value |
|---|---|
| version | 1 (no version field; bumps by adding optional fields only) |
| canonical file | `orchestrator/app/schemas/scene_definition.py` |
| TS mirror | `renderer/src/scenes/types.ts` (hand-written, **no automated sync**) |
| producer | `orchestrator/app/pipeline/stages/s8_scene_json.py` |
| validator | `orchestrator/app/pipeline/stages/s9_validate.py` |
| consumer | `renderer/src/index.ts` → `loadScene.ts` → `Documentary.tsx` |
| validation mechanism | Pydantic v2 model + cross-field validators |
| serialization | JSON written to `workspace/{job_id}/scene_definition.json` |
| status | CANONICAL |
| breaking-change policy | any new required field is a breaking change; add optional fields only; coordinate with TS mirror |

### Top-level fields (from `scene_definition.py`)

- `meta: Meta` (required) — title, description, fps, width, height,
  target_duration_sec
- `style: Style` (default factory) — primary_color, accent_color,
  background_color, text_color, font_family
- `characters: list[Character]` (min 1, max 12)
- `environments: list[Environment]` (min 1, max 16)
- `scenes: list[Scene]` (min 1, max 200)

### Contract gaps (Python field has no TS consumer)

See `docs/TECHNICAL_DEBT.md` C-004/C-005.

- `Scene.sfx[]` — defined in TS, never read.
- `Scene.music` — defined in TS, never read.
- `OverlayText.exit_at_sec` — defined in TS, never read.
- `Actor.exit_anim` — defined in TS, computed but never applied.
- `Character.name`, `Character.description`, `Character.default_pose` —
  validated, never rendered.
- `Environment.name`, `Environment.mood` — validated, never rendered.
- `Style.primary_color` — defined, never read by any scene component.
- `NarrationScene` ignores `scene.overlay_text[]`.

---

## C-02 — `ResearchPackage` (canonical, rich)

| field | value |
|---|---|
| version | 1 (model has no explicit version field) |
| canonical file | `orchestrator/app/schemas/research_package.py` (454 lines) |
| producer | `orchestrator/app/research/engine.py` |
| consumer | `orchestrator/app/pipeline/stages/s1_research.py` (writes to disk), `/research/*` API |
| validation | Pydantic v2 + `_validate_references()` cross-ref check |
| serialization | JSON written to `workspace/{job_id}/research_package.json` |
| status | CANONICAL |

### Sections (17)

1. `metadata: ResearchMetadata` — topic, language, generated_at, model_id,
   schema_version, sources_consulted
2. `research_questions: list[ResearchQuestion]`
3. `sources: list[Source]` — tier, url, title, snippet, content_hash, score
4. `source_lineage: list[SourceLineage]`
5. `claims: list[Claim]` — claim_type, text, confidence, certainty_level
6. `claim_source_links: list[ClaimSourceLink]`
7. `contradictions: list[Contradiction]` — **(always empty today; see
   `docs/TECHNICAL_DEBT.md` C-001)**
8. `timeline: list[TimelineEvent]`
9. `geography: list[GeographicSite]` — **(always empty today; see
   `docs/TECHNICAL_DEBT.md` C-002)**
10. `quantitative_facts: list[QuantitativeFact]` — **(always empty today;
    see `docs/TECHNICAL_DEBT.md` C-002)**
11. `visual_opportunities: list[VisualOpportunity]`
12. `story_opportunities: list[StoryOpportunity]`
13. `research_gaps: list[ResearchGap]`
14. `synthesis: ResearchSynthesis` — central_question, strongest_evidence,
    weakest_evidence, uncertainties
15. `quality_score: ResearchQualityScore` — 9-axis + overall
16. `audit_trail: list[ResearchEvent]` — structured log
17. `open_questions: list[str]`

### Bridge to legacy

`ResearchPackage.to_legacy_dict()` returns
`{topic, facts, open_questions}` matching C-03 below. See `engine.py`.

---

## C-03 — `ResearchPackage` (legacy, compat)

| field | value |
|---|---|
| version | 1 |
| file | `orchestrator/app/schemas/research.py` (22 lines) |
| producer | `ResearchPackage.to_legacy_dict()` |
| consumer | downstream stages s2–s5 (currently) |
| validation | Pydantic v2 |
| serialization | JSON written to `workspace/{job_id}/research.json` |
| status | LEGACY_COMPAT — preserved only for downstream consumers |

### Fields

- `topic: str`
- `facts: list[FactClaim]` — claim, sources
- `open_questions: list[str]`

**Do not rename or remove without coordinating with all downstream stages
and updating the bridge method.**

---

## C-04 — `JobDetail` / `JobSummary` / `JobCreateRequest`

| field | value |
|---|---|
| file | `orchestrator/app/schemas/job.py` (53 lines) |
| producer | API + store |
| consumer | API responses, webapp |
| validation | Pydantic v2 |
| status | CANONICAL |

### Fields

- `job_id: str` (UUID)
- `topic: str`
- `status: JobStatus` (pending | running | completed | failed)
- `stages: list[StageInfo]` (11 entries)
- `created_at`, `updated_at`, `completed_at`
- `error: str | None`

---

## C-05 — `Thesis`

| field | value |
|---|---|
| file | `orchestrator/app/schemas/script.py` (61 lines) |
| producer | `s2_thesis.py` |
| consumer | `s3_titles.py`, `s4_script.py` |
| status | CANONICAL |

### Fields

- `central_thesis: str`
- `supporting_facts: list[str]`
- `counter_arguments: list[str]`
- `hook: str`

---

## C-06 — `TitlePackage`

| field | value |
|---|---|
| file | `orchestrator/app/schemas/script.py` |
| producer | `s3_titles.py` |
| consumer | webapp, `s4_script.py` |
| status | CANONICAL |

### Fields

- `candidates: list[TitleCandidate]` (5)
- `chosen_index: int`
- `chosen_title: str`

---

## C-07 — `Script`

| field | value |
|---|---|
| file | `orchestrator/app/schemas/script.py` |
| producer | `s4_script.py` |
| consumer | `s5_storyboard.py`, `s7_narration.py`, `s8_scene_json.py` |
| status | CANONICAL |

### Fields

- `title: str`
- `sections: list[ScriptSection]` (each: heading + beats)
- `total_word_count: int`

---

## C-08 — `Storyboard`

| field | value |
|---|---|
| file | `orchestrator/app/schemas/script.py` |
| producer | `s5_storyboard.py` |
| consumer | `s6_assets.py`, `s8_scene_json.py` |
| status | CANONICAL |

### Fields

- `beats: list[StoryboardBeat]` (environment_id, characters, duration_sec,
  visual_description, narration_summary)

---

## C-09 — Asset (background PNG)

| field | value |
|---|---|
| file | `orchestrator/app/pipeline/stages/s6_assets.py` (implicit; no Pydantic model) |
| producer | `s6_assets.py` |
| consumer | `s8_scene_json.py` (writes `environment.background_asset` to SceneDefinition) |
| status | INTERNAL — file-on-disk; not a typed contract |

### Shape

- Path: `workspace/{job_id}/backgrounds/{environment_id}.png`
- Producer: DALL-E 3 (`dalle_image.py:66`) or
  PlaceholderImageProvider (`placeholder_image.py:72`)

---

## C-10 — Narration

| field | value |
|---|---|
| file | `orchestrator/app/pipeline/stages/s7_narration.py` (implicit) |
| producer | `s7_narration.py` |
| consumer | `s10_render.py` (audio track), `s8_scene_json.py` (word timestamps) |
| status | INTERNAL |

### Outputs

- `workspace/{job_id}/narration.mp3`
- `workspace/{job_id}/narration.words.json` — `list[WordTimestamp]`

---

## C-11 — `RenderResult`

| field | value |
|---|---|
| file | implicit (no Pydantic model) |
| producer | `s10_render.py` (subprocess) |
| consumer | `s11_short.py`, webapp |
| status | INTERNAL |

### Output

- `workspace/{job_id}/output.mp4`

---

## C-12 — `StoryPackage`

| field | value |
|---|---||
| version | 1 |
| canonical file | `orchestrator/app/schemas/story.py` |
| producer | `orchestrator/app/story/engine.py` |
| consumer | `s2_thesis.py`, `s3_titles.py`, `s4_script.py`, `s5_storyboard.py` (read), `/story/*` API |
| validation | Pydantic v2 + 5 model validators (research gate, thesis selection, title count >= 20, title revalidation, no critical unsupported) |
| serialization | JSON written to `workspace/{job_id}/story_package.json` |
| status | CANONICAL |

### Sections (16)

1. `metadata: StoryMetadata` — story_package_id, research_package_id, research_package_hash, topic, job_id, status, review_status
2. `thesis: ThesisSelection` — candidates + selected_id + artifact_version
3. `angle: AngleSelection` — candidates + selected_id + artifact_version
4. `title: TitleSelection` — candidates + selected_id + validated_against_script
5. `hook: HookSelection` — candidates + selected_id
6. `blueprint: NarrativeBlueprint` — beats + total_estimated_duration_sec + flags
7. `script: ScriptDraft` — versions (DRAFT/REVISION/FINAL) + active_version
8. `traceability: ClaimTraceabilityReport` — entries + critical_unsupported + coverage scores
9. `critique: ScriptCritique` — findings + counts + flags
10. `retention: RetentionAnalysis` — segment_retentions + risks
11. `revision_history: RevisionHistory` — entries + current_revision_number
12. `storyboard_intent: StoryboardIntent` — items + visual_mode_counts
13. `quality_score: StoryQualityScore` — 15 dimensions + overall
14. `research_failures` — drives status BLOCKED
15. `research_warnings` — drives status NEEDS_REVIEW
16. `research_status` — "passed" | "failed" | "warned"

### Bridge to legacy

`StoryPackage.to_legacy_thesis()`, `to_legacy_title_package()`, `to_legacy_script()`, `to_legacy_storyboard()` return the old contract shapes used by s3, s4, s5 legacy files.

---

## C-13 — `StoryboardPackage`

| field | value |
|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/schemas/storyboard.py` (~700 lines) |
| producer | `orchestrator/app/storyboard/engine.py` (StoryboardEngine) |
| consumer | `/storyboard/*` API, `webapp/app/jobs/[id]/storyboard/page.tsx` UI |
| validation | Pydantic v2 + 3 model validators (no-overlap, all-assets-declared, quality normalize) |
| serialization | JSON written to `workspace/{job_id}/storyboard_package.json` |
| status | CANONICAL |

### Sections (24)

1. `metadata: StoryboardMetadata` — storyboard_package_id, story_package_id, story_version, job_id, topic, status, input_hash
2. `story_package_id: str` — provenance to source StoryPackage
3. `story_version: str` — version of source StoryPackage
4. `segments: list[str]` — segment_ids covered
5. `visual_beats: list[VisualBeat]` — the executable visual blueprint
6. `continuity_state: ContinuityState` — running state between beats
7. `continuity_updates: list[ContinuityUpdate]` — what each beat changed
8. `continuity_dependencies: list[ContinuityDependency]` — what each beat depends on
9. `continuity_issues: list[ContinuityIssue]` — warnings + failures
10. `asset_requirements: list[AssetRequirement]` — characters / environments / props / overlays
11. `camera_plan: list[CameraPlan]` — per-beat camera plans
12. `transition_plan: list[dict]` — per-beat transitions with reasons
13. `text_plan: list[TextItem]` — on-screen text (not narration subtitles)
14. `audio_sync_points: list[AudioSyncPoint]` — visual change alignment with narration
15. `diagram_specs: list[DiagramSpec]` — nodes / arrows / sequence
16. `map_specs: list[MapSpec]` — region / locations / routes (no coordinates)
17. `timeline_specs: list[TimelineSpec]` — events / ordering / approximate dates
18. `comparison_specs: list[ComparisonSpec]` — axis / items / values
19. `data_visualization_specs: list[DataVisualizationSpec]` — metric / unit / value / visual_type
20. `scene_definition_candidates: list[SceneDefinitionCandidate]` — render-ready candidates
21. `storyboard_quality_score: StoryboardQualityScore | None` — 14-axis quality score
22. `warnings: list[str]`
23. `failures: list[str]`
24. `status: StoryboardStatus` — draft | needs_review | approved | rejected | blocked

### VisualBeat fields (~30)

beat_id, segment_id, order, start_time, end_time, duration, purpose,
visual_function, visual_mode, visual_rationale, composition, characters,
environment, props, action, camera, motion, text, transition, transition_reason,
source_ids, claim_ids, evidence_trace, continuity_requirements,
asset_requirements, information_alignment, information_alignment_note,
reconstruction_confidence, uncertainty_treatment, scene_definition_candidate

### Visual Modes (11)

CHARACTER, ENVIRONMENT, DIAGRAM, MAP, TIMELINE, COMPARISON, ARTIFACT,
TEXT_GRAPHIC, DATA_VISUALIZATION, ARCHIVAL, HYBRID

### Camera Types (11)

STATIC, PUSH_IN, PULL_OUT, PAN, TRACK, PARALLAX, TILT, SHAKE, CUT,
MATCH_CUT, ORBIT

### Transitions (6)

CUT, MATCH_CUT, CROSSFADE, WIPE, MORPH, CONTINUITY_CUT

### Quality Score Axes (14)

narration_visual_alignment, visual_variety, visual_clarity,
information_communication, character_continuity, environment_continuity,
camera_quality, motion_quality, composition, asset_reuse,
evidence_traceability, uncertainty_integrity, vertical_reframe_readiness,
editorial_progression

### Bridge to SceneDefinition

`SceneDefinitionCandidate` is a render-ready SceneDefinition scene. The future
Character/Asset/Animation systems will fill in actor positions, prop placements,
overlay texts, etc. before the existing `s8_scene_json` LLM call finalises.

---

## C-14 — `CharacterSystemPackage`

| field | value |
|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/schemas/character.py` (~650 lines) |
| producer | `orchestrator/app/character/engine.py` (CharacterSystemEngine) |
| consumer | `/api/characters/*` API, `webapp/app/jobs/[id]/characters/page.tsx` UI |
| validation | Pydantic v2 + model validators |
| serialization | JSON written to `workspace/{job_id}/character_system_package.json` |
| status | CANONICAL |

### Sections (12)

1. `characters: list[CharacterDefinition]` — canonical character identities
2. `instances: list[CharacterInstance]` — scene-specific placements
3. `wardrobes: list[WardrobeDefinition]` — clothing configurations
4. `poses: list[PoseDefinition]` — all 8 renderer-supported poses
5. `expressions: list[ExpressionDefinition]` — all 11 canonical expressions
6. `asset_packages: list[CharacterAssetPackage]` — filesystem contract
7. `resolutions: list[CharacterResolution]` — resolution log (new/reuse)
8. `registry: CharacterRegistry` — character management state
9. `character_quality_scores: dict[str, CharacterQualityScore]` — 11-dim per character
10. `overall_quality_score: float` — average of character scores
11. `warnings: list[str]`
12. `failures: list[str]`

### Sub-schemas

| Schema | Purpose |
|---|---|
| `CharacterDefinition` | Canonical persistent identity (id, name, role, color, skeleton, palette) |
| `CharacterInstance` | Scene-specific placement (pose, expression, position, scale) |
| `CharacterSkeletonDefinition` | 2D joint/anchor hierarchy (15 joints) for animation readiness |
| `WardrobeDefinition` | Clothing configuration (clothing_items, continuity_lock) |
| `PoseDefinition` | Canonical pose (body/arm/leg/head configuration, 8 renderer poses) |
| `ExpressionDefinition` | Canonical expression (eye/mouth state, 11 expressions) |
| `CharacterQualityScore` | 11-dimension quality (identity/proportion/silhouette/style/wardrobe/pose/expression/component/animation/asset/continuity) |
| `CharacterRegistryEntry` | Registry management (version, status, usage tracking) |
| `CharacterRegistry` | Global/project character registry |
| `CharacterAssetPackage` | Filesystem contract (identity/design/wardrobe/poses/expressions metadata) |

### Enums

`CharacterCategory` (8 values), `AgeClass` (6), `CharacterStatus` (5 lifecycle states),
`CharacterScope` (PROJECT/GLOBAL), `Orientation` (6), `ExpressionLabel` (11),
`ActionLabel` (24), `SilhouetteComplexity` (4).

### Bridge to SceneDefinition (C-01)

`CharacterSystemEngine.to_scene_definition_characters()` produces `SceneDefinition.characters[]`
(list of `Character` with id/name/color/default_pose/description).

`CharacterSystemEngine.to_scene_definition_actors()` produces per-scene `Actor` lists
with character_id/x/y/scale/rotation_deg/pose/enter_anim/exit_anim.

All character_ids are lowercase `snake_case`, all colors are `#RRGGBB`, all poses are
one of: stand/walk/run/sit/point/think/celebrate/hide. Compatible with existing
`renderer/src/components/Character.tsx` (8 pose variants) and `NarrationScene.tsx`
(Actor placement).

### Cache

Content-addressed cache at `workspace/{job_id}/character_cache/` with per-category
TTL (mirrors ResearchCache/StoryCache/StoryboardCache pattern).

---

## Duplicate-Contract Watch List

| contract pair | status | resolution |
|---|---|---|
| `ResearchPackage` (canonical rich) vs `ResearchPackage` (legacy thin) | INTENTIONAL | bridged by `to_legacy_dict()`; do not rename legacy |
| `SceneDefinition` (Python) vs `SceneDefinition` (TS mirror) | INTENTIONAL | no automated sync; manual discipline required (C-004/C-005) |

If a future PR adds a new contract, **search first** to avoid duplication
(see `docs/SAFE_CHANGE_RULES.md` rule 4).

---

## C-15 — `AssetSystemPackage` (Prompt 6)

| field | value |
|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/schemas/asset.py` |
| producer | `orchestrator/app/assets/engine.py` → `AssetSystemEngine` |
| consumer | `s6_assets.py`, `s8_scene_json.py`, renderer |
| validation mechanism | Pydantic v2 model + cross-field validators |
| serialization | JSON written to `workspace/{job_id}/asset_system_package.json` |
| status | CANONICAL |
| breaking-change policy | additions only; no required fields; coordinate with s6/s8/renderer |

### Top-level fields (from `asset.py`)

1. `job_id: str`
2. `project_id: str`
3. `version: str` ("1.0.0")
4. `schema_version: str` ("1.0.0")
5. `environments: list[EnvironmentAsset]` — all resolved environments
6. `environment_instances: list[EnvironmentInstance]` — scene-specific overrides
7. `props: list[PropAsset]` — all resolved props
8. `prop_instances: list[PropInstance]` — scene-specific placements
9. `asset_references: list[AssetReference]` — renderer-consumable
10. `resolutions: list[AssetResolution]` — resolution log
11. `registry: AssetRegistry` — canonical registry state
12. `asset_packages: list[AssetPackage]` — filesystem contracts
13. `overall_quality_score: float` — aggregated score
14. `quality_scores: dict[str, AssetQualityScore]`
15. `warnings: list[str]`
16. `failures: list[str]`
17. `lifecycle: AssetLifecycle` (DRAFT/GENERATING/GENERATED/VALIDATED/REVIEW/APPROVED/REJECTED/DEPRECATED/ARCHIVED)

### Sub-schemas

| Schema | Purpose |
|---|---|
| `AssetReference` | The ONLY object passed to renderer (asset_id/type/version/variant/uri/format/dimensions/anchors/metadata) |
| `AssetPackage` | Filesystem contract (identity/design/metadata/quality/preview file paths) |
| `AssetRegistry` | Canonical asset management (register/lookup/search/usage/approve/deprecate) |
| `AssetRegistryEntry` | Registry row (asset_id/type/version/lifecycle/quality/usage_count) |
| `AssetResolution` | Resolution log entry (source/reuse/predefined/generated/similarity) |
| `AssetQualityScore` | 11-dimension deterministic quality score |
| `EnvironmentAsset` | Canonical persistent environment (identity/style/palette/lighting/composition/continuity) |
| `EnvironmentInstance` | Scene-specific environment overrides (lighting/camera) |
| `EnvironmentStyleProfile` | Illustration style (line_weight/shading/color_temperature) |
| `EnvironmentLightingProfile` | Lighting conditions (primary/secondary/weather/time) |
| `EnvironmentPaletteProfile` | Color palette (primary/secondary/accent/sky/ground/mood_tint) |
| `EnvironmentCompositionProfile` | Camera-safe composition (safe_area/focal_point/depth/horizon) |
| `EnvironmentContinuityProfile` | Locked properties + permitted scene changes |
| `PropAsset` | Canonical persistent prop (identity/category/material/anchors/style) |
| `PropInstance` | Scene-specific prop placement (x/y/scale/rotation/interaction_anchor) |
| `PropAnchorPoint` | Anchor point on prop for character interaction (grip_left/grip_right/top/center) |

### Enums

`AssetType` (6), `AssetLifecycle` (9 states), `ReusePolicy` (5 strategies),
`EnvironmentEra` (10), `EnvironmentScale` (7), `LightingType` (10),
`WeatherType` (8), `TimeOfDay` (7), `PropCategory` (12), `AssetStatus` (5).

### Bridge to SceneDefinition (C-01)

`AssetReference.to_scene_definition_environment()` produces a dict compatible with
SceneDefinition.Environment (id/name/background_asset/mood).

`s6_assets.py` continues to write `backgrounds/{environment_id}.png` paths for backward compatibility.
`s8_scene_json.py` is now prompted with the canonical asset registry to prevent LLM invention of
new asset IDs.

### Bridge to Character System (C-14)

Asset layer treats `AssetType.CHARACTER` as an external type. Character assets are owned by
the Character System (Prompt 5); the Asset System only manages registry/lifecycle/quality
metadata for them.

### Cache

Content-addressed cache at `workspace/asset_cache/{asset_type}/{asset_id}/v{version}/`
with SHA-256 fingerprint of inputs + style + provider version. Idempotent: same
inputs produce same fingerprint → cache hit, no re-generation.

### Reuse Policy Semantics

- `REUSE_ALWAYS` — never create new instance; always reference existing
- `REUSE_PREFERRED` — prefer reuse; create only if no match
- `REUSE_ALLOWED` — check for matches first
- `SCENE_LOCAL` — never reuse across scenes
- `NEVER_REUSE` — always generate new

---

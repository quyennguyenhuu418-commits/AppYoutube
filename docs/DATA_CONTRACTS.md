# DATA_CONTRACTS





Canonical registry of every cross-system data contract. Two contracts may


not share a canonical definition. Versions are bumped on breaking changes;


non-breaking additions do not bump versions.





Status values: `CANONICAL`, `LEGACY_COMPAT`, `INTERNAL`.





---





## C-01 � `SceneDefinition`





| field | value |


|---|---|


| version | 1 (no version field; bumps by adding optional fields only) |


| canonical file | `orchestrator/app/schemas/scene_definition.py` |


| TS mirror | `renderer/src/scenes/types.ts` (hand-written, **no automated sync**) |


| producer | `orchestrator/app/pipeline/stages/s8_scene_json.py` |


| validator | `orchestrator/app/pipeline/stages/s9_validate.py` |


| consumer | `renderer/src/index.ts` ? `loadScene.ts` ? `Documentary.tsx` |


| validation mechanism | Pydantic v2 model + cross-field validators |


| serialization | JSON written to `workspace/{job_id}/scene_definition.json` |


| status | CANONICAL |


| breaking-change policy | any new required field is a breaking change; add optional fields only; coordinate with TS mirror |





### Top-level fields (from `scene_definition.py`)





- `meta: Meta` (required) � title, description, fps, width, height,


  target_duration_sec


- `style: Style` (default factory) � primary_color, accent_color,


  background_color, text_color, font_family


- `characters: list[Character]` (min 1, max 12)


- `environments: list[Environment]` (min 1, max 16)


- `scenes: list[Scene]` (min 1, max 200)





### Contract gaps (Python field has no TS consumer)





See `docs/TECHNICAL_DEBT.md` C-004/C-005.





- `Scene.sfx[]` � defined in TS, never read.


- `Scene.music` � defined in TS, never read.


- `OverlayText.exit_at_sec` � defined in TS, never read.


- `Actor.exit_anim` � defined in TS, computed but never applied.


- `Character.name`, `Character.description`, `Character.default_pose` �


  validated, never rendered.


- `Environment.name`, `Environment.mood` � validated, never rendered.


- `Style.primary_color` � defined, never read by any scene component.


- `NarrationScene` ignores `scene.overlay_text[]`.





---





## C-02 � `ResearchPackage` (canonical, rich)





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





1. `metadata: ResearchMetadata` � topic, language, generated_at, model_id,


   schema_version, sources_consulted


2. `research_questions: list[ResearchQuestion]`


3. `sources: list[Source]` � tier, url, title, snippet, content_hash, score


4. `source_lineage: list[SourceLineage]`


5. `claims: list[Claim]` � claim_type, text, confidence, certainty_level


6. `claim_source_links: list[ClaimSourceLink]`


7. `contradictions: list[Contradiction]` � **(always empty today; see


   `docs/TECHNICAL_DEBT.md` C-001)**


8. `timeline: list[TimelineEvent]`


9. `geography: list[GeographicSite]` � **(always empty today; see


   `docs/TECHNICAL_DEBT.md` C-002)**


10. `quantitative_facts: list[QuantitativeFact]` � **(always empty today;


    see `docs/TECHNICAL_DEBT.md` C-002)**


11. `visual_opportunities: list[VisualOpportunity]`


12. `story_opportunities: list[StoryOpportunity]`


13. `research_gaps: list[ResearchGap]`


14. `synthesis: ResearchSynthesis` � central_question, strongest_evidence,


    weakest_evidence, uncertainties


15. `quality_score: ResearchQualityScore` � 9-axis + overall


16. `audit_trail: list[ResearchEvent]` � structured log


17. `open_questions: list[str]`





### Bridge to legacy





`ResearchPackage.to_legacy_dict()` returns


`{topic, facts, open_questions}` matching C-03 below. See `engine.py`.





---





## C-03 � `ResearchPackage` (legacy, compat)





| field | value |


|---|---|


| version | 1 |


| file | `orchestrator/app/schemas/research.py` (22 lines) |


| producer | `ResearchPackage.to_legacy_dict()` |


| consumer | downstream stages s2�s5 (currently) |


| validation | Pydantic v2 |


| serialization | JSON written to `workspace/{job_id}/research.json` |


| status | LEGACY_COMPAT � preserved only for downstream consumers |





### Fields





- `topic: str`


- `facts: list[FactClaim]` � claim, sources


- `open_questions: list[str]`





**Do not rename or remove without coordinating with all downstream stages


and updating the bridge method.**





---





## C-04 � `JobDetail` / `JobSummary` / `JobCreateRequest`





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





## C-05 � `Thesis`





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





## C-06 � `TitlePackage`





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





## C-07 � `Script`





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





## C-08 � `Storyboard`





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





## C-09 � Asset (background PNG)





| field | value |


|---|---|


| file | `orchestrator/app/pipeline/stages/s6_assets.py` (implicit; no Pydantic model) |


| producer | `s6_assets.py` |


| consumer | `s8_scene_json.py` (writes `environment.background_asset` to SceneDefinition) |


| status | INTERNAL � file-on-disk; not a typed contract |





### Shape





- Path: `workspace/{job_id}/backgrounds/{environment_id}.png`


- Producer: DALL-E 3 (`dalle_image.py:66`) or


  PlaceholderImageProvider (`placeholder_image.py:72`)





---





## C-10 � Narration





| field | value |


|---|---|


| file | `orchestrator/app/pipeline/stages/s7_narration.py` (implicit) |


| producer | `s7_narration.py` |


| consumer | `s10_render.py` (audio track), `s8_scene_json.py` (word timestamps) |


| status | INTERNAL |





### Outputs





- `workspace/{job_id}/narration.mp3`


- `workspace/{job_id}/narration.words.json` � `list[WordTimestamp]`





---





## C-11 � `RenderResult`





| field | value |


|---|---|


| file | implicit (no Pydantic model) |


| producer | `s10_render.py` (subprocess) |


| consumer | `s11_short.py`, webapp |


| status | INTERNAL |





### Output





- `workspace/{job_id}/output.mp4`





---





## C-12 � `StoryPackage`





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





1. `metadata: StoryMetadata` � story_package_id, research_package_id, research_package_hash, topic, job_id, status, review_status


2. `thesis: ThesisSelection` � candidates + selected_id + artifact_version


3. `angle: AngleSelection` � candidates + selected_id + artifact_version


4. `title: TitleSelection` � candidates + selected_id + validated_against_script


5. `hook: HookSelection` � candidates + selected_id


6. `blueprint: NarrativeBlueprint` � beats + total_estimated_duration_sec + flags


7. `script: ScriptDraft` � versions (DRAFT/REVISION/FINAL) + active_version


8. `traceability: ClaimTraceabilityReport` � entries + critical_unsupported + coverage scores


9. `critique: ScriptCritique` � findings + counts + flags


10. `retention: RetentionAnalysis` � segment_retentions + risks


11. `revision_history: RevisionHistory` � entries + current_revision_number


12. `storyboard_intent: StoryboardIntent` � items + visual_mode_counts


13. `quality_score: StoryQualityScore` � 15 dimensions + overall


14. `research_failures` � drives status BLOCKED


15. `research_warnings` � drives status NEEDS_REVIEW


16. `research_status` � "passed" | "failed" | "warned"





### Bridge to legacy





`StoryPackage.to_legacy_thesis()`, `to_legacy_title_package()`, `to_legacy_script()`, `to_legacy_storyboard()` return the old contract shapes used by s3, s4, s5 legacy files.





---





## C-13 � `StoryboardPackage`





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





1. `metadata: StoryboardMetadata` � storyboard_package_id, story_package_id, story_version, job_id, topic, status, input_hash


2. `story_package_id: str` � provenance to source StoryPackage


3. `story_version: str` � version of source StoryPackage


4. `segments: list[str]` � segment_ids covered


5. `visual_beats: list[VisualBeat]` � the executable visual blueprint


6. `continuity_state: ContinuityState` � running state between beats


7. `continuity_updates: list[ContinuityUpdate]` � what each beat changed


8. `continuity_dependencies: list[ContinuityDependency]` � what each beat depends on


9. `continuity_issues: list[ContinuityIssue]` � warnings + failures


10. `asset_requirements: list[AssetRequirement]` � characters / environments / props / overlays


11. `camera_plan: list[CameraPlan]` � per-beat camera plans


12. `transition_plan: list[dict]` � per-beat transitions with reasons


13. `text_plan: list[TextItem]` � on-screen text (not narration subtitles)


14. `audio_sync_points: list[AudioSyncPoint]` � visual change alignment with narration


15. `diagram_specs: list[DiagramSpec]` � nodes / arrows / sequence


16. `map_specs: list[MapSpec]` � region / locations / routes (no coordinates)


17. `timeline_specs: list[TimelineSpec]` � events / ordering / approximate dates


18. `comparison_specs: list[ComparisonSpec]` � axis / items / values


19. `data_visualization_specs: list[DataVisualizationSpec]` � metric / unit / value / visual_type


20. `scene_definition_candidates: list[SceneDefinitionCandidate]` � render-ready candidates


21. `storyboard_quality_score: StoryboardQualityScore | None` � 14-axis quality score


22. `warnings: list[str]`


23. `failures: list[str]`


24. `status: StoryboardStatus` � draft | needs_review | approved | rejected | blocked





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





## C-14 � `CharacterSystemPackage`





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





1. `characters: list[CharacterDefinition]` � canonical character identities


2. `instances: list[CharacterInstance]` � scene-specific placements


3. `wardrobes: list[WardrobeDefinition]` � clothing configurations


4. `poses: list[PoseDefinition]` � all 8 renderer-supported poses


5. `expressions: list[ExpressionDefinition]` � all 11 canonical expressions


6. `asset_packages: list[CharacterAssetPackage]` � filesystem contract


7. `resolutions: list[CharacterResolution]` � resolution log (new/reuse)


8. `registry: CharacterRegistry` � character management state


9. `character_quality_scores: dict[str, CharacterQualityScore]` � 11-dim per character


10. `overall_quality_score: float` � average of character scores


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





## C-15 � `AssetSystemPackage` (Prompt 6)





| field | value |


|---|---|


| version | 1.0.0 |


| canonical file | `orchestrator/app/schemas/asset.py` |


| producer | `orchestrator/app/assets/engine.py` ? `AssetSystemEngine` |


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


5. `environments: list[EnvironmentAsset]` � all resolved environments


6. `environment_instances: list[EnvironmentInstance]` � scene-specific overrides


7. `props: list[PropAsset]` � all resolved props


8. `prop_instances: list[PropInstance]` � scene-specific placements


9. `asset_references: list[AssetReference]` � renderer-consumable


10. `resolutions: list[AssetResolution]` � resolution log


11. `registry: AssetRegistry` � canonical registry state


12. `asset_packages: list[AssetPackage]` � filesystem contracts


13. `overall_quality_score: float` � aggregated score


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





### Asset Identity Integrity (PROMPT 6.5)





`s9_validate.py` now performs deterministic post-generation validation: every `character_id`,


`environment_id`, and `prop.kind` in `SceneDefinition` is cross-referenced against


`asset_system_package.json` and `registry.json`. Unknown IDs cause explicit `ValueError`


(no silent LLM "fixing"). See `test_pipeline_integration_65.py::test_validate_*` (4 tests).





### Renderer Adapter (PROMPT 6.5)





`renderer/src/lib/assetAdapter.ts` bridges `AssetReference` to existing renderer


components. It is **fs-free** (no `node:fs` imports) so it can be safely imported


by Remotion compositions. Loader side (`assetAdapterLoader.ts`) is the only module


that touches `node:fs`, used exclusively by `render_cli.tsx`.





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


inputs produce same fingerprint ? cache hit, no re-generation.





### Reuse Policy Semantics





- `REUSE_ALWAYS` � never create new instance; always reference existing


- `REUSE_PREFERRED` � prefer reuse; create only if no match


- `REUSE_ALLOWED` � check for matches first


- `SCENE_LOCAL` � never reuse across scenes


- `NEVER_REUSE` � always generate new





---





 


 - - - 


 


 


 


 # #   C - 1 6      A n i m a t i o n P l a n   ( P R O M P T   7 ) 


 


 


 


 |   f i e l d   |   v a l u e   | 


 


 | - - - | - - - | 


 


 |   v e r s i o n   |   1 . 0 . 0   | 


 


 |   c a n o n i c a l   f i l e   ( P y t h o n )   |   o r c h e s t r a t o r / a p p / a n i m a t i o n / s c h e m a s . p y   | 


 


 |   c a n o n i c a l   f i l e   ( T S )   |   r e n d e r e r / s r c / a n i m a t i o n / r u n t i m e . t s   | 


 


 |   p r o d u c e r   |   A n i m a t i o n P l a n B u i l d e r   ( o r c h e s t r a t o r / a p p / a n i m a t i o n / b u i l d e r . p y )   | 


 


 |   c o n s u m e r   |   A n i m a t i o n C o m p i l e r ,   A n i m a t i o n D r i v e r   ( r e n d e r e r )   | 


 


 |   s h a p e   |   A n i m a t i o n P l a n   {   m e t a d a t a ,   d u r a t i o n _ s e c ,   c a m e r a ,   c h a r a c t e r s [ ] ,   p r o p s [ ] ,   t r a c k s [ ] ,   e v e n t s [ ] ,   w a r n i n g s [ ] ,   f a i l u r e s [ ]   }   | 


 


 |   s u b - m o d e l s   |   A n i m a t i o n T a r g e t ,   A n i m a t i o n T r a c k ,   K e y f r a m e ,   P o s e S e g m e n t ,   W a l k C y c l e P a r a m s ,   P r o p I n t e r a c t i o n ,   C a m e r a A n i m a t i o n ,   C h a r a c t e r A n i m a t i o n ,   P r o p A n i m a t i o n ,   A n i m a t i o n E v e n t   | 


 


 |   e n u m s   |   I n t e r p o l a t i o n   ( l i n e a r / e a s e _ i n / e a s e _ o u t / e a s e _ i n _ o u t / h o l d ) ,   T a r g e t K i n d ,   A c t i o n L a b e l ,   P o s e T r a n s i t i o n ,   T r a n s f o r m P r o p e r t y ,   C a m e r a P r o p e r t y   | 


 


 


 


 T h e   A n i m a t i o n P l a n   i s   t h e   c a n o n i c a l   d e c l a r a t i v e   a n i m a t i o n   c o n t r a c t .   T h e   P y t h o n   s c h e m a   a n d   T y p e S c r i p t   r u n t i m e   a r e   h a n d - m i r r o r e d   a n d   m u s t   s t a y   b y t e - e q u i v a l e n t   o n   s e r i a l i z a t i o n   ( v a l i d a t e d   b y   t e s t s ) . 


 


 





---





## C-17 � VoiceDefinition (PROMPT 8)





| field | value |


|---|---|


| version | 1.0.0 |


| canonical file (Python) | orchestrator/app/voice/schemas.py |


| canonical file (TS) | renderer/src/voice/types.ts |


| producer | VoiceRegistry.register(), LLM voice-intent adapter (future) |


| consumer | VoiceResolver, VoiceTTSProvider, VoiceTTSCache |


| shape | VoiceDefinition { voice_id, name, language, locale, gender, provider, provider_voice_id, style, settings (VoiceSettings), supported_languages[], pronunciation_hints[], status, version_label, metadata, created_at } |


| enums | VoiceLifecycleStatus (DRAFT/VALIDATED/APPROVED/ACTIVE/DEPRECATED/ARCHIVED), VoiceGender, VoiceStyle, TtsProviderName (MOCK/GTTS/ELEVENLABS/LOCAL/F5_TTS/VI_F5_TTS/COSYVOICE) |





Voice identity is canonical and content-based. Lifecycle transitions are audited. Provider-specific fields are isolated.





---





## C-18 � NarrationScript (PROMPT 8)





| field | value |


|---|---|


| version | 1.0.0 |


| canonical file (Python) | orchestrator/app/voice/schemas.py |


| canonical file (TS) | renderer/src/voice/types.ts |


| producer | build_narration_script() adapter from Script + StoryboardPackage |


| consumer | VoiceResolver, TTS pipeline |


| shape | NarrationScript { version, script_id, project_id, job_id, language, locale, units[NarrationUnit], default_voice_id, version_label, source_lineage, warnings[], failures[] } |


| sub-models | NarrationUnit (narration_id, scene_id, beat_id, speaker_id, speaker_role, voice_id, text, language, locale, pronunciation_hints[], emphasis_hints[], pacing_intent, expected_duration_sec, version, source_lineage) |





One narration unit per beat. VoiceId is per-unit (override) or resolved via VoiceResolver.





---





## C-19 � AudioArtifact (PROMPT 8)





| field | value |


|---|---|


| version | 1.0.0 |


| canonical file (Python) | orchestrator/app/voice/schemas.py |


| canonical file (TS) | renderer/src/voice/types.ts |


| producer | VoiceTTSProvider.synthesize() + write_audio_artifact() |


| consumer | AudioCue.tsx (renderer), AudioLibrary, downstream (Editorial/Mastering) |


| shape | AudioArtifact { artifact_id, narration_id, voice_id, provider, provider_version, source_text_hash, voice_config_hash, format, sample_rate, channels, bits_per_sample, duration_sec, uri, absolute_path, checksum_sha256, byte_size, status, fingerprint, version, created_at, metadata } |


| enums | AudioArtifactStatus (GENERATED/VALIDATED/REJECTED/NORMALIZED) |





Artifact identity is content-addressed (SHA-256 of normalized text + voice config). Idempotent. No secrets in serialized form.





---





## C-20 � SpeechTiming (PROMPT 8)





| field | value |


|---|---|


| version | 1.0.0 |


| canonical file (Python) | orchestrator/app/voice/schemas.py |


| canonical file (TS) | renderer/src/voice/types.ts |


| producer | VoiceTTSProvider.synthesize() OR build_speech_timing() |


| consumer | Captions (PROMPT 9), NarrationTimeline |


| shape | SpeechTiming { timing_id, artifact_id, narration_id, language, timestamp_source, words[WordTiming], segments[SegmentTiming], duration_sec, provider, metadata } |


| sub-models | WordTiming (word, start_sec, end_sec, confidence), SegmentTiming (text, start_sec, end_sec) |


| enums | TimestampSource (PROVIDER_NATIVE/UNIFORM_ALIGNMENT/FORCED_ALIGNMENT/UNAVAILABLE) |





Timestamps are NEVER fabricated. If provider doesn't give trustworthy timestamps, TimestampSource=UNAVAILABLE and words=[].





---





## C-21 � NarrationTimeline (PROMPT 8)





| field | value |


|---|---|


| version | 1.0.0 |


| canonical file (Python) | orchestrator/app/voice/schemas.py |


| canonical file (TS) | renderer/src/voice/types.ts |


| producer | build_timeline() in app.voice.timeline |


| consumer | Captions (PROMPT 9), Editorial (future), Scene timing alignment |


| shape | NarrationTimeline { timeline_id, script_id, project_id, job_id, fps, total_duration_sec, entries[NarrationTimelineEntry], default_padding_sec, default_pre_roll_sec, default_post_roll_sec, strategy, warnings[], failures[], metadata } |


| sub-models | NarrationTimelineEntry (narration_id, scene_id, artifact_id, timing_id, voice_id, speaker_id, audio_start_sec, audio_end_sec, scene_start_sec, scene_end_sec, pre_roll_sec, post_roll_sec, padding_sec, resolution_strategy, metadata) |





Maps (NarrationScript, AudioArtifact, SpeechTiming) to scene timing. Duration reconciliation strategy is deterministic (follow_audio by default).





---





## C-22 � CaptionTrack (PROMPT 9)





| field | value |


|---|---|


| version | 1.0.0 |


| canonical file (Python) | orchestrator/app/captions/schemas.py |


| canonical file (TS) | renderer/src/captions/types.ts |


| producer | CaptionCompiler (orchestrator/app/captions/compiler.py) |


| consumer | Remotion CaptionRenderer (renderer/src/captions/CaptionRenderer.tsx), QA, captions UI |


| shape | CaptionTrack { track_id, caption_id, project_id, job_id, narration_timeline_id, scene_id, language, locale, fps, style (CaptionStyle), segments[CaptionSegment], style_id, timestamp_source, alignment_provider_id, quality (TimingQualityScore), scene_start_sec, scene_end_sec, warnings[], failures[], metadata, created_at } |


| sub-models | CaptionStyle, CaptionSegment, CaptionLine, CaptionWord, TimingQualityScore |


| enums | CaptionVerticalAnchor (TOP/CENTER/BOTTOM/LOWER_THIRD), CaptionAnimationMode (NONE/FADE/WORD_HIGHLIGHT/SEGMENT_POP), CaptionBreakReason (PUNCTUATION/MAX_CHARS/MAX_WORDS/MAX_DURATION/MIN_DURATION/PHRASE/SPEAKER_CHANGE/NARRATION_END/HARD_SPLIT), TimestampSource (reused from C-20) |





CaptionTrack is the canonical timing authority for visible caption


display. The renderer NEVER invents timing � it consumes the


precompiled track. Scene timing comes from NarrationTimeline (C-21);


animation timing comes from AnimationPlan (C-16). CaptionTrack only


references those � it does not duplicate them.





### Bridges





- `CaptionCompiler.compile(req)` consumes `(NarrationTimeline, dict[narration_id ? SpeechTiming], dict[narration_id ? narration_text], CaptionStyle)` and produces `CaptionTrack[]` (one per scene).


- `toLegacyWordTimestamps(track)` adapts CaptionTrack to the legacy `renderer/src/components/Caption.tsx` consumer (PROMPT 9 �25 � adapter boundary, not duplicate timing).





---





## C-23 � CaptionStyle (PROMPT 9)





| field | value |


|---|---|


| canonical file (Python) | orchestrator/app/captions/schemas.py |


| canonical file (TS) | renderer/src/captions/types.ts |


| shape | CaptionStyle { style_id, name, font_family, font_size_px, font_weight, letter_spacing_px, max_lines, max_chars_per_line, line_spacing_px, alignment, text_color, highlight_color, background_color, shadow, safe_area_pct, vertical_safe_area_pct, vertical_anchor, bottom_margin_pct, animation_mode, highlight_hold_pad_ms, metadata } |





CaptionStyle is data-driven and resolution-independent. The same


CaptionStyle + CaptionTrack produce valid output for 16:9, 9:16, and


1:1. Safe-area math adapts at render time (PROMPT 9 �27, �28).





---





## C-24 � AlignmentProvider boundary (PROMPT 9)





| field | value |


|---|---|


| canonical file (Python) | orchestrator/app/captions/alignment.py |


| consumer | CaptionCompiler (future: when forced alignment is enabled) |


| shape | Protocol: align(request: AlignmentRequest) ? AlignmentResult |


| concrete impl | UniformAlignmentProvider (timestamp_source=UNIFORM_ALIGNMENT) |





No real forced-alignment engine is implemented in P9 (PROMPT 9 �34).


The boundary is ready for future Whisper alignment, MFA, wav2vec-based,


or provider-native alignment engines.





---





## C-25 � `EditorialProject` (PROMPT 10)





| field | value |


|---|---|


| version | 1 (no version field; bumps by adding optional fields only) |


| canonical file (Python) | `orchestrator/app/editorial/schemas.py` |


| TS mirror | `renderer/src/editorial/types.ts` (hand-written, no automated sync) |


| producer | `EditorialCompiler.compile(project)` |


| validator | `orchestrator/app/editorial/validation.py` + Pydantic `model_validator` |


| consumer | `RenderPlan` (C-26) and downstream Remotion composition |


| validation mechanism | Pydantic v2 `extra="forbid"` + cross-field validators (unique orders, unique scene_ids, unique track_ids, layer_order duplicates, transition_in duration ? scene duration) |


| serialization | JSON written to `workspace/{job_id}/editorial_project.json` |


| status | CANONICAL |





### Top-level fields





- `project_id: str` (required) � opaque project identifier


- `timeline: EditorialTimeline` (required)


- `source_bundle: SourceBundle` � references to upstream canonical artifacts


- `quality_policy: EditorialQualityPolicy` (default) � thresholds for quality score


- `version: int` (default 1)





### Sub-schemas





- `EditorialTimeline`: scenes (ordered), audio_tracks, layer_order (z-order), title_cards, master_markers, allow_micro_gaps, target_fps, narration_priority_policy (default `AudioMixingPolicy`).


- `EditorialScene`: scene_id, order, source_scene_duration_sec, transition_in/out, holds, animation_plan_id, caption_track_id, pacing_category, emphasis_level, audio_clips, layer_overrides.


- `Transition`: kind (CUT/FADE/CROSSFADE/DISSOLVE/DIP_TO_BLACK/DIP_TO_WHITE), duration_sec, easing (LINEAR/EASE_IN/EASE_OUT/EASE_IN_OUT), overlap_behavior.


- `EditorialHold`: position (BEFORE/AFTER), duration_sec, reason.


- `AudioClipRef`: clip_id, artifact_id, track_kind, priority, start_offset_sec, gain_db, fade_in_sec, fade_out_sec, mute, duck_under_narration.


- `AudioTrackLayer`: track_id, track_kind, default_gain_db, allow_ducking, priority, layout (SEPARATE/AMBIENT_BED/MIX_BUS).


- `AudioMixingPolicy`: priority_order (list[AudioTrackKind]), default_duck_db, narration_priority_window_sec, enable_music_ducking, enable_sfx_ducking.


- `TitleCardSpec`: card_id, kind (INTRO/CHAPTER/SECTION/OUTRO), master_start_sec, duration_sec, headline, subline, accent_color.


- `EditorialQualityPolicy`: minimum_score (0�100), reject_on_failure_reasons (list[str]).


- `EditorialQualityScore`: total (0�100), subscores (timeline_validity, scene_continuity, transition_consistency, audio_continuity, caption_alignment, animation_alignment, asset_integrity, pacing_consistency), pass_fail, failures (list[FailureReason]), warnings (list[FailureReason]).





### Breaking-change policy





Adding new required field is breaking. Add optional fields only. Coordinate with TS mirror.





---





## C-26 � `RenderPlan` (PROMPT 10)





| field | value |


|---|---|


| version | 1 (no version field; bumps by adding optional fields only) |


| canonical file (Python) | `orchestrator/app/editorial/schemas.py::RenderPlan` |


| TS mirror | `renderer/src/editorial/types.ts::RenderPlan` |


| producer | `EditorialCompiler.compile(project).render_plan` |


| validator | `orchestrator/app/editorial/compiler.py` (post-compile invariants) |


| consumer | `renderer/src/compositions/RenderPlanComposition.tsx` |


| validation mechanism | Pydantic v2 + manual invariants (scene-local vs master timeline coherence, fps divisibility) |


| serialization | JSON written to `workspace/{job_id}/render_plan.json` |


| status | CANONICAL |





### Top-level fields





- `plan_id: str` (required)


- `project_id: str` (required)


- `source_fingerprint: str` (min length 8) � deterministic cache key


- `fps: int` (positive)


- `width: int`, `height: int` (positive)


- `total_duration_sec: float` (non-negative)


- `total_duration_frames: int` (non-negative, must equal `int(round(total_duration_sec * fps))`)


- `scenes: list[RenderScene]`


- `audio_tracks: list[RenderAudioTrack]`


- `audio_clips: list[RenderAudioClip]`


- `audio_mix: RenderAudioMix`


- `layers: list[RenderLayer]`


- `layer_order: list[LayerKind]`


- `title_cards: list[RenderTitleCard]`


- `markers: list[RenderMasterMarker]`


- `transition_summary: dict[str, int]` � counts of each transition kind for QA


- `quality_score: EditorialQualityScore`





### Sub-schemas





- `RenderScene`: scene_id, master_start_frame, master_end_frame, master_start_sec, master_end_sec, scene_local_offset_sec, source_scene_duration_sec, transition_in, transition_out, holds, z_layers, audio_clip_refs, animation_plan_id, caption_track_id.


- `RenderLayer`: layer_id, kind (BACKGROUND/ENVIRONMENT/PROPS/CHARACTERS/DIAGRAMS/OVERLAYS/CAPTIONS/TITLE_CARDS), z, scene_id, payload_ref.


- `RenderAudioClip`: clip_id, artifact_id, track_id, kind, master_start_frame, master_end_frame, master_start_sec, master_end_sec, gain_db, fade_in_sec, fade_out_sec, mute, duck_under_narration, source_scene_id.


- `RenderAudioMix`: sample_rate, narration_priority_order, default_duck_db, music_ducking_enabled, mastering_metadata (target_lufs, peak_db, true_peak_db, limiter_required).


- `RenderTransition`: from_scene_id, to_scene_id, kind, duration_sec, overlap_behavior.


- `RenderMasterMarker`: marker_id, master_frame, master_sec, kind (CHAPTER_BREAK/SILENCE_GAP/EMPHASIS/RESET), note.


- `RenderTitleCard`: card_id, kind, master_start_frame, master_end_frame, master_start_sec, master_end_sec, headline, subline, accent_color.





### Determinism contract





Given the same `(project, source_bundle)` and the same canonical source artifacts, `EditorialCompiler.compile` MUST produce a byte-identical `RenderPlan` JSON. This is verified by `test_editorial_compiler_determinism` and the cross-runtime test that hashes the fixture.





### Breaking-change policy





Adding new required field is breaking. Add optional fields only. Coordinate with TS mirror.





---





## C-27 � RenderProfile (PROMPT 11)





Canonical versioned render settings. Any change to width/height/fps/codec/bitrate/sample-rate/channels/container must bump profile_version, which changes the fingerprint.





| field | type | notes |


|---|---|---|


| profile_id | str (=4 chars) | unique per profile |


| profile_version | int = 1 | bumped on breaking change |


| width | int ? [320, 7680] | even; horizontal resolution |


| height | int ? [240, 4320] | even; vertical resolution |


| ps | float ? (1, 120) | CFR; FFmpeg -r |


| pixel_format | enum | yuv420p (default), yuv444p, � |


| ideo_codec | enum | h264 (default), h265, p9, prores |


| ideo_bitrate_kbps | int > 0 | default 5000 |


| ideo_crf | int ? [0, 51] | default 23; lower = higher quality |


| udio_codec | enum | ac (default), mp3, opus, lac, pcm_s16le |


| udio_sample_rate_hz | int ? [8000, 192000] | default 48000 |


| udio_channels | int ? [1, 8] | default 2 |


| udio_bitrate_kbps | int > 0 | default 192 |


| container | enum | mp4 (default), mov, mkv, webm |


| ingerprint | str (auto) | deterministic hash of all fields + version |





Defined in orchestrator/app/mastering/schemas.py as RenderProfile.





## C-28 � MasteringProfile + FinalVideoArtifact (PROMPT 11)





### MasteringProfile





| field | type | notes |


|---|---|---|


| profile_id | str (=4 chars) | unique per mastering profile |


| profile_version | int = 1 | bumped on breaking change |


| 	arget_lufs | float ? [-30, -6] | target integrated loudness (default -16 web) |


| loudness_tolerance | float > 0 | LU window considered PASS (default 2.0) |


| max_true_peak | float < 0 | dBTP ceiling (default -1.0) |


| 


ormalization_enabled | bool | two-pass loudnorm (default True) |


| limiter_enabled | bool | future; default False |


| ade_in_ms | int = 0 | leading fade (default 0) |


| ade_out_ms | int = 0 | trailing fade (default 0) |


| silence_policy | enum | WARN (default), STRICT, IGNORE |


| max_leading_silence_ms | int = 0 | default 250 |


| max_trailing_silence_ms | int = 0 | default 250 |


| ingerprint | str (auto) | deterministic hash |





### FinalVideoArtifact





| field | type | notes |


|---|---|---|


| rtifact_id | str (=4 chars) | unique per final artifact |


| project_id | str | owning project |


| 


ender_plan_id | str | upstream render plan |


| 


aw_artifact_id | str | the immediate raw render artifact |


| 


ender_profile_id / mastering_profile_id | str | upstream profiles |


| 


enderer_version | str | FFmpeg + Remotion versions |


| width / height / ps | int/int/float | mirror of profile (verified) |


| ideo_codec / udio_codec | enum | actual codec after encoding |


| udio_sample_rate_hz / udio_channels | int | measured |


| duration_sec | float | measured by ffprobe |


| ile_size_bytes | int = 0 | actual on-disk size |


| checksum_sha256 | str (hex 64) | reproducible for identical bytes |


| loudness_lufs / 	rue_peak_dbtp / loudness_range_lu | float? | nullable if UNAVAILABLE |


| qa_report_id | str | ? MediaQAReport (C-29) |


| lifecycle_status | enum | RENDERED, VALIDATING, APPROVED, REJECTED, SUPERSEDED, ARCHIVED |


| qa_status | enum | RENDER_SUCCESS, QA_PENDING, QA_PASS, QA_WARN, QA_FAIL, FINAL_APPROVED |


| inal_path | str | absolute path to the MP4 |


| ingerprint | str (auto) | composite of plan + profiles + renderer + raw |


| created_at | datetime | UTC |





Defined in orchestrator/app/mastering/schemas.py.





## C-29 � MediaQAReport + Check Types (PROMPT 11)





11 discriminated QA check types. Every check returns PASS | WARN | FAIL | UNAVAILABLE and carries check_id, expected, measured, tolerance, status, explanation.





| check_id | type | measures |


|---|---|---|


| VIDEO_STREAM | VideoStreamCheck | =1 video stream, =1 audio stream where required |


| AUDIO_STREAM | AudioStreamCheck | audio stream presence + sample-rate / channel match |


| DURATION | DurationCheck | final vs RenderPlan within �0.1 s |


| FPS | FPSCheck | actual vs profile within �0.1 fps |


| RESOLUTION | ResolutionCheck | width/height vs profile exact |


| CODEC | CodecCheck | video codec matches RenderProfile; audio codec matches MasteringProfile |


| AUDIO_DURATION | AudioDurationCheck | audio duration vs final within �0.1 s |


| LOUDNESS | LoudnessCheck | measured LUFS vs target within loudness_tolerance |


| TRUE_PEAK | TruePeakCheck | measured dBTP = max_true_peak |


| DECODE | DecodeCheck | FFmpeg decode validation passes |


| SYNC | SyncCheck | audio/video drift = 5 ms |


| ARTIFACT_INTEGRITY | ArtifactIntegrityCheck | checksum reproducibility |





overall_status follows the QAPolicy (critical-fail = REJECT; warn-only = APPROVED with warnings).





Defined in orchestrator/app/mastering/qa.py and schemas.py.





---





## C-30 � `RenderJob` (PROMPT 12)


| field | value |


|---|---|


| version | 1.0.0 |


| canonical file | `orchestrator/app/orchestration/render_job.py` |


| producer | `RenderOrchestrator.orchestrate()` |


| consumer | `/render/*` API, `RenderOrchestrator.load_job()`, `webapp/lib/api.ts::RenderStatus` |


| validation | Pydantic v2 + `model_validator` (safe-id on job_id, project_id, render_plan_id, artifact_id) |


| serialization | JSON written to `workspace/{job_id}/render_job.json` |


| status | CANONICAL |





### Top-level fields





- `job_id: str` (required, regex `^[A-Za-z0-9_-]+$`, length 1�64)


- `project_id: str` (required, length 1�128)


- `topic: str` (required, length 1�300)


- `lifecycle: JobLifecycle` (see lifecycle enum below)


- `progress_pct: int` (0�100)


- `current_stage: str | None` � name of currently running stage


- `stage_progress: dict[str, int]` � stage-name ? progress percentage


- `stages: list[RenderJobStageInfo]` � per-stage detail


- `is_terminal: bool` � derived from lifecycle


- `error: str | None` � failure description


- `error_stage: str | None` � which stage failed (preparing/preflight/rendering/mastering/qa/finalizing)


- `render_plan_id: str | None`


- `render_plan_fingerprint: str | None`


- `raw_artifact_id: str | None`


- `final_artifact_id: str | None`


- `qa_report_id: str | None`


- `renderer_version: str | None` � e.g. `remotion-0.1.0`


- `ffmpeg_version: str | None` � e.g. `ffmpeg-9.0`


- `request_fingerprint: RenderRequestFingerprint | None` � composite hash of upstream inputs


- `workspace_dir: str` � internal-only; never exposed to webapp


- `final_mp4_path: str | None` � internal-only; explicitly nulled in API responses


- `created_at`, `started_at`, `finished_at`, `updated_at: datetime`





### `JobLifecycle` enum





`QUEUED`, `PREPARING`, `PREFLIGHT`, `RENDERING`, `MASTERING`, `QA`,


`FINALIZING`, `APPROVED`, `FAILED`, `CANCELLED`.





### Lifecycle state machine





```


QUEUED     ? PREPARING


PREPARING  ? PREFLIGHT | FAILED


PREFLIGHT  ? RENDERING | FAILED


RENDERING  ? MASTERING | FAILED


MASTERING  ? QA | FAILED


QA         ? FINALIZING | FAILED


FINALIZING ? APPROVED | FAILED


APPROVED   ? (terminal)


FAILED     ? (terminal)


CANCELLED  ? (terminal)


```





Terminal states: `APPROVED`, `FAILED`, `CANCELLED`. Invalid transitions raise `InvalidTransitionError`.





### `RenderJobStageInfo` sub-schema





- `name: str` � preparing | preflight | rendering | mastering | qa | finalizing


- `label: str` � human-readable label


- `status: StageStatus` � pending | running | completed | failed | skipped


- `started_at: datetime | None`


- `finished_at: datetime | None`


- `error: str | None`





### `RenderRequestFingerprint` sub-schema





- `render_plan_fingerprint: str` (min length 4)


- `render_profile_fingerprint: str` (min length 4)


- `mastering_profile_fingerprint: str` (min length 4)


- `renderer_version: str` (min length 4)


- `ffmpeg_version: str` (min length 4)


- `composite: str` (auto-computed SHA-256 hash, prefixed `rj_`)


- `upstream_fingerprints: list[str]`





### Progress semantics





Stage-weighted progress (not raw frame progress):





| Stage | Weight |


|---|---|


| queued | 0% |


| preparing | 5% |


| preflight | 10% |


| rendering | 55% |


| mastering | 75% |


| qa | 90% |


| finalizing | 98% |


| approved | 100% |


| failed | 100% |


| cancelled | 100% |





### Strict-model invariant





`RENDERING SUCCESS != FINAL SUCCESS`. A job is only `APPROVED` when both:


- `FinalVideoArtifact.lifecycle == APPROVED`, AND


- `FinalVideoArtifact.qa_status == FINAL_APPROVED`.





If the QA gate rejects the candidate at the finalizing stage, the orchestrator transitions the job to `FAILED` at `error_stage="finalizing"` � the artifact remains available on disk for debugging but is NEVER served through the public `/render/{id}/video` endpoint (P12 �34).





### Breaking-change policy





Adding new required fields is breaking. Add optional fields only. The `JobLifecycle` enum is the only place lifecycle strings are defined � every UI/API consumer must derive from this canonical source.

---

## C-31 - `KnowledgeSource` (L-U1)

| field | value |
|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/knowledge/schemas.py` |
| producer | `KnowledgeLayer` (L-U1) |
| consumer | future prompt builders (read-only) |
| validation | Pydantic v2 with `Field(pattern=...)` on `source_id`, `version` |
| serialization | JSON |
| status | **CANONICAL** |

### Top-level fields

- `source_id` - stable opaque identifier (lowercase snake_case, 3-64 chars)
- `source_name` - human label (1-200 chars)
- `source_type` - enum (REFERENCE_DOCUMENT, CHANNEL_ANALYSIS, SYSTEM_PROMPT, PROJECT_RULE, INTERNAL_DOC)
- `source_section` - optional section reference (max 200 chars)
- `source_reference` - optional URL / file path / ADR ID
- `confidence` - bounded float [0.0, 1.0]
- `version` - semver string `^\d+\.\d+\.\d+$`
- `notes` - optional human notes (max 2000 chars)

### Breaking-change policy

Adding required fields is breaking. Add optional fields only. Coordinate with the canonical `KnowledgeEntry` schema (C-32).

---

## C-32 - `KnowledgeEntry` (L-U1)

| field | value |
|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/knowledge/schemas.py` |
| producer | Knowledge Layer seeds + future ingestion |
| consumer | future prompt builders |
| validation | Pydantic v2 with id pattern + rule-length validator + examples-vs-rules validator |
| serialization | JSON |
| status | **CANONICAL** |

### Top-level fields

- `id` - stable lowercase snake_case (3-96 chars)
- `domain` - enum: `VISUAL_STYLE`, `COMPOSITION`, `CHARACTER`, `CHARACTER_CONSISTENCY`, `IMAGE_PROMPT`, `VIDEO_PROMPT`, `CAMERA`, `CAMERA_MOVEMENT`, `MOTION`, `SOUND`, `NEGATIVE_CONSTRAINT`, `CONTINUITY`, `FORMAT`
- `name` (1-200 chars)
- `description` (1-2000 chars)
- `rules` - list of reusable production principles (max 64, each >= 5 chars)
- `constraints` - things this knowledge FORBIDS / REQUIRES (max 64)
- `examples` - NON-canonical illustrative examples (max 32)
- `applicability` - where this applies (max 16 tags)
- `status` - enum: `EXPLICIT`, `INFERENCE`, `EXPERIMENTAL`, `PROJECT_RULE`
- `version` - semver string
- `tags` - free-form tags (max 32)
- `created_at`, `updated_at` - UTC datetime

### Critical invariants

1. **Rules MUST be reusable production principles**, not specific examples. Validator enforces >= 5 chars per rule.
2. **Examples MUST NOT be silently promoted to rules.** Validator rejects any entry whose `examples` text appears verbatim in `rules`.
3. **EXPLICIT != PROJECT_RULE.** Status conversion requires an explicit version bump via `KnowledgeRegistry.bump_version()`.
4. **Provenance is mandatory.** Every entry carries `KnowledgeSource` provenance via the seed module.

---

## C-33 - `VisualGrammar` (L-U1)

| field | value |
|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/knowledge/visual_grammar.py` |
| producer | Knowledge Layer + future prompt builders |
| consumer | future prompt-emission adapters |
| status | **CANONICAL** |

### Top-level fields

- `style` - `StyleIntent` (profile, palette, outline, line_quality, rendering_notes)
- `subject` - `SubjectIntent` (character_ref, description, pose, expression, props, framing_hint)
- `environment` - `EnvironmentIntent` (setting, era, time_of_day, weather, lighting)
- `composition` - `CompositionIntent` (shot_type, focal_subject, rule_of_thirds, depth_layers, notes)
- `action` - `ActionIntent` (description, verbs, intensity)
- `effects` - `EffectsIntent` (motion_lines, metaphor_elements, text_overlays, particles, other)
- `camera` - `CameraIntent` (shot_type, movement, easing, notes)
- `motion` - `MotionIntent` (pattern, duration_sec, loop, notes)
- `background` - `BackgroundIntent` (color, treatment, notes)
- `typography` - `TypographyIntent` (text, position, style, color)
- `constraints` - `ConstraintsIntent` (forbid, require)
- `format` - `FormatIntent` (aspect_ratio, medium, notes)
- `provenance_ids` - list of KnowledgeEntry IDs informing this grammar (max 16)
- `source_grammar_id` - optional ID of source grammar if derived

### Critical invariants

1. **VisualGrammar is INTENT, not free-form prompt text.** No field carries raw prompt strings.
2. **Image grammar vs video grammar.** `is_image_grammar()` returns False iff `motion.pattern` or `camera.movement` is set.
3. **Bounded vocabularies.** `CameraShotType`, `CameraMovementType`, `MotionPattern`, `VisualStyleProfile` are closed enums; new values require a KnowledgeEntry promotion.

---

## C-34 - `CharacterGrammar` (L-U1)

| field | value |
|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/knowledge/character_grammar.py` |
| producer | Knowledge Layer + future character production systems |
| consumer | future CharacterDefinition emitters |
| status | **CANONICAL** |

### Top-level fields

- `grammar_id` - stable lowercase snake_case
- `name`, `description` - human label and explanation
- `identity` - `IdentityBlock` (family, identity_lock_fields)
- `head` - `HeadBlock` (shape, relative_size)
- `face` - `FaceBlock` (eye_style, eyebrow_style, mouth_styles, expression_palette)
- `proportions` - `ProportionsBlock` (body_type, posture, notes)
- `outline` - `OutlineBlock` (weight, color, quality)
- `palette` - `ColorPaletteBlock` (primary_hex, primary_name, fills, notes)
- `wardrobe` - `WardrobeBlock` (default_outfit, palette, continuity_lock, notes)
- `signature_props` - `SignaturePropsBlock` (props, lock_props)
- `orientation` - `OrientationBlock` (safe_orientations, flip_allowed)
- `reference_sheet` - `ReferenceSheetBlock` (panels_required, background, grid)
- `consistency` - `ConsistencyRulesBlock` (rules, explicit_rules)
- `provenance_ids` - list of KnowledgeEntry IDs
- `version` - semver string

### Critical invariants

1. **CharacterGrammar is NOT a character.** It owns the principles; concrete identities live in `CharacterDefinition` (C-14).
2. **Reference-sheet panel rules are declarative**, not imperative. The grammar describes what the sheet MUST contain; the actual sheet is generated elsewhere.
3. **Continuity rules are first-class.** `ConsistencyRulesBlock.rules` enumerates `ConsistencyRuleKind` enums; `explicit_rules` carries plain-text reusable rules.

---

## C-35 - `CharacterReferenceSpecification` (L-U4)

| field | value |
|---|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/character/reference_schema.py` |
| producer | `KnowledgeCharacterAdapter` (L-U4) consulting `KnowledgeContext` (L-U3) |
| consumer | future `CharacterSystemEngine` integrations, L-U5 Prompt Compiler |
| status | **CANONICAL** |

### Top-level fields

- `character_id` - which character this spec applies to
- `identity_properties` - frozenset of LOCKED properties (e.g. HEAD_SHAPE, PALETTE, PROPORTIONS)
- `scene_variables` - frozenset of MUTABLE properties (e.g. POSE, EXPRESSION, ORIENTATION)
- `resolved_rules` - list of `ResolvedCharacterRule` with provenance
- `palette_guidance` - optional `PaletteGuidance` (hints, not values)
- `wardrobe_guidance` - optional `WardrobeGuidance` (continuity rules)
- `negative_constraints` - list of `NegativeConstraint` (do-not rules)
- `explicit_overrides` - list of `ExplicitOverride` (with justification)
- `conflicts` - list of `CharacterKnowledgeConflict` (REPRESENTED, not silently resolved)
- `knowledge_ids_used` - frozenset of KnowledgeEntry IDs
- `knowledge_version` - semver of knowledge registry or "no-knowledge"
- `is_knowledge_active` - whether Knowledge Layer was consulted
- `fallback_policy_used` - which `FallbackPolicy` was applied

### Critical invariants

1. **CharacterReferenceSpecification is NOT a CharacterDefinition.** It
   is GUIDANCE derived from the Knowledge Layer. Actual character values
   (colors, head shapes) live in `CharacterDefinition` (C-14).
2. **Identity ? Scene State.** The two frozensets MUST NOT overlap.
3. **Provenance is mandatory.** Every `ResolvedCharacterRule` carries a
   `KnowledgeProvenance` from L-U3.
4. **Knowledge versioning is independent of Character versioning.**
5. **No provider-specific prompt syntax.** This contract is provider-neutral.
   L-U5 (Prompt Compiler) consumes this and adds provider syntax.

---

## C-36 - `CanonicalPromptIR` (L-U5)

| field | value |
|---|---|---|
| version | 1.0.0 |
| canonical file | `orchestrator/app/prompt/schemas.py` |
| producer | `PromptCompiler` (L-U5) consulting `KnowledgeContext` (L-U3) + `CharacterReferenceSpecification` (L-U4) + `VisualGrammar` (L-U1) |
| consumer | `ProviderPromptAdapter` subclasses (Google Flow, DINO AI, etc.); future L-U6 |
| status | **CANONICAL** |

### Top-level fields

- `prompt_kind` - `PromptKind.IMAGE` or `PromptKind.VIDEO`
- `compiler_version` - semver of the compiler
- `knowledge_ids_used` - frozenset of `KnowledgeEntry` IDs that contributed
- `knowledge_version` - semver of knowledge registry or "no-knowledge"
- `is_knowledge_active` - whether Knowledge Layer was consulted
- `identity` - `IdentityPreservationBlock` (locked properties + resolved rules)
- `scene_elements` - `SceneElementsBlock` (permitted scene variations)
- `style` - `StyleBlock` (from VISUAL_STYLE knowledge)
- `subject` - `SubjectBlock` (character + pose + expression + props)
- `environment` - `EnvironmentBlock`
- `action` - `ActionBlock`
- `camera` - `CameraBlock` (shot + movement, VIDEO has movement)
- `motion` - `MotionBlock` (VIDEO only)
- `background` - `BackgroundBlock`
- `effects` - `EffectsBlock`
- `constraints` - `NegativeConstraintsBlock` (first-class, not string append)
- `sound` - `SoundBlock` (semantic only)
- `format` - `FormatBlock` (semantic, NOT provider-specific)
- `provenance` - aggregate `KnowledgeProvenance`

### Critical invariants

1. **CanonicalPromptIR is structured intent, NOT a raw prompt string.**
2. **Provider syntax is EXCLUDED from core.** The IR must not contain
   `--ar`, `--style`, `--seed`, etc. Provider adapters do the encoding.
3. **IMAGE and VIDEO are explicitly distinguished.** Motion is VIDEO-only.
4. **Negative constraints are first-class.** They are structured records,
   not string appends.
5. **Identity ? Scene State.** `IdentityPreservationBlock.locked_properties`
   and `SceneElementsBlock.permitted_variations` MUST NOT overlap.
6. **Bounded vocabulary.** Camera, motion, and style use canonical enums.
7. **Provenance mandatory** on every knowledge-derived element.
8. **Deterministic.** Same inputs produce the same IR. No timestamps,
   no random IDs in the IR.
9. **Frozen.** The IR is immutable after construction.

---

## L-U6 � Camera + Motion + Sound Compilation Contracts

L-U6 extends L-U5's `CanonicalPromptIR` semantics with rich camera, motion,
and sound intent. **L-U5 contracts UNCHANGED.** All new contracts are
separate frozen Pydantic models.

### Contracts added by L-U6

| ID | Contract | File | Purpose |
|---|---|---|---|
| C-LU6-1 | `CameraBlockExt` | `orchestrator/app/prompt/schemas.py` | Camera intent extension: framing, subject_relationship, movement_direction, intensity, duration_sec |
| C-LU6-2 | `MotionBlockExt` | `orchestrator/app/prompt/schemas.py` | Motion intent extension: subject_action, direction, easing |
| C-LU6-3 | `SoundBlockExt` | `orchestrator/app/prompt/schemas.py` | Sound intent extension: semantic layers, master_duck_under_narration |
| C-LU6-4 | `SubjectMotionSpec` | `orchestrator/app/prompt/schemas.py` | Semantic subject/object motion (WALK, RUN, GESTURE, �) � separate from camera and animation |
| C-LU6-5 | `SoundLayerSpec` | `orchestrator/app/prompt/schemas.py` | One semantic sound layer (category, description, priority, duck_under_narration, loop, volume_hint) |
| C-LU6-6 | `SoundLayersSpec` | `orchestrator/app/prompt/schemas.py` | Collection of `SoundLayerSpec` for a scene |
| C-LU6-7 | `CameraMotionSoundCompilationResult` | `orchestrator/app/prompt/schemas.py` | Frozen Pydantic output of the `CameraMotionSoundCompiler` |

### Vocabularies added by L-U6 (canonical enums)

| Enum | Values |
|---|---|
| `SubjectMotionVocabulary` | none, stand, walk, run, point, think, celebrate, hide, sit, enter, exit, gesture, look, turn, breathing, idle |
| `SubjectMotionDirection` | none, left, right, forward, backward, up, down |
| `SubjectMotionIntensity` | low, medium, high |
| `SoundLayerCategory` | ambient, music, sfx, environment, narration, dialogue, impact, silence |
| `SoundLayerPriority` | primary, secondary, tertiary, background |
| `FramingIntent` | rule_of_thirds, center, golden_ratio, leading_room, balanced, asymmetric |
| `SubjectRelationship` | front, side, back, three_quarter, over, under, pov |
| `CameraDirection` | none, left, right, up, down, forward, backward |

### Critical invariants for L-U6

1. **Three distinct concepts.** `camera.movement` (camera action),
   `subject_motion.action` (subject action), `motion.pattern`
   (rendering pattern) are separate fields.
2. **Sound intent ? Audio file ? Audio mix.** L-U6 describes intent
   only. Audio generation belongs to `app.voice`. Audio mixing
   belongs to Editorial/Mastering.
3. **Timing authority not duplicated.** `NarrationTimeline` (P8) remains
   the authority for narration timing. `AnimationPlan` (P7) remains
   the authority for animation timing. L-U6 expresses
   `duration_sec` as semantic intent only.
4. **Bounded vocabulary.** All values come from canonical enums.
   New vocabulary requires a `KnowledgeEntry` promotion.
5. **Deterministic.** Same inputs produce the same output. No LLM,
   no random, no timestamps.
6. **Provider-neutral.** No `--ar`, `--style`, `--seed`, `--camera`,
   Remotion syntax, FFmpeg syntax, or provider SDK in the core.
7. **Frozen.** All L-U6 contracts are immutable after construction.
8. **Knowledge boundary.** All knowledge access goes through
   `KnowledgeContext` + `KnowledgeResolver`. No direct `KnowledgeRegistry`
   access from L-U6.
9. **Identity ? Scene State.** `SubjectMotionSpec.target_id` references
   the character but does NOT embed identity. Identity lives in
   `CharacterReferenceSpecification.identity_properties`.

---

## L-U7 � Hybrid Quality Validation Contracts

L-U7 is a **read-only**, **deterministic**, **provider-neutral**,
**renderer-neutral** quality gate that consumes upstream contracts and
produces a `QualityValidationResult`. L-U7 does NOT generate media, call
providers, call LLMs, or render.

### Contracts added by L-U7

| ID | Contract | File | Purpose |
|---|---|---|---|
| C-LU7-1 | `QualityValidationResult` | `orchestrator/app/quality/schemas.py` | Frozen Pydantic result of the `QualityEngine` |
| C-LU7-2 | `QualityValidationContext` | `orchestrator/app/quality/schemas.py` | Immutable bundle of upstream contract references |
| C-LU7-3 | `ValidationPolicy` | `orchestrator/app/quality/schemas.py` | STRICT / STANDARD / LENIENT thresholds |
| C-LU7-4 | `ValidationIssue` | `orchestrator/app/quality/schemas.py` | One structured validation issue |
| C-LU7-5 | `DimensionResult` | `orchestrator/app/quality/schemas.py` | Per-dimension state and issue counts |
| C-LU7-6 | `PromptLossReport` | `orchestrator/app/quality/schemas.py` | Structural report of input intent loss |

### Enums added by L-U7

| Enum | Values |
|---|---|
| `ValidationStatus` | PASS, WARN, REJECT, UNAVAILABLE |
| `GenerationReadiness` | READY, READY_WITH_WARNINGS, NOT_READY, UNAVAILABLE |
| `ValidationSeverity` | INFO, WARNING, ERROR, BLOCKING |
| `ValidationDimension` | 15 dimensions (completeness, identity, camera, motion, camera_motion_compatibility, continuity, prompt_loss, knowledge_provenance, format, sound_semantic, fallback_visibility, conflict_visibility, contract_compatibility, provider_readiness, generation_readiness) |
| `DimensionState` | PASS, WARN, FAIL, UNAVAILABLE |
| `ValidationPolicyName` | STRICT, STANDARD, LENIENT |
| `IssueSource` | EXPLICIT_INTENT, KNOWLEDGE, ENGINE_DEFAULT, CROSS_CONTRACT, STRUCTURAL, UNKNOWN |

### Critical invariants for L-U7

1. **Validator REPORTS, does not MUTATE.** Validation ? normalization.
2. **No fake quality scores.** Status is categorical (PASS/WARN/REJECT/UNAVAILABLE).
3. **No LLM, no embedding, no vision model, no external API.**
4. **Provider-neutral.** No provider SDK, no `--ar`, `--style`, etc.
5. **Renderer-neutral.** No Remotion, FFmpeg, `interpolate()`, `spring()`, `Sequence`, `AbsoluteFill`.
6. **Deterministic.** Same inputs ? same output. `validation_id` derived deterministically from input fingerprints. No timestamp in decision.
7. **Identity authority unchanged.** `CharacterReferenceSpecification` (L-U4) remains identity authority.
8. **Timing authority unchanged.** P7/P8/P9 retain frame/audio mixing authority. L-U7 does not duplicate.
9. **Frozen.** All L-U7 contracts are immutable after construction.
10. **Hybrid = structural + semantic + cross-contract + provenance.** No LLM.
11. **Knowledge boundary preserved.** `QualityEngine` consumes contracts only; no direct `KnowledgeRegistry` access.
12. **Backward compatible.** L-U5 and L-U6 contracts unchanged. All 1314 prior tests pass.

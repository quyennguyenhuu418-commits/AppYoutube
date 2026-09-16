# Prompt Compiler V2

L-U5 — Prompt Compiler: Knowledge + Character Aware.

## Purpose

The L-U5 Prompt Compiler V2 is the **canonical, deterministic, provider-neutral**
engine that transforms structured production intent into a structured
intermediate representation (IR). Provider-specific serialization
(Google Flow, DINO AI, Axen) lives in `ProviderPromptAdapter` subclasses.

## Architecture

```
PromptCompilationRequest
        ↓
PromptCompiler                          (canonical, provider-neutral)
├── KnowledgePromptAdapter (thin L-U5)   (consults KnowledgeContext)
├── CharacterReferenceSpecification (L-U4)  (identity vs scene state)
├── VisualGrammar (L-U1)                  (style, camera, motion vocab)
        ↓
CanonicalPromptIR (structured, NOT string)
        ↓
PromptValidator (deterministic, no LLM)
        ↓
PromptCompilationResult (with provenance, validation, version metadata)
        ↓
ProviderPromptAdapter (Google Flow, DINO, etc.)  ← provider syntax here
        ↓
ProviderPrompt (serialized string)
```

## What L-U5 Does

- ✅ Compile structured intent into structured IR
- ✅ Consume `KnowledgeContext` + `KnowledgeResolver` (L-U3) for prompt rules
- ✅ Consume `CharacterReferenceSpecification` (L-U4) for identity/scene
- ✅ Preserve provenance (Knowledge IDs, source, confidence)
- ✅ Validate deterministically (no LLM)
- ✅ Support both IMAGE and VIDEO prompts
- ✅ Provide provider-neutral serialization boundary

## What L-U5 Does NOT Do

- ❌ Generate images/videos
- ❌ Call image/video generation APIs
- ❌ Use LLM to write or score prompts
- ❌ Hard-code provider syntax in core
- ❌ Replace `CharacterDefinition`, `CharacterReferenceSpecification`,
      `VisualGrammar`, or any existing contract
- ❌ Mutate the `KnowledgeRegistry`

## Key Contracts

### `CanonicalPromptIR` (frozen Pydantic)

The structured intermediate representation. **NOT a raw prompt string.**

Top-level fields:

- `prompt_kind`: `PromptKind.IMAGE` or `PromptKind.VIDEO`
- `identity`: `IdentityPreservationBlock` (from CharacterRefSpec)
- `scene_elements`: `SceneElementsBlock` (from CharacterRefSpec)
- `style`: `StyleBlock` (from VisualGrammar + Knowledge)
- `subject`: `SubjectBlock` (character + pose + expression + props)
- `environment`: `EnvironmentBlock` (setting + lighting + era)
- `action`: `ActionBlock` (verbs + description)
- `camera`: `CameraBlock` (shot + movement)
- `motion`: `MotionBlock` (VIDEO only)
- `background`: `BackgroundBlock`
- `effects`: `EffectsBlock`
- `constraints`: `NegativeConstraintsBlock` (first-class)
- `sound`: `SoundBlock` (semantic only)
- `format`: `FormatBlock` (semantic only)
- `provenance`: aggregate `KnowledgeProvenance`
- `knowledge_ids_used`: frozenset of KnowledgeEntry IDs
- `knowledge_version`: semver or "no-knowledge"
- `is_knowledge_active`: bool
- `compiler_version`: semver of the compiler

### `PromptCompilationRequest`

The structured input to the compiler.

Fields include:
- `request_id`, `prompt_kind`
- `character_reference_id` + optional `character_reference_spec`
- Optional `visual_grammar` (from L-U1)
- Scene-specific overrides: `scene_pose`, `scene_expression`,
  `scene_orientation`, `scene_action`, `scene_environment`, `scene_camera`
- `aspect_ratio`
- `request_reason` (for logs)

### `PromptCompilationResult`

The structured output of the compiler.

Fields include:
- `request_id`, `prompt_kind`
- `ir`: the compiled `CanonicalPromptIR`
- `validation`: `PromptValidationReport`
- `compiler_version`, `knowledge_version`, `character_version`
- `fallback_policy_used`, `is_knowledge_active`
- `has_conflicts`, `has_overrides`
- `compiled_at` (UTC)

### `PromptValidationReport`

The deterministic validation result. Fields:
- `is_valid`: True iff no BLOCKING findings
- `blocking_findings`, `warnings`, `info`: lists of `ValidationFinding`
- `summary()`: human-readable summary

## Negative Constraints

`NegativeConstraintsBlock` carries `NegativeConstraintItem` entries.
Each item has:
- `constraint_id`, `property_name`, `constraint_text`
- `is_identity_bearing`: True if this preserves character identity
- `provenance`: optional `KnowledgeProvenance`

Constraints are first-class — they are NOT a string appended at the end
of a prompt. The provider adapter decides how to encode them.

## Camera / Motion Vocabulary

The compiler uses **bounded vocabularies** mapped from L-U1 VisualGrammar:

**Shot types:** `extreme_wide`, `wide`, `medium_wide`, `medium`,
`medium_close`, `close`, `extreme_close`, `over_shoulder`, `pov`, `dutch`,
`birds_eye`, `worms_eye`, `two_shot`.

**Movements:** `hold`, `push_in`, `pull_out`, `pan`, `tilt`, `zoom`,
`tracking`, `shake`, `orbit`.

**Motion patterns:** `frame_by_frame`, `loop`, `rig_pose_interpolation`,
`kinetic_text`, `shake_nervous`.

Adding new vocabulary requires a `KnowledgeEntry` promotion.

## Identity vs Scene State

The compiler preserves the L-U4 separation:

- `IdentityPreservationBlock.locked_properties` ← `CharacterReferenceSpecification.identity_properties`
- `SceneElementsBlock.permitted_variations` ← `CharacterReferenceSpecification.scene_variables`

These two frozensets MUST remain disjoint.

When the compiler produces an IR, identity-bearing properties appear in
`identity.locked_properties` (and are added to negative constraints
when the rules are identity-bearing). Scene-variable properties appear
in `subject.pose`, `subject.expression`, `subject.orientation`, etc.

## Provenance

Every knowledge-derived element carries `KnowledgeProvenance` from L-U3:

- Style: `StyleBlock.provenance` (from VISUAL_STYLE domain)
- Camera: `CameraBlock.provenance` (from CAMERA domain)
- Motion: `MotionBlock.provenance` (from MOTION domain)
- Constraints: `NegativeConstraintItem.provenance` (from NEGATIVE_CONSTRAINT)
- Aggregate: `CanonicalPromptIR.provenance`, `knowledge_ids_used`

This is the canonical provenance chain. Providers do NOT add their own
provenance; they only serialize what is already in the IR.

## Determinism

The compiler is deterministic. Same inputs → same IR.

```python
compiler = PromptCompiler()
req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE, ...)
result1 = compiler.compile(req)
result2 = compiler.compile(req)
assert result1.ir == result2.ir
```

No timestamps in the IR (only in the result's `compiled_at`).
No random IDs.
No UUIDs.

Request IDs are derived from SHA-256 of the canonical content.

## Knowledge-Disabled Mode

The compiler works without any `KnowledgeContext`:

```python
compiler = PromptCompiler()  # no knowledge
result = compiler.compile(req)
assert result.is_knowledge_active is False
assert result.ir.knowledge_version == "no-knowledge"
assert result.fallback_policy_used == "engine_default"
```

This is the canonical backward-compatible path (L-U2 / L-U3 behavior).

## Provider Boundary

The canonical `PromptCompiler` does NOT contain provider syntax.
Provider-specific adapters live in `app/prompt/provider_adapter.py`.

A reference implementation `GoogleFlowPromptAdapter` is provided as an
example of how to serialize the IR. It does NOT call any provider API.

To add a new provider:

```python
class NewProviderAdapter(ProviderPromptAdapter):
    @property
    def provider_name(self) -> str:
        return "new_provider"

    @property
    def adapter_version(self) -> str:
        return "1.0.0"

    def serialize(self, ir: CanonicalPromptIR) -> ProviderPrompt:
        # Provider-specific serialization
        ...
```

## Validation

`PromptValidator` performs deterministic, NO-LLM validation:

1. `subject_required`: blocking if no subject
2. `identity_not_preserved`: warning if character but no identity block
3. `constraints_missing`: warning if knowledge active but no constraints
4. `motion_on_image`: warning if motion on IMAGE prompt
5. `aspect_ratio_unknown`: warning if aspect ratio not in canonical list
6. `camera_shot_unknown`: warning if shot type not canonical
7. `motion_pattern_unknown`: warning if motion not canonical
8. `forbidden_provider_syntax`: BLOCKING if `--ar` etc. appears in IR
9. `provenance_missing`: warning if knowledge active but no IDs

All rules are deterministic and structural.

## Backward Compatibility

L-U5 is strictly **additive**:

- `CharacterSystemEngine` — unchanged
- `CharacterDefinition`, `CharacterInstance`, `CharacterRegistry` — unchanged
- `StoryboardEngine`, `StoryboardPackage` — unchanged
- `KnowledgeResolver`, `KnowledgeContext`, `KnowledgeQuery` — unchanged
- `KnowledgeStoryboardAdapter` (L-U2) — unchanged
- `KnowledgeCharacterAdapter` (L-U4) — unchanged
- `VisualGrammar`, `CharacterGrammar` (L-U1) — unchanged

**Verified:** All 1122 pre-L-U5 tests still pass.

## Future Boundary

```
CanonicalPromptIR          ← L-U5 STOPS HERE
        ↓
L-U6 Camera + Motion + Sound Compiler (future, recommended)
        ↓
L-U7 Hybrid Quality Validation (future, optional)
```

L-U5 produces a structured IR. L-U6 can extend camera/motion/sound
semantics if needed. L-U7 can add hybrid quality validation.

L-U5 deliberately does NOT include provider-specific logic, image
generation, video generation, LLM scoring, or pipeline integration.

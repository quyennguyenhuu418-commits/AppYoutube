# Camera + Motion + Sound Compiler (L-U6)

L-U6 — Semantic Production Grammar Compiler.

## Purpose

The L-U6 **CameraMotionSoundCompiler** is the semantic, deterministic,
provider-neutral compiler that enriches camera, motion, and sound
semantics in the canonical `CanonicalPromptIR` (L-U5). It produces
**structured semantic intent**, NOT raw implementation.

## Three Distinct Concepts

L-U6 enforces a strict distinction:

| Concept | What | Example | Belongs to |
|---|---|---|---|
| Camera Movement | Camera action | PUSH_IN, PAN, ZOOM | `CameraBlockExt.movement` |
| Subject Motion | What the subject does | WALK, RUN, GESTURE | `SubjectMotionSpec.action` |
| Animation Pattern | How motion is rendered | RIG_POSE_INTERPOLATION | `MotionBlockExt.pattern` |

These three concepts MUST NOT be conflated. A character walking can have:
- Camera: PUSH_IN (camera moves)
- Subject motion: WALK (character walks)
- Animation pattern: RIG_POSE_INTERPOLATION (deterministic walk cycle)

## Sound vs Audio

L-U6 distinguishes:

| Concept | What | Example | Belongs to |
|---|---|---|---|
| Sound Intent | WHAT should be heard | "rice field ambience" | `SoundLayerSpec` |
| Audio File | Actual WAV/MP3 | narration_001.wav | `AudioArtifact` (P8 voice/) |
| Audio Mix | Gain, ducking, bus | -6dB, duck under narration | Editorial/Mastering (P9/P10) |

L-U6 only describes intent. It does NOT generate audio or mix.

## Timing Authority

L-U6 expresses `duration_sec` as a semantic intent. It does NOT
duplicate timing authority:

| Authority | Purpose |
|---|---|
| `NarrationTimeline` (P8 voice) | Narration timing |
| `SpeechTiming` (P8 voice) | Word-level timestamps |
| `AnimationPlan` (P7) | Animation timing |
| `CameraMotionSoundCompilationResult` (L-U6) | Semantic intent only |

L-U6 may describe a relationship ("duck under narration") but does
NOT compute the actual dB.

## Architecture

```
PromptCompilationRequest (L-U5)
        ↓
PromptCompiler (L-U5) → CanonicalPromptIR (basic camera/motion/sound)
        ↓
CameraMotionSoundCompiler (L-U6) — adds rich semantics
    ├── KnowledgeCameraMotionSoundAdapter (thin L-U3 consumer)
    ├── Deterministic keyword parsing (no LLM)
    └── Strict precedence: EXPLICIT > KNOWLEDGE > DEFAULT
        ↓
CameraMotionSoundCompilationResult (extended semantics)
        ↓
Animation / Editorial / Prompt downstream consumers
```

## Bounded Vocabularies

All values come from canonical enums. New vocabulary requires a
`KnowledgeEntry` promotion (per L-U3).

### Camera shot types
`extreme_wide`, `wide`, `medium_wide`, `medium`, `medium_close`, `close`,
`extreme_close`, `over_shoulder`, `pov`, `dutch`, `birds_eye`,
`worms_eye`, `two_shot`

### Camera movements
`hold`, `push_in`, `pull_out`, `pan`, `tilt`, `zoom`, `tracking`,
`shake`, `orbit`

### Camera directions
`none`, `left`, `right`, `up`, `down`, `forward`, `backward`

### Subject motion (semantic)
`none`, `stand`, `walk`, `run`, `point`, `think`, `celebrate`,
`hide`, `sit`, `enter`, `exit`, `gesture`, `look`, `turn`,
`breathing`, `idle`

### Animation patterns
`frame_by_frame`, `loop`, `rig_pose_interpolation`, `kinetic_text`,
`shake_nervous`

### Sound layer categories
`ambient`, `music`, `sfx`, `environment`, `narration`, `dialogue`,
`impact`, `silence`

### Sound layer priority
`primary`, `secondary`, `tertiary`, `background`

## What L-U6 Does

- ✅ Compile structured intent into extended semantic blocks
- ✅ Consume `KnowledgeContext` + `KnowledgeResolver` (L-U3) for CMS rules
- ✅ Consume `CharacterReferenceSpecification` (L-U4)
- ✅ Preserve provenance (Knowledge IDs, source, confidence)
- ✅ Validate deterministically (no LLM)
- ✅ Distinguish camera movement, subject motion, animation pattern
- ✅ Distinguish sound intent, audio file, audio mix

## What L-U6 Does NOT Do

- ❌ Generate images/videos
- ❌ Generate audio files
- ❌ Mix audio
- ❌ Call image/video/audio generation APIs
- ❌ Use LLM to write or score semantics
- ❌ Hard-code provider syntax in core
- ❌ Replace `AnimationPlan`, `AnimationCompiler`, `EditorialCompiler`,
      `AudioArtifact`, `SpeechTiming`, `NarrationTimeline`
- ❌ Mutate the `KnowledgeRegistry`
- ❌ Import Remotion, FFmpeg, or any runtime

## Key Contracts

### `CameraMotionSoundCompilationResult` (frozen Pydantic)

The structured output of the compiler.

Top-level fields:
- `request_id`, `prompt_kind`
- `camera`: `CameraBlockExt` (L-U5 CameraBlock + framing, subject_rel, direction, intensity, duration)
- `motion`: `MotionBlockExt` (L-U5 MotionBlock + subject_action, direction, easing)
- `subject_motion`: `SubjectMotionSpec` (separate from camera/motion)
- `sound`: `SoundBlockExt` (L-U5 SoundBlock + semantic layers)
- `is_valid`, `validation_messages`
- `is_knowledge_active`, `knowledge_version`, `knowledge_ids_used`
- `fallback_policy_used`
- `compiler_version`
- `provenance`

### `SubjectMotionSpec` (frozen Pydantic)

Semantic subject/object motion.

Fields: `action`, `direction`, `intensity`, `duration_sec`, `target_id`,
`purpose`, `provenance`.

### `SoundLayersSpec` (frozen Pydantic)

Collection of semantic sound layers.

Fields: `layers` (list of `SoundLayerSpec`), `master_duck_under_narration`,
`provenance`.

### `SoundLayerSpec` (frozen Pydantic)

A single semantic sound layer.

Fields: `category`, `description`, `priority`, `duck_under_narration`,
`loop`, `volume_hint`, `provenance`.

### `CameraBlockExt` (frozen Pydantic)

Extended camera intent.

Fields (L-U5): `shot_type`, `movement`, `easing`, `notes`, `provenance`.
Fields (L-U6): `framing`, `subject_relationship`, `movement_direction`,
`intensity`, `duration_sec`.

### `MotionBlockExt` (frozen Pydantic)

Extended motion intent.

Fields (L-U5): `pattern`, `duration_sec`, `loop`, `notes`, `provenance`.
Fields (L-U6): `subject_action`, `direction`, `easing`.

### `SoundBlockExt` (frozen Pydantic)

Extended sound intent.

Fields (L-U5): `category`, `description`, `notes`, `provenance`.
Fields (L-U6): `layers`, `master_duck_under_narration`.

## Negative Constraints

Negative constraints are NOT duplicated here. The L-U5 compiler
already manages `NegativeConstraintsBlock` for prompt generation.

L-U6 is purely semantic — no string appends, no negative constraints
beyond what L-U5 already provides.

## Camera / Motion / Sound Vocabulary

The compiler uses **bounded vocabularies** mapped from L-U1 VisualGrammar:

**Shot types:** `extreme_wide`, `wide`, `medium_wide`, `medium`,
`medium_close`, `close`, `extreme_close`, `over_shoulder`, `pov`, `dutch`,
`birds_eye`, `worms_eye`, `two_shot`.

**Movements:** `hold`, `push_in`, `pull_out`, `pan`, `tilt`, `zoom`,
`tracking`, `shake`, `orbit`.

**Camera directions:** `none`, `left`, `right`, `up`, `down`, `forward`,
`backward`.

**Framing intents:** `rule_of_thirds`, `center`, `golden_ratio`,
`leading_room`, `balanced`, `asymmetric`.

**Subject relationships:** `front`, `side`, `back`, `three_quarter`,
`over`, `under`, `pov`.

**Subject motions:** `none`, `stand`, `walk`, `run`, `point`, `think`,
`celebrate`, `hide`, `sit`, `enter`, `exit`, `gesture`, `look`,
`turn`, `breathing`, `idle`.

**Motion patterns:** `frame_by_frame`, `loop`, `rig_pose_interpolation`,
`kinetic_text`, `shake_nervous`.

**Sound categories:** `ambient`, `music`, `sfx`, `environment`,
`narration`, `dialogue`, `impact`, `silence`.

**Sound priorities:** `primary`, `secondary`, `tertiary`, `background`.

Adding new vocabulary requires a `KnowledgeEntry` promotion.

## Precedence Rules

The compiler uses strict precedence:

1. **EXPLICIT scene intent** (from `PromptCompilationRequest.scene_camera`,
   `scene_action`) — highest priority
2. **KNOWLEDGE guidance** (from `KnowledgeResolver`) — middle priority
3. **ENGINE DEFAULT** — lowest priority

For each semantic field, the compiler first checks explicit input,
then knowledge, then falls back to default. This is deterministic.

## Identity ≠ Scene State Preservation

The L-U4 invariant is preserved:
- `SubjectMotionSpec.target_id` references the character but does NOT
  embed identity. Identity lives in `CharacterReferenceSpecification.identity_properties`.
- Subject motion action (WALK, GESTURE) is a scene variable. It may
  vary per scene without changing identity.

The character consistency test (test_subject_motion_consistency) verifies
this.

## Determinism

The compiler is deterministic. Same inputs → same result.

- No random
- No timestamps in IR fields
- No UUIDs
- Request IDs derived from SHA-256 of canonical content

```python
compiler = CameraMotionSoundCompiler()
req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO, ...)
result1 = compiler.compile(req)
result2 = compiler.compile(req)
assert result1.camera == result2.camera
assert result1.subject_motion == result2.subject_motion
```

## Knowledge-Disabled Mode

The compiler works without any `KnowledgeContext`:

```python
compiler = CameraMotionSoundCompiler()  # no knowledge
result = compiler.compile(req)
assert result.is_knowledge_active is False
assert result.knowledge_version == "no-knowledge"
assert result.fallback_policy_used == "engine_default"
```

This is the canonical backward-compatible path.

## Provider Boundary

The L-U6 compiler does NOT contain provider syntax. Provider-specific
serialization lives in `ProviderPromptAdapter` subclasses (L-U5).

L-U6 extends the IR's semantics; the L-U5 adapters serialize it.

## Validation

`CameraMotionSoundValidator` performs deterministic, NO-LLM validation:

1. Camera movement must not be on IMAGE
2. Subject motion must not be on IMAGE
3. Camera shot type is in canonical vocabulary
4. Camera movement is in canonical vocabulary
5. Motion pattern is in canonical vocabulary
6. Narration layer cannot duck under itself
7. No forbidden provider syntax (--ar, etc.)
8. Duration capped at 300s
9. Sound layer count ≤ 8

All rules are deterministic and structural.

## Backward Compatibility

L-U6 is strictly **additive**:

- `PromptCompiler` (L-U5) — unchanged
- `CanonicalPromptIR` (L-U5) — unchanged
- `CameraBlock`, `MotionBlock`, `SoundBlock` (L-U5) — unchanged
- `CharacterSystemEngine` — unchanged
- `CharacterReferenceSpecification` (L-U4) — unchanged
- `VisualGrammar`, `CharacterGrammar` (L-U1) — unchanged
- `KnowledgeResolver`, `KnowledgeContext` (L-U3) — unchanged
- `AnimationPlan`, `AnimationCompiler` (P7) — unchanged
- `AudioArtifact`, `SpeechTiming`, `NarrationTimeline` (P8) — unchanged
- `EditorialCompiler`, `RenderPlan` (P9) — unchanged

**Verified:** All 1208 pre-L-U6 tests still pass.

L-U6 adds NEW contracts (`CameraBlockExt`, `MotionBlockExt`,
`SoundBlockExt`, `SubjectMotionSpec`, `SoundLayersSpec`) as separate
frozen Pydantic models. The L-U5 contracts are NOT modified.

## Future Boundary

```
PromptCompiler (L-U5)
        ↓
CameraMotionSoundCompiler (L-U6) STOPS HERE
        ↓
L-U7 — Hybrid Quality Validation (future, recommended)
        ↓
L-U8+ — Real provider integration
```

L-U6 deliberately does NOT include:
- Provider-specific logic
- Image generation
- Video generation
- Audio file generation
- Audio mixing
- LLM scoring
- Pipeline integration

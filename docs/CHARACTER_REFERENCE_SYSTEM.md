# Character Reference System

L-U4 — Character Reference System Integration.

## Purpose

The Character Reference System (L-U4) bridges the **Knowledge Layer**
(L-U1 / L-U2 / L-U3) and the **Character System** (existing PROMPT 5
architecture) without replacing either.

It produces a **structured guidance contract** —
`CharacterReferenceSpecification` — that tells the `CharacterSystemEngine`
how characters should be represented and kept consistent, based on
**governed Character Knowledge**.

## Core Architectural Principle

```
Knowledge answers:        "How should characters be represented and kept consistent?"
CharacterDefinition:      "Which actual character exists?"
CharacterInstance:        "Where and how is that character instantiated?"
CharacterAsset:           "What visual asset represents the character?"
```

These responsibilities MUST remain separate.

```
CharacterRequirement
        ↓
KnowledgeCharacterAdapter     (L-U4)
        ↓
KnowledgeResolver             (L-U3)
        ↓
KnowledgeContext              (L-U3)
        ↓
CharacterReferenceSpecification  (L-U4 — this contract)
        ↓
CharacterDefinition           (existing — PROMPT 5)
        ↓
CharacterInstance             (existing — PROMPT 5)
        ↓
CharacterAsset                (existing — PROMPT 5)
```

## The IDENTITY vs SCENE STATE Concept

The most important concept of L-U4 is the **separation between
identity-bearing and scene-variable** properties.

### Identity-bearing (LOCKED unless explicitly overridden)

| Property            | What it controls                        |
| ------------------- | --------------------------------------- |
| `HEAD_SHAPE`        | Head silhouette / shape                 |
| `FACE_STRUCTURE`    | Face structure / features               |
| `SILHOUETTE`        | Overall body silhouette                 |
| `PROPORTIONS`       | Body proportions / ratios               |
| `PALETTE`           | Color palette identity                  |
| `SKIN_TONE`         | Skin tone                               |
| `STYLE_PROFILE`     | Art style profile                       |
| `DEFAULT_OUTLINE`   | Default outline color                   |
| `WARDROBE`          | Core wardrobe (continuity_locked)       |
| `SIGNATURE_PROP`    | Identity-bearing props                  |

### Scene-variable (may change per scene without changing identity)

| Property             | What it controls                       |
| -------------------- | -------------------------------------- |
| `POSE`               | Body pose                              |
| `EXPRESSION`         | Facial expression                      |
| `ORIENTATION`        | Character orientation (front/side/etc) |
| `CAMERA_ANGLE`       | Camera framing                         |
| `ACTION`             | Action the character is performing     |
| `SCALE`              | Scene-specific scale                   |
| `POSITION`           | Scene-specific position                |
| `SCENE_WARDROBE_VARIANT` | Temporary costume variation         |

This separation is **structural** — `CharacterReferenceSpecification`
contains two disjoint frozensets (`identity_properties` and `scene_variables`)
and the two sets MUST NOT overlap.

## Components

### 1. `CharacterReferenceSpecification` (Pydantic, frozen)

The canonical guidance contract. Lives in
`orchestrator/app/character/reference_schema.py`.

Key fields:

- `character_id` — which character this spec applies to
- `identity_properties` — frozenset of locked properties
- `scene_variables` — frozenset of mutable properties
- `resolved_rules` — list of `ResolvedCharacterRule` from Knowledge
- `palette_guidance` — optional `PaletteGuidance`
- `wardrobe_guidance` — optional `WardrobeGuidance`
- `negative_constraints` — list of `NegativeConstraint`
- `explicit_overrides` — list of `ExplicitOverride`
- `conflicts` — list of `CharacterKnowledgeConflict` (REPRESENTED, not swallowed)
- `knowledge_ids_used` — frozenset of knowledge IDs
- `knowledge_version` — semver of the knowledge registry
- `is_knowledge_active` — was knowledge consulted?
- `fallback_policy_used` — which fallback policy was applied

### 2. `KnowledgeCharacterAdapter`

Thin adapter. Lives in
`orchestrator/app/character/knowledge_adapter.py`.

```python
from app.character.knowledge_adapter import KnowledgeCharacterAdapter
from app.knowledge import KnowledgeContext, build_default_registry, default_sources

# Canonical L-U3 path:
ctx = KnowledgeContext.from_registry(build_default_registry(), sources=default_sources())
adapter = KnowledgeCharacterAdapter(context=ctx)

# Legacy L-U2 path (still supported):
adapter = KnowledgeCharacterAdapter(registry=build_default_registry())

# No-knowledge mode (backward compatible):
adapter = KnowledgeCharacterAdapter()
```

The adapter NEVER:

- Generates actual character values (colors, shapes)
- Calls image generation providers
- Mutates the KnowledgeRegistry
- Makes character identity decisions

The adapter ONLY:

- Consults the Knowledge Layer
- Translates results to character guidance
- Preserves provenance
- Builds a `CharacterReferenceSpecification`

### 3. Resolved Components

- `ResolvedCharacterRule` — one rule from Knowledge with provenance
- `PaletteGuidance` — palette hints from Knowledge (not actual palette)
- `WardrobeGuidance` — wardrobe continuity rules from Knowledge
- `NegativeConstraint` — "do NOT change X" rules
- `ExplicitOverride` — explicit scene overrides (never silent)
- `CharacterKnowledgeConflict` — represented conflicts (never silently swallowed)

## Usage

```python
from app.character.knowledge_adapter import KnowledgeCharacterAdapter
from app.knowledge import build_default_registry, default_sources, KnowledgeContext
from app.schemas.storyboard import CharacterRequirement

# Setup
registry = build_default_registry()
ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
adapter = KnowledgeCharacterAdapter(context=ctx)

# Resolve reference for a storyboard requirement
req = CharacterRequirement(
    character_id="farmer_01",
    required_clothing="simple_farm_clothing",
)

spec = adapter.resolve_character_reference(req)

# Inspect the spec
print(spec.provenance_summary())   # → [dino.character.reference_sheet@1.0.0], ...
print(spec.knowledge_version)      # → 1.0.0
print(len(spec.identity_properties))  # → 8
print(len(spec.scene_variables))     # → 7

# Feed to CharacterSystemEngine (the engine uses spec, not the other way around)
# The engine is the AUTHORITY for CharacterDefinition.
```

## Backward Compatibility

L-U4 is strictly **additive**. The existing `CharacterSystemEngine`,
`CharacterDefinition`, `CharacterInstance`, `CharacterRegistry`, etc.
are **unchanged**.

```python
# Still works exactly as before (no knowledge):
engine = CharacterSystemEngine(job_id="...", cache=cache)
pkg = engine.run(storyboard_pkg, story_pkg_id)

# Knowledge-aware (NEW):
adapter = KnowledgeCharacterAdapter(context=ctx)
spec = adapter.resolve_character_reference(req)
# The engine can optionally consult the spec, but it is not required to.
```

## Knowledge Versioning vs Character Versioning

These are independent:

| System          | Versioning                              |
| --------------- | --------------------------------------- |
| Knowledge       | `1.0.0` semver (registry version)       |
| Character       | `1.0.0` semver (per-CharacterDefinition) |

A new knowledge version does NOT mutate existing character versions.
If knowledge influences a new character, the knowledge version is recorded
in `CharacterReferenceSpecification.knowledge_version` for traceability.

## Conflict Handling

When a scene request conflicts with character knowledge rules, L-U4
**REPRESENTS** the conflict, not silently resolves it.

```python
spec = CharacterReferenceSpecification(
    character_id="farmer_01",
    conflicts=[
        CharacterKnowledgeConflict(
            scene_request="make character wear winter coat",
            rule="preserve canonical white shirt",
            property_name="wardrobe",
            severity="warning",
            provenance=...,
        ),
    ],
)
```

The pipeline can then choose:

- WARN (proceed with a warning)
- REJECT (block scene)
- EXPLICIT OVERRIDE (require justification)

## What L-U4 Does NOT Do

L-U4 does NOT:

- Generate images (PNG/SVG) — that's `svg_generator.py`
- Generate prompts — that's L-U5
- Call image generation providers
- Modify the `CharacterSystemEngine`
- Modify `CharacterDefinition`
- Modify the KnowledgeRegistry

L-U4 is **pure guidance** that the engine can use.

## Future Boundary: L-U5 Prompt Compiler

```
CharacterReferenceSpecification  ← L-U4 stops here
        ↓
Prompt Compiler                  ← L-U5 (future)
        ↓
Provider Adapter                 ← L-Ux (future)
```

L-U5 will consume `CharacterReferenceSpecification` and produce
**provider-specific** prompts (Google Flow, DINO, etc.).
L-U4 deliberately does NOT include prompt syntax.

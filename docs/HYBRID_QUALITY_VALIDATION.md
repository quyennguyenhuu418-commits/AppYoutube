# Hybrid Quality Validation (L-U7)

L-U7 — Quality gate before provider/generation layer.

## Purpose

L-U7 builds an **intermediate Quality Validation layer** that verifies the
correctness of the semantic production plan before the system proceeds to
provider integration, generation, or rendering.

L-U7 consumes the canonical contracts from L-U3, L-U4, L-U5, L-U6 and the
Storyboard layer. It **does not generate media**, **does not call any
provider**, **does not call any LLM**, and **does not render**.

L-U7's sole purpose is to answer the question:

> *"Is the current semantic production intent sufficient, consistent,
> traceable to provenance, and qualified to proceed?"*

## Architecture

```
              StoryboardPackage (P5)
                       ↓
            PromptCompiler (L-U5)
                       ↓
            CanonicalPromptIR
                       ↓
        CameraMotionSoundCompiler (L-U6)
                       ↓
        CameraMotionSoundCompilationResult
                       ↓
        CharacterReferenceSpecification (L-U4)
                       ↓
            KnowledgeContext (L-U3)
                       ↓
       ┌─────────────────────────────────┐
       │      QualityEngine (L-U7)       │
       │                                 │
       │  - Hybrid Quality Validation    │
       │  - Deterministic, no LLM        │
       │  - Provider-neutral             │
       │  - Renderer-neutral             │
       └─────────────────────────────────┘
                       ↓
       QualityValidationResult
       (PASS / WARN / REJECT / UNAVAILABLE)
                       ↓
       [PROVIDER ADAPTER LAYER — FUTURE]
```

## What L-U7 Does

- ✅ Validate semantic completeness of the prompt
- ✅ Validate character identity consistency (L-U4 invariant)
- ✅ Validate camera consistency (L-U5/L-U6 vocabulary)
- ✅ Validate motion consistency (subject motion vs animation pattern)
- ✅ Validate camera/motion compatibility
- ✅ Validate cross-scene continuity
- ✅ Detect prompt loss between intent and compiled output
- ✅ Validate knowledge/provenance coverage
- ✅ Validate format consistency (IMAGE vs VIDEO)
- ✅ Validate sound semantic consistency
- ✅ Validate fallback visibility
- ✅ Validate conflict visibility
- ✅ Validate contract compatibility
- ✅ Validate provider readiness (semantic, not API)
- ✅ Validate generation readiness

## What L-U7 Does NOT Do

- ❌ Generate media
- ❌ Call any provider (Google Flow, DINO, Veo, Runway, Wan, Hunyuan, LTX, OpenAI)
- ❌ Call any LLM
- ❌ Render (Remotion, FFmpeg)
- ❌ Mutate upstream contracts
- ❌ Become an AnimationCompiler
- ❌ Become an EditorialCompiler
- ❌ Become a CharacterSystemEngine
- ❌ Touch timing/audio mixing authority (P7/P8/P9)
- ❌ Create fake quality scores or fake confidence

## Validation Model

### QualityValidationResult

| Field | Type | Description |
|---|---|---|
| `validation_id` | str | Deterministic SHA-256[:32] of canonical inputs |
| `status` | ValidationStatus | PASS / WARN / REJECT / UNAVAILABLE |
| `generation_readiness` | GenerationReadiness | READY / READY_WITH_WARNINGS / NOT_READY / UNAVAILABLE |
| `is_valid` | bool | True iff status is PASS or WARN |
| `policy_name` | ValidationPolicyName | STRICT / STANDARD / LENIENT |
| `dimensions` | tuple[DimensionResult] | Per-dimension state |
| `blocking_issues` | tuple[ValidationIssue] | Blocking issues only |
| `errors` | tuple[ValidationIssue] | Error issues only |
| `warnings` | tuple[ValidationIssue] | Warning issues only |
| `infos` | tuple[ValidationIssue] | Info issues only |
| `prompt_loss` | PromptLossReport | Structural prompt loss |
| `knowledge_version` | str | Knowledge version (e.g. "no-knowledge") |
| `is_knowledge_active` | bool | Whether knowledge was used |
| `knowledge_ids_used` | frozenset[str] | Knowledge IDs that contributed |
| `prompt_compilation_fingerprint` | str | Fingerprint of PCR |
| `cms_compilation_fingerprint` | str | Fingerprint of CMS result |
| `character_reference_id` | str | Character ID (if any) |
| `storyboard_fingerprint` | str | Fingerprint of storyboard |
| `engine_version` | str | "1.0.0" |
| `policy_version` | str | "1.0.0" |
| `validated_at` | datetime | Informational only, NOT in fingerprint |

### Severity Model

- **INFO**: optional field absent or minor note
- **WARNING**: knowledge fallback, optional missing, low-confidence
- **ERROR**: semantic mismatch, completeness violation
- **BLOCKING**: identity drift, malformed contract, impossible contradiction

### ValidationStatus

- **PASS**: ready for downstream pipeline
- **WARN**: ready, with non-blocking issues
- **REJECT**: blocking issues, cannot proceed
- **UNAVAILABLE**: validation could not run (missing inputs)

## 15 Validation Dimensions

| # | Dimension | What it checks |
|---|---|---|
| 1 | SEMANTIC_COMPLETENESS | Required semantic fields present |
| 2 | CHARACTER_IDENTITY_CONSISTENCY | L-U4 invariant (identity ≠ scene state) |
| 3 | CAMERA | Vocabulary, direction, IMAGE/VIDEO compatibility |
| 4 | MOTION | Subject motion ≠ animation pattern |
| 5 | CAMERA_MOTION_COMPATIBILITY | Three concepts are distinct |
| 6 | CONTINUITY | Cross-scene identity, palette, wardrobe |
| 7 | PROMPT_LOSS | Intent → IR → CMS semantic preservation |
| 8 | KNOWLEDGE_PROVENANCE | Knowledge-derived fields have provenance |
| 9 | FORMAT | IMAGE vs VIDEO, motion rules |
| 10 | SOUND_SEMANTIC | Sound layer intent (not audio mixing) |
| 11 | FALLBACK_VISIBILITY | Fallback is recorded, not silent |
| 12 | CONFLICT_VISIBILITY | EXPLICIT > KNOWLEDGE > DEFAULT visible |
| 13 | CONTRACT_COMPATIBILITY | Upstream contracts are well-formed |
| 14 | PROVIDER_READINESS | Semantic readiness for adapter |
| 15 | GENERATION_READINESS | Semantic readiness for generation |

## Validation Policies

- **STRICT**: critical uncertainty → block, max 3 warnings, warnings block
- **STANDARD** (default): errors block, warnings are non-blocking
- **LENIENT**: only blocking issues block, broad tolerance

Policies change **validation thresholds**; they do NOT change canonical
semantics. LENIENT still surfaces identity drift as BLOCKING.

## Determinism

L-U7 is fully deterministic. Same inputs → same output.

- No random, UUID, current timestamp in decision fields
- `validation_id` derived deterministically from input fingerprints
- Validator fingerprint is reproducible

## Hybrid Validation

"Hybrid" means:

1. **Structural Validation** — Pydantic field presence, type checks
2. **Semantic Rule Validation** — domain-specific rules (camera direction, etc.)
3. **Cross-Contract Validation** — PCR ↔ CMS ↔ CharacterReference ↔ Storyboard
4. **Provenance Validation** — Knowledge-derived fields have provenance

L-U7 does NOT use LLMs, embeddings, vision models, or external APIs.

## Architecture Tests

L-U7 is forbidden from importing:

- `app.providers.*`
- `Remotion`, `FFmpeg`, `subprocess`
- `app.animation` runtime implementation
- `app.editorial` runtime implementation
- `app.voice` runtime implementation

L-U7 can consume contracts (via context reference, not copy).

## Files

```
orchestrator/app/quality/
    __init__.py          — public exports
    schemas.py           — canonical schemas
    validators.py        — 15 dimension validators
    engine.py            — QualityEngine orchestrator

orchestrator/tests/
    test_hybrid_quality_validation.py — 78 tests

docs/
    HYBRID_QUALITY_VALIDATION.md   — this file
    ADR-016.md                      — architectural decision record
    PROMPT_LU7_FINAL_REPORT.md      — final report
```

## Pipeline

```
validate(ctx)
    ↓
1. validate_contract_compatibility
    ↓
2. validate_semantic_completeness
    ↓
3. validate_character_identity
    ↓
4. validate_camera
    ↓
5. validate_motion
    ↓
6. validate_camera_motion_compatibility
    ↓
7. validate_continuity
    ↓
8. validate_prompt_loss
    ↓
9. validate_knowledge_provenance
    ↓
10. validate_sound_semantic
    ↓
11. validate_format
    ↓
12. validate_fallback_visibility
    ↓
13. validate_conflict_visibility
    ↓
14. validate_provider_readiness
    ↓
15. validate_generation_readiness
    ↓
aggregate → QualityValidationResult
```

All dimensions are evaluated; L-U7 does not short-circuit.

## Future Boundary

L-U7 is the last pipeline stage **before**:

- Provider Adapter Layer (FUTURE)
- Image/Video Generation (FUTURE)
- Animation, Editorial, Voice, Mastering (P7/P8/P9/P10)
- Media QA
- Final Video, Shorts, Thumbnail, Publishing

L-U7 does NOT implement these stages. It only validates that the upstream
intent is qualified to enter them.

## Example

```python
from app.quality import (
    QualityEngine,
    QualityValidationContext,
    ValidationPolicy,
)

engine = QualityEngine(ValidationPolicy.standard())

# Build context from upstream contracts (no copy)
ctx = QualityValidationContext(
    prompt_compilation_result=pcr,
    cms_compilation_result=cms,
    character_reference_spec=spec,
    policy=ValidationPolicy.standard(),
)

# Run validation
result = engine.validate(ctx)

# Use the result
if result.status == ValidationStatus.REJECT:
    log_blocking_issues(result.blocking_issues)
elif result.status == ValidationStatus.WARN:
    log_warnings(result.warnings)
elif result.status == ValidationStatus.PASS:
    proceed_to_provider_layer(result)
else:  # UNAVAILABLE
    handle_missing_inputs(result)
```

## Status

L-U7 is **IMPLEMENTED** and **VERIFIED**.

PRODUCTION_READY is pending full pipeline integration (P0-P12).

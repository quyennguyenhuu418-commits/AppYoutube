# Provider Adapter Layer (L-U8)

## Status

**IMPLEMENTED — STRUCTURAL_ONLY**

This layer defines the canonical contracts and adapters for translating
semantic production intent into provider-specific generation requests.
No real provider has been execution-verified in this layer.

---

## Purpose

The Provider Adapter Layer (L-U8) is the translation boundary between the
canonical semantic production pipeline (L-U1–L-U8) and the generation runtime.

```
CanonicalPromptIR (L-U5)
CameraMotionSoundCompilationResult (L-U6)
CharacterReferenceSpecification (L-U4)
QualityValidationResult (L-U7)
        |
        v
ProviderPromptAdapter (L-U8)  <-- You are here
        |
        v
ProviderGenerationRequest
        |
        v
[PROVIDER-SPECIFIC REPRESENTATION]
        |
        v
[GENERATION RUNTIME - FUTURE]
```

L-U8 does NOT:
- Call any real provider API
- Generate media
- Implement GPU schedulers, worker queues, or retry engines
- Rewrite canonical IR with LLMs

---

## Architecture

### Provider Abstraction

`ProviderDefinition` — canonical metadata for a provider:

- `provider_id` — unique ID (e.g., `mock_gen`, `google_flow`)
- `provider_type` — semantic categories (IMAGE_GENERATION, VIDEO_GENERATION, etc.)
- `display_name` — human-readable name
- `version` — provider API version
- `execution_mode` — LOCAL / REMOTE / UNKNOWN
- `adapter_version` — version of the adapter contract
- `status` — ACTIVE / DISABLED / EXPERIMENTAL / UNAVAILABLE
- `verification` — VERIFIED / DECLARED / UNKNOWN

`ProviderType` — semantic category (NOT provider business logic):
- `IMAGE_GENERATION`
- `VIDEO_GENERATION`
- `TTS`
- `TRANSLATION`
- `RESEARCH`
- `EMBEDDING`

### Capability Registry

`ProviderCapability` — describes what a provider can do for a specific task:

- `capability_id` — unique ID
- `provider_id` — parent provider
- `supported_prompt_kinds` — which prompt kinds (image, video, etc.)
- `supported_aspect_ratios` — aspect ratio support
- `supported_camera_shots` — which camera shots
- `supported_camera_movements` — which camera movements
- `supported_subject_motions` — which subject motions
- `character_reference_support` — character reference support
- `negative_constraint_support` — negative constraint support
- `verification` — VERIFIED / DECLARED / UNKNOWN

`CapabilityMatcher` — deterministic matching:

```
GenerationCapabilityRequirement
        |
        v
CapabilityMatcher
        |
        v
CapabilityMatchResult { SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED | UNKNOWN }
```

NO ranking. NO recommendation engine.

### Provider Prompt Adapter

`ProviderPromptAdapter` — abstract interface:

```python
class ProviderPromptAdapter(ABC):
    @abstractmethod
    def translate(
        self,
        canonical_ir,       # CanonicalPromptIR (L-U5)
        cms_result,         # CameraMotionSoundCompilationResult (L-U6)
        quality_result,     # QualityValidationResult (L-U7)
        character_spec,     # CharacterReferenceSpecification (L-U4)
        provider_params=None,
    ) -> ProviderPromptRepresentation:
        ...
```

`ProviderPromptRepresentation` — output of the adapter:

- `provider_id` — which provider this was translated for
- `capability_id` — which capability was used
- `representation` — provider-specific structured data
- `semantic_loss` — SemanticLossReport

### Semantic Loss Report

**BANNER: Every semantic field MUST appear in this report. No silent dropping.**

`SemanticLossReport` — field-level translation status:

- `SUPPORTED` — provider fully supports this field
- `TRANSFORMED` — supported but with provider-specific syntax
- `APPROXIMATED` — approximated with a close semantic
- `OMITTED_WITH_REASON` — intentionally omitted, reason provided
- `UNSUPPORTED` — provider cannot represent this field

Properties:
- `has_loss` — True if unsupported or omitted fields exist
- `coverage_ratio` — supported_fields / total_fields
- `all_supported` — True if all fields are SUPPORTED

### Provider Generation Request

`ProviderGenerationRequest` — canonical execution boundary:

- `request_id` — unique request ID
- `provider_id` — target provider
- `capability_id` — which capability
- `canonical_prompt_fingerprint` — SHA-256[:32] of canonical IR
- `provider_representation` — from the adapter
- `character_reference_id` — from L-U4
- `asset_ids` — from AssetRegistry
- `adapter_version` + `provider_version`
- `provider_request_fingerprint` — deterministic, NO secrets
- `quality_status` — PASS / WARN / REJECT / UNAVAILABLE from L-U7
- `provenance` — metadata (NO secrets)

Secrets are passed via execution boundary (environment, headers), NOT in this request.

### Provider Error Taxonomy

`ProviderError` — canonical error boundary:

| Error Kind | Retry Classification |
|---|---|
| `INVALID_REQUEST` | NON_RETRYABLE |
| `UNSUPPORTED_CAPABILITY` | NON_RETRYABLE |
| `AUTHENTICATION` | NON_RETRYABLE |
| `AUTHORIZATION` | NON_RETRYABLE |
| `RATE_LIMIT` | RETRYABLE |
| `TIMEOUT` | RETRYABLE |
| `NETWORK` | RETRYABLE |
| `PROVIDER_UNAVAILABLE` | RETRYABLE |
| `CONTENT_REJECTED` | NON_RETRYABLE |
| `INVALID_RESPONSE` | UNKNOWN |
| `UNKNOWN` | UNKNOWN |

---

## Quality Gate Integration

L-U7 `QualityValidationResult` is the gate:

```
QualityValidationResult.status = REJECT
        --> NO provider request compilation (caller must enforce)
QualityValidationResult.status = WARN
        --> Compilation allowed, warnings preserved
QualityValidationResult.status = PASS
        --> Normal compilation
QualityValidationResult.status = UNAVAILABLE
        --> DO NOT assume generation-ready
```

The ProviderPromptAdapter does NOT override QualityEngine decisions.

---

## Files

| File | Description |
|---|---|
| `app/providers/generation/schemas.py` | Canonical Pydantic contracts |
| `app/providers/generation/registry.py` | ProviderRegistry + default providers |
| `app/providers/generation/matcher.py` | Deterministic capability matcher |
| `app/providers/generation/mock_adapter.py` | MockGenerationProviderAdapter |
| `tests/test_provider_adapter_layer.py` | 94 tests covering all L-U8 components |

---

## Known Providers

| Provider | Type | Status | Verification |
|---|---|---|---|
| `mock_gen` | IMAGE, VIDEO | ACTIVE | DECLARED |
| `google_flow` | IMAGE | EXPERIMENTAL | UNKNOWN |
| `dino_ai` | IMAGE | EXPERIMENTAL | UNKNOWN |
| `generic_video` | VIDEO | EXPERIMENTAL | UNKNOWN |

---

## Constraints

1. **No real generation** — L-U8 is a translation layer only
2. **No provider SDK imports** in `app.prompt`, `app.knowledge`, `app.character`, `app.quality`
3. **No silent semantic loss** — every field must be reported
4. **No secrets in requests or fingerprints**
5. **No ranking or recommendation** — only compatibility determination
6. **No execution infrastructure** — no queues, schedulers, or workers

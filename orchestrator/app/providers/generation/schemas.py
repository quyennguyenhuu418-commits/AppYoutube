"""
Canonical schemas for the Provider Adapter Layer (L-U8).

This module defines the canonical contracts for translating structured
semantic production intent (CanonicalPromptIR, CameraMotionSoundCompilationResult,
CharacterReferenceSpecification, QualityValidationResult) into
provider-specific generation requests.

L-U8 does NOT implement real generation. It establishes the deterministic
translation boundary between the canonical semantic layer (L-U5/L-U6/L-U7)
and the generation runtime.

Architecture
------------
    CanonicalPromptIR (L-U5)
    CameraMotionSoundCompilationResult (L-U6)
    CharacterReferenceSpecification (L-U4)
    QualityValidationResult (L-U7)
            ↓
    ┌──────────────────────────────┐
    │  ProviderPromptAdapter (L-U8)  │
    │  (canonical interface)          │
    └──────────────────────────────┘
            ↓
    ProviderGenerationRequest
            ↓
    Provider-specific representation
            ↓
    [GENERATION RUNTIME — FUTURE]

Critical invariants
-----------------
1. ProviderAdapter REPORTS semantic loss. It never mutates the canonical IR.
2. Provider-specific syntax lives ONLY in the provider representation.
3. No provider SDK, API key, or secret in the canonical request.
4. Deterministic: same canonical input + same provider → same request fingerprint.
5. Character identity from L-U4 is preserved. Provider cannot redesign identity.
6. Asset IDs from AssetRegistry are the authority. Provider adapter translates.
7. QualityValidationResult.REJECT blocks compilation. Adapter cannot override.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, FrozenSet, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Provider type — semantic categories, NOT provider business logic
# ============================================================================


class ProviderType(str, Enum):
    """Semantic category of a provider.

    These are NOT provider IDs. One ProviderDefinition may have multiple types.
    """

    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    TTS = "tts"
    TRANSLATION = "translation"
    RESEARCH = "research"
    EMBEDDING = "embedding"


class ProviderStatus(str, Enum):
    """Runtime availability state of a provider."""

    ACTIVE = "active"
    DISABLED = "disabled"
    EXPERIMENTAL = "experimental"
    UNAVAILABLE = "unavailable"


class ExecutionMode(str, Enum):
    """Semantic execution mode of a provider."""

    LOCAL = "local"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class ProviderVerificationStatus(str, Enum):
    """Verification status of a provider definition.

    - VERIFIED: runtime-validated end-to-end.
    - DECLARED: documented but not runtime-verified.
    - UNKNOWN: no runtime evidence.
    """

    VERIFIED = "verified"
    DECLARED = "declared"
    UNKNOWN = "unknown"


# ============================================================================
# Semantic Loss — field-level translation status
# ============================================================================


class SemanticLossStatus(str, Enum):
    """Status of a semantic field after translation.

    - SUPPORTED: provider fully supports this semantic field.
    - TRANSFORMED: supported but transformed to provider-specific syntax.
    - APPROXIMATED: approximated with a close but not exact semantic.
    - OMITTED_WITH_REASON: intentionally omitted, reason provided.
    - UNSUPPORTED: provider cannot represent this field.
    """

    SUPPORTED = "supported"
    TRANSFORMED = "transformed"
    APPROXIMATED = "approximated"
    OMITTED_WITH_REASON = "omitted_with_reason"
    UNSUPPORTED = "unsupported"


class SemanticLossField(BaseModel):
    """Translation status for one semantic field."""

    model_config = {"frozen": True}

    field_path: str = Field(
        min_length=1, max_length=128,
        description="Dot-path to the semantic field (e.g. 'camera.shot_type')",
    )
    status: SemanticLossStatus = Field(...)
    description: str = Field(
        max_length=256,
        description="Human-readable description of what happened",
    )
    provider_value: Optional[str] = Field(
        default=None, max_length=512,
        description="Provider-specific serialized value if relevant",
    )
    reason: Optional[str] = Field(
        default=None, max_length=256,
        description="Explanation when OMITTED_WITH_REASON or UNSUPPORTED",
    )


class SemanticLossReport(BaseModel):
    """Report of semantic translation from canonical IR to provider representation.

    Every semantic field MUST appear in this report with an explicit status.
    Silent dropping is prohibited.
    """

    model_config = {"frozen": True}

    total_fields: int = Field(ge=0)
    supported_fields: int = Field(ge=0)
    transformed_fields: int = Field(ge=0)
    approximated_fields: int = Field(ge=0)
    omitted_fields: int = Field(ge=0)
    unsupported_fields: int = Field(ge=0)

    fields: tuple[SemanticLossField, ...] = Field(default_factory=tuple)

    @property
    def has_loss(self) -> bool:
        return self.unsupported_fields > 0 or self.omitted_fields > 0

    @property
    def coverage_ratio(self) -> float:
        if self.total_fields == 0:
            return 1.0
        return self.supported_fields / self.total_fields

    @property
    def all_supported(self) -> bool:
        return self.total_fields == self.supported_fields


# ============================================================================
# Provider Definition — canonical metadata
# ============================================================================


class ProviderDefinition(BaseModel):
    """Canonical metadata for a single provider.

    This is NOT a concrete implementation. It describes what a provider
    can do, what its capabilities are, and what its status is.

    The ProviderRegistry maintains the canonical registry of all known providers.
    """

    model_config = {"frozen": True}

    provider_id: str = Field(
        min_length=1, max_length=64,
        description="Unique canonical provider ID (e.g. 'google_flow', 'dino_ai', 'mock_gen')",
    )
    display_name: str = Field(
        max_length=128,
        description="Human-readable display name",
    )
    provider_type: tuple[ProviderType, ...] = Field(
        min_length=1,
        description="Semantic categories this provider supports",
    )
    version: str = Field(
        max_length=32,
        description="Provider API/version string",
    )
    execution_mode: ExecutionMode = Field(default=ExecutionMode.UNKNOWN)
    adapter_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
    )
    status: ProviderStatus = Field(default=ProviderStatus.EXPERIMENTAL)
    verification: ProviderVerificationStatus = Field(
        default=ProviderVerificationStatus.UNKNOWN,
    )

    # Execution requirements (NOT secrets)
    requires_api_key: bool = Field(default=False)
    endpoint: Optional[str] = Field(
        default=None, max_length=256,
        description="Base URL if REMOTE, None if LOCAL",
    )
    default_model: Optional[str] = Field(
        default=None, max_length=64,
    )

    # Identity
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def is_active(self) -> bool:
        return self.status == ProviderStatus.ACTIVE

    def supports_type(self, kind: ProviderType) -> bool:
        return kind in self.provider_type


# ============================================================================
# Provider Capability — what a provider can do for a given generation task
# ============================================================================


class CapabilityVerificationStatus(str, Enum):
    """Verification status of a capability claim."""

    VERIFIED = "verified"
    DECLARED = "declared"
    UNKNOWN = "unknown"


class AspectRatioSpec(BaseModel):
    """Supported aspect ratio for a capability."""

    model_config = {"frozen": True}

    ratio: str = Field(
        description="Aspect ratio string, e.g. '16:9', '9:16', '1:1', '4:3'",
    )
    supported: bool = Field(default=True)


class ProviderCapability(BaseModel):
    """Canonical description of what a provider can do for a specific task.

    One ProviderDefinition may have multiple ProviderCapabilities (one per task).
    """

    model_config = {"frozen": True}

    capability_id: str = Field(min_length=1, max_length=64)
    provider_id: str = Field(min_length=1, max_length=64)
    provider_type: ProviderType = Field(...)

    # Prompt kind coverage
    supported_prompt_kinds: tuple[str, ...] = Field(
        min_length=1,
        description="Supported prompt kinds: 'image', 'video', etc.",
    )

    # Format
    supported_aspect_ratios: tuple[AspectRatioSpec, ...] = Field(
        default_factory=tuple,
    )

    # Semantic coverage
    supported_camera_shots: FrozenSet[str] = Field(default_factory=frozenset)
    supported_camera_movements: FrozenSet[str] = Field(default_factory=frozenset)
    supported_subject_motions: FrozenSet[str] = Field(default_factory=frozenset)
    supported_motion_patterns: FrozenSet[str] = Field(default_factory=frozenset)
    supported_sound_semantics: FrozenSet[str] = Field(default_factory=frozenset)

    # Feature support
    character_reference_support: bool = Field(default=False)
    negative_constraint_support: bool = Field(default=False)
    sound_layers_support: bool = Field(default=False)

    # Constraints
    maximum_duration_sec: Optional[float] = Field(
        default=None, ge=0,
        description="Maximum video duration in seconds (video only)",
    )
    maximum_characters: Optional[int] = Field(
        default=None, ge=0,
        description="Maximum character count for prompts",
    )

    # Verification
    verification: CapabilityVerificationStatus = Field(
        default=CapabilityVerificationStatus.UNKNOWN,
    )

    def supports_aspect_ratio(self, ratio: str) -> bool:
        for spec in self.supported_aspect_ratios:
            if spec.ratio == ratio:
                return spec.supported
        return False

    def supports_prompt_kind(self, kind: str) -> bool:
        return kind in self.supported_prompt_kinds


# ============================================================================
# Generation Capability Requirement
# ============================================================================


class GenerationCapabilityRequirement(BaseModel):
    """Canonical description of what a generation task requires.

    Used by CapabilityMatcher to find compatible providers.
    """

    model_config = {"frozen": True}

    prompt_kind: str = Field(...)
    aspect_ratio: Optional[str] = Field(default=None)
    duration_sec: Optional[float] = Field(default=None, ge=0)
    requires_character_reference: bool = Field(default=False)
    requires_negative_constraints: bool = Field(default=False)
    requires_sound_layers: bool = Field(default=False)
    camera_shots: FrozenSet[str] = Field(default_factory=frozenset)
    camera_movements: FrozenSet[str] = Field(default_factory=frozenset)
    subject_motions: FrozenSet[str] = Field(default_factory=frozenset)


class CapabilityCompatibility(str, Enum):
    """Result of matching a requirement against a capability."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class CapabilityMatchResult(BaseModel):
    """Result of matching a requirement against a capability."""

    model_config = {"frozen": True}

    compatibility: CapabilityCompatibility = Field(...)
    capability: ProviderCapability = Field(...)
    unsupported_features: tuple[str, ...] = Field(default_factory=tuple)
    partially_supported_features: tuple[str, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple)


# ============================================================================
# Provider Prompt Adapter — canonical translation interface
# ============================================================================


class ProviderPromptAdapter(ABC):
    """Abstract interface for translating canonical IR to provider-specific prompts.

    This is the STRUCTURAL interface. It does NOT make real API calls.
    Real execution belongs to the generation runtime (future).

    Subclasses MUST implement translate() and can optionally override
    get_capability() for dynamic capability queries.
    """

    @abstractmethod
    def translate(
        self,
        canonical_ir: Any,
        cms_result: Any,
        quality_result: Any,
        character_spec: Any,
        provider_generation_params: Optional[Any] = None,
    ) -> "ProviderPromptRepresentation":
        """Translate canonical semantic IR to provider-specific representation.

        Parameters:
            canonical_ir: CanonicalPromptIR (L-U5)
            cms_result: CameraMotionSoundCompilationResult (L-U6)
            quality_result: QualityValidationResult (L-U7)
            character_spec: CharacterReferenceSpecification (L-U4)
            provider_generation_params: Optional provider-specific generation params

        Returns:
            ProviderPromptRepresentation with serialized prompts and semantic loss

        Raises:
            ProviderCompilationError: if translation cannot proceed
        """
        ...

    def get_capability(self) -> ProviderCapability:
        """Return the capability description for this adapter.

        Override to return dynamic capability based on adapter state.
        """
        raise NotImplementedError


# ============================================================================
# Provider Prompt Representation — output of the adapter
# ============================================================================


class ProviderPromptRepresentation(BaseModel):
    """Structured provider-specific prompt representation.

    This is the output of ProviderPromptAdapter.translate().
    It contains the serialized provider prompt and the semantic loss report.

    The representation is provider-specific and MUST NOT be consumed by
    other providers.
    """

    model_config = {"frozen": True}

    provider_id: str = Field(...)
    capability_id: str = Field(...)
    prompt_kind: str = Field(...)  # 'image' or 'video'

    # Provider-specific serialized representation
    # The content of this field is provider-specific. Its structure depends
    # on what the specific ProviderPromptAdapter emits.
    # Examples:
    #   - Google Flow: {"prompt_text": "...", "style": "...", "aspect_ratio": "..."}
    #   - DINO: {"prompt": "...", "pet_size": "sm"}
    #   - Mock: {"semantic_prompt": "...", "mock_generation": True}
    representation: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific structured representation",
    )

    # Semantic loss
    semantic_loss: SemanticLossReport = Field(...)

    # Provenance
    adapter_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
    )
    provider_version: str = Field(default="unknown", max_length=32)
    compiled_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_unsupported_fields(self) -> bool:
        return self.semantic_loss.unsupported_fields > 0

    @property
    def coverage_ratio(self) -> float:
        return self.semantic_loss.coverage_ratio


# ============================================================================
# Provider Generation Request — canonical boundary for execution
# ============================================================================


class ProviderGenerationRequest(BaseModel):
    """Canonical request boundary for provider execution.

    This is the request that the generation runtime sends to a provider.
    It contains all necessary information for the provider to execute
    the generation request, WITHOUT including secrets or API keys.

    Secrets are passed via the execution boundary (environment, headers),
    not in this request.
    """

    model_config = {"frozen": True}

    # Identity
    request_id: str = Field(min_length=1, max_length=64)
    provider_id: str = Field(min_length=1, max_length=64)
    capability_id: str = Field(min_length=1, max_length=64)

    # Semantic context
    prompt_kind: str = Field(...)
    canonical_prompt_fingerprint: str = Field(
        max_length=64,
        description="SHA-256[:32] fingerprint of the canonical IR",
    )

    # Provider representation
    provider_representation: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific prompt representation from adapter",
    )

    # Format
    aspect_ratio: Optional[str] = Field(default=None)
    format: str = Field(default="png")  # 'png', 'mp4', etc.

    # Character reference (if applicable)
    character_reference_id: Optional[str] = Field(default=None, max_length=64)
    character_reference_fingerprint: Optional[str] = Field(
        default=None, max_length=64,
    )

    # Asset references
    asset_ids: tuple[str, ...] = Field(default_factory=tuple)

    # Duration (video only)
    duration_sec: Optional[float] = Field(default=None, ge=0)

    # Version metadata
    adapter_version: str = Field(default="1.0.0")
    provider_version: str = Field(default="unknown")
    provider_request_fingerprint: str = Field(
        default="__unspecified__",
        max_length=64,
        description="SHA-256[:32] of canonical inputs only (NO secrets). "
                    "Must be set explicitly for real requests.",
    )

    # Provenance
    quality_status: str = Field(
        max_length=16,
        description="PASS, WARN, REJECT, or UNAVAILABLE from L-U7",
    )
    quality_validation_id: Optional[str] = Field(
        default=None, max_length=64,
    )
    provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about origin (NO secrets)",
    )

    # Metadata (informational only, NOT in fingerprint)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Canonical error taxonomy
# ============================================================================


class ProviderErrorKind(str, Enum):
    """Canonical taxonomy of provider errors.

    These are the ONLY error kinds that the ProviderAdapterLayer may emit.
    The generation runtime (future) maps provider-specific errors to these kinds.
    """

    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK = "network"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CONTENT_REJECTED = "content_rejected"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN = "unknown"


class RetryClassification(str, Enum):
    """Retry classification for provider errors."""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    UNKNOWN = "unknown"


class ProviderError(BaseModel):
    """Canonical provider error."""

    model_config = {"frozen": True}

    kind: ProviderErrorKind = Field(...)
    message: str = Field(max_length=512)
    retry_classification: RetryClassification = Field(
        default=RetryClassification.UNKNOWN,
    )
    provider_id: str = Field(max_length=64)
    request_id: Optional[str] = Field(default=None, max_length=64)
    provider_error_code: Optional[str] = Field(
        default=None, max_length=64,
        description="Provider-specific error code",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional details (NO secrets)",
    )
    occurred_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def classify(cls, kind: ProviderErrorKind) -> "ProviderError":
        """Create a canonical error with the correct retry classification."""
        retry_map = {
            ProviderErrorKind.INVALID_REQUEST: RetryClassification.NON_RETRYABLE,
            ProviderErrorKind.UNSUPPORTED_CAPABILITY: RetryClassification.NON_RETRYABLE,
            ProviderErrorKind.AUTHENTICATION: RetryClassification.NON_RETRYABLE,
            ProviderErrorKind.AUTHORIZATION: RetryClassification.NON_RETRYABLE,
            ProviderErrorKind.RATE_LIMIT: RetryClassification.RETRYABLE,
            ProviderErrorKind.TIMEOUT: RetryClassification.RETRYABLE,
            ProviderErrorKind.NETWORK: RetryClassification.RETRYABLE,
            ProviderErrorKind.PROVIDER_UNAVAILABLE: RetryClassification.RETRYABLE,
            ProviderErrorKind.CONTENT_REJECTED: RetryClassification.NON_RETRYABLE,
            ProviderErrorKind.INVALID_RESPONSE: RetryClassification.UNKNOWN,
            ProviderErrorKind.UNKNOWN: RetryClassification.UNKNOWN,
        }
        return cls(
            kind=kind,
            message="",
            provider_id="unknown",
            retry_classification=retry_map.get(kind, RetryClassification.UNKNOWN),
        )


# ============================================================================
# Public exports
# ============================================================================


__all__ = [
    # Enums
    "ProviderType",
    "ProviderStatus",
    "ExecutionMode",
    "ProviderVerificationStatus",
    "SemanticLossStatus",
    "CapabilityCompatibility",
    "CapabilityVerificationStatus",
    "ProviderErrorKind",
    "RetryClassification",
    # Schemas
    "SemanticLossField",
    "SemanticLossReport",
    "ProviderDefinition",
    "AspectRatioSpec",
    "ProviderCapability",
    "GenerationCapabilityRequirement",
    "CapabilityMatchResult",
    "ProviderPromptRepresentation",
    "ProviderGenerationRequest",
    "ProviderError",
    # Abstract interface
    "ProviderPromptAdapter",
]

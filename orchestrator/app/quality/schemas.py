"""
Hybrid Quality Validation — canonical schemas.

L-U7 — Quality gate before provider/generation layer.

Architecture
------------
L-U7 consumes existing canonical contracts (no mutation):

    PromptCompilationResult (L-U5)
            ↓
    CameraMotionSoundCompilationResult (L-U6)
            ↓
    CharacterReferenceSpecification (L-U4)
            ↓
    StoryboardPackage (P5)
            ↓
    KnowledgeContext / KnowledgeResolver (L-U3)
            ↓
    ┌──────────────────────────────┐
    │  QualityValidationEngine     │
    │  (L-U7 — pure, deterministic)│
    └──────────────────────────────┘
            ↓
    QualityValidationResult
            ↓
    PASS / WARN / REJECT / UNAVAILABLE
            ↓
    [PROVIDER ADAPTER LAYER — FUTURE]

What this module provides:
- Validation dimension vocabulary (15 dimensions)
- Severity model (INFO/WARNING/ERROR/BLOCKING)
- Issue schema (structured validation issue)
- QualityValidationResult (frozen Pydantic)
- ValidationContext (immutable input bundle)
- ValidationPolicy (STRICT/STANDARD/LENIENT)

What this module does NOT do:
- Generate media
- Call providers
- Call LLM
- Render
- Mutate upstream contracts
- Touch animation/editorial/voice runtime

Critical invariants:
1. The validator REPORTS issues. It NEVER mutates contracts.
2. No fake quality scores. No fake confidence.
3. No provider SDK, Remotion, FFmpeg imports.
4. Deterministic: same input → same output.
5. Identity ≠ Scene State (L-U4) is preserved.
6. Timing authority remains with P7/P8/P9. L-U7 does not duplicate it.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, FrozenSet, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Validation status
# ============================================================================


class ValidationStatus(str, Enum):
    """Quality validation outcome.

    - PASS: ready for downstream pipeline (provider/generation).
    - WARN: ready, with non-blocking issues surfaced.
    - REJECT: blocking issues. Cannot proceed without resolution.
    - UNAVAILABLE: validation could not run (missing inputs, etc.).
    """

    PASS = "pass"
    WARN = "warn"
    REJECT = "reject"
    UNAVAILABLE = "unavailable"


class GenerationReadiness(str, Enum):
    """Semantic readiness for the next pipeline stage."""

    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    NOT_READY = "not_ready"
    UNAVAILABLE = "unavailable"


class ValidationSeverity(str, Enum):
    """Severity of a validation issue.

    Not all severities are blocking. The mapping is policy-driven.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class ValidationDimension(str, Enum):
    """Validation dimensions covered by L-U7."""

    SEMANTIC_COMPLETENESS = "semantic_completeness"
    CHARACTER_IDENTITY_CONSISTENCY = "character_identity_consistency"
    CAMERA = "camera"
    MOTION = "motion"
    CAMERA_MOTION_COMPATIBILITY = "camera_motion_compatibility"
    CONTINUITY = "continuity"
    PROMPT_LOSS = "prompt_loss"
    KNOWLEDGE_PROVENANCE = "knowledge_provenance"
    FORMAT = "format"
    SOUND_SEMANTIC = "sound_semantic"
    FALLBACK_VISIBILITY = "fallback_visibility"
    CONFLICT_VISIBILITY = "conflict_visibility"
    CONTRACT_COMPATIBILITY = "contract_compatibility"
    PROVIDER_READINESS = "provider_readiness"
    GENERATION_READINESS = "generation_readiness"


class DimensionState(str, Enum):
    """Per-dimension state in the validation result."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


class ValidationPolicyName(str, Enum):
    """Validation policy — STRICT, STANDARD, LENIENT."""

    STRICT = "strict"
    STANDARD = "standard"
    LENIENT = "lenient"


class IssueSource(str, Enum):
    """Where a validation issue originated."""

    EXPLICIT_INTENT = "explicit_intent"
    KNOWLEDGE = "knowledge"
    ENGINE_DEFAULT = "engine_default"
    CROSS_CONTRACT = "cross_contract"
    STRUCTURAL = "structural"
    UNKNOWN = "unknown"


# ============================================================================
# Validation Policy
# ============================================================================


class ValidationPolicy(BaseModel):
    """Configurable validation policy.

    Policies change validation thresholds; they do NOT change canonical
    semantics. A LENIENT policy still surfaces blocking issues like
    identity drift.
    """

    model_config = {"frozen": True}

    name: ValidationPolicyName = ValidationPolicyName.STANDARD

    # Severity → blocking mapping
    block_on_blocking: bool = Field(default=True)
    block_on_error: bool = Field(default=True)
    block_on_warning: bool = Field(default=False)  # default: only errors/blocking
    block_on_info: bool = Field(default=False)

    # Dimension-specific thresholds
    max_warnings: int = Field(default=10, ge=0, le=1000)
    allow_knowledge_disabled: bool = Field(default=True)
    require_provenance_on_knowledge_fields: bool = Field(default=True)
    require_character_continuity: bool = Field(default=True)
    require_explicit_override_justification: bool = Field(default=True)
    allow_motion_on_image: bool = Field(default=False)
    require_sound_layers_for_video: bool = Field(default=False)

    @classmethod
    def strict(cls) -> "ValidationPolicy":
        return cls(
            name=ValidationPolicyName.STRICT,
            block_on_blocking=True,
            block_on_error=True,
            block_on_warning=True,  # STRICT: warnings also block
            block_on_info=False,
            max_warnings=3,
            allow_knowledge_disabled=False,
            require_provenance_on_knowledge_fields=True,
            require_character_continuity=True,
            require_explicit_override_justification=True,
            allow_motion_on_image=False,
            require_sound_layers_for_video=True,
        )

    @classmethod
    def standard(cls) -> "ValidationPolicy":
        return cls(
            name=ValidationPolicyName.STANDARD,
            block_on_blocking=True,
            block_on_error=True,
            block_on_warning=False,
            block_on_info=False,
            max_warnings=10,
            allow_knowledge_disabled=True,
            require_provenance_on_knowledge_fields=True,
            require_character_continuity=True,
            require_explicit_override_justification=True,
            allow_motion_on_image=False,
            require_sound_layers_for_video=False,
        )

    @classmethod
    def lenient(cls) -> "ValidationPolicy":
        return cls(
            name=ValidationPolicyName.LENIENT,
            block_on_blocking=True,
            block_on_error=False,
            block_on_warning=False,
            block_on_info=False,
            max_warnings=50,
            allow_knowledge_disabled=True,
            require_provenance_on_knowledge_fields=False,
            require_character_continuity=False,
            require_explicit_override_justification=False,
            allow_motion_on_image=True,
            require_sound_layers_for_video=False,
        )


# ============================================================================
# Validation Issue
# ============================================================================


class ValidationIssue(BaseModel):
    """A single structured validation issue.

    The validator REPORTS issues. It NEVER mutates contracts.
    """

    model_config = {"frozen": True}

    issue_id: str = Field(min_length=1, max_length=64)
    dimension: ValidationDimension = Field(...)
    severity: ValidationSeverity = Field(...)
    source: IssueSource = IssueSource.UNKNOWN
    message: str = Field(min_length=1, max_length=512)
    field_path: Optional[str] = Field(default=None, max_length=128)
    contract_reference: Optional[str] = Field(default=None, max_length=128)
    knowledge_id: Optional[str] = Field(default=None, max_length=64)
    rule_id: Optional[str] = Field(default=None, max_length=64)

    def is_blocking(self, policy: ValidationPolicy) -> bool:
        if self.severity == ValidationSeverity.BLOCKING:
            return policy.block_on_blocking
        if self.severity == ValidationSeverity.ERROR:
            return policy.block_on_error
        if self.severity == ValidationSeverity.WARNING:
            return policy.block_on_warning
        if self.severity == ValidationSeverity.INFO:
            return policy.block_on_info
        return False


# ============================================================================
# Dimension state
# ============================================================================


class DimensionResult(BaseModel):
    """Per-dimension validation outcome."""

    model_config = {"frozen": True}

    dimension: ValidationDimension = Field(...)
    state: DimensionState = Field(default=DimensionState.UNAVAILABLE)
    issue_count: int = Field(default=0, ge=0)
    info_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    blocking_count: int = Field(default=0, ge=0)
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @classmethod
    def from_issues(
        cls,
        dimension: ValidationDimension,
        issues: list[ValidationIssue],
        notes: Optional[list[str]] = None,
    ) -> "DimensionResult":
        info = sum(1 for i in issues if i.severity == ValidationSeverity.INFO)
        warning = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
        error = sum(1 for i in issues if i.severity == ValidationSeverity.ERROR)
        blocking = sum(1 for i in issues if i.severity == ValidationSeverity.BLOCKING)

        if blocking > 0 or error > 0:
            state = DimensionState.FAIL
        elif warning > 0 or info > 0:
            state = DimensionState.WARN
        elif len(issues) == 0:
            state = DimensionState.PASS
        else:
            state = DimensionState.WARN

        return cls(
            dimension=dimension,
            state=state,
            issue_count=len(issues),
            info_count=info,
            warning_count=warning,
            error_count=error,
            blocking_count=blocking,
            notes=tuple(notes or []),
        )


# ============================================================================
# Prompt loss report
# ============================================================================


class PromptLossReport(BaseModel):
    """Tracks prompt loss between input intent and compiled output.

    This is a STRUCTURAL report. It does NOT use AI to guess what was
    'expected'. Expected values come only from explicit request,
    canonical IR, storyboard intent, or authoritative knowledge.
    """

    model_config = {"frozen": True}

    expected_elements: tuple[str, ...] = Field(default_factory=tuple)
    resolved_elements: tuple[str, ...] = Field(default_factory=tuple)
    lost_elements: tuple[str, ...] = Field(default_factory=tuple)
    partially_resolved: tuple[str, ...] = Field(default_factory=tuple)
    severity: ValidationSeverity = ValidationSeverity.INFO

    @property
    def coverage_ratio(self) -> float:
        if not self.expected_elements:
            return 1.0
        resolved = len(self.resolved_elements)
        return resolved / len(self.expected_elements)

    @property
    def has_loss(self) -> bool:
        return len(self.lost_elements) > 0


# ============================================================================
# Quality Validation Result
# ============================================================================


class QualityValidationResult(BaseModel):
    """Final structured output of the QualityValidationEngine.

    Frozen Pydantic. Deterministic. No timestamps in decision fields.
    """

    model_config = {"frozen": True}

    # --- Identity ---
    validation_id: str = Field(min_length=1, max_length=64)

    # --- Status ---
    status: ValidationStatus = Field(...)
    generation_readiness: GenerationReadiness = Field(...)
    is_valid: bool = Field(...)

    # --- Policy ---
    policy_name: ValidationPolicyName = Field(...)

    # --- Per-dimension state ---
    dimensions: tuple[DimensionResult, ...] = Field(default_factory=tuple)

    # --- Issues (severity-sorted) ---
    blocking_issues: tuple[ValidationIssue, ...] = Field(default_factory=tuple)
    errors: tuple[ValidationIssue, ...] = Field(default_factory=tuple)
    warnings: tuple[ValidationIssue, ...] = Field(default_factory=tuple)
    infos: tuple[ValidationIssue, ...] = Field(default_factory=tuple)

    # --- Prompt loss (separate, structured) ---
    prompt_loss: Optional[PromptLossReport] = Field(default=None)

    # --- Provenance ---
    knowledge_version: str = Field(
        default="no-knowledge",
        pattern=r"^\d+\.\d+\.\d+$|^no-knowledge$",
    )
    is_knowledge_active: bool = Field(default=False)
    knowledge_ids_used: FrozenSet[str] = Field(default_factory=frozenset)

    # --- Input fingerprints (for reproducibility) ---
    prompt_compilation_fingerprint: Optional[str] = Field(default=None, max_length=64)
    cms_compilation_fingerprint: Optional[str] = Field(default=None, max_length=64)
    character_reference_id: Optional[str] = Field(default=None, max_length=64)
    storyboard_fingerprint: Optional[str] = Field(default=None, max_length=64)

    # --- Version metadata ---
    engine_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
    )
    policy_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
    )

    # --- Validation timestamp (informational only, NOT in fingerprint) ---
    validated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_dimension_state(self, dimension: ValidationDimension) -> DimensionState:
        for d in self.dimensions:
            if d.dimension == dimension:
                return d.state
        return DimensionState.UNAVAILABLE

    def get_dimension_result(
        self, dimension: ValidationDimension
    ) -> Optional[DimensionResult]:
        for d in self.dimensions:
            if d.dimension == dimension:
                return d
        return None

    @property
    def total_issues(self) -> int:
        return (
            len(self.blocking_issues)
            + len(self.errors)
            + len(self.warnings)
            + len(self.infos)
        )

    @property
    def has_blocking_issues(self) -> bool:
        return len(self.blocking_issues) > 0


# ============================================================================
# Validation Context
# ============================================================================


class QualityValidationContext(BaseModel):
    """Immutable bundle of inputs to the QualityValidationEngine.

    Contains REFERENCES to upstream contracts, not copies of their
    full content. Downstream consumers should access these contracts
    through their canonical paths.
    """

    model_config = {"frozen": True}

    # --- Single-scene / canonical results ---
    prompt_compilation_result: Optional[Any] = Field(
        default=None,
        description="PromptCompilationResult (L-U5). Stored as Any to avoid coupling.",
    )
    canonical_prompt_ir: Optional[Any] = Field(
        default=None,
        description="CanonicalPromptIR (L-U5). Same Pydantic model as above.",
    )
    cms_compilation_result: Optional[Any] = Field(
        default=None,
        description="CameraMotionSoundCompilationResult (L-U6).",
    )
    character_reference_spec: Optional[Any] = Field(
        default=None,
        description="CharacterReferenceSpecification (L-U4).",
    )
    storyboard_package: Optional[Any] = Field(
        default=None,
        description="StoryboardPackage (P5).",
    )

    # --- Cross-scene continuity ---
    previous_validation_result: Optional[QualityValidationResult] = Field(default=None)
    next_validation_result: Optional[QualityValidationResult] = Field(default=None)
    previous_scene_context: Optional[Any] = Field(default=None)
    next_scene_context: Optional[Any] = Field(default=None)

    # --- Knowledge ---
    knowledge_version: str = Field(
        default="no-knowledge",
        pattern=r"^\d+\.\d+\.\d+$|^no-knowledge$",
    )
    is_knowledge_active: bool = Field(default=False)
    knowledge_ids_used: FrozenSet[str] = Field(default_factory=frozenset)

    # --- Policy ---
    policy: ValidationPolicy = Field(default_factory=ValidationPolicy.standard)

    # --- Metadata ---
    scene_id: Optional[str] = Field(default=None, max_length=64)
    request_id: Optional[str] = Field(default=None, max_length=64)

    def has_minimum_inputs(self) -> bool:
        """Check that at least one canonical input is present."""
        return (
            self.prompt_compilation_result is not None
            or self.cms_compilation_result is not None
        )


# ============================================================================
# Fingerprint helpers
# ============================================================================


def derive_deterministic_id(
    *,
    prompt_compilation_fingerprint: Optional[str] = None,
    cms_compilation_fingerprint: Optional[str] = None,
    character_reference_id: Optional[str] = None,
    storyboard_fingerprint: Optional[str] = None,
    policy_name: str = "standard",
    engine_version: str = "1.0.0",
) -> str:
    """Derive a deterministic validation_id from canonical input fingerprints.

    No timestamp, no random, no UUID.
    """
    content = (
        f"l-u7:{engine_version}:{policy_name}:"
        f"{prompt_compilation_fingerprint or ''}:"
        f"{cms_compilation_fingerprint or ''}:"
        f"{character_reference_id or ''}:"
        f"{storyboard_fingerprint or ''}"
    )
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def derive_content_fingerprint(content: str) -> str:
    """Derive a content fingerprint from a string."""
    return hashlib.sha256(content.encode()).hexdigest()[:32]


# ============================================================================
# Public exports
# ============================================================================


__all__ = [
    # Enums
    "ValidationStatus",
    "GenerationReadiness",
    "ValidationSeverity",
    "ValidationDimension",
    "DimensionState",
    "ValidationPolicyName",
    "IssueSource",
    # Models
    "ValidationPolicy",
    "ValidationIssue",
    "DimensionResult",
    "PromptLossReport",
    "QualityValidationResult",
    "QualityValidationContext",
    # Helpers
    "derive_deterministic_id",
    "derive_content_fingerprint",
]

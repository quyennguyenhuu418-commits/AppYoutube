"""
Prompt Compilation Schemas — canonical contracts for L-U5.

L-U5 — Prompt Compiler V2: Knowledge + Character Aware.

Purpose
-------
This module defines the canonical contracts for the Prompt Compilation
subsystem. It is the ONLY location for prompt-related schemas.

Architecture
------------
    PromptCompilationRequest        ← input
            ↓
    PromptCompiler                 ← consumes KnowledgeContext + CharacterRefSpec
            ↓
    CanonicalPromptIR              ← structured intermediate (NOT raw string)
            ↓
    PromptCompilationResult        ← output with provenance
            ↓
    ProviderPromptAdapter          ← provider-specific serialization

What this module does NOT do:
- It does NOT contain provider-specific serialization logic
- It does NOT call image/video generation APIs
- It does NOT generate raw prompt strings
- It does NOT use LLM to write prompts

Critical design principles
-------------------------
1. CANONICAL PROMPT IR IS STRUCTURED, NOT STRING
   The IR represents semantic intent as typed fields. It can be
   serialized to JSON, tested structurally, and diffed.

2. PROVIDER SYNTAX IS EXCLUDED FROM CORE
   Provider-specific formatting (Google Flow, DINO AI, Axen, etc.)
   belongs in ProviderPromptAdapter subclasses. The core IR is
   provider-neutral.

3. IDENTITY ≠ SCENE STATE IS PRESERVED
   The IR separates identity-bearing content (from CharacterReferenceSpecification)
   from scene-variable content (from Storyboard).

4. KNOWLEDGE PROVENANCE IS MANDATORY
   Every knowledge-derived element in the IR carries its provenance chain.

5. THE IR IS DETERMINISTIC
   Same inputs → same IR. No random, no timestamp in content.

Vocabulary mapping
-----------------
The IR uses terminology derived from the L-U1 VisualGrammar and
CharacterGrammar, mapped as follows:

    VisualGrammar.camera          → PromptIR.camera
    VisualGrammar.motion         → PromptIR.motion
    VisualGrammar.constraints    → PromptIR.constraints
    VisualGrammar.format         → PromptIR.format
    VisualGrammar.style          → PromptIR.style
    VisualGrammar.subject        → PromptIR.subject
    VisualGrammar.environment    → PromptIR.environment
    VisualGrammar.action         → PromptIR.action
    VisualGrammar.background     → PromptIR.background

    CharacterRefSpec.identity_properties → PromptIR.identity_preservation
    CharacterRefSpec.scene_variables    → PromptIR.scene_elements

Terminology preservation: The IR uses the same semantic vocabulary as
the Production Knowledge (STYLE, SUBJECT, ENVIRONMENT, CAMERA, MOTION,
ACTION, BACKGROUND, NEGATIVE CONSTRAINTS, FORMAT, SOUND).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, FrozenSet, Optional

from pydantic import BaseModel, Field

from app.knowledge.result import KnowledgeProvenance


# ============================================================================
# Prompt Kind — distinguishes IMAGE from VIDEO
# ============================================================================

class PromptKind(str, Enum):
    """The type of generation this prompt targets.

    IMAGE: static image (single frame)
    VIDEO: video (motion, camera movement, etc.)
    """
    IMAGE = "image"
    VIDEO = "video"


# ============================================================================
# Validation state
# ============================================================================

class ValidationSeverity(str, Enum):
    """How severe is a validation finding?"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class ValidationFinding(BaseModel):
    """A single validation finding."""
    model_config = {"frozen": True}

    rule_id: str = Field(min_length=1, max_length=128)
    """ID of the rule or check that triggered this finding."""

    field_path: str = Field(
        default="",
        max_length=128,
        description="Dot-notation path to the affected field, e.g. 'subject.character_id'",
    )

    message: str = Field(min_length=5, max_length=512)

    severity: ValidationSeverity

    provenance: Optional[KnowledgeProvenance] = Field(
        default=None,
        description="If this finding comes from a knowledge rule, its provenance",
    )


class PromptValidationReport(BaseModel):
    """The result of validating a PromptCompilationResult."""
    model_config = {"frozen": True}

    is_valid: bool = Field(
        description="True iff there are no BLOCKING findings",
    )

    blocking_findings: list[ValidationFinding] = Field(
        default_factory=list,
        max_length=32,
        description="Findings that should block generation",
    )

    warnings: list[ValidationFinding] = Field(
        default_factory=list,
        max_length=32,
        description="Non-blocking warnings",
    )

    info: list[ValidationFinding] = Field(
        default_factory=list,
        max_length=32,
        description="Informational findings",
    )

    def has_blocking(self) -> bool:
        return len(self.blocking_findings) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def summary(self) -> str:
        if self.is_valid:
            parts = [f"VALID ({len(self.info)} info, {len(self.warnings)} warnings)"]
        else:
            parts = [f"INVALID ({len(self.blocking_findings)} blocking, {len(self.warnings)} warnings)"]
        return "; ".join(parts)


# ============================================================================
# Negative constraints — first-class, not string append
# ============================================================================

class NegativeConstraintItem(BaseModel):
    """A single negative constraint in the IR."""

    model_config = {"frozen": True}

    constraint_id: str = Field(min_length=1, max_length=96)
    """Identifier for this constraint, e.g. 'head_shape_lock'."""

    property_name: str = Field(
        min_length=1,
        max_length=64,
        description="The property being constrained, e.g. 'head_shape', 'palette'",
    )

    constraint_text: str = Field(
        min_length=5,
        max_length=256,
        description="Human-readable constraint text, e.g. 'Do not alter head shape'",
    )

    is_identity_bearing: bool = Field(
        default=True,
        description="True = this constraint preserves character identity",
    )

    provenance: Optional[KnowledgeProvenance] = Field(
        default=None,
        description="Source of this constraint (from Knowledge Layer)",
    )


class NegativeConstraintsBlock(BaseModel):
    """The complete negative-constraints section of the IR."""

    model_config = {"frozen": True}

    constraints: list[NegativeConstraintItem] = Field(
        default_factory=list,
        max_length=32,
        description="All negative constraints",
    )

    provenance: Optional[KnowledgeProvenance] = Field(
        default=None,
    )

    def is_empty(self) -> bool:
        return len(self.constraints) == 0

    def identity_constraints(self) -> list[NegativeConstraintItem]:
        """Constraints that preserve character identity."""
        return [c for c in self.constraints if c.is_identity_bearing]


# ============================================================================
# Camera — semantic intent, not provider syntax
# ============================================================================

class CameraShotVocabulary(str, Enum):
    """Canonical shot vocabulary from L-U1 VisualGrammar + DINO AI.

    These are the ONLY valid shot types. No additions without a
    KnowledgeEntry promotion.
    """
    EXTREME_WIDE = "extreme_wide"       # EWS — full establishing
    WIDE = "wide"                        # WS — environment context
    MEDIUM_WIDE = "medium_wide"          # MWS — knees up
    MEDIUM = "medium"                    # MS — waist up
    MEDIUM_CLOSE = "medium_close"        # MCU — chest up
    CLOSE = "close"                      # CU — face
    EXTREME_CLOSE = "extreme_close"      # ECU — single detail
    OVER_SHOULDER = "over_shoulder"      # OTS
    POV = "pov"                         # character perspective
    DUTCH = "dutch"                      # tilted
    BIRDS_EYE = "birds_eye"            # from above
    WORMS_EYE = "worms_eye"            # from below
    TWO_SHOT = "two_shot"              # two subjects


class CameraMovementVocabulary(str, Enum):
    """Canonical camera movement vocabulary from L-U1 VisualGrammar."""
    HOLD = "hold"
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    PAN = "pan"
    TILT = "tilt"
    ZOOM = "zoom"
    TRACKING = "tracking"
    SHAKE = "shake"
    ORBIT = "orbit"


class CameraBlock(BaseModel):
    """Camera intent — semantic, not provider-specific."""
    model_config = {"frozen": True}

    shot_type: Optional[CameraShotVocabulary] = Field(
        default=None,
        description="Canonical shot type",
    )

    movement: Optional[CameraMovementVocabulary] = Field(
        default=None,
        description="Canonical movement (VIDEO only)",
    )

    easing: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Easing description, e.g. 'ease_in_out'",
    )

    notes: str = Field(
        default="",
        max_length=256,
        description="Additional camera notes",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Motion — semantic intent, not Remotion syntax
# ============================================================================

class MotionPatternVocabulary(str, Enum):
    """Canonical motion patterns from L-U1 VisualGrammar."""
    FRAME_BY_FRAME = "frame_by_frame"
    LOOP = "loop"
    RIG_POSE_INTERPOLATION = "rig_pose_interpolation"
    KINETIC_TEXT = "kinetic_text"
    SHAKE_NERVOUS = "shake_nervous"


class MotionBlock(BaseModel):
    """Motion intent — semantic, not animation-runtime syntax."""
    model_config = {"frozen": True}

    pattern: Optional[MotionPatternVocabulary] = Field(
        default=None,
        description="Canonical motion pattern",
    )

    duration_sec: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=300.0,
        description="Approximate duration in seconds",
    )

    loop: bool = Field(
        default=False,
        description="Whether this motion should loop seamlessly",
    )

    notes: str = Field(
        default="",
        max_length=256,
        description="Additional motion notes",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Style — from VisualGrammar + CharacterGrammar
# ============================================================================

class VisualStyleVocabulary(str, Enum):
    """Canonical visual style from L-U1 VisualGrammar."""
    HAND_DRAWN_DOODLE = "hand_drawn_doodle"
    SEMI_REALISTIC_2D = "semi_realistic_2d"
    FLAT_VECTOR = "flat_vector"
    STORYBOARD_SKETCH = "storyboard_sketch"
    INFOGRAPHIC_CLEAN = "infographic_clean"


class StyleBlock(BaseModel):
    """Visual style intent."""
    model_config = {"frozen": True}

    profile: VisualStyleVocabulary = Field(
        ...,
        description="Canonical style profile",
    )

    palette_hint: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Style palette description, e.g. 'muted earth tones'",
    )

    outline_hint: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Outline description, e.g. 'bold black marker outlines'",
    )

    line_quality: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Line quality description",
    )

    rendering_notes: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="Additional style notes",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Subject — character + props
# ============================================================================

class SubjectBlock(BaseModel):
    """Subject intent — what/who is depicted."""
    model_config = {"frozen": True}

    # Character reference
    character_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="@CHARACTER reference token, e.g. 'farmer_01'",
    )

    character_name: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Human-readable name",
    )

    character_description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Character description if not in registry",
    )

    # Scene-specific appearance
    pose: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Scene pose, e.g. 'walk', 'stand' (from ActionLabel)",
    )

    expression: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Scene expression, e.g. 'neutral', 'happy' (from ExpressionLabel)",
    )

    orientation: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Scene orientation, e.g. 'front', 'three_quarter_left'",
    )

    # Props
    props: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Prop tokens in this scene",
    )

    # Framing hint
    framing_hint: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Framing hint for the subject",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Environment
# ============================================================================

class EnvironmentBlock(BaseModel):
    """Environment intent — where the scene takes place."""
    model_config = {"frozen": True}

    setting: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Setting name, e.g. 'rice field'",
    )

    era: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Historical era, e.g. 'prehistoric', 'modern'",
    )

    time_of_day: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Time of day, e.g. 'morning', 'golden hour'",
    )

    weather: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Weather condition",
    )

    lighting: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Lighting description",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Action
# ============================================================================

class ActionBlock(BaseModel):
    """Action intent — what is happening."""
    model_config = {"frozen": True}

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Action description",
    )

    verbs: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Action verbs, e.g. 'walking', 'harvesting'",
    )

    intensity: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Intensity level, e.g. 'low', 'medium', 'high'",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Background
# ============================================================================

class BackgroundBlock(BaseModel):
    """Background treatment intent."""
    model_config = {"frozen": True}

    color: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Background color or token, e.g. '@C-BLUE-01'",
    )

    treatment: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Background treatment, e.g. 'solid', 'gradient'",
    )

    notes: str = Field(
        default="",
        max_length=256,
        description="Additional background notes",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Sound — semantic, not audio generation
# ============================================================================

class SoundVocabulary(str, Enum):
    """Canonical sound categories from production knowledge."""
    AMBIENT = "ambient"
    NARRATION = "narration"
    IMPACT = "impact"
    ENVIRONMENT = "environment"
    MUSIC = "music"
    SILENCE = "silence"


class SoundBlock(BaseModel):
    """Sound intent — semantic, not audio generation."""
    model_config = {"frozen": True}

    category: Optional[SoundVocabulary] = Field(
        default=None,
        description="Canonical sound category",
    )

    description: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Sound description, e.g. 'gentle wind through rice stalks'",
    )

    notes: str = Field(
        default="",
        max_length=256,
        description="Additional sound notes",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Format — canonical semantic data, not provider-specific syntax
# ============================================================================

class FormatBlock(BaseModel):
    """Output format intent — semantic, not provider syntax."""
    model_config = {"frozen": True}

    aspect_ratio: Optional[str] = Field(
        default=None,
        max_length=16,
        description="Aspect ratio, e.g. '16:9', '9:16', '1:1'",
    )

    medium: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Output medium, e.g. 'image', 'video'",
    )

    notes: str = Field(
        default="",
        max_length=256,
        description="Additional format notes",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Continuity / Identity preservation
# ============================================================================

class IdentityPreservationBlock(BaseModel):
    """Identity preservation from CharacterReferenceSpecification.

    This block captures which properties are identity-bearing and must
    remain stable across scenes. It is derived from
    CharacterReferenceSpecification.identity_properties and the resolved
    character rules.
    """

    model_config = {"frozen": True}

    # The properties that are identity-bearing for this character
    locked_properties: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=16,
        description=(
            "Properties that must remain stable across all scenes. "
            "Derived from CharacterReferenceSpecification.identity_properties."
        ),
    )

    # The specific rules resolved from the Knowledge Layer
    resolved_rules: list[str] = Field(
        default_factory=list,
        max_length=64,
        description=(
            "Plain-text rules from Knowledge Layer that govern identity. "
            "These are included in the IR as structured text for the "
            "prompt builder to incorporate into negative constraints."
        ),
    )

    # Knowledge IDs that contributed to these rules
    knowledge_ids: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=32,
        description="KnowledgeEntry IDs that informed these rules",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)

    def is_property_locked(self, property_name: str) -> bool:
        return property_name in self.locked_properties


class SceneElementsBlock(BaseModel):
    """Scene-variable elements from CharacterReferenceSpecification.

    These properties may vary per scene without changing character identity.
    """

    model_config = {"frozen": True}

    permitted_variations: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=16,
        description=(
            "Properties that may vary per scene. "
            "Derived from CharacterReferenceSpecification.scene_variables."
        ),
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Effects
# ============================================================================

class EffectsBlock(BaseModel):
    """Effects intent — motion lines, particles, overlays."""
    model_config = {"frozen": True}

    motion_lines: bool = Field(
        default=False,
        description="Include motion lines",
    )

    metaphor_elements: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Metaphor elements to include",
    )

    text_overlays: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Text overlays to include",
    )

    particles: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Particle effect description",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Canonical Prompt IR — the core intermediate representation
# ============================================================================

class CanonicalPromptIR(BaseModel):
    """The canonical intermediate representation for prompt compilation.

    This is the STRUCTURED output of the PromptCompiler. It is NOT a
    raw prompt string. It is NOT provider-specific.

    The IR represents WHAT should be generated (semantic intent) without
    specifying HOW the provider encodes it.

    Provider-specific serialization (Google Flow syntax, DINO format, etc.)
    belongs in ProviderPromptAdapter subclasses.

    Design principles
    ----------------
    1. Every field is semantically typed, not raw string.
    2. Every knowledge-derived field carries provenance.
    3. The IR is frozen (immutable after construction).
    4. The IR is deterministic (same inputs → same IR).
    5. The IR separates IDENTITY from SCENE STATE.

    Fields
    ------
    - prompt_kind: IMAGE or VIDEO
    - identity: identity preservation from CharacterRefSpec
    - scene_elements: scene-variable from CharacterRefSpec
    - style: visual style intent
    - subject: character + props
    - environment: setting + lighting
    - action: what is happening
    - camera: shot + movement (VIDEO) / shot only (IMAGE)
    - motion: motion pattern (VIDEO)
    - background: background treatment
    - effects: overlays
    - constraints: negative constraints (first-class, not string append)
    - sound: sound intent
    - format: output format
    - provenance: aggregate provenance
    - knowledge_ids_used: all KnowledgeEntry IDs that contributed
    - knowledge_version: knowledge registry version
    - compiler_version: version of the prompt compiler
    """

    model_config = {"frozen": True}

    # --- Core identification ---
    prompt_kind: PromptKind = Field(
        ...,
        description="IMAGE or VIDEO",
    )

    compiler_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Version of the PromptCompiler",
    )

    # --- Knowledge provenance ---
    knowledge_ids_used: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=32,
        description="KnowledgeEntry IDs that contributed to this IR",
    )

    knowledge_version: str = Field(
        default="no-knowledge",
        pattern=r"^\d+\.\d+\.\d+$|^no-knowledge$",
        description="Version of the knowledge registry used",
    )

    is_knowledge_active: bool = Field(
        default=False,
        description="True iff the Knowledge Layer was consulted",
    )

    # --- Character reference (from L-U4) ---
    identity: IdentityPreservationBlock = Field(
        default_factory=IdentityPreservationBlock,
        description="Identity preservation rules from CharacterReferenceSpecification",
    )

    scene_elements: SceneElementsBlock = Field(
        default_factory=SceneElementsBlock,
        description="Scene-variable elements from CharacterReferenceSpecification",
    )

    # --- Production intent (from VisualGrammar) ---
    style: Optional[StyleBlock] = Field(
        default=None,
        description="Visual style intent",
    )

    subject: Optional[SubjectBlock] = Field(
        default=None,
        description="Subject intent (character + props)",
    )

    environment: Optional[EnvironmentBlock] = Field(
        default=None,
        description="Environment intent",
    )

    action: Optional[ActionBlock] = Field(
        default=None,
        description="Action intent",
    )

    camera: Optional[CameraBlock] = Field(
        default=None,
        description="Camera intent",
    )

    motion: Optional[MotionBlock] = Field(
        default=None,
        description="Motion intent (VIDEO only)",
    )

    background: Optional[BackgroundBlock] = Field(
        default=None,
        description="Background treatment intent",
    )

    effects: Optional[EffectsBlock] = Field(
        default=None,
        description="Effects intent",
    )

    constraints: NegativeConstraintsBlock = Field(
        default_factory=NegativeConstraintsBlock,
        description="Negative constraints (first-class, not string append)",
    )

    sound: Optional[SoundBlock] = Field(
        default=None,
        description="Sound intent",
    )

    format: Optional[FormatBlock] = Field(
        default=None,
        description="Output format intent",
    )

    # --- Aggregate provenance ---
    provenance: Optional[KnowledgeProvenance] = Field(
        default=None,
        description="Aggregate provenance of the compilation",
    )

    # --- Convenience ---
    def get_identity_constraints(self) -> list[NegativeConstraintItem]:
        return self.constraints.identity_constraints()

    def has_blocking_constraints(self) -> bool:
        return len(self.constraints.constraints) > 0

    def provenance_summary(self) -> str:
        if not self.is_knowledge_active:
            return "no-knowledge (engine-default mode)"
        ids = list(self.knowledge_ids_used)
        if len(ids) == 0:
            return "no-knowledge"
        if len(ids) <= 3:
            return ", ".join(ids)
        return f"{ids[0]}, {ids[1]}, {ids[2]}... +{len(ids)-3} more"


# ============================================================================
# Prompt Compilation Request — input contract
# ============================================================================

class PromptCompilationRequest(BaseModel):
    """Input to the PromptCompiler.

    This is the structured request that initiates prompt compilation.
    It bundles:
    - The prompt kind (IMAGE or VIDEO)
    - Optional CharacterReferenceSpecification (from L-U4)
    - Optional VisualGrammar (from L-U1)
    - Optional CharacterDefinition (from PROMPT 5)
    - Scene-specific intent
    - Format requirements
    - Provider context (optional, for adapter selection)
    """

    model_config = {"frozen": False}

    # --- Core request ---
    request_id: str = Field(
        default="",
        max_length=64,
        description="Unique request ID. If empty, derived deterministically.",
    )

    prompt_kind: PromptKind = Field(
        ...,
        description="IMAGE or VIDEO",
    )

    # --- Character reference (L-U4) ---
    character_reference_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Character ID (e.g. 'farmer_01') to look up in CharacterRefSpec",
    )

    character_reference_spec: Optional[Any] = Field(
        default=None,
        description=(
            "Optional CharacterReferenceSpecification (L-U4). "
            "If not provided, the compiler looks it up by character_reference_id."
        ),
    )

    # --- Visual grammar (L-U1) ---
    visual_grammar: Optional[Any] = Field(
        default=None,
        description="Optional VisualGrammar (L-U1) for structured intent",
    )

    # --- Scene-specific overrides ---
    scene_pose: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Scene-specific pose override",
    )

    scene_expression: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Scene-specific expression override",
    )

    scene_orientation: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Scene-specific orientation override",
    )

    scene_action: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Scene-specific action description",
    )

    scene_environment: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Scene environment description",
    )

    scene_camera: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Scene camera intent (shot type or movement)",
    )

    # --- Format ---
    aspect_ratio: Optional[str] = Field(
        default=None,
        max_length=16,
        description="Desired aspect ratio, e.g. '16:9'",
    )

    # --- Observability ---
    request_reason: str = Field(
        default="",
        max_length=200,
        description="Why this prompt is being compiled (for logs)",
    )


# ============================================================================
# Prompt Compilation Result — output contract
# ============================================================================

class PromptCompilationResult(BaseModel):
    """The result of compiling a PromptCompilationRequest.

    This is the STRUCTURED output of the PromptCompiler. It contains:
    - The canonical Prompt IR
    - Validation report
    - Version metadata for reproducibility
    - Any conflicts or overrides
    """

    model_config = {"frozen": True}

    # --- Request identity ---
    request_id: str = Field(
        default="",
        max_length=64,
        description="Request ID (same as in the request)",
    )

    prompt_kind: PromptKind = Field(...)

    # --- The compiled IR ---
    ir: CanonicalPromptIR = Field(
        ...,
        description="The compiled canonical Prompt IR",
    )

    # --- Validation ---
    validation: PromptValidationReport = Field(
        ...,
        description="Validation report for this result",
    )

    # --- Version metadata for reproducibility ---
    compiler_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
    )

    knowledge_version: str = Field(
        default="no-knowledge",
        pattern=r"^\d+\.\d+\.\d+$|^no-knowledge$",
    )

    character_version: Optional[str] = Field(
        default=None,
        max_length=16,
        description="Version of the CharacterDefinition used (if applicable)",
    )

    # --- Fallback tracking ---
    fallback_policy_used: str = Field(
        default="engine_default",
        max_length=32,
        description="Which FallbackPolicy was applied",
    )

    is_knowledge_active: bool = Field(default=False)

    # --- Conflict/override tracking ---
    has_conflicts: bool = Field(
        default=False,
        description="True iff there are unresolved character knowledge conflicts",
    )

    has_overrides: bool = Field(
        default=False,
        description="True iff there are explicit overrides",
    )

    # --- Timestamp ---
    compiled_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this result was compiled (UTC)",
    )

    def provenance_summary(self) -> str:
        return self.ir.provenance_summary()

    def is_valid_for_generation(self) -> bool:
        """True iff the result is valid and can be sent to a provider."""
        return self.validation.is_valid


# ============================================================================
# Subject Motion — semantic character/object motion (L-U6)
# ============================================================================
# L-U6 distinguishes three motion concepts:
# 1. CAMERA MOVEMENT (CameraBlock.movement) — camera action
# 2. SUBJECT MOTION (SubjectMotionSpec) — character/object semantic motion
# 3. ANIMATION PATTERN (MotionBlock.pattern) — how the motion is rendered
#
# Example:
#   Camera: PUSH_IN        (camera action)
#   Subject: WALK          (what the character does)
#   Animation: RIG_POSE_INTERPOLATION  (how the walk is rendered)


class SubjectMotionVocabulary(str, Enum):
    """Canonical semantic subject motion vocabulary.

    These are WHAT the subject is doing (character or object).
    They are NOT animation implementation (FRAME_BY_FRAME, etc.).

    Derived from StoryboardMotionType (app/schemas/storyboard.py) and
    ActionLabel (app/animation/schemas.py). Adding new vocabulary
    requires a KnowledgeEntry promotion.
    """
    NONE = "none"
    STAND = "stand"
    WALK = "walk"
    RUN = "run"
    POINT = "point"
    THINK = "think"
    CELEBRATE = "celebrate"
    HIDE = "hide"
    SIT = "sit"
    ENTER = "enter"
    EXIT = "exit"
    GESTURE = "gesture"
    LOOK = "look"
    TURN = "turn"
    BREATHING = "breathing"
    IDLE = "idle"


class SubjectMotionDirection(str, Enum):
    """Canonical direction for subject motion."""
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    FORWARD = "forward"
    BACKWARD = "backward"
    UP = "up"
    DOWN = "down"


class SubjectMotionIntensity(str, Enum):
    """Canonical intensity for subject motion."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SubjectMotionSpec(BaseModel):
    """Semantic subject/object motion intent.

    This is WHAT the subject (character or object) is doing.
    It is NOT camera movement and NOT animation implementation.

    Examples:
        farmer_01: WALK, FORWARD, MEDIUM
        hunter_main: RUN, FORWARD, HIGH
        spear: TURN, NONE, LOW
    """
    model_config = {"frozen": True}

    # Semantic action
    action: SubjectMotionVocabulary = SubjectMotionVocabulary.NONE

    # Direction of motion
    direction: SubjectMotionDirection = SubjectMotionDirection.NONE

    # Intensity
    intensity: SubjectMotionIntensity = SubjectMotionIntensity.MEDIUM

    # Duration hint (optional, for VIDEO)
    duration_sec: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=300.0,
        description="Approximate duration in seconds",
    )

    # Target subject (character_id or prop_id)
    target_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Subject of the motion, e.g. 'farmer_01', 'prop:wheat_stalk'",
    )

    # Narrative purpose (for provenance)
    purpose: str = Field(
        default="",
        max_length=200,
        description="Narrative purpose of this motion",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Sound Layers — semantic sound design (L-U6)
# ============================================================================
# L-U6 SoundSpec describes INTENDED SOUND DESIGN.
# It does NOT produce audio files.
# Audio generation remains with voice/ TTS providers.
# Audio mixing remains with Editorial/Mastering.


class SoundLayerCategory(str, Enum):
    """Canonical sound layer categories.

    These describe WHAT KIND of sound is intended, not the actual audio file.
    """
    AMBIENT = "ambient"       # Background atmosphere
    MUSIC = "music"           # Musical score
    SFX = "sfx"              # Sound effects
    ENVIRONMENT = "environment"  # Environmental sound
    NARRATION = "narration"  # Spoken narration (referenced)
    DIALOGUE = "dialogue"    # Character dialogue
    IMPACT = "impact"         # Emphasis/impact sound
    SILENCE = "silence"       # Intentional silence


class SoundLayerPriority(str, Enum):
    """Priority of a sound layer in the mix."""
    PRIMARY = "primary"      # Most important (narration)
    SECONDARY = "secondary"  # Music / dialogue
    TERTIARY = "tertiary"    # Ambient / SFX
    BACKGROUND = "background"  # Subtle background


class SoundLayerSpec(BaseModel):
    """A single semantic sound layer.

    Describes INTENDED sound, not actual audio files.
    Audio file generation belongs to voice/ TTS subsystem.
    Audio mixing belongs to Editorial/Mastering.
    """
    model_config = {"frozen": True}

    # Which layer
    category: SoundLayerCategory = SoundLayerCategory.AMBIENT

    # Semantic description
    description: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Semantic description, e.g. 'gentle wind through rice stalks'",
    )

    # Priority in the mix
    priority: SoundLayerPriority = SoundLayerPriority.TERTIARY

    # Narration relationship
    duck_under_narration: bool = Field(
        default=False,
        description=(
            "True = this layer should duck (reduce gain) when narration is active. "
            "Used by Editorial/Mastering to compute gain. "
            "Does NOT directly set dB — that's the mixing layer's job."
        ),
    )

    # Loop intent
    loop: bool = Field(
        default=True,
        description="Whether this sound should loop",
    )

    # Relative volume hint (semantic, not dB)
    volume_hint: str = Field(
        default="medium",
        max_length=32,
        description="Semantic volume: 'quiet', 'medium', 'loud'",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


class SoundLayersSpec(BaseModel):
    """Collection of semantic sound layers for a scene.

    Describes intended sound design across all layers.
    Does NOT produce audio files.
    Does NOT compute dB gains.
    Does NOT mix audio.
    """
    model_config = {"frozen": True}

    # All intended layers
    layers: list[SoundLayerSpec] = Field(
        default_factory=list,
        max_length=8,
        description="Semantic sound layers for this scene",
    )

    # Master narration relationship (for all layers)
    master_duck_under_narration: bool = Field(
        default=False,
        description=(
            "True = all non-narration layers should duck when narration is active. "
            "Semantic intent only — actual gain computation belongs to Editorial."
        ),
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)

    def is_empty(self) -> bool:
        return len(self.layers) == 0

    def has_narration_layer(self) -> bool:
        return any(
            layer.category == SoundLayerCategory.NARRATION for layer in self.layers
        )

    def ducking_layers(self) -> list[SoundLayerSpec]:
        """Layers that should duck under narration."""
        return [
            layer for layer in self.layers
            if layer.duck_under_narration
            and layer.category != SoundLayerCategory.NARRATION
        ]


# ============================================================================
# Camera Framing (L-U6 extension)
# ============================================================================


class FramingIntent(str, Enum):
    """Canonical framing intent."""
    RULE_OF_THIRDS = "rule_of_thirds"
    CENTER = "center"
    GOLDEN_RATIO = "golden_ratio"
    LEADING_ROOM = "leading_room"
    BALANCED = "balanced"
    ASYMMETRIC = "asymmetric"


class SubjectRelationship(str, Enum):
    """Canonical camera-to-subject relationship."""
    FRONT = "front"
    SIDE = "side"
    BACK = "back"
    THREE_QUARTER = "three_quarter"
    OVER = "over"
    UNDER = "under"
    POV = "pov"  # Point of view


class CameraDirection(str, Enum):
    """Canonical camera movement direction."""
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    FORWARD = "forward"   # push in
    BACKWARD = "backward"  # pull out


# ============================================================================
# Extended CameraBlock (L-U6)
# ============================================================================


class CameraBlockExt(BaseModel):
    """Extended camera intent with richer semantics (L-U6).

    This is a SEPARATE semantic layer on top of CameraBlock.
    CameraBlock carries shot_type + movement (L-U5).
    CameraBlockExt adds framing, subject relationship, direction, intensity, duration.

    The L-U5 PromptCompiler produces CameraBlock.
    The L-U6 CameraMotionSoundCompiler extends it to CameraBlockExt.
    The animation/editorial consumers decide how to interpret these semantics.
    """
    model_config = {"frozen": True}

    # Base camera intent (from L-U5 CameraBlock)
    shot_type: Optional[CameraShotVocabulary] = Field(
        default=None,
        description="Canonical shot type",
    )
    movement: Optional[CameraMovementVocabulary] = Field(
        default=None,
        description="Canonical movement (VIDEO only)",
    )
    easing: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Easing description, e.g. 'ease_in_out'",
    )
    notes: str = Field(
        default="",
        max_length=256,
        description="Additional camera notes",
    )

    # L-U6 extensions
    framing: Optional[FramingIntent] = Field(
        default=None,
        description="Framing intent, e.g. 'rule_of_thirds'",
    )

    subject_relationship: Optional[SubjectRelationship] = Field(
        default=None,
        description="Camera-to-subject relationship",
    )

    movement_direction: CameraDirection = CameraDirection.NONE

    # Intensity of movement
    intensity: SubjectMotionIntensity = SubjectMotionIntensity.MEDIUM

    # Duration hint
    duration_sec: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=300.0,
        description="Approximate duration in seconds",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Extended MotionBlock (L-U6)
# ============================================================================


class MotionBlockExt(BaseModel):
    """Extended motion intent with richer semantics (L-U6).

    Adds semantic action, direction, and easing to MotionBlock.
    """
    model_config = {"frozen": True}

    # Base motion intent (from L-U5 MotionBlock)
    pattern: Optional[MotionPatternVocabulary] = Field(
        default=None,
        description="Canonical motion pattern",
    )
    duration_sec: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=300.0,
        description="Approximate duration in seconds",
    )
    loop: bool = Field(
        default=False,
        description="Whether this motion should loop seamlessly",
    )
    notes: str = Field(
        default="",
        max_length=256,
        description="Additional motion notes",
    )

    # L-U6 extensions
    # Semantic subject action (what the subject is doing)
    subject_action: Optional[SubjectMotionVocabulary] = Field(
        default=None,
        description="Semantic subject action, e.g. 'walk', 'run'",
    )

    # Direction of the motion
    direction: SubjectMotionDirection = SubjectMotionDirection.NONE

    # Easing for the motion
    easing: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Easing description, e.g. 'ease_in_out'",
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Extended SoundBlock (L-U6)
# ============================================================================


class SoundBlockExt(BaseModel):
    """Extended sound intent with richer semantics (L-U6).

    Adds semantic sound layers to SoundBlock.
    """
    model_config = {"frozen": True}

    # Base sound intent (from L-U5 SoundBlock)
    category: Optional[SoundVocabulary] = Field(
        default=None,
        description="Canonical sound category",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Sound description",
    )
    notes: str = Field(
        default="",
        max_length=256,
        description="Additional sound notes",
    )

    # L-U6 extensions
    # Rich semantic layers
    layers: SoundLayersSpec = Field(
        default_factory=SoundLayersSpec,
        description="Semantic sound layers",
    )

    # Master narration ducking
    master_duck_under_narration: bool = Field(
        default=False,
        description=(
            "True = all non-narration layers duck under narration. "
            "Semantic intent only — Editorial/Mastering does actual mixing."
        ),
    )

    provenance: Optional[KnowledgeProvenance] = Field(default=None)


# ============================================================================
# Camera/Motion/Sound Compilation Result (L-U6)
# ============================================================================


class CameraMotionSoundCompilationResult(BaseModel):
    """Result of compiling camera/motion/sound semantics.

    This is the output of the CameraMotionSoundCompiler.
    It carries enriched camera, motion, and sound semantics that can be
    consumed by Animation, Editorial, and other downstream subsystems.

    The result is immutable (frozen).
    """
    model_config = {"frozen": True}

    # Request identity
    request_id: str = Field(default="", max_length=64)
    prompt_kind: PromptKind = Field(...)  # IMAGE or VIDEO

    # Enriched camera semantics
    camera: CameraBlockExt = Field(
        default_factory=lambda: CameraBlockExt(),
        description="Enriched camera intent",
    )

    # Enriched motion semantics
    motion: MotionBlockExt = Field(
        default_factory=lambda: MotionBlockExt(),
        description="Enriched motion intent",
    )

    # Subject motion (what the subject is doing)
    subject_motion: SubjectMotionSpec = Field(
        default_factory=lambda: SubjectMotionSpec(),
        description="Semantic subject/object motion",
    )

    # Enriched sound semantics
    sound: SoundBlockExt = Field(
        default_factory=lambda: SoundBlockExt(),
        description="Enriched sound intent",
    )

    # Validation
    is_valid: bool = Field(default=True)
    validation_messages: list[str] = Field(
        default_factory=list,
        max_length=32,
    )

    # Knowledge metadata
    is_knowledge_active: bool = Field(default=False)
    knowledge_version: str = Field(
        default="no-knowledge",
        pattern=r"^\d+\.\d+\.\d+$|^no-knowledge$",
    )
    knowledge_ids_used: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=32,
    )

    # Fallback tracking
    fallback_policy_used: str = Field(
        default="engine_default",
        max_length=32,
    )

    # Compiler version
    compiler_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
    )

    # Provenance
    provenance: Optional[KnowledgeProvenance] = Field(default=None)

    def provenance_summary(self) -> str:
        if not self.is_knowledge_active:
            return "no-knowledge"
        if not self.knowledge_ids_used:
            return "no-knowledge"
        ids = list(self.knowledge_ids_used)
        if len(ids) <= 3:
            return ", ".join(ids)
        return f"{ids[0]}, {ids[1]}... +{len(ids) - 2} more"


__all__ = [
    # L-U5 exports (unchanged)
    "PromptKind",
    "ValidationSeverity",
    "CameraShotVocabulary",
    "CameraMovementVocabulary",
    "MotionPatternVocabulary",
    "VisualStyleVocabulary",
    "SoundVocabulary",
    "ValidationFinding",
    "PromptValidationReport",
    "NegativeConstraintItem",
    "NegativeConstraintsBlock",
    "CameraBlock",
    "MotionBlock",
    "StyleBlock",
    "SubjectBlock",
    "EnvironmentBlock",
    "ActionBlock",
    "BackgroundBlock",
    "SoundBlock",
    "FormatBlock",
    "IdentityPreservationBlock",
    "SceneElementsBlock",
    "EffectsBlock",
    "CanonicalPromptIR",
    "PromptCompilationRequest",
    "PromptCompilationResult",
    # L-U6 exports (new)
    "SubjectMotionVocabulary",
    "SubjectMotionDirection",
    "SubjectMotionIntensity",
    "SubjectMotionSpec",
    "SoundLayerCategory",
    "SoundLayerPriority",
    "SoundLayerSpec",
    "SoundLayersSpec",
    "FramingIntent",
    "SubjectRelationship",
    "CameraDirection",
    "CameraBlockExt",
    "MotionBlockExt",
    "SoundBlockExt",
    "CameraMotionSoundCompilationResult",
]

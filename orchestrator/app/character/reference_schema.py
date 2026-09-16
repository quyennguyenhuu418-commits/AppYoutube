"""
CharacterReferenceSpecification — canonical contract bridging Knowledge Layer
and the Character System.

L-U4 — Character Reference System Integration.

Purpose
-------
The `CharacterReferenceSpecification` is a **structured guidance contract**
produced by consulting the Knowledge Layer. It captures:

    1. Which properties of a character are identity-bearing (locked)
       and which are scene-variable (mutable).
    2. The canonical rules that govern character representation.
    3. Full provenance (which knowledge entry produced which guidance).

It is NOT a `CharacterDefinition`. It does NOT store actual character
values (color, head shape, etc.). Those live in `CharacterDefinition`.

Architecture
------------
    CharacterRequirement
            ↓
    KnowledgeCharacterAdapter (L-U4)
            ↓
    KnowledgeResolver
            ↓
    CharacterReferenceSpecification
            ↓
    CharacterSystemEngine (produces CharacterDefinition)

The `CharacterReferenceSpecification` is an **input** to the engine,
not a replacement for it.

Separation of concerns
---------------------
    Knowledge Layer:     "preserve identity, maintain proportions, keep wardrobe stable"
    CharacterSystem:   "which actual color, head shape, clothing items?"
    CharacterDefinition: actual chosen values

Design principles
----------------
1. The spec is GUIDANCE, not VALUES.
2. Identity-bearing properties are explicitly marked.
3. Scene-variable properties are explicitly marked.
4. Provenance is mandatory on every resolved rule.
5. Overrides are explicit and traceable.
6. The spec is frozen (immutable after construction).

Key concept: IDENTITY vs SCENE STATE
------------------------------------
IDENTITY-BEARING (locked unless explicitly overridden):
    - head shape
    - face structure
    - silhouette
    - proportions
    - palette
    - wardrobe (continuity_locked)
    - signature props
    - skin tone
    - style profile

SCENE-VARIABLE (may change per scene):
    - pose
    - expression
    - orientation
    - camera angle
    - action
    - scene-specific wardrobe variant (if override is explicit)
    - scale
    - position
"""

from __future__ import annotations

from typing import Any, FrozenSet, Optional

from pydantic import BaseModel, Field

from app.knowledge.result import KnowledgeProvenance


# ============================================================================
# Identity vs scene-state vocabulary
# ============================================================================

class IdentityBearingProperty(str):
    """Properties that define who the character IS.

    These should remain stable across all scenes.
    """
    HEAD_SHAPE = "head_shape"
    FACE_STRUCTURE = "face_structure"
    SILHOUETTE = "silhouette"
    PROPORTIONS = "proportions"
    PALETTE = "palette"
    SKIN_TONE = "skin_tone"
    STYLE_PROFILE = "style_profile"
    DEFAULT_OUTLINE = "default_outline"


class SceneVariableProperty(str):
    """Properties that vary per scene without changing identity."""
    POSE = "pose"
    EXPRESSION = "expression"
    ORIENTATION = "orientation"
    CAMERA_ANGLE = "camera_angle"
    ACTION = "action"
    SCALE = "scale"
    POSITION = "position"
    SCENE_WARDROBE_VARIANT = "scene_wardrobe_variant"


# ============================================================================
# Resolved rule — one rule from the Knowledge Layer with provenance
# ============================================================================

class ResolvedCharacterRule(BaseModel):
    """A single production rule resolved from the Knowledge Layer.

    This is what the resolver returns, translated into character semantics.
    It carries provenance so every guidance decision is traceable.
    """

    model_config = {"frozen": True}

    # What kind of guidance
    rule_id: str = Field(min_length=1, max_length=96)
    domain: str = Field(min_length=1, max_length=64)
    category: str = Field(
        min_length=1,
        max_length=64,
        description=(
            "Category within the character domain, e.g. "
            "'identity_lock', 'wardrobe', 'palette', 'proportions', "
            "'silhouette', 'style', 'signature_prop'"
        ),
    )

    # The rule text
    rule: str = Field(min_length=5, max_length=256)

    # Which properties this rule governs
    governed_properties: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=16,
        description="Property names this rule applies to",
    )

    # Whether this rule is identity-bearing
    is_identity_bearing: bool = Field(
        default=False,
        description="True = this rule governs identity; False = scene-variable",
    )

    # Provenance
    provenance: KnowledgeProvenance = Field(...)

    # Knowledge version that produced this
    knowledge_version: str = Field(
        pattern=r"^\d+\.\d+\.\d+(\.\d+)?$",
        description="Semver of the knowledge entry",
    )

    # Confidence
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================================
# Palette guidance — from the Knowledge Layer
# ============================================================================

class PaletteGuidance(BaseModel):
    """Palette guidance resolved from Knowledge Layer.

    This is a GUIDANCE contract. The actual palette values live in
    CharacterDefinition.color_palette. This class carries the
    knowledge-derived preferences, not the resolved values.
    """

    model_config = {"frozen": True}

    # Knowledge-derived guidance
    primary_hints: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Suggested primary color themes or adjectives",
    )
    secondary_hints: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Suggested secondary color themes",
    )
    outline_hint: Optional[str] = Field(
        default=None,
        description="Suggested outline color guidance",
    )
    skin_tone_hint: Optional[str] = Field(
        default=None,
        description="Suggested skin tone guidance",
    )

    # What the knowledge said
    rules: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=16,
        description="Actual rule texts from the knowledge entry",
    )

    # Provenance
    provenance: KnowledgeProvenance = Field(...)

    knowledge_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


# ============================================================================
# Wardrobe guidance — from the Knowledge Layer
# ============================================================================

class WardrobeGuidance(BaseModel):
    """Wardrobe guidance resolved from Knowledge Layer.

    Captures:
        - whether wardrobe is continuity-locked
        - what kinds of wardrobe changes are permitted
        - explicit override categories
    """

    model_config = {"frozen": True}

    # Continuity lock
    is_continuity_locked: bool = Field(
        default=True,
        description=(
            "True = wardrobe must remain stable across scenes. "
            "False = wardrobe may vary with explicit scene justification."
        ),
    )

    # Permitted scene-specific variations
    permitted_variations: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=16,
        description="Permitted wardrobe variation categories, e.g. 'seasonal', 'activity'",
    )

    # Forbidden variations
    forbidden_variations: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=16,
        description="Explicitly forbidden wardrobe variation categories",
    )

    # What the knowledge said
    rules: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=16,
        description="Actual rule texts from the knowledge entry",
    )

    provenance: KnowledgeProvenance = Field(...)
    knowledge_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


# ============================================================================
# Negative constraints — from the Knowledge Layer
# ============================================================================

class NegativeConstraint(BaseModel):
    """A negative constraint for character generation.

    Represents: "do NOT change / do NOT redesign / do NOT alter X".

    Unlike ResolvedCharacterRule, a negative constraint is a hard rule
    that should block silent overrides.
    """

    model_config = {"frozen": True}

    # What is forbidden
    forbids_property: str = Field(
        min_length=1,
        max_length=64,
        description="The property or aspect that is forbidden to change",
    )

    # Why it is forbidden
    rule: str = Field(min_length=5, max_length=256)

    # Is this identity-bearing?
    is_identity_bearing: bool = Field(default=True)

    # Provenance
    provenance: KnowledgeProvenance = Field(...)
    knowledge_version: str = Field(pattern=r"^\d+\.\d+\.\d+(\.\d+)?$")


# ============================================================================
# Override model — explicit scene overrides
# ============================================================================

class ExplicitOverride(BaseModel):
    """An explicit override of a canonical character property.

    Overrides are not automatic. They must be:
        1. Explicit (not silently applied)
        2. Justified (with a scene reason)
        3. Traceable (to a decision, not to LLM hallucination)
    """

    model_config = {"frozen": True}

    # What is being overridden
    property_name: str = Field(min_length=1, max_length=64)

    # The canonical value (from CharacterDefinition)
    canonical_value: str = Field(min_length=1, max_length=256)

    # The override value
    override_value: str = Field(min_length=1, max_length=256)

    # Why this override is justified
    justification: str = Field(min_length=5, max_length=256)

    # Is this allowed by the reference spec?
    is_permitted: bool = Field(
        default=True,
        description=(
            "True = this override is permitted by the reference spec. "
            "False = this override conflicts with identity rules."
        ),
    )

    # If not permitted, what conflict exists?
    conflict_with: Optional[str] = Field(
        default=None,
        max_length=256,
        description="The identity rule this override would violate",
    )


# ============================================================================
# Conflict record
# ============================================================================

class CharacterKnowledgeConflict(BaseModel):
    """A conflict between a scene request and character knowledge rules.

    Represented, not silently resolved. The consumer (engine or pipeline)
    decides how to handle conflicts.
    """

    model_config = {"frozen": True}

    # What the scene requested
    scene_request: str = Field(min_length=1, max_length=256)

    # What the knowledge rule says
    rule: str = Field(min_length=5, max_length=256)

    # The governed property
    property_name: str = Field(min_length=1, max_length=64)

    # How to handle
    severity: str = Field(
        min_length=1,
        max_length=32,
        description="'error' | 'warning' | 'info'",
    )

    provenance: KnowledgeProvenance = Field(...)


# ============================================================================
# Canonical Character Reference Specification
# ============================================================================

class CharacterReferenceSpecification(BaseModel):
    """Canonical guidance contract from the Knowledge Layer for character creation.

    This is the OUTPUT of the KnowledgeCharacterAdapter when fed a
    CharacterRequirement. It is an INPUT to the CharacterSystemEngine.

    It does NOT replace CharacterDefinition. It provides structured guidance
    that the engine can use (or ignore, if it has good reasons).

    Properties
    ----------
        character_id: the character this spec applies to
        identity_properties: explicitly locked properties (identity-bearing)
        scene_variables: explicitly permitted scene-specific changes
        resolved_rules: all rules resolved from the Knowledge Layer
        palette_guidance: knowledge-derived palette hints
        wardrobe_guidance: wardrobe continuity rules
        negative_constraints: hard constraints (do not alter X)
        explicit_overrides: any current overrides (from pipeline context)
        conflicts: any unresolved conflicts
        provenance: which knowledge entries were consulted
        knowledge_version: version of the knowledge consulted
        is_knowledge_active: whether the Knowledge Layer was available
    """

    model_config = {"frozen": True}

    # Identity
    character_id: str = Field(min_length=1, max_length=64)

    # Core separation: identity vs scene state
    identity_properties: FrozenSet[str] = Field(
        default_factory=lambda: frozenset({
            IdentityBearingProperty.HEAD_SHAPE,
            IdentityBearingProperty.FACE_STRUCTURE,
            IdentityBearingProperty.SILHOUETTE,
            IdentityBearingProperty.PROPORTIONS,
            IdentityBearingProperty.PALETTE,
            IdentityBearingProperty.SKIN_TONE,
            IdentityBearingProperty.STYLE_PROFILE,
        }),
        max_length=16,
        description="Properties that must remain stable (identity-bearing)",
    )

    scene_variables: FrozenSet[str] = Field(
        default_factory=lambda: frozenset({
            SceneVariableProperty.POSE,
            SceneVariableProperty.EXPRESSION,
            SceneVariableProperty.ORIENTATION,
            SceneVariableProperty.CAMERA_ANGLE,
            SceneVariableProperty.ACTION,
            SceneVariableProperty.SCALE,
            SceneVariableProperty.POSITION,
        }),
        max_length=16,
        description="Properties that may vary per scene without changing identity",
    )

    # Resolved rules from the Knowledge Layer
    resolved_rules: list[ResolvedCharacterRule] = Field(
        default_factory=list,
        max_length=64,
        description="All production rules resolved from knowledge entries",
    )

    # Domain-specific guidance
    palette_guidance: Optional[PaletteGuidance] = Field(
        default=None,
        description="Knowledge-derived palette guidance",
    )
    wardrobe_guidance: Optional[WardrobeGuidance] = Field(
        default=None,
        description="Knowledge-derived wardrobe guidance",
    )

    # Hard constraints
    negative_constraints: list[NegativeConstraint] = Field(
        default_factory=list,
        max_length=32,
        description="Hard constraints: do NOT alter X",
    )

    # Explicit overrides (from pipeline context)
    explicit_overrides: list[ExplicitOverride] = Field(
        default_factory=list,
        max_length=16,
        description="Explicit scene overrides, not silently applied",
    )

    # Conflicts (not silently resolved)
    conflicts: list[CharacterKnowledgeConflict] = Field(
        default_factory=list,
        max_length=16,
        description="Represented conflicts, not silently swallowed",
    )

    # Provenance chain
    knowledge_ids_used: FrozenSet[str] = Field(
        default_factory=frozenset,
        max_length=32,
        description="KnowledgeEntry IDs that contributed to this spec",
    )
    knowledge_version: str = Field(
        default="no-knowledge",
        pattern=r"^\d+\.\d+\.\d+$|^no-knowledge$",
        description="Knowledge registry version used",
    )

    # Whether knowledge was available
    is_knowledge_active: bool = Field(
        default=False,
        description="True = Knowledge Layer was consulted. False = defaults only.",
    )

    # Fallback indicator
    fallback_policy_used: str = Field(
        default="no-knowledge",
        max_length=32,
        description="Which FallbackPolicy was applied: 'engine_default', 'warn', etc.",
    )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_identity_rules(self) -> list[ResolvedCharacterRule]:
        """All rules that govern identity-bearing properties."""
        return [r for r in self.resolved_rules if r.is_identity_bearing]

    def get_scene_variable_rules(self) -> list[ResolvedCharacterRule]:
        """All rules that govern scene-variable properties."""
        return [r for r in self.resolved_rules if not r.is_identity_bearing]

    def is_identity_property(self, property_name: str) -> bool:
        """Check if a property is identity-bearing."""
        return property_name in self.identity_properties

    def get_governed_rules(self, property_name: str) -> list[ResolvedCharacterRule]:
        """All rules governing a specific property."""
        return [r for r in self.resolved_rules if property_name in r.governed_properties]

    def has_conflicts(self) -> bool:
        """True if there are unresolved conflicts."""
        return len(self.conflicts) > 0

    def has_overrides(self) -> bool:
        """True if there are explicit overrides."""
        return len(self.explicit_overrides) > 0

    def provenance_summary(self) -> str:
        """Human-readable provenance summary for logs."""
        if not self.is_knowledge_active:
            return "no-knowledge (backward-compatible mode)"
        parts = []
        for r in self.resolved_rules[:3]:
            parts.append(f"[{r.rule_id}@{r.knowledge_version}]")
        if len(self.resolved_rules) > 3:
            parts.append(f"... +{len(self.resolved_rules) - 3} more")
        return ", ".join(parts)


__all__ = [
    "CharacterReferenceSpecification",
    "ResolvedCharacterRule",
    "PaletteGuidance",
    "WardrobeGuidance",
    "NegativeConstraint",
    "ExplicitOverride",
    "CharacterKnowledgeConflict",
    "IdentityBearingProperty",
    "SceneVariableProperty",
]

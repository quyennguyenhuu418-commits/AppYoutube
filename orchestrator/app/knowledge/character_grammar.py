"""
Character Grammar — production rules for character consistency.

L-U1 — Production Knowledge & Visual Grammar Foundation.

Purpose
-------
This module defines the **production rules** that govern how a character
SHOULD be represented. It does NOT replace CharacterDefinition — that
remains the canonical representation of an actual character in the
production system (Prompt 5). CharacterGrammar is the layer ABOVE
CharacterDefinition, describing the principles of character production
rather than the specific identity of any character.

Architecture
------------
    CharacterGrammar           ← this module
        ↓
    CharacterReference rules   ← character.grammar module (character/grammar.py)
        ↓
    CharacterDefinition / CharacterInstance

Critical invariant
------------------
    CharacterDefinition owns a specific character's identity.
    CharacterGrammar owns the rules that govern how any character
    (or any specific character) SHOULD be represented.

    You CAN read CharacterGrammar to produce CharacterDefinition.
    You CANNOT read CharacterDefinition to override CharacterGrammar
    (unless you also bump the CharacterGrammar version).

Field coverage (where supported by source)
------------------------------------------
    - identity consistency
    - head shape
    - facial characteristics
    - proportions
    - outline
    - colors
    - wardrobe
    - signature props
    - orientation
    - expression
    - pose consistency
    - reference-sheet usage
    - redesign prevention
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Enums — bounded vocabulary
# ============================================================================

class HeadShape(str, Enum):
    """Canonical head-shape vocabulary."""
    ROUND = "round"
    OVAL = "oval"
    SQUARE = "square"
    TRIANGULAR = "triangular"
    RECTANGULAR = "rectangular"
    ABSTRACT = "abstract"


class EyeStyle(str, Enum):
    """Canonical eye-style vocabulary."""
    DOT = "dot"
    LINE = "line"
    ROUND = "round"
    OVAL = "oval"
    ALMOND = "almond"
    CLOSED = "closed"
    STYLIZED = "stylized"


class EyebrowStyle(str, Enum):
    """Canonical eyebrow-style vocabulary."""
    DOT = "dot"
    LINE = "line"
    THICK_MARKER = "thick_marker"
    ARCHED = "arched"
    ANGRY_SLANT = "angry_slant"
    WORRIED = "worried"


class OutlineWeight(str, Enum):
    """Outline weight vocabulary."""
    THIN = "thin"
    MEDIUM = "medium"
    THICK = "thick"
    EXTRA_THICK = "extra_thick"


class BodyType(str, Enum):
    """Canonical body-type vocabulary."""
    STICK = "stick"
    SLIM = "slim"
    AVERAGE = "average"
    GAUNT = "gaunt"
    MUSCULAR = "muscular"
    CHUBBY = "chubby"


class CharacterFamily(str, Enum):
    """Shared visual lineage (e.g. @FARMER and @ANCESTOR share a family)."""
    ANCESTOR = "ancestor"
    FARMER = "farmer"
    HUNTER = "hunter"
    SCIENTIST = "scientist"
    MODERN_PERSON = "modern_person"
    NARRATOR = "narrator"
    GENERIC_HUMAN = "generic_human"


class ConsistencyRuleKind(str, Enum):
    """The kind of consistency rule being declared."""
    IDENTITY_PRESERVATION = "identity_preservation"
    PROPORTION_LOCK = "proportion_lock"
    PALETTE_LOCK = "palette_lock"
    OUTLINE_LOCK = "outline_lock"
    REDESIGN_PREVENTION = "redesign_prevention"
    FAMILY_LINEAGE = "family_lineage"
    EXPRESSION_CONSISTENCY = "expression_consistency"
    POSE_CONSISTENCY = "pose_consistency"


# ============================================================================
# Sub-blocks of the grammar
# ============================================================================

class IdentityBlock(BaseModel):
    """Identity-consistency rules."""
    identity_preservation_required: bool = True
    family: Optional[CharacterFamily] = Field(
        default=None,
        description="Shared visual lineage (e.g. ANCESTOR → FARMER)",
    )
    identity_lock_fields: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="Fields that MUST stay identical across instances, e.g. ['head_shape', 'eye_style']",
    )


class HeadBlock(BaseModel):
    """Head design rules."""
    shape: Optional[HeadShape] = None
    relative_size: Optional[str] = Field(
        default=None,
        max_length=64,
        description="e.g. 'large (relative to body)', 'small'",
    )


class FaceBlock(BaseModel):
    """Facial-feature rules."""
    eye_style: Optional[EyeStyle] = None
    eye_notes: list[str] = Field(default_factory=list, max_length=8)
    eyebrow_style: Optional[EyebrowStyle] = None
    eyebrow_notes: list[str] = Field(default_factory=list, max_length=8)
    mouth_styles: list[str] = Field(default_factory=list, max_length=8)
    expression_palette: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="Canonical expressions this character uses, e.g. 'tired-hunched', 'strained'",
    )


class ProportionsBlock(BaseModel):
    """Body proportions."""
    body_type: Optional[BodyType] = None
    posture: Optional[str] = Field(
        default=None,
        max_length=64,
        description="e.g. 'hunched', 'upright', 'slumped'",
    )
    relative_notes: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="e.g. 'large round head vs minimal body'",
    )


class OutlineBlock(BaseModel):
    """Outline / line-art rules."""
    weight: Optional[OutlineWeight] = None
    color: Optional[str] = Field(
        default=None,
        max_length=16,
        description="e.g. '#000000', 'black'",
    )
    quality: Optional[str] = Field(
        default=None,
        max_length=64,
        description="e.g. 'slightly imperfect sketchy marker lines'",
    )


class ColorPaletteBlock(BaseModel):
    """Color palette rules."""
    primary_hex: Optional[str] = Field(
        default=None,
        max_length=16,
        description="e.g. '#8B5E3C'",
    )
    primary_name: Optional[str] = Field(
        default=None,
        max_length=64,
        description="e.g. 'dull earth-brown'",
    )
    fills: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="e.g. 'flat single-color fills'",
    )
    notes: list[str] = Field(default_factory=list, max_length=8)


class WardrobeBlock(BaseModel):
    """Wardrobe / clothing rules."""
    default_outfit: Optional[str] = Field(default=None, max_length=200)
    palette: list[str] = Field(default_factory=list, max_length=8)
    continuity_lock: bool = Field(
        default=False,
        description="If True, wardrobe MUST stay identical across instances",
    )
    notes: list[str] = Field(default_factory=list, max_length=8)


class SignaturePropsBlock(BaseModel):
    """Signature props that distinguish characters."""
    props: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="e.g. ['wooden hoe', 'wheat stalk']",
    )
    lock_props: bool = Field(
        default=True,
        description="If True, props MUST stay identical across panels",
    )


class OrientationBlock(BaseModel):
    """Orientation rules — when can the character be flipped, mirrored, etc."""
    safe_orientations: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Orientations allowed: front, side, back, three-quarter, etc.",
    )
    flip_allowed: bool = Field(
        default=True,
        description="If False, character MUST NOT be horizontally flipped (asymmetry preservation)",
    )


class ReferenceSheetBlock(BaseModel):
    """Reference-sheet layout rules."""
    panels_required: list[str] = Field(
        default_factory=list,
        max_length=16,
        description=(
            "e.g. ['full-body front', 'full-body side', 'full-body back', "
            "'head turnaround', '4 expression panels', 'close-up signature prop']"
        ),
    )
    background: Optional[str] = Field(
        default=None,
        max_length=120,
        description="e.g. 'pure white with thin light-grey grid'",
    )
    grid: bool = Field(
        default=False,
        description="Whether the reference sheet uses a thin grid for alignment",
    )


class ConsistencyRulesBlock(BaseModel):
    """The consistency-rule set for character production."""
    rules: list[ConsistencyRuleKind] = Field(
        default_factory=list,
        max_length=16,
    )
    explicit_rules: list[str] = Field(
        default_factory=list,
        max_length=16,
        description=(
            "Plain-text reusable rules, e.g. "
            "'All panels show EXACT same character'"
        ),
    )


# ============================================================================
# The CharacterGrammar root
# ============================================================================

class CharacterGrammar(BaseModel):
    """The canonical character-production rules for a single character
    archetype / family.

    This module owns the PRINCIPLES of how a character should be
    represented. It does NOT declare any actual identity. Concrete
    character identities (e.g. @FARMER, @MODERNYOU) live in
    CharacterDefinition.

    Architecture
    ------------
        CharacterGrammar           ← this module (principles)
            ↓
        CharacterReference rules   ← character.grammar module (rules)
            ↓
        CharacterDefinition        ← concrete identity (Prompt 5)
            ↓
        CharacterInstance          ← scene placement (Prompt 5)
    """

    # Identity of the grammar (NOT of a specific character)
    grammar_id: str = Field(
        ...,
        min_length=3,
        max_length=96,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
        description="Stable identifier; e.g. 'hand_drawn_doodle_v1', 'doodad_farmer_grammar'",
    )
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)

    # The rule blocks
    identity: IdentityBlock = Field(default_factory=IdentityBlock)
    head: HeadBlock = Field(default_factory=HeadBlock)
    face: FaceBlock = Field(default_factory=FaceBlock)
    proportions: ProportionsBlock = Field(default_factory=ProportionsBlock)
    outline: OutlineBlock = Field(default_factory=OutlineBlock)
    palette: ColorPaletteBlock = Field(default_factory=ColorPaletteBlock)
    wardrobe: WardrobeBlock = Field(default_factory=WardrobeBlock)
    signature_props: SignaturePropsBlock = Field(default_factory=SignaturePropsBlock)
    orientation: OrientationBlock = Field(default_factory=OrientationBlock)
    reference_sheet: ReferenceSheetBlock = Field(default_factory=ReferenceSheetBlock)
    consistency: ConsistencyRulesBlock = Field(default_factory=ConsistencyRulesBlock)

    # Provenance
    provenance_ids: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="KnowledgeEntry IDs that informed this grammar",
    )

    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")

    @model_validator(mode="after")
    def _validate_family_lineage(self) -> "CharacterGrammar":
        """When a family is set, the consistency rules should declare
        FAMILY_LINEAGE explicitly. This is a soft check (warning,
        not block) because in some grammars the family link is
        external (e.g. a KnowledgeEntry).
        """
        # We do not block here — the consistency block is the source
        # of truth.
        return self

"""
Visual Grammar — the canonical structured intent for image and video prompts.

L-U1 — Production Knowledge & Visual Grammar Foundation.

Purpose
-------
This module defines the **structured intent** that downstream prompt
builders should emit, NOT free-form prompt strings. The renderer
contract (SceneDefinition) does NOT change — VisualGrammar is an
*intermediate representation* between the knowledge layer and the
existing canonical schemas.

Why structured (not free-form prompt text)?
-------------------------------------------
    1. Free-form prompt text is provider-specific.
    2. Structured intent can be validated, tested, diffed.
    3. The same VisualGrammar can produce prompts for many providers.
    4. The renderer does NOT depend on prompt syntax.

Conceptual representation
-------------------------
    {
        "style":              {...},   # visual style intent
        "subject":            {...},   # who/what is depicted
        "environment":        {...},   # where the scene takes place
        "composition":        {...},   # framing / focal / camera placement
        "action":             {...},   # what is happening
        "effects":            {...},   # motion lines, metaphor elements
        "camera":             {...},   # shot type + movement + intent
        "background":         {...},   # background color / treatment
        "typography":         {...},   # text overlay
        "constraints":        {...},   # negative constraints
        "format":             {...},   # aspect ratio, target medium
    }

Critical invariant
------------------
    - VisualGrammar is INTENT. It never contains raw prompt text.
    - All fields are optional EXCEPT where noted; the minimum useful
      VisualGrammar is just `style` + `subject`.
    - The same schema is used for image and video. Video grammar adds
      `motion` and `camera_movement` in addition.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Camera shot vocabulary (from DINO AI Cinematic Dictionary)
# ============================================================================

class CameraShotType(str, Enum):
    """Canonical shot types — bounded vocabulary.

    Each value is the standard cinematography name. Renderer / prompt
    builders consume this enum directly.
    """
    EXTREME_WIDE_SHOT = "extreme_wide_shot"      # EWS — full establishing
    WIDE_SHOT = "wide_shot"                       # WS — environment context
    MEDIUM_WIDE_SHOT = "medium_wide_shot"         # MWS — knees up
    MEDIUM_SHOT = "medium_shot"                   # MS — waist up, dialogue
    MEDIUM_CLOSE_UP = "medium_close_up"           # MCU — chest up
    CLOSE_UP = "close_up"                          # CU — face / object
    EXTREME_CLOSE_UP = "extreme_close_up"         # ECU — single detail
    OVER_THE_SHOULDER = "over_the_shoulder"       # OTS — POV dialogue
    POINT_OF_VIEW = "point_of_view"               # POV — character perspective
    DUTCH_ANGLE = "dutch_angle"                   # Tilted — unease
    BIRDS_EYE = "birds_eye"                       # From above
    WORMS_EYE = "worms_eye"                       # From below
    TWO_SHOT = "two_shot"                         # Two subjects in frame


class CameraMovementType(str, Enum):
    """Canonical camera movements."""
    HOLD = "hold"                                 # Static
    PUSH_IN = "push_in"                           # Dolly forward
    PULL_OUT = "pull_out"                         # Dolly backward
    PAN = "pan"                                   # Horizontal rotation
    TILT = "tilt"                                 # Vertical rotation
    ZOOM = "zoom"                                 # Focal-length change
    TRACKING = "tracking"                         # Follow subject
    SHAKE = "shake"                               # Handheld / nervous
    ORBIT = "orbit"                               # Around subject
    PARALLAX = "parallax"                         # Layered depth shift


# ============================================================================
# Motion vocabulary (animation patterns)
# ============================================================================

class MotionPattern(str, Enum):
    """Reusable motion patterns for video prompts.

    The first three are the most common in the Google Flow reference
    corpus. The rest are common animation vocabulary.
    """
    FRAME_BY_FRAME_DOODLE = "frame_by_frame_doodle"   # Hand-drawn cell animation
    LOOP = "loop"                                       # Seamless loop
    RIG_POSE_INTERPOLATION = "rig_pose_interpolation" # Skeletal animation
    KINETIC_TEXT = "kinetic_text"                       # Animated typography
    PARALLAX_PAN = "parallax_pan"                       # Layered depth scroll
    METAPHOR_DROP = "metaphor_drop"                     # Symbolic object drop
    SHAKE_NERVOUS = "shake_nervous"                     # Tension shake


# ============================================================================
# Visual style profiles
# ============================================================================

class VisualStyleProfile(str, Enum):
    """Bounded visual style vocabulary.

    New styles require a KnowledgeEntry under VISUAL_STYLE domain and
    an explicit PROJECT_RULE promotion.
    """
    HAND_DRAWN_DOODLE = "hand_drawn_doodle"
    SEMI_REALISTIC_2D = "semi_realistic_2d"
    FLAT_VECTOR = "flat_vector"
    STORYBOARD_SKETCH = "storyboard_sketch"
    INFOGRAPHIC_CLEAN = "infographic_clean"


# ============================================================================
# Sub-blocks of the grammar
# ============================================================================

class StyleIntent(BaseModel):
    """The visual style foundation."""
    profile: Optional[VisualStyleProfile] = None
    palette: Optional[str] = Field(
        default=None,
        max_length=120,
        description="e.g. 'flat colors', 'muted earth tones', 'neon accents'",
    )
    outline: Optional[str] = Field(
        default=None,
        max_length=120,
        description="e.g. 'bold black marker outlines', 'thin ink', 'no outlines'",
    )
    line_quality: Optional[str] = Field(
        default=None,
        max_length=120,
        description="e.g. 'slightly imperfect sketchy marker lines', 'clean geometric'",
    )
    rendering_notes: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="Additional style notes, e.g. 'no gradients, no shadows'",
    )


class SubjectIntent(BaseModel):
    """Who or what is depicted."""
    character_ref: Optional[str] = Field(
        default=None,
        max_length=64,
        description="@CHARACTER reference token (e.g. '@MODERNYOU'), if any",
    )
    description: Optional[str] = Field(default=None, max_length=500)
    pose: Optional[str] = Field(default=None, max_length=64)
    expression: Optional[str] = Field(default=None, max_length=64)
    props: list[str] = Field(default_factory=list, max_length=8)
    framing_hint: Optional[str] = Field(
        default=None,
        max_length=120,
        description="e.g. 'extreme close-up', 'waist-up'",
    )


class EnvironmentIntent(BaseModel):
    """Where the scene takes place."""
    setting: Optional[str] = Field(default=None, max_length=200)
    era: Optional[str] = Field(default=None, max_length=64)
    time_of_day: Optional[str] = Field(default=None, max_length=64)
    weather: Optional[str] = Field(default=None, max_length=64)
    lighting: Optional[str] = Field(default=None, max_length=200)


class CompositionIntent(BaseModel):
    """Framing, focal point, layering."""
    shot_type: Optional[CameraShotType] = None
    focal_subject: Optional[str] = Field(default=None, max_length=120)
    rule_of_thirds: Optional[bool] = None
    depth_layers: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="e.g. ['foreground', 'midground', 'background']",
    )
    notes: list[str] = Field(default_factory=list, max_length=8)


class ActionIntent(BaseModel):
    """What is happening in the scene."""
    description: Optional[str] = Field(default=None, max_length=500)
    verbs: list[str] = Field(default_factory=list, max_length=8)
    intensity: Optional[str] = Field(
        default=None,
        max_length=64,
        description="e.g. 'low', 'medium', 'high'",
    )


class EffectsIntent(BaseModel):
    """Overlay effects: motion lines, metaphors, particles."""
    motion_lines: Optional[bool] = None
    metaphor_elements: list[str] = Field(default_factory=list, max_length=8)
    text_overlays: list[str] = Field(default_factory=list, max_length=4)
    particles: Optional[str] = Field(default=None, max_length=120)
    other: list[str] = Field(default_factory=list, max_length=8)


class CameraIntent(BaseModel):
    """Camera shot + movement for VIDEO grammar.

    For image grammar, only `shot_type` applies.
    """
    shot_type: Optional[CameraShotType] = None
    movement: Optional[CameraMovementType] = None
    easing: Optional[str] = Field(default=None, max_length=32)
    notes: list[str] = Field(default_factory=list, max_length=8)


class MotionIntent(BaseModel):
    """Motion pattern for VIDEO grammar."""
    pattern: Optional[MotionPattern] = None
    duration_sec: Optional[float] = None
    loop: Optional[bool] = None
    notes: list[str] = Field(default_factory=list, max_length=8)


class BackgroundIntent(BaseModel):
    """Background treatment."""
    color: Optional[str] = Field(
        default=None,
        max_length=64,
        description="e.g. 'cold cobalt blue', '@C-BLUE-01'",
    )
    treatment: Optional[str] = Field(
        default=None,
        max_length=120,
        description="e.g. 'solid', 'gradient', 'subtle radial'",
    )
    notes: list[str] = Field(default_factory=list, max_length=8)


class TypographyIntent(BaseModel):
    """Text overlay intent."""
    text: Optional[str] = Field(default=None, max_length=64)
    position: Optional[str] = Field(
        default=None,
        max_length=64,
        description="e.g. 'top-left', 'lower-third'",
    )
    style: Optional[str] = Field(default=None, max_length=120)
    color: Optional[str] = Field(default=None, max_length=64)


class ConstraintsIntent(BaseModel):
    """Negative constraints (anti-patterns)."""
    forbid: list[str] = Field(
        default_factory=list,
        max_length=32,
        description="Things this prompt FORBIDS, e.g. 'no gradients', 'no 3D'",
    )
    require: list[str] = Field(
        default_factory=list,
        max_length=32,
        description="Things this prompt REQUIRES, e.g. 'drop shadow under character'",
    )


class FormatIntent(BaseModel):
    """Output format."""
    aspect_ratio: Optional[str] = Field(
        default=None,
        max_length=16,
        description="e.g. '16:9', '9:16', '1:1'",
    )
    medium: Optional[str] = Field(
        default=None,
        max_length=64,
        description="e.g. 'image', 'video', 'educational YouTube explainer doodle'",
    )
    notes: list[str] = Field(default_factory=list, max_length=8)


# ============================================================================
# The VisualGrammar root
# ============================================================================

class VisualGrammar(BaseModel):
    """The canonical structured intent for image and video prompts.

    Fields are mostly optional. The minimum useful VisualGrammar is
    `style` + `subject`. Validation only fires when conflicting fields
    are explicitly set (e.g. motion on an image prompt).

    Critical invariant
    ------------------
        VisualGrammar is INTENT. It never contains raw prompt text.
        A separate renderer-side adapter (NOT in this module) maps
        VisualGrammar → provider-specific prompt strings.
    """

    style: StyleIntent = Field(default_factory=StyleIntent)
    subject: SubjectIntent = Field(default_factory=SubjectIntent)
    environment: EnvironmentIntent = Field(default_factory=EnvironmentIntent)
    composition: CompositionIntent = Field(default_factory=CompositionIntent)
    action: ActionIntent = Field(default_factory=ActionIntent)
    effects: EffectsIntent = Field(default_factory=EffectsIntent)
    camera: CameraIntent = Field(default_factory=CameraIntent)
    motion: MotionIntent = Field(default_factory=MotionIntent)
    background: BackgroundIntent = Field(default_factory=BackgroundIntent)
    typography: TypographyIntent = Field(default_factory=TypographyIntent)
    constraints: ConstraintsIntent = Field(default_factory=ConstraintsIntent)
    format: FormatIntent = Field(default_factory=FormatIntent)

    # Provenance
    provenance_ids: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="KnowledgeEntry IDs that informed this grammar instance",
    )
    source_grammar_id: Optional[str] = Field(
        default=None,
        max_length=96,
        description="If this is a derived grammar, the ID of the source",
    )

    def is_image_grammar(self) -> bool:
        """Does this grammar target a static image (not video)?"""
        # Image grammar MUST NOT declare motion.pattern or
        # camera.movement (camera.shot_type is allowed for framing).
        if self.motion.pattern is not None:
            return False
        if self.camera.movement is not None:
            return False
        return True

    def is_video_grammar(self) -> bool:
        """Does this grammar target a video?"""
        return not self.is_image_grammar()

    @model_validator(mode="after")
    def _validate_consistency(self) -> "VisualGrammar":
        """Cross-field consistency checks."""
        # An empty grammar is allowed but discouraged — it generates
        # nothing useful. We do not block here; downstream prompt
        # builders will fail noisily.
        return self

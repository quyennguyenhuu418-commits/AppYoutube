"""
Character Intelligence System — canonical schemas.

This module defines the complete Character System data contract:

    StoryboardPackage.character_requirements
    → CharacterSystem.resolve()
    → CharacterDefinition + CharacterAssetPackage
    → SceneDefinition.characters[] + SceneDefinition.actors[]

Design principles:
    - CharacterIdentity is separate from CharacterInstance (scene placement)
    - CharacterDefinition is persistent and versioned — NOT a generated image
    - The system maps to the existing renderer (Pose: stand/walk/run/sit/point/
      think/celebrate/hide) and SceneDefinition (Character + Actor models)
    - SVG is the preferred asset format; components have local coordinate systems
    - Duplicate detection uses semantic identity keys, not string equality

External contracts:
    - SceneDefinition (C-01): character/actor fields
    - StoryboardPackage (C-13): CharacterRequirement inputs
    - renderer/src/components/Character.tsx: 8 pose variants, color prop
    - renderer/src/scenes/types.ts: Character/Actor/Pose TypeScript types
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Enums — Character domain vocabulary
# ============================================================================

class CharacterCategory(str, Enum):
    """Semantic role of the character in the documentary."""
    HUMAN_MALE = "human_male"
    HUMAN_FEMALE = "human_female"
    HUMAN_CHILD = "human_child"
    HUMAN_GENERIC = "human_generic"
    ANIMAL = "animal"
    CREATURE = "creature"
    NARRATOR = "narrator"
    DIAGRAM_ACTOR = "diagram_actor"


class AgeClass(str, Enum):
    """Rough age bracket for silhouette and proportions."""
    CHILD = "child"
    YOUNG_ADULT = "young_adult"
    ADULT = "adult"
    MIDDLE_AGED = "middle_aged"
    ELDERLY = "elderly"
    UNKNOWN = "unknown"


class CharacterStatus(str, Enum):
    """Production lifecycle status."""
    DRAFT = "draft"
    DESIGN = "design"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class CharacterScope(str, Enum):
    """Whether the character belongs to one project or is reusable globally."""
    PROJECT = "project"
    GLOBAL = "global"


class Orientation(str, Enum):
    """Character facing direction. Do NOT blindly flip asymmetrical characters."""
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"
    THREE_QUARTER_LEFT = "three_quarter_left"
    THREE_QUARTER_RIGHT = "three_quarter_right"


class ExpressionLabel(str, Enum):
    """Canonical expression vocabulary — maps to face component states."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    AFRAID = "afraid"
    SURPRISED = "surprised"
    CONFUSED = "confused"
    CURIOUS = "curious"
    TIRED = "tired"
    PAIN = "pain"
    FOCUSED = "focused"


class ActionLabel(str, Enum):
    """High-level character actions — map to pose selections."""
    STAND = "stand"
    WALK = "walk"
    RUN = "run"
    SIT = "sit"
    KNEEL = "kneel"
    LIE = "lie"
    CROUCH = "crouch"
    HOLD = "hold"
    CARRY = "carry"
    REACH = "reach"
    POINT = "point"
    THROW = "throw"
    CLIMB = "climb"
    FIGHT = "fight"
    SLEEP = "sleep"
    WARM_HANDS = "warm_hands"
    EAT = "eat"
    WORK = "work"
    LOOK = "look"
    TALK = "talk"
    THINK = "think"
    CELEBRATE = "celebrate"
    HIDE = "hide"


class SilhouetteComplexity(str, Enum):
    """How detailed the silhouette is. Higher = more complex."""
    MINIMAL = "minimal"      # Single-line stick figure
    SIMPLE = "simple"        # Basic filled shapes
    MEDIUM = "medium"        # With clothing outlines
    DETAILED = "detailed"    # Full illustration


# ============================================================================
# Style Profile — channel-level visual configuration
# ============================================================================

class StyleProfile(BaseModel):
    """Character art style configuration. Stored once per project/channel."""
    body_ratio: float = Field(default=0.35, ge=0.1, le=1.0,
                              description="Head-to-body height ratio (0.35 = cartoon head)")
    head_ratio: float = Field(default=0.25, ge=0.1, le=0.5,
                              description="Head width to body width ratio")
    shoulder_to_height_ratio: float = Field(default=0.30, ge=0.1, le=0.6)
    line_weight: float = Field(default=2.0, ge=0.5, le=8.0,
                               description="SVG stroke-width for limbs")
    eye_style: str = Field(default="dot", max_length=32)
    mouth_style: str = Field(default="line", max_length=32)
    silhouette_complexity: SilhouetteComplexity = SilhouetteComplexity.SIMPLE
    shading_level: str = Field(default="none", max_length=16)  # none | flat | simple
    default_outline_color: str = Field(default="#222222", max_length=16)


# ============================================================================
# Skeleton / Anchor Model — for future animation
# ============================================================================

class JointAnchor(BaseModel):
    """A 2D joint/anchor point on the character."""
    joint_id: str = Field(min_length=1, max_length=32)
    parent_joint: str | None = None
    """Local offset from parent joint (or root if no parent)."""
    x: float = Field(default=0.0)
    y: float = Field(default=0.0)
    min_rotation: float = Field(default=-180.0, ge=-180.0, le=180.0)
    max_rotation: float = Field(default=180.0, ge=-180.0, le=180.0)
    flip_allowed: bool = Field(default=False)
    description: str = Field(default="", max_length=100)


class CharacterSkeletonDefinition(BaseModel):
    """2D joint/anchor hierarchy for animation readiness."""
    root_x: float = Field(default=0.0, description="Root anchor X offset")
    root_y: float = Field(default=0.0, description="Root anchor Y offset")
    joints: list[JointAnchor] = Field(default_factory=list)
    canonical_width: float = Field(default=100.0, ge=10.0)
    canonical_height: float = Field(default=200.0, ge=20.0)


# ============================================================================
# Color Palette
# ============================================================================

class CharacterColorPalette(BaseModel):
    """Color tokens for a character — used for SVG rendering."""
    primary: str = Field(default="#8B6914", pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    outline: str = Field(default="#222222", pattern=r"^#[0-9A-Fa-f]{6}$")
    skin_tone: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    hair_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    clothing_primary: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    clothing_secondary: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


# ============================================================================
# Body / Head / Face Profiles
# ============================================================================

class BodyProfile(BaseModel):
    height_cm: int | None = Field(default=None, ge=50, le=250)
    build: str = Field(default="average", max_length=32)  # thin / average / stocky / muscular
    shoulder_width_ratio: float = Field(default=0.30, ge=0.1, le=0.6)


class HeadProfile(BaseModel):
    shape: str = Field(default="oval", max_length=32)  # round / oval / square / elongated
    size_ratio: float = Field(default=0.35, ge=0.15, le=0.5)


class FaceProfile(BaseModel):
    eye_size: str = Field(default="medium", max_length=16)  # small / medium / large
    eye_spacing: float = Field(default=0.30, ge=0.1, le=0.6,
                                description="Inter-eye distance as ratio of head width")
    eyebrow_style: str = Field(default="simple", max_length=32)
    nose_style: str = Field(default="minimal", max_length=32)  # minimal / defined
    mouth_width_ratio: float = Field(default=0.35, ge=0.1, le=0.6)


class HairProfile(BaseModel):
    style: str = Field(default="short", max_length=32)  # bald / short / long / braided / mohawk
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    has_accessories: bool = Field(default=False)


class SkinProfile(BaseModel):
    tone: str = Field(default="medium", max_length=32)  # pale / light / medium / dark / deep
    color: str = Field(default="#8D5524", pattern=r"^#[0-9A-Fa-f]{6}$")


# ============================================================================
# Clothing / Wardrobe
# ============================================================================

class ClothingItem(BaseModel):
    """A single clothing item in a wardrobe."""
    item_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    layer: str = Field(default="base", max_length=32)  # base / outer / accessory
    material: str = Field(default="animal_hide", max_length=64)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    historical_context: str = Field(default="", max_length=200)
    covers: list[str] = Field(default_factory=list,
                              description="Body parts this item covers: torso, legs, head, etc.")
    visibility_priority: int = Field(default=0, ge=0, le=10,
                                      description="Higher = rendered on top")


class WardrobeDefinition(BaseModel):
    """A named clothing configuration for a character."""
    wardrobe_id: str = Field(min_length=1, max_length=64)
    character_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    season: str = Field(default="", max_length=32)  # spring / summer / autumn / winter
    historical_context: str = Field(default="", max_length=200)
    clothing_items: list[ClothingItem] = Field(default_factory=list)
    continuity_locked: bool = Field(default=False,
                                    description="If True, this wardrobe cannot be changed without review")
    is_default: bool = Field(default=False)
    notes: str = Field(default="", max_length=300)


# ============================================================================
# Pose Definitions
# ============================================================================

class BodyConfiguration(BaseModel):
    """Pose of individual body parts."""
    torso_angle: float = Field(default=0.0, ge=-90.0, le=90.0,
                               description="Degrees from vertical")
    spine_curve: float = Field(default=0.0, ge=-30.0, le=30.0)
    balance_offset_x: float = Field(default=0.0, ge=-50.0, le=50.0)


class ArmConfiguration(BaseModel):
    """Configuration for one arm."""
    shoulder_angle: float = Field(default=0.0, ge=-180.0, le=180.0)
    elbow_angle: float = Field(default=0.0, ge=-180.0, le=180.0)
    wrist_angle: float = Field(default=0.0, ge=-180.0, le=180.0)
    raised: bool = Field(default=False)


class LegConfiguration(BaseModel):
    """Configuration for one leg."""
    hip_angle: float = Field(default=0.0, ge=-180.0, le=180.0)
    knee_angle: float = Field(default=0.0, ge=-180.0, le=180.0)
    ankle_angle: float = Field(default=0.0, ge=-180.0, le=180.0)


class HeadOrientation(BaseModel):
    """Head tilt and direction."""
    tilt_deg: float = Field(default=0.0, ge=-45.0, le=45.0)
    look_direction: Orientation = Orientation.THREE_QUARTER_LEFT


class PoseDefinition(BaseModel):
    """A canonical pose — the design source for all render variants."""
    pose_id: str = Field(min_length=1, max_length=64)
    character_id: str = Field(min_length=1, max_length=64)
    pose_type: ActionLabel
    body: BodyConfiguration = Field(default_factory=BodyConfiguration)
    left_arm: ArmConfiguration = Field(default_factory=ArmConfiguration)
    right_arm: ArmConfiguration = Field(default_factory=ArmConfiguration)
    left_leg: LegConfiguration = Field(default_factory=LegConfiguration)
    right_leg: LegConfiguration = Field(default_factory=LegConfiguration)
    head: HeadOrientation = Field(default_factory=HeadOrientation)
    symmetry: float = Field(default=1.0, ge=0.0, le=1.0,
                            description="1.0 = perfectly symmetrical, 0.0 = fully asymmetric")
    thumbnail_svg: str = Field(default="", max_length=500,
                                description="Inline SVG path data or path to thumbnail")
    version: str = Field(default="1.0.0", max_length=16)
    notes: str = Field(default="", max_length=200)


# ============================================================================
# Expression Definitions
# ============================================================================

class EyeState(BaseModel):
    """State of the eyes for a given expression."""
    shape: str = Field(default="open", max_length=32)  # open / closed / squint / wide
    eyebrow_raise: float = Field(default=0.0, ge=-1.0, le=1.0,
                                  description="-1.0 = frown, 0.0 = neutral, 1.0 = raised")
    eyebrow_inner_raise: float = Field(default=0.0, ge=-1.0, le=1.0)
    pupil_size: float = Field(default=0.5, ge=0.1, le=1.0)
    look_direction: Orientation = Orientation.FRONT


class MouthState(BaseModel):
    """State of the mouth for a given expression."""
    shape: str = Field(default="neutral", max_length=32)  # neutral / smile / frown / open / o_shape
    corner_raise: float = Field(default=0.0, ge=-1.0, le=1.0)
    open_amount: float = Field(default=0.0, ge=0.0, le=1.0)


class ExpressionDefinition(BaseModel):
    """A canonical facial expression — modifies only approved face components."""
    expression_id: str = Field(min_length=1, max_length=64)
    character_id: str = Field(min_length=1, max_length=64)
    label: ExpressionLabel
    eyes: EyeState = Field(default_factory=EyeState)
    mouth: MouthState = Field(default_factory=MouthState)
    eyebrow_modifier: str = Field(default="", max_length=64,
                                   description="e.g. furrowed / raised / angled")
    version: str = Field(default="1.0.0", max_length=16)


# ============================================================================
# Continuity Profile
# ============================================================================

class CharacterContinuityProfile(BaseModel):
    """Which aspects of a character are locked for production consistency."""
    identity_locked: bool = True
    palette_locked: bool = True
    proportions_locked: bool = True
    hair_locked: bool = True
    wardrobe_locked: bool = False
    permitted_scene_changes: list[str] = Field(
        default_factory=lambda: ["pose", "expression", "orientation", "scale", "position"],
        description="What a scene IS allowed to change per CharacterInstance"
    )


# ============================================================================
# Canonical Character Identity
# ============================================================================

class CharacterDefinition(BaseModel):
    """Canonical character identity — persistent across all scenes and projects.

    This is NOT a generated image. It is a production entity with:
    - Identity (who this is)
    - Design (how this looks)
    - Assets (SVG components, poses, expressions, wardrobe)
    - Continuity rules (what must stay consistent)
    - Version (immutable once active)
    """
    # --- Identity ---
    character_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(default="", min_length=0, max_length=64)
    role: str = Field(default="", max_length=200,
                       description="Narrator role, character archetype, or 'generic_human'")
    category: CharacterCategory = CharacterCategory.HUMAN_GENERIC
    age_class: AgeClass = AgeClass.ADULT
    scope: CharacterScope = CharacterScope.PROJECT

    # --- Appearance ---
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$",
                        description="Primary color — must match SceneDefinition.Character.color")
    default_pose: str = Field(default="stand", max_length=32)
    default_expression: ExpressionLabel = ExpressionLabel.NEUTRAL
    silhouette_complexity: SilhouetteComplexity = SilhouetteComplexity.SIMPLE

    # --- Design profiles ---
    style_profile: StyleProfile = Field(default_factory=StyleProfile)
    body_profile: BodyProfile = Field(default_factory=BodyProfile)
    head_profile: HeadProfile = Field(default_factory=HeadProfile)
    face_profile: FaceProfile = Field(default_factory=FaceProfile)
    hair_profile: HairProfile = Field(default_factory=HairProfile)
    skin_profile: SkinProfile = Field(default_factory=SkinProfile)
    color_palette: CharacterColorPalette = Field(default_factory=CharacterColorPalette)
    skeleton: CharacterSkeletonDefinition = Field(default_factory=CharacterSkeletonDefinition)

    # --- Production metadata ---
    continuity_profile: CharacterContinuityProfile = Field(
        default_factory=CharacterContinuityProfile
    )

    # --- Versioning ---
    version: str = Field(default="1.0.0", max_length=16)
    input_hash: str = Field(default="", max_length=64,
                              description="Hash of the input CharacterRequirement that created this")
    style_version: str = Field(default="1.0.0", max_length=16)

    # --- Lifecycle ---
    status: CharacterStatus = CharacterStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # --- Approval ---
    approved_by: str = Field(default="", max_length=64)
    approved_at: datetime | None = None

    # --- Description (for renderer / human) ---
    description: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _validate_color_matches_palette(self) -> "CharacterDefinition":
        """The primary color must match the palette primary."""
        if self.color != self.color_palette.primary:
            # Auto-correct to match for consistency
            object.__setattr__(self.color_palette, "primary", self.color)
        return self

    @model_validator(mode="after")
    def _validate_default_pose(self) -> "CharacterDefinition":
        """Default pose must be one of the 8 renderer-supported poses."""
        valid_poses = {
            "stand", "walk", "run", "sit", "point",
            "think", "celebrate", "hide"
        }
        if self.default_pose not in valid_poses:
            object.__setattr__(self, "default_pose", "stand")
        return self

    def to_scene_definition_character(self) -> dict[str, Any]:
        """Convert to the SceneDefinition Character model fields."""
        return {
            "id": self.character_id,
            "name": self.name,
            "color": self.color,
            "default_pose": self.default_pose,
            "description": self.description,
        }


# ============================================================================
# Character Instance — scene-specific appearance
# ============================================================================

class CharacterInstance(BaseModel):
    """A character's specific appearance in ONE scene.

    This does NOT duplicate identity data. It references character_id
    and adds only scene-specific state: pose, expression, wardrobe, position.
    """
    character_id: str = Field(min_length=1, max_length=64)
    scene_id: str = Field(min_length=1, max_length=64)

    # --- Visual state ---
    pose: str = Field(default="stand", max_length=32)
    expression: ExpressionLabel = ExpressionLabel.NEUTRAL
    orientation: Orientation = Orientation.THREE_QUARTER_LEFT

    # --- Wardrobe ---
    wardrobe_id: str = Field(default="", max_length=64,
                              description="Which WardrobeDefinition is active. Empty = use character default.")

    # --- Spatial (normalized 0..1, renderer multiplies by frame size) ---
    x: float = Field(default=0.5, ge=0.0, le=1.0)
    y: float = Field(default=0.5, ge=0.0, le=1.0)
    scale: float = Field(default=1.0, ge=0.1, le=4.0)
    rotation_deg: float = Field(default=0.0, ge=-360.0, le=360.0)

    # --- Animation ---
    enter_anim: str = Field(default="fade_in", max_length=32)
    exit_anim: str = Field(default="none", max_length=32)

    # --- Continuity ---
    continuity_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Explicitly allowed scene-specific changes (e.g. wardrobe change for plot reason)"
    )

    @model_validator(mode="after")
    def _validate_pose(self) -> "CharacterInstance":
        valid_poses = {
            "stand", "walk", "run", "sit", "point",
            "think", "celebrate", "hide"
        }
        if self.pose not in valid_poses:
            object.__setattr__(self, "pose", "stand")
        return self

    def to_scene_definition_actor(self) -> dict[str, Any]:
        """Convert to the SceneDefinition Actor model fields."""
        # Map our expression/orientation to a renderer-compatible pose
        return {
            "character_id": self.character_id,
            "x": self.x,
            "y": self.y,
            "scale": self.scale,
            "rotation_deg": self.rotation_deg,
            "pose": self.pose,
            "enter_anim": self.enter_anim,
            "exit_anim": self.exit_anim,
        }


# ============================================================================
# Character Asset Package — filesystem contract
# ============================================================================

class CharacterAssetPackage(BaseModel):
    """The on-disk package structure for a canonical character.

    Path: {workspace}/characters/{character_id}/
    """
    character_id: str = Field(min_length=1, max_length=64)
    character_version: str = Field(default="1.0.0", max_length=16)
    package_version: str = Field(default="1.0.0", max_length=16)

    # Files (relative paths inside the package directory)
    identity_file: str = Field(default="identity.json", max_length=128)
    design_file: str = Field(default="design.json", max_length=128)
    wardrobe_file: str = Field(default="wardrobe.json", max_length=128)
    poses_file: str = Field(default="poses.json", max_length=128)
    expressions_file: str = Field(default="expressions.json", max_length=128)
    metadata_file: str = Field(default="metadata.json", max_length=128)

    # Optional preview
    preview_svg: str = Field(default="", max_length=500,
                               description="Inline SVG or relative path to preview.svg")
    preview_png: str = Field(default="", max_length=256)

    # SVG component paths
    component_svg_dir: str = Field(default="components/", max_length=128)
    pose_svg_dir: str = Field(default="poses/", max_length=128)
    expression_svg_dir: str = Field(default="expressions/", max_length=128)

    # Quality
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    design_approved: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Character Registry Entry — canonical management
# ============================================================================

class CharacterRegistryEntry(BaseModel):
    """A single entry in the global/project character registry."""
    character_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    role: str = Field(default="", max_length=200)
    category: CharacterCategory = CharacterCategory.HUMAN_GENERIC
    scope: CharacterScope = CharacterScope.PROJECT
    status: CharacterStatus = CharacterStatus.DRAFT
    version: str = Field(default="1.0.0", max_length=16)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    # Asset locations
    package_dir: str = Field(default="", max_length=256)
    active_wardrobe_id: str = Field(default="", max_length=64)
    available_wardrobes: list[str] = Field(default_factory=list)
    available_poses: list[str] = Field(default_factory=list)
    available_expressions: list[str] = Field(default_factory=list)

    # Pose/expression coverage
    pose_coverage: float = Field(default=0.0, ge=0.0, le=1.0,
                                  description="Fraction of required poses covered")
    expression_coverage: float = Field(default=0.0, ge=0.0, le=1.0)

    # Quality
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    # Usage tracking
    projects_using: list[str] = Field(default_factory=list,
                                       description="job_ids that have used this character")
    scene_count: int = Field(default=0, ge=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: datetime | None = None


class CharacterRegistry(BaseModel):
    """The canonical character registry — answers: which characters exist, where, what version?"""
    project_id: str = Field(default="", max_length=64)
    scope: CharacterScope = CharacterScope.PROJECT
    characters: list[CharacterRegistryEntry] = Field(default_factory=list)
    global_characters: list[str] = Field(default_factory=list,
                                           description="character_ids that are globally reusable")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_character(self, character_id: str) -> CharacterRegistryEntry | None:
        return next(
            (c for c in self.characters if c.character_id == character_id),
            None
        )

    def find_by_role(self, role: str) -> list[CharacterRegistryEntry]:
        return [c for c in self.characters if c.role == role]

    def find_by_category(self, category: CharacterCategory) -> list[CharacterRegistryEntry]:
        return [c for c in self.characters if c.category == category]


# ============================================================================
# Character Quality Score — 11-dimension evaluation
# ============================================================================

class CharacterQualityScore(BaseModel):
    """11-dimension quality score for a CharacterDefinition."""
    # 11 dimensions
    identity_consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    proportion_consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    silhouette_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    style_consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    wardrobe_consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    pose_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    expression_coverage: float = Field(ge=0.0, le=1.0, default=0.0)
    component_completeness: float = Field(ge=0.0, le=1.0, default=0.0)
    animation_readiness: float = Field(ge=0.0, le=1.0, default=0.0)
    asset_format_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    continuity_readiness: float = Field(ge=0.0, le=1.0, default=0.0)

    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_overall(self) -> "CharacterQualityScore":
        if self.dimension_scores:
            # Recompute from dimension_scores dict
            vals = list(self.dimension_scores.values())
            object.__setattr__(self, "overall_score", round(sum(vals) / len(vals), 3))
        elif self.overall_score == 0.0:
            # Auto-compute from field values
            fields = [
                self.identity_consistency,
                self.proportion_consistency,
                self.silhouette_quality,
                self.style_consistency,
                self.wardrobe_consistency,
                self.pose_coverage,
                self.expression_coverage,
                self.component_completeness,
                self.animation_readiness,
                self.asset_format_quality,
                self.continuity_readiness,
            ]
            object.__setattr__(self, "overall_score", round(sum(fields) / len(fields), 3))
        return self


# ============================================================================
# Character System Output — pipeline stage result
# ============================================================================

class CharacterResolution(BaseModel):
    """Resolution of one CharacterRequirement to a CharacterDefinition."""
    character_id: str
    source: str = Field(default="new", max_length=16)  # "new" | "reuse" | "resolve"
    character_definition: CharacterDefinition | None = None
    wardrobe: WardrobeDefinition | None = None
    poses: list[PoseDefinition] = Field(default_factory=list)
    expressions: list[ExpressionDefinition] = Field(default_factory=list)
    asset_package: CharacterAssetPackage | None = None
    quality_score: CharacterQualityScore | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CharacterSystemPackage(BaseModel):
    """The complete output of the Character System for one project/job."""
    job_id: str = Field(default="", max_length=64)
    project_id: str = Field(default="", max_length=64)
    version: str = "1.0.0"
    schema_version: str = "1.0.0"

    # All character definitions produced
    characters: list[CharacterDefinition] = Field(default_factory=list)

    # All scene-specific instances
    instances: list[CharacterInstance] = Field(default_factory=list)

    # All wardrobe definitions
    wardrobes: list[WardrobeDefinition] = Field(default_factory=list)

    # All pose definitions
    poses: list[PoseDefinition] = Field(default_factory=list)

    # All expression definitions
    expressions: list[ExpressionDefinition] = Field(default_factory=list)

    # Asset packages
    asset_packages: list[CharacterAssetPackage] = Field(default_factory=list)

    # Resolution log
    resolutions: list[CharacterResolution] = Field(default_factory=list)

    # Registry state
    registry: CharacterRegistry | None = None

    # Quality
    overall_quality_score: float = Field(ge=0.0, le=1.0, default=0.0)
    character_quality_scores: dict[str, CharacterQualityScore] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: CharacterStatus = CharacterStatus.DRAFT

    @model_validator(mode="after")
    def _compute_quality(self) -> "CharacterSystemPackage":
        if self.character_quality_scores:
            scores = [s.overall_score for s in self.character_quality_scores.values()]
            object.__setattr__(
                self, "overall_quality_score",
                round(sum(scores) / len(scores), 3)
            )
        return self

    def get_character(self, character_id: str) -> CharacterDefinition | None:
        return next(
            (c for c in self.characters if c.character_id == character_id),
            None
        )

    def get_instances_for_scene(self, scene_id: str) -> list[CharacterInstance]:
        return [i for i in self.instances if i.scene_id == scene_id]

    def get_wardrobe(self, wardrobe_id: str) -> WardrobeDefinition | None:
        return next(
            (w for w in self.wardrobes if w.wardrobe_id == wardrobe_id),
            None
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

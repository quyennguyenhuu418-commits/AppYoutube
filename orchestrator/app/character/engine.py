"""
Character Intelligence Engine — transforms StoryboardPackage CharacterRequirements
into canonical CharacterDefinitions, CharacterAssetPackages, pose/expression
libraries, and CharacterContinuityMetadata.

Pipeline: StoryboardPackage → CharacterSystemEngine → CharacterSystemPackage

Key principles:
    - ONE canonical character per semantic identity (no duplicate hunter_01/hunter_02)
    - Character identity is SEPARATE from character instance (scene placement)
    - All 8 renderer-supported poses are always available (stand/walk/run/sit/point/think/celebrate/hide)
    - SVG is the preferred asset format; components have local coordinate systems
    - Cache + idempotency: identical inputs produce identical outputs
    - Backward compatible: outputs SceneDefinition.characters[] + SceneDefinition.actors[]
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.schemas.character import (
    ActionLabel,
    CharacterAssetPackage,
    CharacterContinuityProfile,
    CharacterDefinition,
    CharacterInstance,
    CharacterQualityScore,
    CharacterRegistry,
    CharacterRegistryEntry,
    CharacterResolution,
    CharacterScope,
    CharacterSkeletonDefinition,
    CharacterStatus,
    CharacterSystemPackage,
    ClothingItem,
    ExpressionDefinition,
    ExpressionLabel,
    EyeState,
    HeadOrientation,
    JointAnchor,
    MouthState,
    Orientation,
    PoseDefinition,
    StyleProfile,
    WardrobeDefinition,
)
from app.schemas.scene_definition import Character as SceneDefCharacter
from app.schemas.scene_definition import SceneDefinition
from app.schemas.storyboard import CharacterRequirement, StoryboardPackage, VisualBeat

if TYPE_CHECKING:
    from app.character.cache import CharacterCache

log = logging.getLogger(__name__)

# Valid renderer poses (from scene_definition.py Pose enum)
VALID_POSES = {"stand", "walk", "run", "sit", "point", "think", "celebrate", "hide"}


# ============================================================================
# Character Identity Key — for duplicate detection
# ============================================================================

def character_identity_key(req: CharacterRequirement, beat: VisualBeat) -> str:
    """Compute a deterministic semantic identity key for duplicate detection.

    Two CharacterRequirements that differ only in scene-specific state (position,
    scale) but share the same semantic identity should resolve to ONE character.

    The key is based on:
        - role/archetype (from character_id semantic tokens)
        - clothing (required_clothing)
        - historical context (from environment)
        - continuity constraints

    NOT based on: required_pose, required_expression, screen_position,
                   required_scale, orientation.
    """
    # Extract semantic role from character_id (e.g. hunter_01 → hunter)
    parts = req.character_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        role_token = parts[0]
    else:
        role_token = req.character_id

    # Environment historical context
    hist_ctx = ""
    if beat.environment and beat.environment.environment_id:
        env_map = {
            "ice_age": "ice_age_prehistoric",
            "cave": "prehistoric_cave",
            "mammoth": "prehistoric",
            "stone": "stone_age",
        }
        for k, v in env_map.items():
            if k in beat.environment.environment_id.lower():
                hist_ctx = v
                break

    key_parts = [
        role_token.lower(),
        req.required_clothing.lower() if req.required_clothing else "default",
        hist_ctx,
    ]
    key_str = "|".join(key_parts)
    return hashlib.sha256(key_str.encode()).hexdigest()[:24]


# ============================================================================
# Pose Mapper — Storyboard action → renderer pose
# ============================================================================

def map_action_to_pose(action: str) -> str:
    """Map a storyboard action string to one of the 8 valid renderer poses."""
    action_lower = action.lower()
    mapping = {
        "walk": "walk",
        "running": "run",
        "run": "run",
        "standing": "stand",
        "stand": "stand",
        "sit": "sit",
        "kneel": "sit",
        "lie": "sit",
        "crouch": "sit",
        "hold": "stand",
        "carry": "stand",
        "reach": "point",
        "point": "point",
        "throw": "point",
        "climb": "walk",
        "fight": "walk",
        "sleep": "hide",
        "warm": "think",
        "eat": "stand",
        "work": "think",
        "look": "think",
        "talk": "stand",
        "think": "think",
        "celebrate": "celebrate",
        "hide": "hide",
    }
    for key, pose in mapping.items():
        if key in action_lower:
            return pose
    return "stand"


def map_expression_to_label(expression: str) -> ExpressionLabel:
    """Map a storyboard expression string to ExpressionLabel."""
    expr_lower = expression.lower()
    mapping = {
        "happy": ExpressionLabel.HAPPY,
        "sad": ExpressionLabel.SAD,
        "angry": ExpressionLabel.ANGRY,
        "fear": ExpressionLabel.AFRAID,
        "afraid": ExpressionLabel.AFRAID,
        "surprise": ExpressionLabel.SURPRISED,
        "surprised": ExpressionLabel.SURPRISED,
        "confused": ExpressionLabel.CONFUSED,
        "curious": ExpressionLabel.CURIOUS,
        "tired": ExpressionLabel.TIRED,
        "pain": ExpressionLabel.PAIN,
        "focus": ExpressionLabel.FOCUSED,
        "focused": ExpressionLabel.FOCUSED,
    }
    for key, label in mapping.items():
        if key in expr_lower:
            return label
    return ExpressionLabel.NEUTRAL


# ============================================================================
# Default Skeleton Builder
# ============================================================================

def build_default_skeleton(character_id: str) -> CharacterSkeletonDefinition:
    """Build a standard 2D joint/anchor skeleton for a human character.

    Joint hierarchy:
        root → head → (none, no children)
        root → torso → shoulder_left → elbow_left → hand_left
                             → shoulder_right → elbow_right → hand_right
        root → torso → hip_left → knee_left → foot_left
                             → hip_right → knee_right → foot_right
    """
    joints = [
        JointAnchor(joint_id="root", parent_joint=None, x=0.0, y=0.0),
        # Head is relative to root
        JointAnchor(joint_id="head", parent_joint="root", x=0.0, y=-170.0),
        # Torso is relative to root
        JointAnchor(joint_id="torso", parent_joint="root", x=0.0, y=-100.0),
        # Shoulders
        JointAnchor(joint_id="shoulder_left", parent_joint="torso", x=-20.0, y=-30.0,
                    min_rotation=-120.0, max_rotation=120.0, flip_allowed=False),
        JointAnchor(joint_id="shoulder_right", parent_joint="torso", x=20.0, y=-30.0,
                    min_rotation=-120.0, max_rotation=120.0, flip_allowed=False),
        # Elbows
        JointAnchor(joint_id="elbow_left", parent_joint="shoulder_left", x=-40.0, y=0.0,
                    min_rotation=-90.0, max_rotation=90.0, flip_allowed=False),
        JointAnchor(joint_id="elbow_right", parent_joint="shoulder_right", x=40.0, y=0.0,
                    min_rotation=-90.0, max_rotation=90.0, flip_allowed=False),
        # Hands
        JointAnchor(joint_id="hand_left", parent_joint="elbow_left", x=-30.0, y=0.0),
        JointAnchor(joint_id="hand_right", parent_joint="elbow_right", x=30.0, y=0.0),
        # Hips
        JointAnchor(joint_id="hip_left", parent_joint="torso", x=-15.0, y=0.0,
                    min_rotation=-45.0, max_rotation=45.0),
        JointAnchor(joint_id="hip_right", parent_joint="torso", x=15.0, y=0.0,
                    min_rotation=-45.0, max_rotation=45.0),
        # Knees
        JointAnchor(joint_id="knee_left", parent_joint="hip_left", x=-30.0, y=0.0,
                    min_rotation=-120.0, max_rotation=5.0),
        JointAnchor(joint_id="knee_right", parent_joint="hip_right", x=30.0, y=0.0,
                    min_rotation=-120.0, max_rotation=5.0),
        # Feet
        JointAnchor(joint_id="foot_left", parent_joint="knee_left", x=-20.0, y=0.0),
        JointAnchor(joint_id="foot_right", parent_joint="knee_right", x=20.0, y=0.0),
    ]
    return CharacterSkeletonDefinition(
        root_x=0.0,
        root_y=0.0,
        joints=joints,
        canonical_width=100.0,
        canonical_height=200.0,
    )


# ============================================================================
# Default Wardrobe Builder
# ============================================================================

def build_default_wardrobe(character_id: str, clothing_desc: str = "") -> WardrobeDefinition:
    """Build a default prehistoric/ancient wardrobe for a character.

    If clothing_desc mentions specific items (e.g. 'fur_cloak', 'barefoot'),
    those are reflected in the wardrobe items.
    """
    items = [
        ClothingItem(
            item_id=f"{character_id}_tunic",
            name="Fur Tunic",
            layer="base",
            material="animal_hide",
            color="#8B6914",
            secondary_color="#5C4A1F",
            covers=["torso"],
        ),
        ClothingItem(
            item_id=f"{character_id}_leggings",
            name="Leather Leggings",
            layer="base",
            material="leather",
            color="#6B4423",
            covers=["legs"],
        ),
    ]
    if "barefoot" in clothing_desc.lower() or "no_shoes" in clothing_desc.lower():
        pass  # No footwear items
    else:
        items.append(
            ClothingItem(
                item_id=f"{character_id}_sandals",
                name="Crude Sandals",
                layer="outer",
                material="plant_fiber",
                color="#7A5C3E",
                covers=["feet"],
            )
        )
    return WardrobeDefinition(
        wardrobe_id=f"{character_id}_default",
        character_id=character_id,
        name="Default Prehistoric Wardrobe",
        season="winter",
        historical_context="Ice Age / Stone Age",
        clothing_items=items,
        is_default=True,
    )


# ============================================================================
# Default Poses Builder — all 8 renderer poses
# ============================================================================

def build_all_poses(character_id: str) -> list[PoseDefinition]:
    """Build all 8 renderer-supported poses for a character."""
    pose_configs = [
        # pose_id, action_label, body_torso_angle
        ("stand", ActionLabel.STAND),
        ("walk", ActionLabel.WALK),
        ("run", ActionLabel.RUN),
        ("sit", ActionLabel.SIT),
        ("point", ActionLabel.POINT),
        ("think", ActionLabel.THINK),
        ("celebrate", ActionLabel.CELEBRATE),
        ("hide", ActionLabel.HIDE),
    ]
    poses = []
    for pose_id, action_label in pose_configs:
        poses.append(
            PoseDefinition(
                pose_id=f"{character_id}_{pose_id}",
                character_id=character_id,
                pose_type=action_label,
                head=HeadOrientation(tilt_deg=0.0, look_direction=Orientation.THREE_QUARTER_LEFT),
                version="1.0.0",
            )
        )
    return poses


# ============================================================================
# Default Expressions Builder
# ============================================================================

def build_all_expressions(character_id: str) -> list[ExpressionDefinition]:
    """Build all 11 canonical expressions for a character."""
    # (label, eye_shape, eyebrow_raise, eyebrow_inner, mouth_shape, corner_raise, open_amount)
    expressions = [
        (ExpressionLabel.NEUTRAL, "neutral", 0.0, 0.0, "neutral", 0.0, 0.0),
        (ExpressionLabel.HAPPY, "wide", 0.0, 0.0, "smile", 0.5, 0.0),
        (ExpressionLabel.SAD, "squint", 0.0, 0.0, "frown", -0.5, 0.0),
        (ExpressionLabel.ANGRY, "squint", 0.3, 0.3, "frown", -0.3, 0.0),
        (ExpressionLabel.AFRAID, "wide", 0.5, 0.5, "o_shape", 0.0, 0.3),
        (ExpressionLabel.SURPRISED, "wide", 0.5, 0.5, "o_shape", 0.0, 0.5),
        (ExpressionLabel.CONFUSED, "squint", 0.0, 0.3, "neutral", 0.0, 0.0),
        (ExpressionLabel.CURIOUS, "wide", 0.2, 0.0, "neutral", 0.0, 0.0),
        (ExpressionLabel.TIRED, "closed", -0.2, -0.2, "neutral", 0.0, 0.0),
        (ExpressionLabel.PAIN, "squint", 0.3, 0.3, "frown", -0.3, 0.1),
        (ExpressionLabel.FOCUSED, "squint", 0.1, 0.1, "neutral", 0.0, 0.0),
    ]
    return [
        ExpressionDefinition(
            expression_id=f"{character_id}_{label.value}",
            character_id=character_id,
            label=label,
            eyes=EyeState(shape=eye_shape, eyebrow_raise=eyebrow_raise,
                          eyebrow_inner_raise=eyebrow_inner, pupil_size=0.5),
            mouth=MouthState(shape=mouth_shape, corner_raise=corner_raise, open_amount=open_amt),
            version="1.0.0",
        )
        for label, eye_shape, eyebrow_raise, eyebrow_inner, mouth_shape, corner_raise, open_amt
        in expressions
    ]


# ============================================================================
# Color Palette Derivation
# ============================================================================

_PREHISTORIC_PALETTES = [
    {"primary": "#8B6914", "secondary": "#5C4A1F", "skin": "#8D5524"},
    {"primary": "#6B8E23", "secondary": "#3D5315", "skin": "#A0522D"},
    {"primary": "#CD853F", "secondary": "#8B4513", "skin": "#C68642"},
    {"primary": "#556B2F", "secondary": "#2F3A1F", "skin": "#9E6B3D"},
    {"primary": "#8FBC8F", "secondary": "#4F7F4F", "skin": "#B8860B"},
]


def derive_palette(character_id: str, role: str) -> dict:
    """Derive a deterministic color palette from character identity."""
    idx = int(hashlib.md5(character_id.encode()).hexdigest(), 16) % len(_PREHISTORIC_PALETTES)
    palette = _PREHISTORIC_PALETTES[idx].copy()
    if "hunter" in character_id.lower():
        palette["primary"] = "#556B2F"
        palette["secondary"] = "#2F3A1F"
    elif "narrator" in character_id.lower():
        palette["primary"] = "#4169E1"
        palette["secondary"] = "#1E3A8A"
    elif "child" in character_id.lower():
        palette["primary"] = "#DEB887"
        palette["secondary"] = "#8B7355"
    return palette


# ============================================================================
# Character Definition Builder
# ============================================================================

def build_character_definition(
    req: CharacterRequirement,
    beat: VisualBeat,
    identity_hash: str,
) -> CharacterDefinition:
    """Build a canonical CharacterDefinition from a CharacterRequirement.

    This is deterministic: same identity_hash + req → same CharacterDefinition.
    """
    from app.schemas.character import (
        AgeClass, BodyProfile, CharacterCategory, CharacterColorPalette,
        CharacterContinuityProfile, FaceProfile, HairProfile, HeadProfile,
        SilhouetteComplexity, SkinProfile, StyleProfile,
    )

    palette = derive_palette(req.character_id, req.character_id)

    skin_profile = SkinProfile(
        tone="medium",
        color=palette["skin"],
    )

    hair_profile = HairProfile(
        style="short",
        color="#1A0A00" if "hunter" in req.character_id.lower() else "#2A1A0A",
        has_accessories=False,
    )

    return CharacterDefinition(
        character_id=req.character_id,
        name=req.character_id.replace("_", " ").title(),
        role=req.character_id.rsplit("_", 1)[0] if "_" in req.character_id else req.character_id,
        category=CharacterCategory.HUMAN_GENERIC,
        age_class=AgeClass.ADULT,
        scope=CharacterScope.PROJECT,
        color=palette["primary"],
        default_pose=map_action_to_pose(req.required_action),
        default_expression=map_expression_to_label(req.required_expression),
        silhouette_complexity=SilhouetteComplexity.SIMPLE,
        style_profile=StyleProfile(),
        body_profile=BodyProfile(shoulder_width_ratio=0.30),
        head_profile=HeadProfile(),
        face_profile=FaceProfile(),
        hair_profile=hair_profile,
        skin_profile=skin_profile,
        color_palette=CharacterColorPalette(
            primary=palette["primary"],
            secondary=palette["secondary"],
            outline="#222222",
            skin_tone=palette["skin"],
            clothing_primary=palette["secondary"],
            clothing_secondary=palette["primary"],
        ),
        skeleton=build_default_skeleton(req.character_id),
        continuity_profile=CharacterContinuityProfile(),
        version="1.0.0",
        input_hash=identity_hash,
        style_version="1.0.0",
        status=CharacterStatus.DRAFT,
        description=f"Storyboard-generated character for {req.character_id}",
    )


# ============================================================================
# Quality Scorer
# ============================================================================

def score_character(definition: CharacterDefinition) -> CharacterQualityScore:
    """Compute the 11-dimension quality score for a CharacterDefinition.

    All dimensions are deterministic based on the definition fields.
    No random scores — every score has a reason.
    """
    from app.schemas.character import (
        CharacterColorPalette, CharacterContinuityProfile,
        SilhouetteComplexity,
    )

    # Dimension 1: identity_consistency
    id_score = 1.0
    if not definition.character_id or not definition.name:
        id_score -= 0.5
    if definition.role and definition.role in definition.name.lower():
        id_score = 1.0
    elif not definition.role:
        id_score -= 0.3

    # Dimension 2: proportion_consistency
    prop_score = 1.0
    if definition.style_profile.body_ratio < 0.1 or definition.style_profile.body_ratio > 0.6:
        prop_score -= 0.3
    if definition.head_profile.size_ratio < 0.1 or definition.head_profile.size_ratio > 0.6:
        prop_score -= 0.3

    # Dimension 3: silhouette_quality
    sil_score = 1.0
    if definition.silhouette_complexity == SilhouetteComplexity.MINIMAL:
        sil_score = 0.8

    # Dimension 4: style_consistency
    style_score = 1.0
    if definition.style_profile.line_weight < 0.5 or definition.style_profile.line_weight > 8.0:
        style_score -= 0.2

    # Dimension 5: wardrobe_consistency
    ward_score = 1.0
    # No wardrobe = warning (production would need one)
    if not definition.color_palette.clothing_primary:
        ward_score -= 0.3

    # Dimension 6: pose_coverage (all 8 renderer poses are pre-built)
    pose_score = 1.0  # We always generate all 8 poses

    # Dimension 7: expression_coverage (all 11 expressions are pre-built)
    expr_score = 1.0  # We always generate all 11 expressions

    # Dimension 8: component_completeness
    comp_score = 1.0
    if not definition.skeleton or len(definition.skeleton.joints) < 4:
        comp_score -= 0.5
    if not definition.skin_profile.color:
        comp_score -= 0.2

    # Dimension 9: animation_readiness
    anim_score = 1.0
    if len(definition.skeleton.joints) < 10:
        anim_score -= 0.3

    # Dimension 10: asset_format_quality
    asset_score = 1.0  # SVG preferred (checked at asset generation time)

    # Dimension 11: continuity_readiness
    cont_score = 1.0
    if definition.continuity_profile.identity_locked:
        cont_score = 1.0
    else:
        cont_score -= 0.3

    scores = {
        "identity_consistency": round(min(1.0, max(0.0, id_score)), 3),
        "proportion_consistency": round(min(1.0, max(0.0, prop_score)), 3),
        "silhouette_quality": round(min(1.0, max(0.0, sil_score)), 3),
        "style_consistency": round(min(1.0, max(0.0, style_score)), 3),
        "wardrobe_consistency": round(min(1.0, max(0.0, ward_score)), 3),
        "pose_coverage": round(min(1.0, max(0.0, pose_score)), 3),
        "expression_coverage": round(min(1.0, max(0.0, expr_score)), 3),
        "component_completeness": round(min(1.0, max(0.0, comp_score)), 3),
        "animation_readiness": round(min(1.0, max(0.0, anim_score)), 3),
        "asset_format_quality": round(min(1.0, max(0.0, asset_score)), 3),
        "continuity_readiness": round(min(1.0, max(0.0, cont_score)), 3),
    }

    warnings = []
    failures = []
    recommendations = []

    if sil_score < 0.8:
        warnings.append(f"Low silhouette complexity for {definition.character_id}")
    if ward_score < 0.8:
        warnings.append(f"No wardrobe defined for {definition.character_id}")
    if comp_score < 0.8:
        warnings.append(f"Incomplete component skeleton for {definition.character_id}")

    return CharacterQualityScore(
        identity_consistency=scores["identity_consistency"],
        proportion_consistency=scores["proportion_consistency"],
        silhouette_quality=scores["silhouette_quality"],
        style_consistency=scores["style_consistency"],
        wardrobe_consistency=scores["wardrobe_consistency"],
        pose_coverage=scores["pose_coverage"],
        expression_coverage=scores["expression_coverage"],
        component_completeness=scores["component_completeness"],
        animation_readiness=scores["animation_readiness"],
        asset_format_quality=scores["asset_format_quality"],
        continuity_readiness=scores["continuity_readiness"],
        dimension_scores=scores,
        warnings=warnings,
        failures=failures,
        recommendations=recommendations,
    )


# ============================================================================
# Character Instance Builder
# ============================================================================

def build_character_instance(
    req: CharacterRequirement,
    scene_id: str,
    pose_override: str | None = None,
) -> CharacterInstance:
    """Build a scene-specific CharacterInstance from a CharacterRequirement."""
    pose = pose_override or map_action_to_pose(req.required_action)

    # Parse position from screen_position
    x, y = 0.5, 0.5  # default center
    pos = req.screen_position.lower()
    if "left" in pos and "right" not in pos:
        x = 0.3
    elif "right" in pos and "left" not in pos:
        x = 0.7
    if "top" in pos or "upper" in pos:
        y = 0.3
    elif "bottom" in pos or "lower" in pos:
        y = 0.7

    return CharacterInstance(
        character_id=req.character_id,
        scene_id=scene_id,
        pose=pose,
        expression=map_expression_to_label(req.required_expression),
        orientation=Orientation.THREE_QUARTER_LEFT,
        x=x,
        y=y,
        scale=req.required_scale,
        rotation_deg=0.0,
        enter_anim="fade_in",
        exit_anim="none",
    )


# ============================================================================
# Registry Builder
# ============================================================================

def build_registry_entry(
    definition: CharacterDefinition,
    poses: list[PoseDefinition],
    expressions: list[ExpressionDefinition],
    wardrobe: WardrobeDefinition | None,
    quality: CharacterQualityScore,
    package_dir: str = "",
) -> CharacterRegistryEntry:
    """Build a registry entry from a character definition and its assets."""
    return CharacterRegistryEntry(
        character_id=definition.character_id,
        name=definition.name,
        role=definition.role,
        category=definition.category,
        scope=definition.scope,
        status=definition.status,
        version=definition.version,
        color=definition.color,
        package_dir=package_dir,
        active_wardrobe_id=wardrobe.wardrobe_id if wardrobe else "",
        available_wardrobes=[wardrobe.wardrobe_id] if wardrobe else [],
        available_poses=[p.pose_id for p in poses],
        available_expressions=[e.expression_id for e in expressions],
        pose_coverage=quality.pose_coverage,
        expression_coverage=quality.expression_coverage,
        quality_score=quality.overall_score,
        warnings=quality.warnings,
        updated_at=datetime.utcnow(),
    )


# ============================================================================
# Main Character System Engine
# ============================================================================

class CharacterSystemEngine:
    """Transforms StoryboardPackage CharacterRequirements into CharacterSystemPackage.

    The engine:
        1. Extracts all CharacterRequirements from storyboard beats
        2. Deduplicates by semantic identity key
        3. Resolves each requirement to a CharacterDefinition (new or reuse)
        4. Generates wardrobe, poses, expressions for each character
        5. Produces scene-specific CharacterInstances
        6. Builds a CharacterRegistry
        7. Computes quality scores
        8. Persists CharacterSystemPackage

    Usage:
        engine = CharacterSystemEngine(job_id, cache)
        pkg = engine.run(storyboard_pkg, story_pkg_id)
    """

    def __init__(
        self,
        job_id: str,
        cache: CharacterCache | None = None,
    ) -> None:
        self.job_id = job_id
        self.cache = cache
        self._registry: CharacterRegistry | None = None
        self._identity_map: dict[str, str] = {}  # identity_key → character_id
        self._seen_characters: dict[str, CharacterDefinition] = {}

    def run(
        self,
        storyboard_pkg: StoryboardPackage,
        story_package_id: str = "",
    ) -> CharacterSystemPackage:
        """Main entry point: transform StoryboardPackage into CharacterSystemPackage."""
        log.info("[character] Starting character system for job %s", self.job_id)

        # Step 1: Extract all CharacterRequirements from beats
        all_reqs = self._extract_requirements(storyboard_pkg)
        log.info("[character] Found %d character requirements across %d beats",
                 len(all_reqs), len(storyboard_pkg.visual_beats))

        # Step 2: Deduplicate by semantic identity
        unique_reqs = self._deduplicate(all_reqs)
        log.info("[character] Deduplicated to %d unique characters", len(unique_reqs))

        # Step 3: Resolve each requirement
        characters: list[CharacterDefinition] = []
        poses: list[PoseDefinition] = []
        expressions: list[ExpressionDefinition] = []
        wardrobes: list[WardrobeDefinition] = []
        resolutions: list[CharacterResolution] = []
        quality_scores: dict[str, CharacterQualityScore] = {}

        for req, beat in unique_reqs:
            identity_hash = character_identity_key(req, beat)

            # Check for reuse
            if identity_hash in self._identity_map:
                existing_id = self._identity_map[identity_hash]
                log.info("[character] Reusing existing character %s for %s",
                         existing_id, req.character_id)
                existing = self._seen_characters[existing_id]
                resolution = CharacterResolution(
                    character_id=existing_id,
                    source="reuse",
                    character_definition=existing,
                )
            else:
                # Build new character — use the source beat directly
                definition = build_character_definition(req, beat, identity_hash)
                definition_poses = build_all_poses(definition.character_id)
                definition_expressions = build_all_expressions(definition.character_id)
                definition_wardrobe = build_default_wardrobe(
                    definition.character_id, req.required_clothing
                )
                quality = score_character(definition)

                self._identity_map[identity_hash] = definition.character_id
                self._seen_characters[definition.character_id] = definition

                characters.append(definition)
                poses.extend(definition_poses)
                expressions.extend(definition_expressions)
                wardrobes.append(definition_wardrobe)

                quality_scores[definition.character_id] = quality

                resolution = CharacterResolution(
                    character_id=definition.character_id,
                    source="new",
                    character_definition=definition,
                    wardrobe=definition_wardrobe,
                    poses=definition_poses,
                    expressions=definition_expressions,
                    quality_score=quality,
                )

            resolutions.append(resolution)

        # Step 4: Build scene instances
        instances = self._build_instances(storyboard_pkg)

        # Step 5: Build asset packages (informational)
        asset_packages = self._build_asset_packages(characters, wardrobes, quality_scores)

        # Step 6: Build registry
        registry_entries = []
        for char in characters:
            char_poses = [p for p in poses if p.character_id == char.character_id]
            char_expressions = [e for e in expressions if e.character_id == char.character_id]
            char_wardrobe = next((w for w in wardrobes if w.character_id == char.character_id), None)
            char_quality = quality_scores.get(char.character_id)
            entry = build_registry_entry(
                char, char_poses, char_expressions, char_wardrobe,
                char_quality or CharacterQualityScore(),
                package_dir=f"characters/{char.character_id}/",
            )
            registry_entries.append(entry)

        self._registry = CharacterRegistry(
            project_id=self.job_id,
            scope=CharacterScope.PROJECT,
            characters=registry_entries,
            updated_at=datetime.utcnow(),
        )

        # Step 7: Build final package
        pkg = CharacterSystemPackage(
            job_id=self.job_id,
            project_id=self.job_id,
            characters=characters,
            instances=instances,
            wardrobes=wardrobes,
            poses=poses,
            expressions=expressions,
            asset_packages=asset_packages,
            resolutions=resolutions,
            registry=self._registry,
            character_quality_scores=quality_scores,
            status=CharacterStatus.ACTIVE,
        )

        # Cache the result
        if self.cache:
            cache_key = self._compute_package_hash(storyboard_pkg)
            self.cache.set_character_package(cache_key, pkg.to_dict())

        log.info("[character] Character system complete: %d characters, %d instances, quality=%.3f",
                 len(characters), len(instances), pkg.overall_quality_score)
        return pkg

    def _extract_requirements(
        self, pkg: StoryboardPackage
    ) -> list[tuple[CharacterRequirement, VisualBeat]]:
        """Extract all CharacterRequirement instances with their parent beat."""
        result: list[tuple[CharacterRequirement, VisualBeat]] = []
        for beat in pkg.visual_beats:
            for req in beat.characters:
                result.append((req, beat))
        return result

    def _deduplicate(
        self, all_reqs: list[tuple[CharacterRequirement, VisualBeat]]
    ) -> list[tuple[CharacterRequirement, VisualBeat]]:
        """Deduplicate requirements by semantic identity key.

        Returns one representative (req, beat) pair per unique identity.
        """
        seen: dict[str, tuple[CharacterRequirement, VisualBeat]] = {}
        for req, beat in all_reqs:
            key = character_identity_key(req, beat)
            if key not in seen:
                seen[key] = (req, beat)
        return list(seen.values())

    def _find_beat_for_req(
        self, req: CharacterRequirement, pkg: StoryboardPackage
    ) -> VisualBeat:
        """Find the beat that contains this requirement by character_id."""
        for beat in pkg.visual_beats:
            for char in beat.characters:
                if char.character_id == req.character_id:
                    return beat
        # Fallback to first beat
        return pkg.visual_beats[0]

    def _build_instances(self, pkg: StoryboardPackage) -> list[CharacterInstance]:
        """Build scene-specific CharacterInstances for all beats."""
        instances = []
        for beat in pkg.visual_beats:
            scene_id = (
                beat.scene_definition_candidate.scene_id
                if beat.scene_definition_candidate
                else f"scene_{beat.order + 1:03d}"
            )
            for req in beat.characters:
                pose_override = map_action_to_pose(req.required_action)
                instance = build_character_instance(req, scene_id, pose_override)
                instances.append(instance)
        return instances

    def _build_asset_packages(
        self,
        characters: list[CharacterDefinition],
        wardrobes: list[WardrobeDefinition],
        quality_scores: dict[str, CharacterQualityScore],
    ) -> list[CharacterAssetPackage]:
        """Build CharacterAssetPackage metadata for each character."""
        packages = []
        for char in characters:
            quality = quality_scores.get(char.character_id)
            wardrobe = next((w for w in wardrobes if w.character_id == char.character_id), None)
            packages.append(
                CharacterAssetPackage(
                    character_id=char.character_id,
                    character_version=char.version,
                    quality_score=quality.overall_score if quality else None,
                    design_approved=char.status == CharacterStatus.APPROVED,
                )
            )
        return packages

    def _compute_package_hash(self, pkg: StoryboardPackage) -> str:
        """Compute a deterministic hash for caching."""
        import json
        # Hash based on character requirements
        req_data = []
        for beat in pkg.visual_beats:
            for req in beat.characters:
                req_data.append(req.model_dump())
        content = json.dumps(req_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_scene_definition_characters(
        self, char_pkg: CharacterSystemPackage
    ) -> list[SceneDefCharacter]:
        """Convert CharacterSystemPackage characters to SceneDefinition Character list."""
        return [
            SceneDefCharacter(
                id=char.character_id,
                name=char.name,
                color=char.color,
                default_pose=char.default_pose,
                description=char.description,
            )
            for char in char_pkg.characters
        ]

    def to_scene_definition_actors(
        self, char_pkg: CharacterSystemPackage
    ) -> dict[str, list[dict]]:
        """Convert CharacterInstances to per-scene actor lists for SceneDefinition.

        Returns: {scene_id: [actor_dict, ...]}
        """
        from app.schemas.scene_definition import Actor, AnimName, Pose

        result: dict[str, list[dict]] = {}
        for instance in char_pkg.instances:
            # Map our pose string to renderer Pose enum
            try:
                renderer_pose = Pose(instance.pose)
            except ValueError:
                renderer_pose = Pose.STAND

            # Map our animation strings
            try:
                enter = AnimName(instance.enter_anim)
            except ValueError:
                enter = AnimName.FADE_IN
            try:
                exit_anim = AnimName(instance.exit_anim)
            except ValueError:
                exit_anim = AnimName.NONE

            actor_dict = Actor(
                character_id=instance.character_id,
                x=instance.x,
                y=instance.y,
                scale=instance.scale,
                rotation_deg=instance.rotation_deg,
                pose=renderer_pose,
                enter_anim=enter,
                exit_anim=exit_anim,
            ).model_dump()

            scene_id = instance.scene_id
            if scene_id not in result:
                result[scene_id] = []
            result[scene_id].append(actor_dict)
        return result

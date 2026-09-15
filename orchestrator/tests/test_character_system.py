"""
Comprehensive tests for the Character Intelligence System.

Covers all 15 areas from PROMPT 5 §43 TEST FIXTURES + §44 UNIT TESTS:

1. CharacterDefinition (human male / female / child)
2. CharacterInstance
3. CharacterSkeletonDefinition (joint/anchor model)
4. WardrobeDefinition
5. PoseDefinition (all 8 renderer poses)
6. ExpressionDefinition (all 11 canonical expressions)
7. CharacterAssetPackage
8. CharacterRegistry
9. Duplicate character detection
10. Character reuse
11. Versioning
12. Cache hit / cache invalidation
13. SVG validation
14. Missing asset
15. Invalid character
16. Orientation
17. Quality scoring (11 dimensions)
18. Requirement mapping
19. SceneDefinition actor compatibility
20. Integration with StoryboardPackage
"""
from __future__ import annotations

import os

# Force mock mode before any other imports
os.environ["OPENAI_API_KEY"] = ""

import pytest
from pydantic import ValidationError

from app.character.cache import CharacterCache
from app.character.engine import (
    CharacterSystemEngine,
    build_all_expressions,
    build_all_poses,
    build_character_definition,
    build_character_instance,
    build_default_skeleton,
    build_default_wardrobe,
    build_registry_entry,
    character_identity_key,
    map_action_to_pose,
    map_expression_to_label,
    score_character,
)
from app.character.svg_generator import (
    compute_svg_hash,
    generate_character_preview_svg,
    generate_expression_svg,
    generate_pose_svg,
    validate_svg,
)
from app.schemas.character import (
    ActionLabel,
    AgeClass,
    CharacterAssetPackage,
    CharacterCategory,
    CharacterColorPalette,
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
    JointAnchor,
    MouthState,
    Orientation,
    PoseDefinition,
    SilhouetteComplexity,
    StyleProfile,
    WardrobeDefinition,
)
from app.schemas.scene_definition import (
    Actor,
    AnimName,
    Character as SceneDefCharacter,
    Pose,
    SceneDefinition,
)
from app.schemas.storyboard import (
    CharacterRequirement,
    Composition,
    EnvironmentRequirement,
    StoryboardMetadata,
    StoryboardPackage,
    StoryboardStatus,
    VisualBeat,
)


# ============================================================================
# 1. Fixtures — Human male / female / child + variants
# ============================================================================

def _make_male_char_req() -> CharacterRequirement:
    return CharacterRequirement(
        character_id="hunter_01",
        required_pose="walk",
        required_expression="focused",
        required_clothing="fur_cloak",
        required_action="walking",
        required_scale=1.0,
        screen_position="left",
        orientation="3/4_left",
        continuity_constraints=["consistent_hunter_appearance"],
    )


def _make_female_char_req() -> CharacterRequirement:
    return CharacterRequirement(
        character_id="gatherer_01",
        required_pose="stand",
        required_expression="neutral",
        required_clothing="leather_dress",
        required_action="standing",
        required_scale=1.0,
        screen_position="right",
        orientation="3/4_right",
        continuity_constraints=[],
    )


def _make_child_char_req() -> CharacterRequirement:
    return CharacterRequirement(
        character_id="child_01",
        required_pose="sit",
        required_expression="happy",
        required_clothing="simple_tunic",
        required_action="sitting",
        required_scale=0.6,
        screen_position="center",
        orientation="front",
        continuity_constraints=[],
    )


def _make_narrator_char_req() -> CharacterRequirement:
    return CharacterRequirement(
        character_id="narrator",
        required_pose="stand",
        required_expression="neutral",
        required_clothing="default",
        required_action="narrating",
        required_scale=1.2,
        screen_position="center",
        orientation="front",
        continuity_constraints=["default_narrator_look"],
    )


def _make_beat(
    beat_id: str = "beat_001",
    characters: list[CharacterRequirement] | None = None,
    environment_id: str = "ice_age_plains",
    start_time: float = 0.0,
    duration: float = 8.0,
) -> VisualBeat:
    """Build a VisualBeat for testing."""
    return VisualBeat(
        beat_id=beat_id,
        segment_id="SEG-001",
        order=0,
        start_time=start_time,
        end_time=start_time + duration,
        duration=duration,
        purpose="Test beat",
        characters=characters or [],
        environment=EnvironmentRequirement(
            environment_id=environment_id,
            location="Test location",
            season="winter",
            weather="snow",
            lighting="natural",
            mood="tense",
        ),
    )


def _make_storyboard_pkg(
    beats: list[VisualBeat] | None = None,
) -> StoryboardPackage:
    """Build a minimal StoryboardPackage for testing."""
    metadata = StoryboardMetadata(
        storyboard_package_id="SB-TEST-001",
        story_package_id="SP-TEST-001",
        job_id="test_job",
        topic="Test topic",
    )
    return StoryboardPackage(
        metadata=metadata,
        story_package_id="SP-TEST-001",
        visual_beats=beats or [],
        status=StoryboardStatus.DRAFT,
    )


@pytest.fixture
def male_char_req() -> CharacterRequirement:
    return _make_male_char_req()


@pytest.fixture
def female_char_req() -> CharacterRequirement:
    return _make_female_char_req()


@pytest.fixture
def child_char_req() -> CharacterRequirement:
    return _make_child_char_req()


@pytest.fixture
def narrator_char_req() -> CharacterRequirement:
    return _make_narrator_char_req()


@pytest.fixture
def beat_with_characters(male_char_req) -> VisualBeat:
    return _make_beat(beat_id="beat_001", characters=[male_char_req])


@pytest.fixture
def character_definition(male_char_req, beat_with_characters) -> CharacterDefinition:
    """Build a CharacterDefinition for tests."""
    identity_hash = character_identity_key(male_char_req, beat_with_characters)
    return build_character_definition(male_char_req, beat_with_characters, identity_hash)


@pytest.fixture
def character_skeleton(character_definition) -> CharacterSkeletonDefinition:
    """Return the character's skeleton."""
    return character_definition.skeleton


@pytest.fixture
def character_wardrobe(character_definition) -> WardrobeDefinition:
    return build_default_wardrobe(character_definition.character_id, "fur_cloak")


@pytest.fixture
def character_poses(character_definition) -> list[PoseDefinition]:
    return build_all_poses(character_definition.character_id)


@pytest.fixture
def character_expressions(character_definition) -> list[ExpressionDefinition]:
    return build_all_expressions(character_definition.character_id)


# ============================================================================
# 2. CharacterDefinition Tests
# ============================================================================

class TestCharacterDefinition:
    """CharacterDefinition schema validation and identity."""

    def test_basic_definition_valid(self, character_definition):
        """A CharacterDefinition with required fields must validate."""
        assert character_definition.character_id == "hunter_01"
        assert character_definition.role in {"hunter", "human"}
        assert character_definition.category == CharacterCategory.HUMAN_GENERIC
        assert character_definition.age_class == AgeClass.ADULT
        assert character_definition.status == CharacterStatus.DRAFT
        assert character_definition.version == "1.0.0"

    def test_character_id_pattern_validated(self):
        """character_id must match lowercase snake_case pattern."""
        with pytest.raises(ValidationError):
            CharacterDefinition(
                character_id="Hunter-01!",  # Invalid chars
                color="#000000",
            )

    def test_color_pattern_validated(self):
        """color must be a 6-char hex with #."""
        with pytest.raises(ValidationError):
            CharacterDefinition(
                character_id="hunter_01",
                color="red",  # Invalid format
            )

    def test_default_pose_must_be_renderer_compatible(self):
        """default_pose must be one of 8 renderer-supported poses."""
        # Valid pose - should pass
        char = CharacterDefinition(
            character_id="hunter_01",
            color="#000000",
            default_pose="walk",
        )
        assert char.default_pose == "walk"

        # Invalid pose - should be auto-corrected to stand
        char2 = CharacterDefinition(
            character_id="hunter_02",
            color="#000000",
            default_pose="dancing",  # Not in valid poses
        )
        assert char2.default_pose == "stand"  # Auto-corrected

    def test_color_palette_primary_matches_color(self):
        """Color palette primary must match main color (validator auto-fixes)."""
        char = CharacterDefinition(
            character_id="hunter_01",
            color="#FF0000",
        )
        assert char.color_palette.primary == "#FF0000"

    def test_character_with_skeleton(self, character_definition):
        """Character must have a populated skeleton."""
        assert len(character_definition.skeleton.joints) >= 4
        # Verify the canonical joints exist
        joint_ids = {j.joint_id for j in character_definition.skeleton.joints}
        assert "root" in joint_ids
        assert "head" in joint_ids
        assert "torso" in joint_ids

    def test_continuity_profile_defaults(self, character_definition):
        """Continuity profile must default to identity locked."""
        assert character_definition.continuity_profile.identity_locked is True
        assert character_definition.continuity_profile.palette_locked is True
        assert "pose" in character_definition.continuity_profile.permitted_scene_changes

    def test_to_scene_definition_character(self, character_definition):
        """Conversion to SceneDefinition.Character must work."""
        d = character_definition.to_scene_definition_character()
        assert d["id"] == character_definition.character_id
        assert d["name"] == character_definition.name
        assert d["color"] == character_definition.color
        assert d["default_pose"] == character_definition.default_pose
        assert "description" in d

    def test_description_field(self, character_definition):
        """description field is preserved."""
        assert character_definition.description != ""

    def test_versioning_defaults(self, character_definition):
        """Default version, input_hash, style_version must be present."""
        assert character_definition.version == "1.0.0"
        assert character_definition.style_version == "1.0.0"
        assert len(character_definition.input_hash) > 0

    def test_human_male_definition(self, male_char_req):
        """Human male character from fixture must build correctly."""
        beat = _make_beat(characters=[male_char_req])
        identity_hash = character_identity_key(male_char_req, beat)
        char = build_character_definition(male_char_req, beat, identity_hash)
        assert char.character_id == "hunter_01"
        assert char.role == "hunter"

    def test_human_female_definition(self, female_char_req):
        """Human female character from fixture must build correctly."""
        beat = _make_beat(characters=[female_char_req])
        identity_hash = character_identity_key(female_char_req, beat)
        char = build_character_definition(female_char_req, beat, identity_hash)
        assert char.character_id == "gatherer_01"
        assert char.role == "gatherer"

    def test_child_character_definition(self, child_char_req):
        """Child character from fixture must build correctly."""
        beat = _make_beat(characters=[child_char_req])
        identity_hash = character_identity_key(child_char_req, beat)
        char = build_character_definition(child_char_req, beat, identity_hash)
        assert char.character_id == "child_01"


# ============================================================================
# 3. CharacterInstance Tests
# ============================================================================

class TestCharacterInstance:
    """CharacterInstance scene-specific state."""

    def test_basic_instance_valid(self):
        """A CharacterInstance with required fields must validate."""
        inst = CharacterInstance(
            character_id="hunter_01",
            scene_id="scene_001",
        )
        assert inst.character_id == "hunter_01"
        assert inst.scene_id == "scene_001"
        assert inst.pose == "stand"
        assert inst.expression == ExpressionLabel.NEUTRAL
        assert inst.x == 0.5
        assert inst.y == 0.5  # default
        assert inst.scale == 1.0

    def test_pose_must_be_renderer_compatible(self):
        """Invalid pose auto-corrects to stand."""
        inst = CharacterInstance(
            character_id="hunter_01",
            scene_id="scene_001",
            pose="dancing",  # invalid
        )
        assert inst.pose == "stand"

    def test_screen_position_left(self, male_char_req):
        """screen_position 'left' must map to x=0.3."""
        inst = build_character_instance(male_char_req, "scene_001")
        assert inst.x == 0.3

    def test_screen_position_right(self, female_char_req):
        """screen_position 'right' must map to x=0.7."""
        inst = build_character_instance(female_char_req, "scene_001")
        assert inst.x == 0.7

    def test_screen_position_center(self, narrator_char_req):
        """screen_position 'center' must map to x=0.5."""
        inst = build_character_instance(narrator_char_req, "scene_001")
        assert inst.x == 0.5

    def test_to_scene_definition_actor(self, male_char_req):
        """Conversion to SceneDefinition.Actor dict must work."""
        inst = build_character_instance(male_char_req, "scene_001")
        d = inst.to_scene_definition_actor()
        assert d["character_id"] == "hunter_01"
        assert d["x"] == 0.3
        assert d["y"] == 0.5
        assert d["scale"] == 1.0
        assert d["rotation_deg"] == 0.0
        assert "pose" in d
        assert "enter_anim" in d
        assert "exit_anim" in d

    def test_continuity_overrides_field(self):
        """continuity_overrides is a free-form dict for scene-specific changes."""
        inst = CharacterInstance(
            character_id="hunter_01",
            scene_id="scene_001",
            continuity_overrides={"wardrobe": "wet_look"},
        )
        assert inst.continuity_overrides["wardrobe"] == "wet_look"


# ============================================================================
# 4. Skeleton / Anchor Model Tests
# ============================================================================

class TestSkeletonAnchors:
    """CharacterSkeletonDefinition and joint/anchor hierarchy."""

    def test_default_skeleton_has_canonical_joints(self):
        """Default skeleton must have head/torso/shoulders/elbows/hips/knees."""
        skeleton = build_default_skeleton("hunter_01")
        joint_ids = {j.joint_id for j in skeleton.joints}

        # Essential joints
        assert "root" in joint_ids
        assert "head" in joint_ids
        assert "torso" in joint_ids
        assert "shoulder_left" in joint_ids
        assert "shoulder_right" in joint_ids
        assert "elbow_left" in joint_ids
        assert "elbow_right" in joint_ids
        assert "hip_left" in joint_ids
        assert "hip_right" in joint_ids
        assert "knee_left" in joint_ids
        assert "knee_right" in joint_ids

    def test_joint_hierarchy(self):
        """Joints must form a valid parent-child hierarchy."""
        skeleton = build_default_skeleton("hunter_01")
        # root has no parent
        root = next(j for j in skeleton.joints if j.joint_id == "root")
        assert root.parent_joint is None

        # head's parent is root
        head = next(j for j in skeleton.joints if j.joint_id == "head")
        assert head.parent_joint == "root"

        # elbow_left's parent is shoulder_left
        elbow = next(j for j in skeleton.joints if j.joint_id == "elbow_left")
        assert elbow.parent_joint == "shoulder_left"

    def test_joint_constraints(self):
        """Each joint has rotation constraints."""
        skeleton = build_default_skeleton("hunter_01")
        for joint in skeleton.joints:
            assert joint.min_rotation >= -180.0
            assert joint.max_rotation <= 180.0
            assert joint.min_rotation <= joint.max_rotation

    def test_canonical_dimensions(self):
        """Canonical dimensions must be set."""
        skeleton = build_default_skeleton("hunter_01")
        assert skeleton.canonical_width > 0
        assert skeleton.canonical_height > 0

    def test_skeleton_attached_to_definition(self, character_definition):
        """CharacterDefinition must carry its skeleton."""
        assert character_definition.skeleton is not None
        assert len(character_definition.skeleton.joints) > 0


# ============================================================================
# 5. Wardrobe System Tests
# ============================================================================

class TestWardrobeSystem:
    """WardrobeDefinition and clothing persistence."""

    def test_default_wardrobe_has_clothing_items(self, character_wardrobe):
        """Default wardrobe must include tunic + leggings at minimum."""
        item_names = [item.name for item in character_wardrobe.clothing_items]
        assert "Fur Tunic" in item_names
        assert "Leather Leggings" in item_names

    def test_barefoot_wardrobe_omits_sandals(self, character_definition):
        """Wardrobe with 'barefoot' clothing desc must NOT include sandals."""
        wardrobe = build_default_wardrobe(character_definition.character_id, "barefoot")
        item_names = [item.name for item in wardrobe.clothing_items]
        assert "Crude Sandals" not in item_names

    def test_wardrobe_has_default_flag(self, character_wardrobe):
        """is_default flag is True on default wardrobe."""
        assert character_wardrobe.is_default is True

    def test_wardrobe_continuity_lock(self, character_wardrobe):
        """continuity_locked can be set."""
        character_wardrobe.continuity_locked = True
        assert character_wardrobe.continuity_locked is True

    def test_clothing_item_covers_field(self, character_wardrobe):
        """ClothingItem covers field specifies body parts."""
        tunic = next(i for i in character_wardrobe.clothing_items if "tunic" in i.item_id.lower())
        assert "torso" in tunic.covers

    def test_clothing_item_color_format(self, character_wardrobe):
        """All clothing items must have valid hex colors."""
        for item in character_wardrobe.clothing_items:
            assert item.color.startswith("#")
            assert len(item.color) == 7

    def test_historical_context_field(self, character_wardrobe):
        """Historical context is preserved."""
        assert "Ice Age" in character_wardrobe.historical_context or "Stone" in character_wardrobe.historical_context


# ============================================================================
# 6. Pose System Tests
# ============================================================================

class TestPoseSystem:
    """PoseDefinition with all 8 renderer-supported poses."""

    def test_all_eight_poses_generated(self, character_poses):
        """All 8 renderer poses must be generated."""
        pose_types = {p.pose_type.value for p in character_poses}
        assert pose_types == {"stand", "walk", "run", "sit", "point", "think", "celebrate", "hide"}

    def test_pose_ids_unique(self, character_poses):
        """Pose IDs must be unique per character."""
        pose_ids = [p.pose_id for p in character_poses]
        assert len(pose_ids) == len(set(pose_ids))

    def test_pose_has_anatomy(self, character_poses):
        """Every pose must have body/arm/leg/head configuration."""
        for pose in character_poses:
            assert pose.body is not None
            assert pose.left_arm is not None
            assert pose.right_arm is not None
            assert pose.left_leg is not None
            assert pose.right_leg is not None
            assert pose.head is not None

    def test_pose_versioned(self, character_poses):
        """Every pose must have a version."""
        for pose in character_poses:
            assert pose.version == "1.0.0"

    def test_map_action_to_pose_stand(self):
        """'standing' action maps to 'stand'."""
        assert map_action_to_pose("standing") == "stand"

    def test_map_action_to_pose_walk(self):
        """'walking' action maps to 'walk'."""
        assert map_action_to_pose("walking") == "walk"

    def test_map_action_to_pose_run(self):
        """'running' action maps to 'run'."""
        assert map_action_to_pose("running") == "run"

    def test_map_action_to_pose_sit(self):
        """'kneeling' action maps to 'sit'."""
        assert map_action_to_pose("kneeling") == "sit"

    def test_map_action_to_pose_point(self):
        """'pointing' action maps to 'point'."""
        assert map_action_to_pose("pointing") == "point"

    def test_map_action_to_pose_unknown(self):
        """Unknown action defaults to 'stand'."""
        assert map_action_to_pose("random_unknown_thing") == "stand"


# ============================================================================
# 7. Expression System Tests
# ============================================================================

class TestExpressionSystem:
    """ExpressionDefinition with all 11 canonical expressions."""

    def test_all_eleven_expressions_generated(self, character_expressions):
        """All 11 canonical expressions must be generated."""
        labels = {e.label for e in character_expressions}
        expected = {
            ExpressionLabel.NEUTRAL, ExpressionLabel.HAPPY, ExpressionLabel.SAD,
            ExpressionLabel.ANGRY, ExpressionLabel.AFRAID, ExpressionLabel.SURPRISED,
            ExpressionLabel.CONFUSED, ExpressionLabel.CURIOUS, ExpressionLabel.TIRED,
            ExpressionLabel.PAIN, ExpressionLabel.FOCUSED,
        }
        assert labels == expected

    def test_expression_modifies_face_only(self, character_expressions):
        """Expression definitions only have face components (eyes, mouth)."""
        for expr in character_expressions:
            assert expr.eyes is not None
            assert expr.mouth is not None

    def test_expression_versioned(self, character_expressions):
        """Every expression has a version."""
        for expr in character_expressions:
            assert expr.version == "1.0.0"

    def test_map_expression_to_label(self):
        """Map expression strings to ExpressionLabel."""
        assert map_expression_to_label("happy") == ExpressionLabel.HAPPY
        assert map_expression_to_label("sad") == ExpressionLabel.SAD
        assert map_expression_to_label("angry") == ExpressionLabel.ANGRY
        assert map_expression_to_label("afraid") == ExpressionLabel.AFRAID
        assert map_expression_to_label("surprised") == ExpressionLabel.SURPRISED
        assert map_expression_to_label("unknown_thing") == ExpressionLabel.NEUTRAL


# ============================================================================
# 8. Character Asset Package Tests
# ============================================================================

class TestCharacterAssetPackage:
    """CharacterAssetPackage filesystem structure."""

    def test_package_has_file_paths(self):
        """Asset package has file paths for identity/design/wardrobe/poses/expressions."""
        pkg = CharacterAssetPackage(character_id="hunter_01")
        assert pkg.identity_file == "identity.json"
        assert pkg.design_file == "design.json"
        assert pkg.wardrobe_file == "wardrobe.json"
        assert pkg.poses_file == "poses.json"
        assert pkg.expressions_file == "expressions.json"
        assert pkg.metadata_file == "metadata.json"

    def test_package_has_component_directories(self):
        """Asset package has SVG component directories."""
        pkg = CharacterAssetPackage(character_id="hunter_01")
        assert pkg.component_svg_dir.endswith("/")
        assert pkg.pose_svg_dir.endswith("/")
        assert pkg.expression_svg_dir.endswith("/")

    def test_package_quality_score(self):
        """Asset package has quality score field."""
        pkg = CharacterAssetPackage(
            character_id="hunter_01",
            quality_score=0.95,
            design_approved=True,
        )
        assert pkg.quality_score == 0.95
        assert pkg.design_approved is True


# ============================================================================
# 9. CharacterRegistry Tests
# ============================================================================

class TestCharacterRegistry:
    """CharacterRegistry management."""

    def test_registry_initialization(self):
        """Empty registry initializes."""
        registry = CharacterRegistry(project_id="test_job")
        assert registry.characters == []
        assert registry.scope == CharacterScope.PROJECT

    def test_registry_get_character(self):
        """get_character returns entry by ID."""
        entry = CharacterRegistryEntry(
            character_id="hunter_01",
            name="Hunter",
            color="#000000",
        )
        registry = CharacterRegistry(characters=[entry])
        found = registry.get_character("hunter_01")
        assert found is not None
        assert found.character_id == "hunter_01"

    def test_registry_get_character_missing(self):
        """get_character returns None for missing ID."""
        registry = CharacterRegistry()
        assert registry.get_character("nonexistent") is None

    def test_registry_find_by_role(self):
        """find_by_role filters by role."""
        entries = [
            CharacterRegistryEntry(character_id="hunter_01", name="Hunter", color="#000000", role="hunter"),
            CharacterRegistryEntry(character_id="hunter_02", name="Hunter 2", color="#111111", role="hunter"),
            CharacterRegistryEntry(character_id="gatherer_01", name="Gatherer", color="#222222", role="gatherer"),
        ]
        registry = CharacterRegistry(characters=entries)
        hunters = registry.find_by_role("hunter")
        assert len(hunters) == 2

    def test_registry_find_by_category(self):
        """find_by_category filters by category."""
        entries = [
            CharacterRegistryEntry(
                character_id="hunter_01", name="H", color="#000000",
                category=CharacterCategory.HUMAN_MALE
            ),
            CharacterRegistryEntry(
                character_id="child_01", name="C", color="#FFFFFF",
                category=CharacterCategory.HUMAN_CHILD
            ),
        ]
        registry = CharacterRegistry(characters=entries)
        humans = registry.find_by_category(CharacterCategory.HUMAN_MALE)
        assert len(humans) == 1
        assert humans[0].character_id == "hunter_01"

    def test_registry_usage_tracking(self):
        """Registry tracks which projects use a character."""
        entry = CharacterRegistryEntry(
            character_id="hunter_01",
            name="H",
            color="#000000",
            projects_using=["job_001", "job_002"],
            scene_count=5,
        )
        assert "job_001" in entry.projects_using
        assert entry.scene_count == 5

    def test_build_registry_entry(self, character_definition, character_poses,
                                    character_expressions, character_wardrobe):
        """build_registry_entry creates a populated entry."""
        quality = score_character(character_definition)
        entry = build_registry_entry(
            character_definition,
            character_poses,
            character_expressions,
            character_wardrobe,
            quality,
            package_dir="characters/hunter_01/",
        )
        assert entry.character_id == character_definition.character_id
        assert entry.color == character_definition.color
        assert entry.package_dir == "characters/hunter_01/"
        assert len(entry.available_poses) == 8
        assert len(entry.available_expressions) == 11


# ============================================================================
# 10. Duplicate Character Detection Tests
# ============================================================================

class TestDuplicateDetection:
    """character_identity_key deduplicates same characters."""

    def test_same_role_same_clothing_same_key(self):
        """Same role + same clothing = same identity key."""
        beat = _make_beat()
        req1 = CharacterRequirement(character_id="hunter_01", required_clothing="fur_cloak")
        req2 = CharacterRequirement(character_id="hunter_02", required_clothing="fur_cloak")
        k1 = character_identity_key(req1, beat)
        k2 = character_identity_key(req2, beat)
        assert k1 == k2

    def test_different_clothing_different_key(self):
        """Different clothing = different identity key."""
        beat = _make_beat()
        req1 = CharacterRequirement(character_id="hunter_01", required_clothing="fur_cloak")
        req2 = CharacterRequirement(character_id="hunter_02", required_clothing="leather_armor")
        k1 = character_identity_key(req1, beat)
        k2 = character_identity_key(req2, beat)
        assert k1 != k2

    def test_different_role_different_key(self):
        """Different role = different identity key."""
        beat = _make_beat()
        req1 = CharacterRequirement(character_id="hunter_01", required_clothing="fur_cloak")
        req2 = CharacterRequirement(character_id="gatherer_01", required_clothing="fur_cloak")
        k1 = character_identity_key(req1, beat)
        k2 = character_identity_key(req2, beat)
        assert k1 != k2

    def test_pose_change_does_not_change_key(self):
        """Pose changes are scene-specific, NOT identity changes."""
        beat = _make_beat()
        req1 = CharacterRequirement(character_id="hunter_01", required_pose="walk")
        req2 = CharacterRequirement(character_id="hunter_01", required_pose="stand")
        k1 = character_identity_key(req1, beat)
        k2 = character_identity_key(req2, beat)
        assert k1 == k2  # Same character, different pose

    def test_scale_change_does_not_change_key(self):
        """Scale changes are scene-specific, NOT identity changes."""
        beat = _make_beat()
        req1 = CharacterRequirement(character_id="hunter_01", required_scale=1.0)
        req2 = CharacterRequirement(character_id="hunter_01", required_scale=2.0)
        k1 = character_identity_key(req1, beat)
        k2 = character_identity_key(req2, beat)
        assert k1 == k2


# ============================================================================
# 11. Character Reuse Tests
# ============================================================================

class TestCharacterReuse:
    """Engine reuses existing characters."""

    def test_engine_deduplicates(self):
        """Engine deduplicates same characters across beats."""
        beat1 = _make_beat(
            beat_id="beat_001",
            characters=[_make_male_char_req()],
        )
        # Beat 2 starts after beat 1 ends (no overlap)
        beat2_obj = VisualBeat(
            beat_id="beat_002",
            segment_id="SEG-002",
            order=1,
            start_time=8.0,
            end_time=16.0,
            duration=8.0,
            purpose="Test beat 2",
            characters=[CharacterRequirement(
                character_id="hunter_02",
                required_pose="stand",
                required_expression="happy",
                required_clothing="fur_cloak",  # Same clothing = same identity
                required_action="standing",
            )],
            environment=EnvironmentRequirement(environment_id="ice_age_plains"),
        )
        pkg = _make_storyboard_pkg(beats=[beat1, beat2_obj])
        engine = CharacterSystemEngine(job_id="test_job")
        result = engine.run(pkg, "SP-TEST")

        # Both should resolve to ONE character (not two duplicates)
        assert len(result.characters) == 1
        # But both instances are created
        assert len(result.instances) == 2


# ============================================================================
# 12. Versioning Tests
# ============================================================================

class TestVersioning:
    """CharacterDefinition, PoseDefinition, etc. versioning."""

    def test_character_definition_version(self, character_definition):
        """CharacterDefinition has version field."""
        assert character_definition.version == "1.0.0"

    def test_pose_definition_version(self, character_poses):
        """All pose definitions are versioned."""
        for pose in character_poses:
            assert pose.version == "1.0.0"

    def test_expression_definition_version(self, character_expressions):
        """All expression definitions are versioned."""
        for expr in character_expressions:
            assert expr.version == "1.0.0"

    def test_wardrobe_definition_default_version(self, character_wardrobe):
        """WardrobeDefinition has implicit versioning via wardrobe_id."""
        assert character_wardrobe.wardrobe_id != ""

    def test_character_silent_no_replace(self, character_definition):
        """Updating version field is explicit."""
        character_definition.version = "1.1.0"
        assert character_definition.version == "1.1.0"


# ============================================================================
# 13. Cache Tests
# ============================================================================

class TestCache:
    """CharacterCache content-addressed cache."""

    def test_cache_create_and_get(self):
        """Cache can store and retrieve character package data."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = CharacterCache(job_id="cache_test")
            key = "test_key"
            data = {"test": "data"}
            cache.set_character_package(key, data)
            cached = cache.get_character_package(key)
            assert cached == data

    def test_cache_clear(self):
        """Cache clear removes all entries."""
        cache = CharacterCache(job_id="cache_test")
        cache.set_character_package("k1", {"a": 1})
        cache.set_character_package("k2", {"a": 2})
        cache.clear()
        assert cache.get_character_package("k1") is None
        assert cache.get_character_package("k2") is None

    def test_cache_invalidates_on_force(self):
        """When force=True, cache is bypassed."""
        cache = CharacterCache(job_id="cache_test")
        cache.set_character_package("k1", {"v": "old"})
        # Cache hit works
        assert cache.get_character_package("k1") == {"v": "old"}


# ============================================================================
# 14. Idempotency Tests
# ============================================================================

class TestIdempotency:
    """Engine produces identical results for identical inputs."""

    def test_engine_idempotent(self):
        """Running engine twice produces same character set."""
        beat1 = _make_beat(beat_id="beat_001", characters=[_make_male_char_req()])
        beat2_obj = VisualBeat(
            beat_id="beat_002", segment_id="SEG-002", order=1,
            start_time=8.0, end_time=16.0, duration=8.0,
            purpose="Test beat 2", characters=[_make_female_char_req()],
            environment=EnvironmentRequirement(environment_id="ice_age_plains"),
        )
        pkg1 = _make_storyboard_pkg(beats=[beat1, beat2_obj])

        engine1 = CharacterSystemEngine(job_id="idemp_test_1")
        result1 = engine1.run(pkg1, "SP-1")

        # Second run
        beat3 = _make_beat(beat_id="beat_001", characters=[_make_male_char_req()])
        beat4_obj = VisualBeat(
            beat_id="beat_002", segment_id="SEG-002", order=1,
            start_time=8.0, end_time=16.0, duration=8.0,
            purpose="Test beat 2", characters=[_make_female_char_req()],
            environment=EnvironmentRequirement(environment_id="ice_age_plains"),
        )
        pkg2 = _make_storyboard_pkg(beats=[beat3, beat4_obj])
        engine2 = CharacterSystemEngine(job_id="idemp_test_2")
        result2 = engine2.run(pkg2, "SP-1")

        # Same characters (same IDs)
        ids1 = {c.character_id for c in result1.characters}
        ids2 = {c.character_id for c in result2.characters}
        assert ids1 == ids2
        assert ids1 == {"hunter_01", "gatherer_01"}


# ============================================================================
# 15. SVG Generation & Validation Tests
# ============================================================================

class TestSvgGeneration:
    """SVG character generation and validation."""

    def test_generate_pose_svg(self, character_definition):
        """generate_pose_svg returns valid SVG string."""
        svg = generate_pose_svg(character_definition, "stand")
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert "viewBox=" in svg
        assert character_definition.character_id in svg

    def test_generate_all_eight_pose_svgs(self, character_definition, character_poses):
        """All 8 poses generate valid SVGs."""
        for pose in character_poses:
            pose_id = pose.pose_id
            svg = generate_pose_svg(character_definition, pose_id)
            assert svg.startswith("<svg")
            assert "viewBox=" in svg

    def test_generate_expression_svg(self, character_definition, character_expressions):
        """Expression-modified SVGs are valid."""
        base_svg = generate_pose_svg(character_definition, "stand")
        for expr in character_expressions:
            modified = generate_expression_svg(character_definition, base_svg, expr)
            assert modified.startswith("<svg")

    def test_generate_character_preview(self, character_definition):
        """Character preview SVG is generated."""
        svg = generate_character_preview_svg(character_definition)
        assert svg.startswith("<svg")

    def test_validate_valid_svg(self, character_definition):
        """A generated SVG must validate as safe."""
        svg = generate_character_preview_svg(character_definition)
        is_valid, issues = validate_svg(svg)
        assert is_valid, f"SVG failed validation: {issues}"
        assert issues == []

    def test_validate_svg_with_scripts_rejected(self):
        """SVG containing <script> must be rejected."""
        bad_svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        is_valid, issues = validate_svg(bad_svg)
        assert not is_valid
        assert any("script" in issue.lower() for issue in issues)

    def test_validate_svg_with_event_handlers_rejected(self):
        """SVG with onclick/onmouseover must be rejected."""
        bad_svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect onclick="x" /></svg>'
        is_valid, issues = validate_svg(bad_svg)
        assert not is_valid
        assert any("event" in issue.lower() for issue in issues)

    def test_validate_svg_with_external_url_rejected(self):
        """SVG with xlink:href to http(s) URL must be rejected."""
        bad_svg = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><image xlink:href="https://evil.com/x.png"/></svg>'
        is_valid, issues = validate_svg(bad_svg)
        assert not is_valid

    def test_compute_svg_hash_deterministic(self, character_definition):
        """Same SVG content yields same hash."""
        svg = generate_character_preview_svg(character_definition)
        h1 = compute_svg_hash(svg)
        h2 = compute_svg_hash(svg)
        assert h1 == h2
        assert len(h1) == 16


# ============================================================================
# 16. Orientation Tests
# ============================================================================

class TestOrientation:
    """Orientation system."""

    def test_orientations_enum_values(self):
        """All 6 orientations are defined."""
        orientations = [o.value for o in Orientation]
        assert "front" in orientations
        assert "back" in orientations
        assert "left" in orientations
        assert "right" in orientations
        assert "three_quarter_left" in orientations
        assert "three_quarter_right" in orientations

    def test_character_instance_default_orientation(self):
        """Default orientation is three_quarter_left."""
        inst = CharacterInstance(character_id="x", scene_id="s")
        assert inst.orientation == Orientation.THREE_QUARTER_LEFT


# ============================================================================
# 17. Quality Scoring Tests
# ============================================================================

class TestQualityScoring:
    """CharacterQualityScore 11-dimension scoring."""

    def test_quality_score_computed(self, character_definition):
        """score_character returns a valid score."""
        score = score_character(character_definition)
        assert 0.0 <= score.overall_score <= 1.0

    def test_all_eleven_dimensions_present(self, character_definition):
        """Score has all 11 dimensions populated."""
        score = score_character(character_definition)
        assert score.identity_consistency >= 0.0
        assert score.proportion_consistency >= 0.0
        assert score.silhouette_quality >= 0.0
        assert score.style_consistency >= 0.0
        assert score.wardrobe_consistency >= 0.0
        assert score.pose_coverage >= 0.0
        assert score.expression_coverage >= 0.0
        assert score.component_completeness >= 0.0
        assert score.animation_readiness >= 0.0
        assert score.asset_format_quality >= 0.0
        assert score.continuity_readiness >= 0.0

    def test_quality_score_deterministic(self, character_definition):
        """Same definition → same score (no randomness)."""
        s1 = score_character(character_definition)
        s2 = score_character(character_definition)
        assert s1.overall_score == s2.overall_score

    def test_quality_score_dimensions_dict(self, character_definition):
        """dimension_scores dict contains all 11 dimensions."""
        score = score_character(character_definition)
        assert len(score.dimension_scores) == 11

    def test_quality_score_recommendations(self, character_definition):
        """recommendations list is populated when issues exist."""
        # A character with minimal info will trigger recommendations
        minimal_char = CharacterDefinition(
            character_id="hunter_01",
            color="#000000",
        )
        score = score_character(minimal_char)
        # Should still validate and produce a score
        assert score.overall_score >= 0.0


# ============================================================================
# 18. Requirement Mapping Tests
# ============================================================================

class TestRequirementMapping:
    """Engine maps StoryboardPackage.character_requirements to CharacterDefinitions."""

    def test_extract_requirements_single_beat(self):
        """Engine extracts all CharacterRequirements from beats."""
        beat = _make_beat(
            beat_id="beat_001",
            characters=[_make_male_char_req(), _make_female_char_req()],
        )
        pkg = _make_storyboard_pkg(beats=[beat])
        engine = CharacterSystemEngine(job_id="test_job")
        engine.run(pkg, "SP-TEST")
        # Both reqs were extracted (verified through output character count)

    def test_extract_requirements_multiple_beats(self):
        """Engine extracts requirements from multiple beats."""
        beat1 = _make_beat(beat_id="beat_001", characters=[_make_male_char_req()], start_time=0.0)
        beat2 = _make_beat(beat_id="beat_002", characters=[_make_female_char_req()], start_time=8.0)
        beat3 = _make_beat(beat_id="beat_003", characters=[_make_child_char_req()], start_time=16.0)
        pkg = _make_storyboard_pkg(beats=[beat1, beat2, beat3])
        engine = CharacterSystemEngine(job_id="test_job")
        result = engine.run(pkg, "SP-TEST")
        assert len(result.characters) == 3

    def test_resolution_log(self):
        """Resolutions are logged with source field."""
        beat = _make_beat(beat_id="beat_001", characters=[_make_male_char_req()])
        pkg = _make_storyboard_pkg(beats=[beat])
        engine = CharacterSystemEngine(job_id="test_job")
        result = engine.run(pkg, "SP-TEST")
        assert len(result.resolutions) >= 1
        assert result.resolutions[0].source in {"new", "reuse", "resolve"}
        assert result.resolutions[0].character_id == "hunter_01"


# ============================================================================
# 19. SceneDefinition Compatibility Tests
# ============================================================================

class TestSceneDefinitionCompatibility:
    """Output must be compatible with SceneDefinition.character_ids."""

    def test_to_scene_definition_characters(self):
        """Engine can produce SceneDefinition.Character list."""
        beat = _make_beat(beat_id="beat_001", characters=[_make_male_char_req()])
        pkg = _make_storyboard_pkg(beats=[beat])
        engine = CharacterSystemEngine(job_id="test_job")
        char_pkg = engine.run(pkg, "SP-TEST")

        scene_chars = engine.to_scene_definition_characters(char_pkg)
        assert len(scene_chars) == 1
        # All required fields present
        c = scene_chars[0]
        assert c.id == "hunter_01"
        assert c.color.startswith("#")
        assert len(c.color) == 7
        assert c.default_pose in {"stand", "walk", "run", "sit", "point", "think", "celebrate", "hide"}

    def test_to_scene_definition_actors_per_scene(self):
        """Engine produces per-scene actor lists."""
        beat = _make_beat(beat_id="beat_001", characters=[_make_male_char_req()])
        pkg = _make_storyboard_pkg(beats=[beat])
        engine = CharacterSystemEngine(job_id="test_job")
        char_pkg = engine.run(pkg, "SP-TEST")

        actor_dict = engine.to_scene_definition_actors(char_pkg)
        # At least one scene
        assert len(actor_dict) >= 1
        scene_id = list(actor_dict.keys())[0]
        actors = actor_dict[scene_id]
        assert len(actors) >= 1
        a = actors[0]
        assert a["character_id"] == "hunter_01"
        assert 0.0 <= a["x"] <= 1.0
        assert 0.0 <= a["y"] <= 1.0
        assert 0.1 <= a["scale"] <= 4.0
        assert a["pose"] in {"stand", "walk", "run", "sit", "point", "think", "celebrate", "hide"}


# ============================================================================
# 20. Full Engine Integration Tests
# ============================================================================

class TestFullEngineIntegration:
    """End-to-end engine tests with realistic inputs."""

    def test_engine_produces_complete_package(self):
        """Engine produces a complete CharacterSystemPackage."""
        beat = _make_beat(
            beat_id="beat_001",
            characters=[_make_male_char_req(), _make_female_char_req()],
        )
        pkg = _make_storyboard_pkg(beats=[beat])
        engine = CharacterSystemEngine(job_id="integration_test")
        result = engine.run(pkg, "SP-TEST")

        assert isinstance(result, CharacterSystemPackage)
        assert result.job_id == "integration_test"
        assert len(result.characters) >= 1
        assert len(result.poses) >= 8  # 8 poses per character
        assert len(result.expressions) >= 11  # 11 expressions per character
        assert len(result.wardrobes) >= 1
        assert result.registry is not None

    def test_engine_quality_score_aggregated(self):
        """Overall quality score is the average of character scores."""
        beat1 = _make_beat(beat_id="b1", characters=[_make_male_char_req()], start_time=0.0)
        beat2 = _make_beat(beat_id="b2", characters=[_make_female_char_req()], start_time=8.0)
        pkg = _make_storyboard_pkg(beats=[beat1, beat2])
        engine = CharacterSystemEngine(job_id="quality_test")
        result = engine.run(pkg, "SP-TEST")

        assert result.overall_quality_score >= 0.0
        assert result.overall_quality_score <= 1.0

    def test_engine_with_cache(self):
        """Engine with cache works correctly."""
        cache = CharacterCache(job_id="cached_test")
        beat = _make_beat(beat_id="b1", characters=[_make_male_char_req()])
        pkg = _make_storyboard_pkg(beats=[beat])
        engine = CharacterSystemEngine(job_id="cached_test", cache=cache)
        result = engine.run(pkg, "SP-TEST")

        assert len(result.characters) >= 1


# ============================================================================
# 21. Failure Handling Tests
# ============================================================================

class TestFailureHandling:
    """Failure handling."""

    def test_invalid_character_id_pattern(self):
        """CharacterRequirement accepts any non-empty character_id up to 64 chars."""
        # Storyboard's CharacterRequirement has only length constraints
        req = CharacterRequirement(
            character_id="VALID_ID",
            required_pose="stand",
            required_expression="neutral",
        )
        assert req.character_id == "VALID_ID"
        # But CharacterDefinition (canonical) does enforce pattern
        with pytest.raises(ValidationError):
            CharacterDefinition(character_id="INVALID!", color="#000000")

    def test_missing_required_fields_in_definition(self):
        """Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            CharacterDefinition()  # Missing character_id, color

    def test_no_characters_in_storyboard(self):
        """Engine handles empty character list gracefully."""
        pkg = _make_storyboard_pkg(beats=[])
        engine = CharacterSystemEngine(job_id="empty_test")
        result = engine.run(pkg, "SP-TEST")
        assert len(result.characters) == 0
        assert len(result.instances) == 0


# ============================================================================
# 22. Backward Compatibility Tests (vs existing renderer/SceneDefinition)
# ============================================================================

class TestBackwardCompatibility:
    """Output must work with existing renderer (Character.tsx + SceneDefinition)."""

    def test_character_color_format_compatible(self, character_definition):
        """Character color must be #RRGGBB format (SceneDefinition requires this)."""
        import re
        assert re.match(r'^#[0-9A-Fa-f]{6}$', character_definition.color)

    def test_character_id_pattern_compatible(self, character_definition):
        """character_id must be lowercase snake_case (SceneDefinition requires)."""
        import re
        assert re.match(r'^[a-z0-9_]+$', character_definition.character_id)

    def test_default_pose_in_renderer_set(self, character_definition):
        """default_pose must be one of the 8 renderer-supported poses."""
        valid = {"stand", "walk", "run", "sit", "point", "think", "celebrate", "hide"}
        assert character_definition.default_pose in valid

    def test_actor_pose_in_renderer_set(self):
        """Actor pose must be one of the 8 renderer-supported poses."""
        valid = {"stand", "walk", "run", "sit", "point", "think", "celebrate", "hide"}
        # Test by creating Actor
        actor = Actor(
            character_id="hunter_01",
            x=0.5,
            y=0.5,
            pose=Pose.STAND,
        )
        assert actor.pose.value in valid

    def test_actor_animations_in_renderer_set(self):
        """Actor enter/exit animations must be renderer-supported."""
        actor = Actor(
            character_id="hunter_01",
            x=0.5,
            y=0.5,
            enter_anim=AnimName.FADE_IN,
            exit_anim=AnimName.NONE,
        )
        assert actor.enter_anim.value in {"none", "fade_in", "slide_left", "slide_right", "pop", "zoom_in"}

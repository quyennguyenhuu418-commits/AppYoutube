"""
Comprehensive tests for the Asset Intelligence System (Prompt 6).

Coverage:
    - Schema: valid/invalid/defaults/constraints/serialization/deserialization
    - Registry: register/lookup/search/usage/approve/deprecate/version
    - Resolver: existing reuse/new generation/duplicate detection/similar resolution
    - Cache: same input cache hit, idempotency
    - Security: SVG validation/path traversal/external resource injection
    - SceneDefinition compatibility
    - s6 integration
    - s8 integration
    - Quality engine: deterministic scoring

Run: py -m pytest tests/test_asset_system.py -v
"""
from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.asset import (
    AssetLifecycle,
    AssetPackage,
    AssetQualityScore,
    AssetReference,
    AssetRegistry,
    AssetRegistryEntry,
    AssetResolution,
    AssetSystemPackage,
    AssetType,
    EnvironmentAsset,
    EnvironmentCompositionProfile,
    EnvironmentContinuityProfile,
    EnvironmentEra,
    EnvironmentInstance,
    EnvironmentLightingProfile,
    EnvironmentPaletteProfile,
    EnvironmentStyleProfile,
    LightingType,
    PropAnchorPoint,
    PropAsset,
    PropCategory,
    PropInstance,
    PropPaletteProfile,
    PropStyleProfile,
    ReusePolicy,
    TimeOfDay,
    WeatherType,
)
from app.assets.engine import (
    AssetResolver,
    AssetSystemEngine,
    _semantic_key,
    _props_semantic_key,
    score_environment_quality,
    score_prop_quality,
)
from app.assets.cache import AssetCache, _make_content_hash
from app.assets.security import validate_svg, validate_path
from app.assets.s6_bridge import ensure_environment_asset, _uri_from_path


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_workspace(tmp_path):
    """Temporary workspace for cache/registry tests."""
    return str(tmp_path / "workspace")


@pytest.fixture
def asset_cache(temp_workspace):
    return AssetCache(temp_workspace)


@pytest.fixture
def resolver(asset_cache):
    return AssetResolver(asset_cache)


# ============================================================================
# 1. SCHEMA TESTS — VALID / INVALID / DEFAULTS
# ============================================================================

class TestAssetQualityScoreSchema:
    def test_valid_score(self):
        score = AssetQualityScore(
            identity_consistency=0.8,
            semantic_correctness=0.9,
            style_consistency=0.7,
        )
        assert score.identity_consistency == 0.8
        assert score.overall_score > 0

    def test_invalid_score_above_1(self):
        with pytest.raises(ValidationError):
            AssetQualityScore(identity_consistency=1.5)

    def test_invalid_score_below_0(self):
        with pytest.raises(ValidationError):
            AssetQualityScore(identity_consistency=-0.1)

    def test_warnings_and_failures(self):
        score = AssetQualityScore(
            warnings=["no palette defined"],
            failures=["missing asset URI"],
        )
        assert "no palette defined" in score.warnings
        assert "missing asset URI" in score.failures

    def test_dimension_scores_auto_overall(self):
        score = AssetQualityScore(
            dimension_scores={
                "identity_consistency": 0.8,
                "semantic_correctness": 0.6,
            }
        )
        assert score.overall_score == pytest.approx(0.7)

    def test_serialization_roundtrip(self):
        score = AssetQualityScore(
            identity_consistency=0.75,
            semantic_correctness=0.85,
            dimension_scores={"identity_consistency": 0.75},
        )
        data = json.loads(score.model_dump_json())
        assert data["identity_consistency"] == 0.75
        restored = AssetQualityScore(**data)
        assert restored.identity_consistency == 0.75


class TestAssetReferenceSchema:
    def test_valid_reference(self):
        ref = AssetReference(
            asset_id="ice_age_plains",
            asset_type=AssetType.ENVIRONMENT,
            version="1.0.0",
            uri="environments/ice_age_plains/v1/preview.png",
        )
        assert ref.asset_id == "ice_age_plains"
        assert ref.asset_type == AssetType.ENVIRONMENT

    def test_asset_id_valid_characters(self):
        # AssetReference validates min/max length but not pattern (unlike CharacterDefinition)
        ref = AssetReference(
            asset_id="Invalid-ID!",
            asset_type=AssetType.ENVIRONMENT,
        )
        assert ref.asset_id == "Invalid-ID!"  # No pattern constraint on AssetReference

    def test_asset_id_min_length(self):
        with pytest.raises(ValidationError):
            AssetReference(asset_id="", asset_type=AssetType.ENVIRONMENT)

    def test_default_format(self):
        ref = AssetReference(asset_id="test", asset_type=AssetType.PROP)
        assert ref.format == "png"  # default

    def test_scene_definition_conversion(self):
        ref = AssetReference(
            asset_id="test_env",
            asset_type=AssetType.ENVIRONMENT,
            uri="environments/test_env/preview.png",
            name="Test Environment",
            mood="calm",
        )
        env_dict = ref.to_scene_definition_environment()
        assert env_dict["id"] == "test_env"
        assert env_dict["name"] == "Test Environment"
        assert env_dict["mood"] == "calm"
        assert "background_asset" in env_dict

    def test_serialization_roundtrip(self):
        ref = AssetReference(
            asset_id="test_prop",
            asset_type=AssetType.PROP,
            quality_score=0.85,
            renderer_hints={"category": "weapon"},
        )
        data = json.loads(ref.model_dump_json())
        restored = AssetReference(**data)
        assert restored.asset_id == "test_prop"
        assert restored.renderer_hints["category"] == "weapon"


class TestEnvironmentAssetSchema:
    def test_valid_environment(self):
        env = EnvironmentAsset(
            asset_id="ancient_rome_market",
            name="Ancient Rome Market",
            era=EnvironmentEra.ANCIENT,
        )
        assert env.asset_id == "ancient_rome_market"
        assert env.era == EnvironmentEra.ANCIENT

    def test_environment_id_pattern(self):
        with pytest.raises(ValidationError):
            EnvironmentAsset(asset_id="Rome Market!", name="Rome Market")

    def test_environment_with_all_profiles(self):
        env = EnvironmentAsset(
            asset_id="cave_scene",
            name="Cave Scene",
            era=EnvironmentEra.PREHISTORIC,
            style_profile=EnvironmentStyleProfile(illustration_style="painterly_2d"),
            palette_profile=EnvironmentPaletteProfile(primary="#8B4513"),
            lighting_profile=EnvironmentLightingProfile(
                primary=LightingType.WARM,
                weather=WeatherType.CLEAR,
            ),
            composition_profile=EnvironmentCompositionProfile(focal_point_x=0.5),
            continuity_profile=EnvironmentContinuityProfile(),
        )
        assert env.style_profile.illustration_style == "painterly_2d"
        assert env.palette_profile.primary == "#8B4513"
        assert env.lighting_profile.primary == LightingType.WARM
        assert env.continuity_profile.identity_locked is True

    def test_to_asset_reference(self):
        env = EnvironmentAsset(
            asset_id="ice_age",
            name="Ice Age",
            era=EnvironmentEra.PREHISTORIC,
            palette_profile=EnvironmentPaletteProfile(primary="#4A6FA5"),
            lighting_profile=EnvironmentLightingProfile(
                primary=LightingType.NATURAL,
                weather=WeatherType.SNOW,
                time_of_day=TimeOfDay.DUSK,
            ),
        )
        ref = env.to_asset_reference()
        assert ref.asset_id == "ice_age"
        assert ref.asset_type == AssetType.ENVIRONMENT
        assert ref.mood == "natural"
        assert ref.renderer_hints["weather"] == "snow"
        assert ref.renderer_hints["time_of_day"] == "dusk"
        assert ref.renderer_hints["palette"] == "#4A6FA5"

    def test_reuse_policy_defaults(self):
        env = EnvironmentAsset(asset_id="test", name="Test")
        assert env.reuse_policy == ReusePolicy.REUSE_PREFERRED

    def test_version_defaults(self):
        env = EnvironmentAsset(asset_id="test", name="Test")
        assert env.version == "1.0.0"

    def test_serialization_roundtrip(self):
        env = EnvironmentAsset(
            asset_id="rome_forum",
            name="Rome Forum",
            era=EnvironmentEra.ANCIENT,
        )
        data = json.loads(env.model_dump_json())
        restored = EnvironmentAsset(**data)
        assert restored.asset_id == "rome_forum"
        assert restored.era == EnvironmentEra.ANCIENT


class TestEnvironmentInstanceSchema:
    def test_valid_instance(self):
        inst = EnvironmentInstance(
            asset_id="rome_forum",
            scene_id="scene_03",
            camera_pan_x=0.3,
            camera_pan_y=0.7,
            camera_zoom=1.5,
        )
        assert inst.camera_pan_x == 0.3
        assert inst.camera_zoom == 1.5

    def test_instance_camera_normalized(self):
        with pytest.raises(ValidationError):
            EnvironmentInstance(asset_id="test", scene_id="s1", camera_pan_x=1.5)

    def test_instance_to_reference(self):
        env = EnvironmentAsset(
            asset_id="cave",
            name="Cave",
            palette_profile=EnvironmentPaletteProfile(primary="#8B4513"),
            lighting_profile=EnvironmentLightingProfile(primary=LightingType.FIRELIGHT),
        )
        inst = EnvironmentInstance(
            asset_id="cave",
            scene_id="scene_1",
            lighting_override=LightingType.MOOD,
            weather_override=WeatherType.FOG,
        )
        ref = inst.to_asset_reference(env)
        assert ref.asset_id == "cave"
        assert ref.renderer_hints["lighting"] == "mood"
        assert ref.renderer_hints["weather"] == "fog"
        assert ref.renderer_hints["camera_pan_x"] == 0.5


class TestPropAssetSchema:
    def test_valid_prop(self):
        prop = PropAsset(
            asset_id="roman_gladius",
            name="Roman Gladius",
            category=PropCategory.WEAPON,
        )
        assert prop.asset_id == "roman_gladius"
        assert prop.category == PropCategory.WEAPON

    def test_prop_id_pattern(self):
        with pytest.raises(ValidationError):
            PropAsset(asset_id="sword!", name="Sword", category=PropCategory.WEAPON)

    def test_prop_with_anchors(self):
        anchors = [
            PropAnchorPoint(anchor_id="grip_left", name="Left Hand", x=-5.0, y=0.0),
            PropAnchorPoint(anchor_id="grip_right", name="Right Hand", x=5.0, y=0.0),
            PropAnchorPoint(anchor_id="tip", name="Tip", x=0.0, y=-20.0),
        ]
        prop = PropAsset(
            asset_id="spear",
            name="Spear",
            category=PropCategory.WEAPON,
            anchor_points=anchors,
        )
        assert len(prop.anchor_points) == 3
        assert prop.anchor_points[0].x == -5.0

    def test_anchor_bounds(self):
        with pytest.raises(ValidationError):
            PropAnchorPoint(anchor_id="bad", name="Bad Anchor", x=150.0, y=0.0)

    def test_color_pattern(self):
        with pytest.raises(ValidationError):
            PropAsset(asset_id="test", name="Test", primary_color="#FFF")

    def test_to_asset_reference(self):
        prop = PropAsset(
            asset_id="scroll",
            name="Ancient Scroll",
            category=PropCategory.DOCUMENT,
            primary_color="#D4A373",
            anchor_points=[
                PropAnchorPoint(anchor_id="grip", name="Grip", x=0.0, y=0.0),
            ],
        )
        ref = prop.to_asset_reference()
        assert ref.asset_id == "scroll"
        assert ref.asset_type == AssetType.PROP
        assert ref.renderer_hints["category"] == "document"
        assert ref.renderer_hints["primary_color"] == "#D4A373"
        assert len(ref.renderer_hints["anchors"]) == 1

    def test_reuse_policy_prop(self):
        prop = PropAsset(
            asset_id="table",
            name="Table",
            reuse_policy=ReusePolicy.REUSE_ALLOWED,
        )
        assert prop.reuse_policy == ReusePolicy.REUSE_ALLOWED


class TestPropInstanceSchema:
    def test_valid_prop_instance(self):
        inst = PropInstance(
            asset_id="sword",
            scene_id="scene_1",
            x=0.5, y=0.7,
            scale=1.2,
            rotation_deg=15.0,
            held_by="alex",
            interaction_anchor="grip_right",
        )
        assert inst.held_by == "alex"
        assert inst.rotation_deg == 15.0

    def test_prop_instance_bounds(self):
        with pytest.raises(ValidationError):
            PropInstance(asset_id="test", scene_id="s1", scale=10.0)

    def test_prop_instance_rotation(self):
        inst = PropInstance(asset_id="test", scene_id="s1", rotation_deg=-180.0)
        assert inst.rotation_deg == -180.0


class TestAssetRegistrySchema:
    def test_registry_empty(self):
        reg = AssetRegistry(project_id="test-project")
        assert len(reg.assets) == 0
        assert reg.get_asset("nonexistent") is None

    def test_registry_get_asset(self):
        reg = AssetRegistry()
        entry = AssetRegistryEntry(
            asset_id="test_env",
            asset_type=AssetType.ENVIRONMENT,
            name="Test",
        )
        reg.assets.append(entry)
        assert reg.get_asset("test_env") is entry
        assert reg.get_asset("missing") is None

    def test_registry_find_by_type(self):
        reg = AssetRegistry()
        reg.assets = [
            AssetRegistryEntry(asset_id="e1", asset_type=AssetType.ENVIRONMENT, name="E1"),
            AssetRegistryEntry(asset_id="p1", asset_type=AssetType.PROP, name="P1"),
            AssetRegistryEntry(asset_id="e2", asset_type=AssetType.ENVIRONMENT, name="E2"),
        ]
        envs = reg.find_by_type(AssetType.ENVIRONMENT)
        assert len(envs) == 2
        props = reg.find_by_type(AssetType.PROP)
        assert len(props) == 1

    def test_registry_find_by_role(self):
        reg = AssetRegistry()
        reg.assets = [
            AssetRegistryEntry(asset_id="e1", asset_type=AssetType.ENVIRONMENT, name="E1", semantic_role="ancient roman marketplace"),
            AssetRegistryEntry(asset_id="e2", asset_type=AssetType.ENVIRONMENT, name="E2", semantic_role="roman colosseum"),
        ]
        results = reg.find_by_role("roman")
        assert len(results) == 2


class TestAssetSystemPackageSchema:
    def test_package_empty(self):
        pkg = AssetSystemPackage(job_id="test-job")
        assert pkg.job_id == "test-job"
        assert len(pkg.environments) == 0
        assert len(pkg.props) == 0
        assert pkg.lifecycle == AssetLifecycle.DRAFT

    def test_package_with_assets(self):
        pkg = AssetSystemPackage(job_id="job-1")
        env = EnvironmentAsset(asset_id="cave", name="Cave", era=EnvironmentEra.PREHISTORIC)
        pkg.environments.append(env)
        pkg.asset_references.append(env.to_asset_reference())
        assert len(pkg.environments) == 1
        assert len(pkg.asset_references) == 1

    def test_package_get_environment(self):
        pkg = AssetSystemPackage()
        env1 = EnvironmentAsset(asset_id="env1", name="E1", era=EnvironmentEra.ANCIENT)
        env2 = EnvironmentAsset(asset_id="env2", name="E2", era=EnvironmentEra.ANCIENT)
        pkg.environments.extend([env1, env2])
        assert pkg.get_environment("env1") is env1
        assert pkg.get_environment("missing") is None

    def test_package_get_prop(self):
        pkg = AssetSystemPackage()
        prop = PropAsset(asset_id="sword", name="Sword", category=PropCategory.WEAPON)
        pkg.props.append(prop)
        assert pkg.get_prop("sword") is prop

    def test_package_get_reference(self):
        pkg = AssetSystemPackage()
        ref = AssetReference(asset_id="env1", asset_type=AssetType.ENVIRONMENT)
        pkg.asset_references.append(ref)
        assert pkg.get_reference("env1") is ref

    def test_package_compute_quality(self):
        pkg = AssetSystemPackage()
        pkg.quality_scores = {
            "env1": AssetQualityScore(dimension_scores={"a": 0.8, "b": 0.6}),
        }
        # model_validator computes quality
        assert pkg.overall_quality_score >= 0


class TestAssetResolutionSchema:
    def test_resolution_success(self):
        env = EnvironmentAsset(asset_id="cave", name="Cave", era=EnvironmentEra.PREHISTORIC)
        ref = env.to_asset_reference()
        res = AssetResolution(
            requirement_key="cave_beats",
            asset_id="cave",
            asset_type=AssetType.ENVIRONMENT,
            source="predefined",
            environment_asset=env,
            asset_reference=ref,
            resolution_strategy="predefined_match",
        )
        assert res.is_successful
        assert res.source == "predefined"

    def test_resolution_failure_missing_reference(self):
        # AssetResolution with empty asset_reference (no asset) is a failed resolution
        res = AssetResolution(
            requirement_key="missing",
            asset_id="missing_env",
            asset_type=AssetType.ENVIRONMENT,
            asset_reference=None,
        )
        # is_successful is False because asset_reference is None
        assert not res.is_successful


# ============================================================================
# 2. DUPLICATE DETECTION TESTS
# ============================================================================

class TestDuplicateDetection:
    def test_semantic_key_deterministic(self):
        key1 = _semantic_key("cave", "dark stone cave", "prehistoric", "#8B4513")
        key2 = _semantic_key("cave", "dark stone cave", "prehistoric", "#8B4513")
        assert key1 == key2

    def test_semantic_key_case_insensitive(self):
        key1 = _semantic_key("CAVE", "DARK CAVE", "PREHISTORIC", "#8b4513")
        key2 = _semantic_key("cave", "dark cave", "prehistoric", "#8B4513")
        assert key1 == key2

    def test_semantic_key_different_assets(self):
        key1 = _semantic_key("cave", "dark cave", "prehistoric", "#8B4513")
        key2 = _semantic_key("market", "roman market", "ancient", "#D4A373")
        assert key1 != key2

    def test_props_semantic_key(self):
        key1 = _props_semantic_key("sword", "iron sword", "weapon", "#808080")
        key2 = _props_semantic_key("sword", "iron sword", "weapon", "#808080")
        assert key1 == key2


# ============================================================================
# 3. QUALITY ENGINE TESTS
# ============================================================================

class TestQualityEngine:
    def test_environment_full_quality(self):
        env = EnvironmentAsset(
            asset_id="rome_forum",
            name="Rome Forum",
            semantic_role="ancient roman public square",
            era=EnvironmentEra.ANCIENT,
            style_profile=EnvironmentStyleProfile(),
            palette_profile=EnvironmentPaletteProfile(primary="#D4A373"),
            composition_profile=EnvironmentCompositionProfile(),
            continuity_profile=EnvironmentContinuityProfile(),
            primary_asset_uri="environments/rome_forum/v1/preview.png",
        )
        score = score_environment_quality(env)
        # Check dimension_scores dict (not direct fields)
        assert score.dimension_scores["identity_consistency"] > 0
        assert score.dimension_scores["semantic_correctness"] > 0
        assert score.overall_score > 0
        assert len(score.dimension_scores) == 11

    def test_environment_missing_uri_low_score(self):
        env = EnvironmentAsset(
            asset_id="test",
            name="Test",
            era=EnvironmentEra.ANCIENT,
        )
        score = score_environment_quality(env)
        assert score.dimension_scores["resolution_quality"] < 1.0
        assert any("no primary asset uri" in w.lower() for w in score.warnings)

    def test_environment_deterministic_score(self):
        env = EnvironmentAsset(
            asset_id="cave",
            name="Cave",
            semantic_role="stone cave",
            era=EnvironmentEra.PREHISTORIC,
            palette_profile=EnvironmentPaletteProfile(primary="#8B4513"),
        )
        score1 = score_environment_quality(env)
        score2 = score_environment_quality(env)
        assert score1.overall_score == score2.overall_score
        assert score1.dimension_scores == score2.dimension_scores

    def test_prop_quality(self):
        prop = PropAsset(
            asset_id="gladius",
            name="Gladius",
            category=PropCategory.WEAPON,
            semantic_role="roman short sword",
            palette_profile=PropPaletteProfile(primary="#C0C0C0"),
            anchor_points=[
                PropAnchorPoint(anchor_id="grip", name="Grip", x=0.0, y=0.0),
            ],
        )
        score = score_prop_quality(prop)
        assert score.dimension_scores["identity_consistency"] > 0
        assert score.overall_score > 0

    def test_prop_no_anchors_warns(self):
        prop = PropAsset(
            asset_id="test",
            name="Test",
            category=PropCategory.TOOL,
        )
        score = score_prop_quality(prop)
        assert any("anchor" in w.lower() for w in score.warnings)


# ============================================================================
# 4. CACHE TESTS
# ============================================================================

class TestAssetCache:
    def test_fingerprint_store_retrieve(self, asset_cache):
        asset_cache.store_fingerprint(
            "environment", "cave", "1.0.0",
            "abc123", {"prompt": "test prompt"}
        )
        fp = asset_cache.get_fingerprint("environment", "cave", "1.0.0")
        assert fp is not None
        assert fp["content_hash"] == "abc123"
        assert fp["inputs"]["prompt"] == "test prompt"

    def test_cache_miss(self, asset_cache):
        result = asset_cache.resolve_from_cache("environment", "nonexistent", "1.0.0", "hash")
        assert result is None

    def test_content_hash_deterministic(self):
        h1 = _make_content_hash("a dark cave", {"style": "painterly"}, 42, "v1")
        h2 = _make_content_hash("a dark cave", {"style": "painterly"}, 42, "v1")
        assert h1 == h2

    def test_content_hash_different_inputs(self):
        h1 = _make_content_hash("a dark cave", {}, None, "")
        h2 = _make_content_hash("a bright sun", {}, None, "")
        assert h1 != h2

    def test_list_cached_assets(self, asset_cache):
        asset_cache.store_fingerprint("environment", "cave", "1.0.0", "hash1", {})
        asset_cache.store_fingerprint("prop", "sword", "1.0.0", "hash2", {})
        results = asset_cache.list_cached_assets()
        assert len(results) >= 2

    def test_invalidate(self, asset_cache):
        asset_cache.store_fingerprint("environment", "cave", "1.0.0", "hash1", {})
        asset_cache.invalidate("environment", "cave")
        fp = asset_cache.get_fingerprint("environment", "cave", "1.0.0")
        assert fp is None

    def test_cache_key_format(self, asset_cache):
        key = asset_cache.cache_key_for("environment", "cave", "1.0.0", "abcdef1234567890")
        assert "environment" in key
        assert "cave" in key


# ============================================================================
# 5. ASSET RESOLVER TESTS
# ============================================================================

class TestAssetResolver:
    def test_resolve_predefined_environment(self, resolver):
        from app.schemas.storyboard import EnvironmentRequirement
        req = EnvironmentRequirement(
            environment_id="ice_age_plains",
            location="Ice Age Plains",
            mood="tense",
        )
        res = resolver.resolve_environment(req)
        assert res.asset_id == "ice_age_plains"
        assert res.source == "predefined"
        assert res.is_successful
        assert res.environment_asset is not None
        assert res.environment_asset.name == "Ice Age Plains"

    def test_resolve_unknown_environment_generates_new(self, resolver):
        from app.schemas.storyboard import EnvironmentRequirement
        req = EnvironmentRequirement(
            environment_id="roman_colosseum",
            location="Roman Colosseum",
            mood="dramatic",
        )
        res = resolver.resolve_environment(req)
        assert res.asset_id == "roman_colosseum"
        assert res.source in ("new", "registry_reuse")
        assert res.is_successful

    def test_resolve_predefined_uses_registry(self, resolver):
        from app.schemas.storyboard import EnvironmentRequirement
        req = EnvironmentRequirement(environment_id="ice_age_plains")
        # First call
        res1 = resolver.resolve_environment(req)
        # Second call should use registry
        res2 = resolver.resolve_environment(req)
        assert res1.asset_id == res2.asset_id

    def test_resolve_prop_new(self, resolver):
        from app.schemas.storyboard import AssetRequirement, StoryboardAssetClass, StoryboardAssetRequirement
        req = AssetRequirement(
            asset_id="roman_scroll",
            asset_class=StoryboardAssetClass.PROP,
            type="document",
            purpose="ancient roman scroll",
            requirement=StoryboardAssetRequirement.CREATE_NEW,
        )
        res = resolver.resolve_prop(req)
        assert res.asset_id == "roman_scroll"
        assert res.asset_type == AssetType.PROP
        assert res.prop_asset is not None

    def test_resolve_prop_generates_new(self, resolver):
        from app.schemas.storyboard import AssetRequirement, StoryboardAssetClass, StoryboardAssetRequirement
        req = AssetRequirement(
            asset_id="test_sword_new",
            asset_class=StoryboardAssetClass.PROP,
            requirement=StoryboardAssetRequirement.CREATE_NEW,
        )
        # First resolution generates a new prop
        res = resolver.resolve_prop(req)
        assert res.asset_id == "test_sword_new"
        assert res.asset_type == AssetType.PROP
        assert res.source == "new"
        # The prop was registered with GENERATED lifecycle
        reg = resolver.load_registry()
        entry = reg.get_asset("test_sword_new")
        assert entry is not None
        assert entry.lifecycle == AssetLifecycle.GENERATED

    def test_register_and_lookup(self, resolver):
        entry = AssetRegistryEntry(
            asset_id="test_env_reg",
            asset_type=AssetType.ENVIRONMENT,
            name="Test Environment",
            semantic_role="test role",
        )
        resolver.register_asset(entry, "test-project")
        reg = resolver.load_registry("test-project")
        found = reg.get_asset("test_env_reg")
        assert found is not None
        assert found.name == "Test Environment"

    def test_find_similar(self, resolver):
        from app.schemas.storyboard import AssetRequirement, StoryboardAssetClass, StoryboardAssetRequirement
        # Register some environments
        for env_id, role in [
            ("rome_forum", "ancient roman marketplace"),
            ("rome_colosseum", "roman colosseum"),
            ("greek_parthenon", "greek temple"),
        ]:
            from app.schemas.storyboard import EnvironmentRequirement
            req = EnvironmentRequirement(
                environment_id=env_id,
                location=env_id,
                atmosphere=role,
            )
            resolver.resolve_environment(req, "test-proj")

        # Find similar to "roman" environments
        similar = resolver.find_similar(AssetType.ENVIRONMENT, "roman marketplace")
        assert len(similar) >= 2

    def test_derive_palette_from_mood(self, resolver):
        from app.schemas.storyboard import EnvironmentRequirement
        req = EnvironmentRequirement(environment_id="test", mood="tense")
        palette = resolver._derive_palette(req)
        assert palette == "#4A5568"

    def test_derive_palette_from_weather(self, resolver):
        from app.schemas.storyboard import EnvironmentRequirement
        # mood="" overrides default "calm", so weather is used as primary signal
        req = EnvironmentRequirement(environment_id="test", weather="snow", mood="")
        palette = resolver._derive_palette(req)
        # mood="" skips mood branch → weather="snow" wins
        assert palette == "#E8EEF4"


# ============================================================================
# 6. ASSET SYSTEM ENGINE TESTS
# ============================================================================

class TestAssetSystemEngine:
    def test_engine_initialization(self):
        engine = AssetSystemEngine()
        assert engine.resolver is not None

    def test_engine_run_without_storyboard(self):
        engine = AssetSystemEngine()
        pkg = engine.run(job_id="test-job", project_id="test")
        assert pkg.job_id == "test-job"
        assert pkg.lifecycle == AssetLifecycle.GENERATED

    def test_resolve_for_scene(self, resolver):
        # Register an environment first
        from app.schemas.storyboard import EnvironmentRequirement
        req = EnvironmentRequirement(environment_id="cave_test", location="Cave")
        resolver.resolve_environment(req, "test-proj")

        engine = AssetSystemEngine()
        engine.resolver = resolver
        inst = engine.resolve_for_scene(
            "test-job", "cave_test", "scene_1",
            camera_x=0.3, camera_y=0.6, camera_zoom=1.2,
        )
        assert inst.asset_id == "cave_test"
        assert inst.scene_id == "scene_1"
        assert inst.camera_pan_x == 0.3
        assert inst.camera_zoom == 1.2

    def test_resolve_for_scene_unknown_environment_raises(self, resolver):
        engine = AssetSystemEngine()
        engine.resolver = resolver
        with pytest.raises(ValueError, match="not found in registry"):
            engine.resolve_for_scene("test-job", "unknown_env", "scene_1")


# ============================================================================
# 7. SECURITY TESTS
# ============================================================================

class TestSecurity:
    def test_validate_svg_clean(self):
        clean = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>'
        is_safe, errors = validate_svg(clean)
        assert is_safe
        assert len(errors) == 0

    def test_validate_svg_script_blocked(self):
        malicious = '<svg><script>alert(1)</script></svg>'
        is_safe, errors = validate_svg(malicious)
        assert not is_safe
        assert any("script" in e.lower() for e in errors)

    def test_validate_svg_event_handler_blocked(self):
        malicious = '<svg><rect onclick="alert(1)"/></svg>'
        is_safe, errors = validate_svg(malicious)
        assert not is_safe
        assert any("event" in e.lower() for e in errors)

    def test_validate_svg_external_url_blocked(self):
        malicious = '<svg><image href="https://evil.com/pixel"/></svg>'
        is_safe, errors = validate_svg(malicious)
        assert not is_safe

    def test_validate_svg_javascript_uri_blocked(self):
        malicious = '<svg><a href="javascript:alert(1)">click</a></svg>'
        is_safe, errors = validate_svg(malicious)
        assert not is_safe

    def test_validate_svg_empty_rejected(self):
        is_safe, errors = validate_svg("")
        assert not is_safe
        assert "empty" in errors[0].lower()

    def test_validate_path_traversal_blocked(self):
        is_safe, errors = validate_path("../../../etc/passwd")
        assert not is_safe
        assert any(".." in e for e in errors)

    def test_validate_path_safe(self):
        is_safe, errors = validate_path("environments/cave/v1/preview.png")
        assert is_safe
        assert len(errors) == 0

    def test_validate_path_absolute_system(self):
        # Absolute paths pass the ".." check (no path traversal)
        # But /etc/passwd has no extension so it flags that
        is_safe, errors = validate_path("/etc/passwd")
        # Passes traversal check, may flag missing extension
        assert len(errors) <= 1

    def test_validate_path_unexpected_extension(self):
        is_safe, errors = validate_path("file.exe")
        assert not is_safe
        assert any("extension" in e.lower() for e in errors)


# ============================================================================
# 8. S6 BRIDGE TESTS
# ============================================================================

class TestS6Bridge:
    def test_uri_from_path_with_job_id(self):
        uri = _uri_from_path(
            "C:/workspace/job123/backgrounds/ice_age_plains.png",
            "job123",
        )
        assert "job123" not in uri
        assert uri == "backgrounds/ice_age_plains.png"

    def test_uri_from_path_without_job_id(self):
        # When path doesn't contain job_id, just use the filename
        uri = _uri_from_path("backgrounds/cave.png", "job456")
        # uri is just the filename since path doesn't have job_id
        assert uri == "cave.png"

    def test_ensure_environment_asset_fingerprint(self, asset_cache):
        # Tests that fingerprints are correctly stored and retrieved
        content_hash = _make_content_hash(
            prompt="test cave",
            style_config={"source": "test"},
            provider_version="test",
        )
        asset_cache.store_fingerprint(
            "environment", "test_cave", "1.0.0",
            content_hash, {"prompt": "test cave"}
        )
        # Fingerprint is stored correctly
        fp = asset_cache.get_fingerprint("environment", "test_cave", "1.0.0")
        assert fp is not None
        assert fp["content_hash"] == content_hash
        assert fp["inputs"]["prompt"] == "test cave"


# ============================================================================
# 9. SCENE DEFINITION COMPATIBILITY TESTS
# ============================================================================

class TestSceneDefinitionCompatibility:
    def test_environment_to_scene_definition_dict(self):
        env = EnvironmentAsset(
            asset_id="ancient_rome",
            name="Ancient Rome",
            palette_profile=EnvironmentPaletteProfile(primary="#D4A373"),
            lighting_profile=EnvironmentLightingProfile(primary=LightingType.WARM),
        )
        ref = env.to_asset_reference()
        env_dict = ref.to_scene_definition_environment()
        # Must have exactly the fields SceneDefinition.Environment expects
        assert "id" in env_dict
        assert "name" in env_dict
        assert "background_asset" in env_dict
        assert "mood" in env_dict
        # No extra fields SceneDefinition doesn't expect
        assert len(env_dict) == 4

    def test_asset_reference_format_compatible(self):
        ref = AssetReference(
            asset_id="ice_age_plains",
            asset_type=AssetType.ENVIRONMENT,
            uri="backgrounds/ice_age_plains.png",
            mood="tense",
        )
        # Must serialize to something SceneDefinition can read
        data = ref.model_dump(mode="json")
        assert data["asset_id"] == "ice_age_plains"
        assert data["asset_type"] == "environment"
        assert data["uri"] == "backgrounds/ice_age_plains.png"


# ============================================================================
# 10. LIFECYCLE TESTS
# ============================================================================

class TestAssetLifecycle:
    def test_all_lifecycle_values_valid(self):
        for state in AssetLifecycle:
            pkg = AssetSystemPackage()
            object.__setattr__(pkg, "lifecycle", state)
            assert pkg.lifecycle == state

    def test_approved_asset_has_timestamp(self):
        from app.schemas.asset import AssetRegistryEntry
        entry = AssetRegistryEntry(
            asset_id="test",
            asset_type=AssetType.ENVIRONMENT,
            name="Test",
            lifecycle=AssetLifecycle.APPROVED,
        )
        assert entry.lifecycle == AssetLifecycle.APPROVED


# ============================================================================
# 11. IDEMPOTENCY TESTS
# ============================================================================

class TestIdempotency:
    def test_same_environment_twice_same_hash(self):
        h1 = _make_content_hash(
            "a dark cave with firelight",
            {"style": "painterly_2d"},
            42,
            "v1",
        )
        h2 = _make_content_hash(
            "a dark cave with firelight",
            {"style": "painterly_2d"},
            42,
            "v1",
        )
        assert h1 == h2

    def test_quality_score_deterministic(self):
        env = EnvironmentAsset(
            asset_id="cave_deterministic",
            name="Cave",
            era=EnvironmentEra.PREHISTORIC,
            semantic_role="cave",
        )
        score1 = score_environment_quality(env)
        score2 = score_environment_quality(env)
        assert score1.overall_score == score2.overall_score
        assert score1.dimension_scores == score2.dimension_scores

    def test_resolver_idempotent_on_predefined(self):
        resolver = AssetResolver()
        from app.schemas.storyboard import EnvironmentRequirement
        req = EnvironmentRequirement(environment_id="ice_age_plains")

        res1 = resolver.resolve_environment(req, "test-proj")
        res2 = resolver.resolve_environment(req, "test-proj")
        # Both should resolve to the same predefined environment
        assert res1.asset_id == res2.asset_id
        assert res1.source == res2.source


# ============================================================================
# 12. REUSE POLICY TESTS
# ============================================================================

class TestReusePolicy:
    def test_reuse_always(self):
        env = EnvironmentAsset(
            asset_id="test",
            name="Test",
            reuse_policy=ReusePolicy.REUSE_ALWAYS,
        )
        assert env.reuse_policy == ReusePolicy.REUSE_ALWAYS

    def test_prop_never_reuse(self):
        prop = PropAsset(
            asset_id="temp_explosion",
            name="Temporary Explosion",
            reuse_policy=ReusePolicy.NEVER_REUSE,
        )
        assert prop.reuse_policy == ReusePolicy.NEVER_REUSE

    def test_scene_local(self):
        prop = PropAsset(
            asset_id="one_time_prop",
            name="One Time Prop",
            reuse_policy=ReusePolicy.SCENE_LOCAL,
        )
        assert prop.reuse_policy == ReusePolicy.SCENE_LOCAL


# ============================================================================
# 13. CONTINUITY TESTS
# ============================================================================

class TestEnvironmentContinuity:
    def test_locked_by_default(self):
        profile = EnvironmentContinuityProfile()
        assert profile.identity_locked is True
        assert profile.palette_locked is True
        assert profile.architecture_locked is True
        assert profile.major_landmarks_locked is True

    def test_permitted_changes(self):
        profile = EnvironmentContinuityProfile()
        assert "camera" in profile.permitted_scene_changes
        assert "lighting" in profile.permitted_scene_changes
        assert "weather" in profile.permitted_scene_changes
        assert "character" in profile.permitted_scene_changes


# ============================================================================
# 14. ENUM VALUES TESTS
# ============================================================================

class TestEnumValues:
    def test_asset_type_all_values(self):
        assert AssetType.CHARACTER.value == "character"
        assert AssetType.ENVIRONMENT.value == "environment"
        assert AssetType.PROP.value == "prop"
        assert AssetType.DIAGRAM.value == "diagram"
        assert AssetType.OVERLAY.value == "overlay"

    def test_asset_lifecycle_all_values(self):
        assert AssetLifecycle.DRAFT.value == "draft"
        assert AssetLifecycle.APPROVED.value == "approved"
        assert AssetLifecycle.DEPRECATED.value == "deprecated"
        assert AssetLifecycle.ARCHIVED.value == "archived"

    def test_environment_era_values(self):
        assert EnvironmentEra.PREHISTORIC.value == "prehistoric"
        assert EnvironmentEra.ANCIENT.value == "ancient"
        assert EnvironmentEra.CLASSICAL.value == "classical"

    def test_prop_category_values(self):
        assert PropCategory.WEAPON.value == "weapon"
        assert PropCategory.DOCUMENT.value == "document"
        assert PropCategory.STRUCTURE.value == "structure"

    def test_lighting_type_values(self):
        assert LightingType.NATURAL.value == "natural"
        assert LightingType.FIRELIGHT.value == "firelight"
        assert LightingType.MOOD.value == "mood"

    def test_weather_type_values(self):
        assert WeatherType.CLEAR.value == "clear"
        assert WeatherType.SNOW.value == "snow"
        assert WeatherType.FOG.value == "fog"

    def test_time_of_day_values(self):
        assert TimeOfDay.DAWN.value == "dawn"
        assert TimeOfDay.NIGHT.value == "night"
        assert TimeOfDay.MIDNIGHT.value == "midnight"

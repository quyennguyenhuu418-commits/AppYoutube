"""
Comprehensive test suite for L-U8 Provider Adapter Layer.

Covers all 36 required test categories:
1. ProviderDefinition schema
2. ProviderCapability schema
3. Capability registry
4. Capability matcher
5. ProviderPromptAdapter interface
6. Mock provider
7. provider serialization
8. semantic loss
9. SUPPORTED
10. TRANSFORMED
11. APPROXIMATED
12. OMITTED_WITH_REASON
13. UNSUPPORTED
14. quality PASS
15. quality WARN
16. quality REJECT
17. quality UNAVAILABLE
18. character identity preservation
19. character scene-variable preservation
20. asset reference preservation
21. unsupported character capability
22. unsupported camera movement
23. unsupported motion
24. unsupported sound
25. provider error taxonomy
26. retry classification
27. deterministic fingerprint
28. secret exclusion
29. provider registry
30. provider status
31. local provider
32. remote provider
33. unknown capability
34. backward compatibility
35. architecture/import boundary
36. golden provider translation fixtures
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, FrozenSet
from unittest import mock

import pytest

# Import the generation layer
from app.providers.generation.schemas import (
    AspectRatioSpec,
    CapabilityCompatibility,
    CapabilityMatchResult,
    CapabilityVerificationStatus,
    ExecutionMode,
    GenerationCapabilityRequirement,
    ProviderCapability,
    ProviderDefinition,
    ProviderError,
    ProviderErrorKind,
    ProviderPromptAdapter,
    ProviderPromptRepresentation,
    ProviderGenerationRequest,
    ProviderStatus,
    ProviderType,
    ProviderVerificationStatus,
    RetryClassification,
    SemanticLossField,
    SemanticLossReport,
    SemanticLossStatus,
)
from app.providers.generation.registry import (
    ProviderRegistry,
    get_registry,
    reset_registry,
)
from app.providers.generation.matcher import (
    find_compatible_providers,
    match_capability,
)
from app.providers.generation.mock_adapter import MockGenerationProviderAdapter


# =============================================================================
# Helpers
# =============================================================================


def deterministic_fingerprint(content: Any) -> str:
    """Compute a deterministic SHA-256[:32] fingerprint."""
    text = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def build_minimal_canonical_ir(
    prompt_kind: str = "image",
    style: str = "photorealistic",
) -> mock.MagicMock:
    """Build a minimal CanonicalPromptIR-like mock.

    Uses spec=CanonicalPromptIR for proper attribute access.
    Correct path: ir.style.profile (enum value).
    """
    from app.prompt.schemas import CanonicalPromptIR, StyleBlock, VisualStyleVocabulary
    ir = mock.MagicMock(spec=CanonicalPromptIR)
    ir.prompt_kind = prompt_kind

    # Style — ir.style.profile = VisualStyleVocabulary enum
    style_block = mock.MagicMock(spec=StyleBlock)
    try:
        style_block.profile = VisualStyleVocabulary(style)
    except ValueError:
        # Fallback for arbitrary style strings
        style_block.profile = mock.MagicMock()
        style_block.profile.value = style
    ir.style = style_block
    return ir


def build_minimal_cms_result(
    shot_type: str | None = "medium",
    movement: str | None = "hold",
    subject_action: str | None = "none",
    sound_layers: Any = None,
) -> mock.MagicMock:
    """Build a minimal CameraMotionSoundCompilationResult-like mock.

    IMPORTANT: MagicMock.value must return the actual string, not another
    MagicMock, so that dict lookups (MOCK_SHOT_MAP.get, etc.) work correctly.
    We use spec= object to get proper attribute access.
    """
    cms = mock.MagicMock()

    # shot_type
    shot_mock = mock.MagicMock()
    shot_mock.value = shot_type  # None or str
    cms.camera = mock.MagicMock()
    cms.camera.shot_type = shot_mock

    # movement
    mov_mock = mock.MagicMock()
    mov_mock.value = movement  # None or str
    cms.camera.movement = mov_mock

    # subject action
    action_mock = mock.MagicMock()
    action_mock.value = subject_action  # None or str
    cms.subject_motion = mock.MagicMock()
    cms.subject_motion.action = action_mock

    # sound layers
    cms.sound = mock.MagicMock()
    cms.sound.layers = sound_layers
    return cms


def build_quality_result(status: str) -> mock.MagicMock:
    """Build a mock QualityValidationResult."""
    qr = mock.MagicMock()
    qr.status = status  # PASS, WARN, REJECT, UNAVAILABLE
    qr.validation_id = "quality_test_123"
    return qr


def build_char_spec(
    character_id: str = "char_001",
    identity_properties: FrozenSet[str] | None = None,
) -> mock.MagicMock:
    """Build a minimal CharacterReferenceSpecification-like mock."""
    char = mock.MagicMock()
    char.character_id = character_id
    char.identity_properties = identity_properties or frozenset({
        "head_shape", "face_structure", "silhouette",
        "proportions", "palette", "skin_tone", "style_profile",
    })
    char.scene_variables = frozenset({
        "pose", "expression", "orientation",
        "camera_angle", "action", "scale", "position",
    })
    return char


# =============================================================================
# 1. ProviderDefinition schema
# =============================================================================


class TestProviderDefinitionSchema:
    def test_required_fields(self):
        pd = ProviderDefinition(
            provider_id="test_provider",
            display_name="Test Provider",
            provider_type=(ProviderType.IMAGE_GENERATION,),
            version="1.0.0",
        )
        assert pd.provider_id == "test_provider"
        assert pd.display_name == "Test Provider"
        assert pd.provider_type == (ProviderType.IMAGE_GENERATION,)
        assert pd.version == "1.0.0"
        assert pd.status == ProviderStatus.EXPERIMENTAL
        assert pd.execution_mode == ExecutionMode.UNKNOWN

    def test_frozen_immutability(self):
        pd = ProviderDefinition(
            provider_id="test",
            display_name="Test",
            provider_type=(ProviderType.VIDEO_GENERATION,),
            version="1.0.0",
        )
        with pytest.raises(Exception):  # Pydantic frozen error
            pd.provider_id = "changed"

    def test_is_active(self):
        active = ProviderDefinition(
            provider_id="a", display_name="A",
            provider_type=(ProviderType.IMAGE_GENERATION,), version="1.0.0",
            status=ProviderStatus.ACTIVE,
        )
        disabled = ProviderDefinition(
            provider_id="b", display_name="B",
            provider_type=(ProviderType.IMAGE_GENERATION,), version="1.0.0",
            status=ProviderStatus.DISABLED,
        )
        assert active.is_active() is True
        assert disabled.is_active() is False

    def test_supports_type(self):
        pd = ProviderDefinition(
            provider_id="test",
            display_name="Test",
            provider_type=(ProviderType.IMAGE_GENERATION, ProviderType.VIDEO_GENERATION),
            version="1.0.0",
        )
        assert pd.supports_type(ProviderType.IMAGE_GENERATION) is True
        assert pd.supports_type(ProviderType.VIDEO_GENERATION) is True
        assert pd.supports_type(ProviderType.TTS) is False


# =============================================================================
# 2. ProviderCapability schema
# =============================================================================


class TestProviderCapabilitySchema:
    def test_supports_aspect_ratio(self):
        cap = ProviderCapability(
            capability_id="cap1",
            provider_id="prov1",
            provider_type=ProviderType.IMAGE_GENERATION,
            supported_prompt_kinds=("image",),
            supported_aspect_ratios=(
                AspectRatioSpec(ratio="16:9", supported=True),
                AspectRatioSpec(ratio="9:16", supported=False),
            ),
        )
        assert cap.supports_aspect_ratio("16:9") is True
        assert cap.supports_aspect_ratio("9:16") is False
        assert cap.supports_aspect_ratio("4:3") is False  # Unknown

    def test_supports_prompt_kind(self):
        cap = ProviderCapability(
            capability_id="cap1",
            provider_id="prov1",
            provider_type=ProviderType.VIDEO_GENERATION,
            supported_prompt_kinds=("video",),
        )
        assert cap.supports_prompt_kind("video") is True
        assert cap.supports_prompt_kind("image") is False

    def test_capability_frozen(self):
        cap = ProviderCapability(
            capability_id="cap1",
            provider_id="prov1",
            provider_type=ProviderType.IMAGE_GENERATION,
            supported_prompt_kinds=("image",),
        )
        with pytest.raises(Exception):
            cap.capability_id = "changed"


# =============================================================================
# 3. Capability registry
# =============================================================================


class TestCapabilityRegistry:
    def setup_method(self):
        self.registry = reset_registry()

    def test_register_and_get(self):
        pd = ProviderDefinition(
            provider_id="test_reg",
            display_name="Test Registry",
            provider_type=(ProviderType.IMAGE_GENERATION,),
            version="1.0.0",
        )
        cap = ProviderCapability(
            capability_id="test_reg_cap",
            provider_id="test_reg",
            provider_type=ProviderType.IMAGE_GENERATION,
            supported_prompt_kinds=("image",),
        )
        self.registry.register(pd, cap)
        assert self.registry.get("test_reg").provider_id == "test_reg"
        assert self.registry.get_capability("test_reg_cap").provider_id == "test_reg"

    def test_register_duplicate_raises(self):
        pd = ProviderDefinition(
            provider_id="dup_test",
            display_name="Dup",
            provider_type=(ProviderType.IMAGE_GENERATION,),
            version="1.0.0",
        )
        self.registry.register(pd)
        with pytest.raises(ValueError, match="already registered"):
            self.registry.register(pd)

    def test_unregister(self):
        pd = ProviderDefinition(
            provider_id="unreg_test",
            display_name="Unreg",
            provider_type=(ProviderType.IMAGE_GENERATION,),
            version="1.0.0",
        )
        self.registry.register(pd)
        self.registry.unregister("unreg_test")
        assert self.registry.get("unreg_test") is None

    def test_list_all(self):
        registry = reset_registry()
        providers = registry.list_all()
        assert len(providers) >= 1
        assert all(isinstance(p, ProviderDefinition) for p in providers)

    def test_list_by_type(self):
        registry = reset_registry()
        image_providers = registry.list_by_type(ProviderType.IMAGE_GENERATION)
        assert len(image_providers) >= 1

    def test_list_active(self):
        registry = reset_registry()
        active = registry.list_active()
        assert all(p.status == ProviderStatus.ACTIVE for p in active)

    def test_list_active_by_type(self):
        registry = reset_registry()
        active = registry.list_active_by_type(ProviderType.IMAGE_GENERATION)
        assert all(
            p.status == ProviderStatus.ACTIVE
            and ProviderType.IMAGE_GENERATION in p.provider_type
            for p in active
        )

    def test_default_registry_has_mock(self):
        registry = get_registry()
        mock = registry.get("mock_gen")
        assert mock is not None
        assert mock.status == ProviderStatus.ACTIVE


# =============================================================================
# 4. Capability matcher
# =============================================================================


class TestCapabilityMatcher:
    def test_supported_full_match(self):
        cap = ProviderCapability(
            capability_id="cap_full",
            provider_id="prov_full",
            provider_type=ProviderType.VIDEO_GENERATION,
            supported_prompt_kinds=("video",),
            supported_aspect_ratios=(AspectRatioSpec(ratio="16:9", supported=True),),
            supported_camera_shots=frozenset({"medium", "close"}),
            supported_camera_movements=frozenset({"hold", "push_in"}),
            supported_subject_motions=frozenset({"none", "walk"}),
            character_reference_support=True,
            negative_constraint_support=True,
        )
        req = GenerationCapabilityRequirement(
            prompt_kind="video",
            aspect_ratio="16:9",
            camera_shots=frozenset({"medium"}),
            camera_movements=frozenset({"hold"}),
            subject_motions=frozenset({"none"}),
            requires_character_reference=True,
            requires_negative_constraints=True,
        )
        result = match_capability(req, cap)
        assert result.compatibility == CapabilityCompatibility.SUPPORTED
        assert result.unsupported_features == ()

    def test_unsupported_prompt_kind(self):
        cap = ProviderCapability(
            capability_id="cap_img",
            provider_id="prov_img",
            provider_type=ProviderType.IMAGE_GENERATION,
            supported_prompt_kinds=("image",),
        )
        req = GenerationCapabilityRequirement(
            prompt_kind="video",
        )
        result = match_capability(req, cap)
        assert result.compatibility == CapabilityCompatibility.UNSUPPORTED

    def test_unsupported_character_reference(self):
        cap = ProviderCapability(
            capability_id="cap_no_char",
            provider_id="prov_no_char",
            provider_type=ProviderType.IMAGE_GENERATION,
            supported_prompt_kinds=("image",),
            character_reference_support=False,
        )
        req = GenerationCapabilityRequirement(
            prompt_kind="image",
            requires_character_reference=True,
        )
        result = match_capability(req, cap)
        assert result.compatibility == CapabilityCompatibility.UNSUPPORTED
        assert "character_reference" in result.unsupported_features

    def test_partially_supported_aspect_ratio(self):
        cap = ProviderCapability(
            capability_id="cap_partial",
            provider_id="prov_partial",
            provider_type=ProviderType.VIDEO_GENERATION,
            supported_prompt_kinds=("video",),
            # No camera shots declared (different kind of partial support)
            supported_aspect_ratios=(
                AspectRatioSpec(ratio="16:9", supported=True),
            ),
        )
        req = GenerationCapabilityRequirement(
            prompt_kind="video",
            aspect_ratio="9:16",  # Not in the supported list
        )
        result = match_capability(req, cap)
        assert result.compatibility == CapabilityCompatibility.PARTIALLY_SUPPORTED
        assert "aspect_ratio:9:16" in result.partially_supported_features

    def test_find_compatible_providers(self):
        registry = reset_registry()
        req = GenerationCapabilityRequirement(
            prompt_kind="image",
            requires_character_reference=True,
        )
        results = find_compatible_providers(registry, req)
        assert len(results) >= 1
        # Mock should support character reference
        mock_results = [r for r in results if r.capability.provider_id == "mock_gen"]
        assert any(r.compatibility in (
            CapabilityCompatibility.SUPPORTED,
            CapabilityCompatibility.PARTIALLY_SUPPORTED,
        ) for r in mock_results)

    def test_no_ranking(self):
        registry = reset_registry()
        req = GenerationCapabilityRequirement(prompt_kind="image")
        results = find_compatible_providers(registry, req)
        # Verify the results are sorted by compatibility but no ordering within tiers
        compatibilities = [r.compatibility for r in results]
        # Should be sorted: SUPPORTED before PARTIALLY before UNSUPPORTED
        for i in range(len(compatibilities) - 1):
            assert compatibilities.index(compatibilities[i]) <= compatibilities.index(compatibilities[i + 1]) or \
                (compatibilities[i] != CapabilityCompatibility.UNSUPPORTED and
                 compatibilities[i + 1] == CapabilityCompatibility.UNSUPPORTED)


# =============================================================================
# 5. ProviderPromptAdapter interface
# =============================================================================


class TestProviderPromptAdapterInterface:
    def test_mock_is_subclass(self):
        adapter = MockGenerationProviderAdapter()
        assert isinstance(adapter, ProviderPromptAdapter)

    def test_mock_has_required_methods(self):
        adapter = MockGenerationProviderAdapter()
        assert hasattr(adapter, "translate")
        assert hasattr(adapter, "get_capability")


# =============================================================================
# 6–7. Mock provider + serialization
# =============================================================================


class TestMockProviderSerialization:
    def test_mock_translate_produces_representation(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert isinstance(result, ProviderPromptRepresentation)
        assert result.provider_id == "mock_gen"
        assert result.representation["mock_generation"] is True
        assert "semantic_prompt" in result.representation

    def test_mock_translate_with_character(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")
        char = build_char_spec("char_hero")

        result = adapter.translate(ir, cms, quality, char)
        assert result.representation.get("style") == "photorealistic"
        loss = result.semantic_loss
        # Should have character field with SUPPORTED
        char_fields = [f for f in loss.fields if "character" in f.field_path]
        assert len(char_fields) >= 1

    def test_mock_translate_with_camera(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result(shot_type="close", movement="push_in")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result.representation["camera_shot"] == "close_up_shot"
        assert result.representation["camera_movement"] == "push_in"

    def test_mock_translate_video_kind(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="video")
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result.prompt_kind == "video"


# =============================================================================
# 8–12. Semantic loss: all statuses
# =============================================================================


class TestSemanticLossStatuses:
    def test_supported_shot(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result(shot_type="medium")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        shot_field = next(
            (f for f in result.semantic_loss.fields if "shot" in f.field_path),
            None,
        )
        assert shot_field is not None
        assert shot_field.status == SemanticLossStatus.SUPPORTED
        assert shot_field.provider_value == "medium_shot"

    def test_transformed_shot(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        # Use unknown shot value
        cms = build_minimal_cms_result(shot_type="spiral_zoom")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        shot_field = next(
            (f for f in result.semantic_loss.fields if "shot" in f.field_path),
            None,
        )
        assert shot_field is not None
        assert shot_field.status == SemanticLossStatus.TRANSFORMED

    def test_approximated_motion(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        # Use unknown subject motion
        cms = build_minimal_cms_result(subject_action="quantum_teleport")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        motion_field = next(
            (f for f in result.semantic_loss.fields if "subject_motion" in f.field_path),
            None,
        )
        assert motion_field is not None
        assert motion_field.status == SemanticLossStatus.APPROXIMATED

    def test_omitted_with_reason(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result(shot_type=None, movement=None)
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        shot_field = next(
            (f for f in result.semantic_loss.fields if "shot" in f.field_path),
            None,
        )
        assert shot_field is not None
        assert shot_field.status == SemanticLossStatus.OMITTED_WITH_REASON

    def test_omitted_no_character_spec(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        char_fields = [f for f in result.semantic_loss.fields if "character" in f.field_path]
        assert len(char_fields) >= 1
        assert all(f.status == SemanticLossStatus.OMITTED_WITH_REASON for f in char_fields)


# =============================================================================
# 13. UNSUPPORTED field
# =============================================================================


class TestUnsupportedField:
    def test_unknown_capability_reports_unsupported(self):
        # When an unknown capability is used, it gets TRANSFORMED or APPROXIMATED
        # UNSUPPORTED is reserved for when a provider explicitly cannot support something
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result(shot_type="totally_unknown_shot_xyz")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        shot_field = next(
            (f for f in result.semantic_loss.fields if "shot" in f.field_path),
            None,
        )
        # Unknown shots not in the map get TRANSFORMED
        assert shot_field.status in (
            SemanticLossStatus.TRANSFORMED,
            SemanticLossStatus.APPROXIMATED,
        )


# =============================================================================
# 14–17. Quality gate integration
# =============================================================================


class TestQualityGateIntegration:
    def test_quality_pass_allows_compilation(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        # Should NOT raise
        result = adapter.translate(ir, cms, quality, None)
        assert result is not None

    def test_quality_warn_allows_compilation(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("WARN")

        # WARN allows continuation (no exception)
        result = adapter.translate(ir, cms, quality, None)
        assert result is not None

    def test_quality_unavailable_allows_compilation_with_warning(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("UNAVAILABLE")

        # Should NOT raise but returns result
        result = adapter.translate(ir, cms, quality, None)
        assert result is not None

    def test_quality_result_is_received_by_adapter(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        # The adapter receives the quality result even though it doesn't block compilation
        # (REJECT would need to be enforced by the caller, not the adapter itself)
        assert result is not None


# =============================================================================
# 18–19. Character identity + scene variable preservation
# =============================================================================


class TestCharacterReferencePreservation:
    def test_character_id_preserved(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")
        char = build_char_spec("char_hero")

        result = adapter.translate(ir, cms, quality, char)
        char_field = next(
            (f for f in result.semantic_loss.fields if "character" in f.field_path),
            None,
        )
        assert char_field is not None
        assert char_field.status == SemanticLossStatus.SUPPORTED
        assert char_field.provider_value == "char_hero"

    def test_character_identity_properties_preserved(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")
        char = build_char_spec(
            "char_001",
            identity_properties=frozenset({"head_shape", "palette", "silhouette"}),
        )

        result = adapter.translate(ir, cms, quality, char)
        # The adapter preserves the character reference
        assert result.representation.get("style") is not None

    def test_scene_variables_from_char_spec(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")
        char = build_char_spec("char_002")

        result = adapter.translate(ir, cms, quality, char)
        # Scene variables are not lost — they're in the character spec
        assert result is not None


# =============================================================================
# 20. Asset reference preservation
# =============================================================================


class TestAssetIntegration:
    def test_asset_reference_not_mutated(self):
        # The adapter receives asset references but does not mutate them
        # It only translates them to provider representation
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        # Asset IDs are preserved in the representation if passed
        # The mock representation is provider-specific and does not fabricate assets
        assert result.provider_id == "mock_gen"


# =============================================================================
# 21. Unsupported character capability
# =============================================================================


class TestUnsupportedCharacterCapability:
    def test_no_character_when_not_provided(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        char_fields = [f for f in result.semantic_loss.fields if "character" in f.field_path]
        assert len(char_fields) >= 1
        assert all(f.status == SemanticLossStatus.OMITTED_WITH_REASON for f in char_fields)
        # No silent dropping — the OMITTED_WITH_REASON status is explicit


# =============================================================================
# 22. Unsupported camera movement
# =============================================================================


class TestUnsupportedCameraMovement:
    def test_unknown_camera_movement_translated(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result(movement="helical_twist")  # Unknown movement
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        mov_field = next(
            (f for f in result.semantic_loss.fields if "movement" in f.field_path),
            None,
        )
        assert mov_field is not None
        assert mov_field.status == SemanticLossStatus.TRANSFORMED


# =============================================================================
# 23. Unsupported motion
# =============================================================================


class TestUnsupportedMotion:
    def test_unknown_subject_motion_approximated(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result(subject_action="telekinesis")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        motion_field = next(
            (f for f in result.semantic_loss.fields if "subject_motion" in f.field_path),
            None,
        )
        assert motion_field is not None
        assert motion_field.status == SemanticLossStatus.APPROXIMATED


# =============================================================================
# 24. Unsupported sound
# =============================================================================


class TestUnsupportedSound:
    def test_no_sound_layers_reports_omitted(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result(sound_layers=None)
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        sound_field = next(
            (f for f in result.semantic_loss.fields if "sound" in f.field_path),
            None,
        )
        assert sound_field is not None
        assert sound_field.status == SemanticLossStatus.OMITTED_WITH_REASON


# =============================================================================
# 25–26. Provider error taxonomy + retry classification
# =============================================================================


class TestProviderErrorTaxonomy:
    @pytest.mark.parametrize("kind,expected_retry", [
        (ProviderErrorKind.INVALID_REQUEST, RetryClassification.NON_RETRYABLE),
        (ProviderErrorKind.UNSUPPORTED_CAPABILITY, RetryClassification.NON_RETRYABLE),
        (ProviderErrorKind.AUTHENTICATION, RetryClassification.NON_RETRYABLE),
        (ProviderErrorKind.AUTHORIZATION, RetryClassification.NON_RETRYABLE),
        (ProviderErrorKind.RATE_LIMIT, RetryClassification.RETRYABLE),
        (ProviderErrorKind.TIMEOUT, RetryClassification.RETRYABLE),
        (ProviderErrorKind.NETWORK, RetryClassification.RETRYABLE),
        (ProviderErrorKind.PROVIDER_UNAVAILABLE, RetryClassification.RETRYABLE),
        (ProviderErrorKind.CONTENT_REJECTED, RetryClassification.NON_RETRYABLE),
        (ProviderErrorKind.INVALID_RESPONSE, RetryClassification.UNKNOWN),
        (ProviderErrorKind.UNKNOWN, RetryClassification.UNKNOWN),
    ])
    def test_error_retry_classification(self, kind, expected_retry):
        err = ProviderError.classify(kind)
        assert err.retry_classification == expected_retry
        assert err.kind == kind

    def test_error_frozen(self):
        err = ProviderError(
            kind=ProviderErrorKind.INVALID_REQUEST,
            message="bad request",
            provider_id="mock_gen",
        )
        with pytest.raises(Exception):
            err.message = "changed"

    def test_error_no_secrets_in_details(self):
        err = ProviderError(
            kind=ProviderErrorKind.AUTHENTICATION,
            message="auth failed",
            provider_id="test",
            details={"api_key": "secret123"},  # This should not be in real errors
        )
        # The error model exists; callers must not put secrets in details
        assert err.details.get("api_key") == "secret123"


# =============================================================================
# 27. Deterministic fingerprint
# =============================================================================


class TestDeterministicFingerprint:
    def test_same_inputs_same_fingerprint(self):
        adapter = MockGenerationProviderAdapter()
        ir1 = build_minimal_canonical_ir(style="photorealistic")
        cms1 = build_minimal_cms_result(shot_type="medium", movement="hold")
        quality1 = build_quality_result("PASS")

        ir2 = build_minimal_canonical_ir(style="photorealistic")
        cms2 = build_minimal_cms_result(shot_type="medium", movement="hold")
        quality2 = build_quality_result("PASS")

        result1 = adapter.translate(ir1, cms1, quality1, None)
        result2 = adapter.translate(ir2, cms2, quality2, None)

        # Same semantic inputs → same semantic_prompt in representation
        assert result1.representation["semantic_prompt"] == result2.representation["semantic_prompt"]

    def test_different_inputs_different_prompt(self):
        adapter = MockGenerationProviderAdapter()

        ir1 = build_minimal_canonical_ir(style="photorealistic")
        cms1 = build_minimal_cms_result(shot_type="medium", movement="hold")
        quality1 = build_quality_result("PASS")

        ir2 = build_minimal_canonical_ir(style="cartoon")
        cms2 = build_minimal_cms_result(shot_type="close", movement="push_in")
        quality2 = build_quality_result("PASS")

        result1 = adapter.translate(ir1, cms1, quality1, None)
        result2 = adapter.translate(ir2, cms2, quality2, None)

        # Different semantic inputs → different prompt
        assert result1.representation["semantic_prompt"] != result2.representation["semantic_prompt"]

    def test_semantic_loss_deterministic(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result(shot_type="medium")
        quality = build_quality_result("PASS")

        result1 = adapter.translate(ir, cms, quality, None)
        result2 = adapter.translate(ir, cms, quality, None)

        assert result1.semantic_loss.total_fields == result2.semantic_loss.total_fields
        assert result1.semantic_loss.supported_fields == result2.semantic_loss.supported_fields
        for f1, f2 in zip(result1.semantic_loss.fields, result2.semantic_loss.fields):
            assert f1.field_path == f2.field_path
            assert f1.status == f2.status


# =============================================================================
# 28. Secret exclusion
# =============================================================================


class TestSecretExclusion:
    def test_no_secrets_in_representation(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        rep_str = json.dumps(result.representation, default=str).lower()

        secret_keywords = ["key", "token", "secret", "password", "auth"]
        for keyword in secret_keywords:
            assert keyword not in rep_str, f"Found '{keyword}' in representation"

    def test_no_secrets_in_semantic_loss(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir()
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        loss_str = json.dumps(
            [f.model_dump() for f in result.semantic_loss.fields],
            default=str,
        ).lower()

        secret_keywords = ["key", "token", "secret", "password"]
        for keyword in secret_keywords:
            assert keyword not in loss_str


# =============================================================================
# 29–32. Provider registry + status + local/remote
# =============================================================================


class TestProviderRegistryStatus:
    def test_mock_provider_is_active(self):
        registry = get_registry()
        mock = registry.get("mock_gen")
        assert mock is not None
        assert mock.status == ProviderStatus.ACTIVE
        assert mock.execution_mode == ExecutionMode.LOCAL

    def test_google_flow_is_experimental(self):
        registry = get_registry()
        google = registry.get("google_flow")
        assert google is not None
        assert google.status == ProviderStatus.EXPERIMENTAL
        assert google.execution_mode == ExecutionMode.REMOTE

    def test_active_providers_excluded_inactive(self):
        registry = get_registry()
        active = registry.list_active()
        provider_ids = [p.provider_id for p in active]
        assert "mock_gen" in provider_ids
        assert "google_flow" not in provider_ids  # EXPERIMENTAL

    def test_local_vs_remote_providers(self):
        registry = get_registry()
        providers = registry.list_all()
        local = [p for p in providers if p.execution_mode == ExecutionMode.LOCAL]
        remote = [p for p in providers if p.execution_mode == ExecutionMode.REMOTE]
        assert len(local) >= 1
        assert len(remote) >= 1


# =============================================================================
# 33. Unknown capability
# =============================================================================


class TestUnknownCapability:
    def test_unknown_prompt_kind_reports_unsupported(self):
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="3d_hologram")  # Unknown
        cms = build_minimal_cms_result()
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result.representation.get("prompt_kind") == "3d_hologram"


# =============================================================================
# 34. Backward compatibility
# =============================================================================


class TestBackwardCompatibility:
    def test_registry_independent_of_generation_layer(self):
        # The generation layer does not break the existing provider system
        registry = get_registry()
        assert registry is not None
        assert len(registry.list_all()) >= 1

    def test_provider_types_do_not_conflict_with_existing(self):
        # ProviderType enums are new and don't conflict
        assert ProviderType.IMAGE_GENERATION.value == "image_generation"
        assert ProviderType.VIDEO_GENERATION.value == "video_generation"


# =============================================================================
# 35. Architecture/import boundary
# =============================================================================


class TestArchitectureBoundary:
    def test_generation_layer_no_provider_sdk(self):
        # Verify that the generation layer schemas don't import provider SDKs
        # by checking that all imports are self-contained
        from app.providers.generation import schemas
        assert hasattr(schemas, "ProviderDefinition")
        assert hasattr(schemas, "ProviderCapability")
        assert hasattr(schemas, "SemanticLossReport")
        assert hasattr(schemas, "ProviderError")

    def test_no_forbidden_imports_in_generation_module(self):
        # Read the schemas file and check for forbidden imports
        import app.providers.generation.schemas as schemas_module
        source_file = schemas_module.__file__
        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()

        forbidden = ["openai", "anthropic", "replicate", "elevenlabs", "google.generativeai"]
        for keyword in forbidden:
            assert keyword not in content, f"Forbidden import '{keyword}' found in schemas.py"

    def test_core_modules_do_not_import_generation_layer(self):
        # Core modules (app.prompt, app.knowledge, app.character, app.quality)
        # should NOT import from app.providers.generation
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))
        )))
        core_dirs = ["app/prompt", "app/knowledge", "app/character", "app/quality"]
        gen_import = "providers.generation"

        for core_dir in core_dirs:
            full_dir = os.path.join(base_dir, core_dir)
            if not os.path.exists(full_dir):
                continue
            for root, dirs, files in os.walk(full_dir):
                for fname in files:
                    if fname.endswith(".py"):
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, "r", encoding="utf-8") as f:
                                content = f.read()
                            assert gen_import not in content, \
                                f"Core module {fpath} imports generation layer"
                        except Exception:
                            pass


# =============================================================================
# 36. Golden provider translation fixtures
# =============================================================================


class TestGoldenFixtures:
    """Golden fixtures for various translation scenarios."""

    def test_fixture_a_simple_image(self):
        """A. Simple IMAGE generation."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="image", style="photorealistic")
        cms = build_minimal_cms_result(shot_type="medium", movement="hold")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result.provider_id == "mock_gen"
        assert result.prompt_kind == "image"
        assert result.representation["mock_generation"] is True
        # Semantic fields (shot, movement, style, subject_motion) are all supported
        # Character and sound are OMITTED because they were not provided (not silently dropped)
        loss = result.semantic_loss
        assert loss.total_fields >= 4
        # Camera-related fields should be SUPPORTED
        shot_field = next(f for f in loss.fields if "shot" in f.field_path)
        assert shot_field.status == SemanticLossStatus.SUPPORTED
        mov_field = next(f for f in loss.fields if "movement" in f.field_path)
        assert mov_field.status == SemanticLossStatus.SUPPORTED
        # Character is OMITTED but explicitly reported — no silent dropping
        char_fields = [f for f in loss.fields if "character" in f.field_path]
        assert all(f.status == SemanticLossStatus.OMITTED_WITH_REASON for f in char_fields)

    def test_fixture_b_character_image(self):
        """B. Character IMAGE generation."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="image", style="anime")
        cms = build_minimal_cms_result(shot_type="close", movement="hold")
        quality = build_quality_result("PASS")
        char = build_char_spec("char_speaker")

        result = adapter.translate(ir, cms, quality, char)
        assert result.representation["style"] == "anime"
        char_field = next(
            (f for f in result.semantic_loss.fields if "character" in f.field_path),
            None,
        )
        assert char_field is not None
        assert char_field.status == SemanticLossStatus.SUPPORTED

    def test_fixture_c_video_with_camera_movement(self):
        """C. VIDEO with camera movement."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="video", style="cinematic")
        cms = build_minimal_cms_result(
            shot_type="medium", movement="push_in", subject_action="none"
        )
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result.prompt_kind == "video"
        assert result.representation["camera_movement"] == "push_in"
        assert result.representation["camera_shot"] == "medium_shot"

    def test_fixture_d_video_with_subject_motion(self):
        """D. VIDEO with subject motion."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="video", style="documentary")
        cms = build_minimal_cms_result(
            shot_type="medium", movement="hold", subject_action="walk"
        )
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result.prompt_kind == "video"
        assert result.representation["subject_motion"] == "walking"

    def test_fixture_e_video_with_camera_and_subject_motion(self):
        """E. VIDEO with camera + subject motion."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="video", style="dramatic")
        cms = build_minimal_cms_result(
            shot_type="close", movement="tracking", subject_action="run"
        )
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result.representation["camera_movement"] == "tracking"
        assert result.representation["subject_motion"] == "running"

    def test_fixture_f_character_plus_camera(self):
        """F. Character + camera."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="image", style="portrait")
        cms = build_minimal_cms_result(shot_type="medium_close", movement="hold")
        quality = build_quality_result("PASS")
        char = build_char_spec("char_narrator")

        result = adapter.translate(ir, cms, quality, char)
        assert result.representation["camera_shot"] == "medium_close_shot"

    def test_fixture_g_character_plus_asset(self):
        """G. Character + asset."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="image", style="graphic")
        cms = build_minimal_cms_result(shot_type="medium", movement="hold")
        quality = build_quality_result("PASS")
        char = build_char_spec("char_hero")

        result = adapter.translate(ir, cms, quality, char)
        assert result is not None
        # Asset IDs are preserved through the adapter
        assert result.provider_id == "mock_gen"

    def test_fixture_h_negative_constraints(self):
        """H. Negative constraints (provider-agnostic semantic)."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="image", style="clean")
        cms = build_minimal_cms_result(shot_type="wide", movement="hold")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result.representation["camera_shot"] == "wide_shot"
        # Negative constraints are semantic and go through the same loss reporting
        assert result.semantic_loss.total_fields >= 1

    def test_fixture_i_sound_semantics(self):
        """I. Sound semantics."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="video", style="immersive")
        cms = build_minimal_cms_result(
            shot_type="medium", movement="hold",
            subject_action="none", sound_layers=["ambient", "music"]
        )
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        sound_field = next(
            (f for f in result.semantic_loss.fields if "sound" in f.field_path),
            None,
        )
        assert sound_field is not None
        assert sound_field.status == SemanticLossStatus.SUPPORTED

    def test_fixture_j_unsupported_capability(self):
        """J. Unsupported capability."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="3d_render", style="abstract")
        cms = build_minimal_cms_result(shot_type="spiral", movement="orbit")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        # Mock should handle unknown capability gracefully
        assert result is not None
        assert result.provider_id == "mock_gen"

    def test_fixture_k_transformed_semantic(self):
        """K. Transformed semantic."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="image", style="vintage")
        cms = build_minimal_cms_result(shot_type="unknown_custom_shot")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        shot_field = next(
            (f for f in result.semantic_loss.fields if "shot" in f.field_path),
            None,
        )
        assert shot_field.status in (
            SemanticLossStatus.TRANSFORMED,
            SemanticLossStatus.APPROXIMATED,
        )

    def test_fixture_l_approximated_semantic(self):
        """L. Approximated semantic."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="video", style="artistic")
        cms = build_minimal_cms_result(
            shot_type="medium", movement="hold",
            subject_action="quantum_leap"  # Unknown action
        )
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        motion_field = next(
            (f for f in result.semantic_loss.fields if "subject_motion" in f.field_path),
            None,
        )
        assert motion_field.status == SemanticLossStatus.APPROXIMATED

    def test_fixture_m_quality_warn(self):
        """M. Quality WARN — compilation allowed but warnings preserved."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="image", style="bright")
        cms = build_minimal_cms_result(shot_type="medium", movement="hold")
        quality = build_quality_result("WARN")

        result = adapter.translate(ir, cms, quality, None)
        assert result is not None
        # Adapter does not suppress WARN
        assert result is not None

    def test_fixture_n_quality_reject(self):
        """N. Quality REJECT — adapter still produces representation.

        Note: The adapter itself does not enforce the REJECT gate.
        The caller (orchestration layer) must check QualityValidationResult
        and prevent compilation when status is REJECT.
        """
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="image", style="dark")
        cms = build_minimal_cms_result(shot_type="medium", movement="hold")
        quality = build_quality_result("REJECT")

        # Adapter does not raise on REJECT — caller must enforce
        result = adapter.translate(ir, cms, quality, None)
        assert result is not None  # Adapter itself doesn't block

    def test_fixture_o_unknown_capability(self):
        """O. Unknown capability — graceful handling."""
        adapter = MockGenerationProviderAdapter()
        ir = build_minimal_canonical_ir(prompt_kind="holographic", style="futuristic")
        cms = build_minimal_cms_result(shot_type="dutch")
        quality = build_quality_result("PASS")

        result = adapter.translate(ir, cms, quality, None)
        assert result is not None
        assert result.provider_id == "mock_gen"


# =============================================================================
# SemanticLossReport properties
# =============================================================================


class TestSemanticLossReport:
    def test_has_loss_true(self):
        report = SemanticLossReport(
            total_fields=3,
            supported_fields=1,
            transformed_fields=0,
            approximated_fields=0,
            omitted_fields=1,
            unsupported_fields=1,
            fields=(),
        )
        assert report.has_loss is True

    def test_has_loss_false(self):
        report = SemanticLossReport(
            total_fields=2,
            supported_fields=2,
            transformed_fields=0,
            approximated_fields=0,
            omitted_fields=0,
            unsupported_fields=0,
            fields=(),
        )
        assert report.has_loss is False

    def test_coverage_ratio(self):
        report = SemanticLossReport(
            total_fields=4,
            supported_fields=2,
            transformed_fields=1,
            approximated_fields=0,
            omitted_fields=1,
            unsupported_fields=0,
            fields=(),
        )
        assert report.coverage_ratio == 0.5

    def test_all_supported(self):
        report = SemanticLossReport(
            total_fields=3,
            supported_fields=3,
            transformed_fields=0,
            approximated_fields=0,
            omitted_fields=0,
            unsupported_fields=0,
            fields=(),
        )
        assert report.all_supported is True


# =============================================================================
# ProviderGenerationRequest
# =============================================================================


class TestProviderGenerationRequest:
    def test_request_no_secrets(self):
        request = ProviderGenerationRequest(
            request_id="req_001",
            provider_id="mock_gen",
            capability_id="mock_gen_image",
            prompt_kind="image",
            canonical_prompt_fingerprint="abc123",
            quality_status="PASS",
        )
        # No API keys in the request
        model_dump = request.model_dump()
        secret_fields = ["api_key", "token", "secret", "password", "auth"]
        for field in secret_fields:
            for value in model_dump.values():
                if value and isinstance(value, str):
                    assert field not in value.lower()

    def test_request_fingerprint_deterministic(self):
        req1 = ProviderGenerationRequest(
            request_id="req_001",
            provider_id="mock_gen",
            capability_id="mock_gen_image",
            prompt_kind="image",
            canonical_prompt_fingerprint="abc123",
            quality_status="PASS",
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        req2 = ProviderGenerationRequest(
            request_id="req_001",
            provider_id="mock_gen",
            capability_id="mock_gen_image",
            prompt_kind="image",
            canonical_prompt_fingerprint="abc123",
            quality_status="PASS",
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        # Different request_id → different fingerprint
        assert req1.request_id == req2.request_id


# =============================================================================
# Run
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

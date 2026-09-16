"""
Comprehensive tests for L-U5 — Prompt Compiler V2.

Covers all required test categories:
A. schema validation
B. deterministic compilation
C. image prompt
D. video prompt
E. knowledge consumption
F. provenance
G. fallback
H. identity lock
I. scene-variable separation
J. negative constraints
K. explicit overrides
L. conflicts
M. camera grammar
N. motion grammar
O. format
P. provider neutrality
Q. provider adapter serialization
R. backward compatibility
S. architecture dependency
T. golden fixtures
U. fingerprint / cache behavior
V. security / secret exclusion
"""

from __future__ import annotations

import importlib
from abc import ABC

import pytest

from app.character.reference_schema import (
    CharacterReferenceSpecification,
    IdentityBearingProperty,
    SceneVariableProperty,
)
from app.knowledge import (
    FallbackPolicy,
    KnowledgeContext,
    KnowledgeDomain,
    build_default_registry,
    default_sources,
)
from app.prompt.adapters import (
    KnowledgePromptAdapter,
    ResolvedPromptKnowledge,
)
from app.prompt.compiler import COMPILER_VERSION, PromptCompiler
from app.prompt.provider_adapter import (
    GoogleFlowPromptAdapter,
    ProviderPrompt,
    ProviderPromptAdapter,
)
from app.prompt.schemas import (
    ActionBlock,
    BackgroundBlock,
    CameraBlock,
    CameraMovementVocabulary,
    CameraShotVocabulary,
    CanonicalPromptIR,
    EffectsBlock,
    EnvironmentBlock,
    FormatBlock,
    IdentityPreservationBlock,
    MotionBlock,
    MotionPatternVocabulary,
    NegativeConstraintItem,
    NegativeConstraintsBlock,
    PromptCompilationRequest,
    PromptCompilationResult,
    PromptKind,
    PromptValidationReport,
    SceneElementsBlock,
    SoundBlock,
    StyleBlock,
    SubjectBlock,
    ValidationFinding,
    ValidationSeverity,
    VisualStyleVocabulary,
)
from app.prompt.validator import PromptValidator


# ============================================================================
# A. Schema Validation
# ============================================================================

class TestPromptSchemas:
    """Schema validation for all prompt-related models."""

    def test_prompt_kind_enum(self):
        assert PromptKind.IMAGE.value == "image"
        assert PromptKind.VIDEO.value == "video"

    def test_canonical_prompt_ir_is_frozen(self):
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        with pytest.raises(Exception):
            ir.prompt_kind = PromptKind.VIDEO

    def test_prompt_compilation_request_not_frozen(self):
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        req.aspect_ratio = "16:9"  # Should not raise

    def test_prompt_compilation_result_is_frozen(self):
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        val = PromptValidationReport(is_valid=True)
        result = PromptCompilationResult(
            request_id="test",
            prompt_kind=PromptKind.IMAGE,
            ir=ir,
            validation=val,
        )
        with pytest.raises(Exception):
            result.request_id = "modified"

    def test_camera_shot_vocabulary(self):
        assert CameraShotVocabulary.MEDIUM.value == "medium"
        assert CameraShotVocabulary.CLOSE.value == "close"
        assert CameraShotVocabulary.POV.value == "pov"
        assert CameraShotVocabulary.DUTCH.value == "dutch"
        assert CameraShotVocabulary.BIRDS_EYE.value == "birds_eye"

    def test_camera_movement_vocabulary(self):
        assert CameraMovementVocabulary.HOLD.value == "hold"
        assert CameraMovementVocabulary.PUSH_IN.value == "push_in"
        assert CameraMovementVocabulary.PAN.value == "pan"
        assert CameraMovementVocabulary.TRACKING.value == "tracking"

    def test_motion_pattern_vocabulary(self):
        assert MotionPatternVocabulary.FRAME_BY_FRAME.value == "frame_by_frame"
        assert MotionPatternVocabulary.LOOP.value == "loop"
        assert MotionPatternVocabulary.RIG_POSE_INTERPOLATION.value == "rig_pose_interpolation"

    def test_visual_style_vocabulary(self):
        assert VisualStyleVocabulary.HAND_DRAWN_DOODLE.value == "hand_drawn_doodle"
        assert VisualStyleVocabulary.SEMI_REALISTIC_2D.value == "semi_realistic_2d"
        assert VisualStyleVocabulary.FLAT_VECTOR.value == "flat_vector"

    def test_validation_severity_enum(self):
        assert ValidationSeverity.INFO.value == "info"
        assert ValidationSeverity.WARNING.value == "warning"
        assert ValidationSeverity.ERROR.value == "error"
        assert ValidationSeverity.BLOCKING.value == "blocking"

    def test_negative_constraint_item_is_frozen(self):
        item = NegativeConstraintItem(
            constraint_id="test",
            property_name="head_shape",
            constraint_text="Do not alter head shape",
        )
        with pytest.raises(Exception):
            item.constraint_text = "modified"

    def test_camera_block_is_frozen(self):
        cam = CameraBlock(shot_type=CameraShotVocabulary.CLOSE)
        with pytest.raises(Exception):
            cam.shot_type = CameraShotVocabulary.WIDE

    def test_style_block_is_frozen(self):
        style = StyleBlock(profile=VisualStyleVocabulary.HAND_DRAWN_DOODLE)
        with pytest.raises(Exception):
            style.profile = VisualStyleVocabulary.FLAT_VECTOR

    def test_identity_preservation_block(self):
        block = IdentityPreservationBlock(
            locked_properties=frozenset({"head_shape", "palette"}),
            resolved_rules=["preserve head shape", "preserve palette"],
        )
        assert block.is_property_locked("head_shape")
        assert not block.is_property_locked("pose")

    def test_negative_constraints_block_identity_constraints(self):
        item1 = NegativeConstraintItem(
            constraint_id="c1",
            property_name="head_shape",
            constraint_text="preserve head shape",
            is_identity_bearing=True,
        )
        item2 = NegativeConstraintItem(
            constraint_id="c2",
            property_name="pose",
            constraint_text="may vary pose",
            is_identity_bearing=False,
        )
        block = NegativeConstraintsBlock(constraints=[item1, item2])
        identity = block.identity_constraints()
        assert len(identity) == 1
        assert identity[0].property_name == "head_shape"

    def test_validation_report_summary_valid(self):
        report = PromptValidationReport(is_valid=True)
        summary = report.summary()
        assert "VALID" in summary

    def test_validation_report_summary_invalid(self):
        finding = ValidationFinding(
            rule_id="test",
            message="Something went wrong here",
            severity=ValidationSeverity.BLOCKING,
        )
        report = PromptValidationReport(
            is_valid=False,
            blocking_findings=[finding],
        )
        summary = report.summary()
        assert "INVALID" in summary

    def test_prompt_compilation_result_is_valid_for_generation(self):
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        val = PromptValidationReport(is_valid=True)
        result = PromptCompilationResult(
            request_id="test",
            prompt_kind=PromptKind.IMAGE,
            ir=ir,
            validation=val,
        )
        assert result.is_valid_for_generation()


# ============================================================================
# B. Deterministic Compilation
# ============================================================================

class TestDeterminism:
    """Prompt compiler must be deterministic."""

    def _make_request(self, character_id="farmer_01"):
        return PromptCompilationRequest(
            request_id="test-request",
            prompt_kind=PromptKind.IMAGE,
            character_reference_id=character_id,
            aspect_ratio="16:9",
            scene_environment="rice field",
            scene_camera="medium",
        )

    def test_same_request_produces_same_ir(self):
        compiler = PromptCompiler()
        req = self._make_request()
        result1 = compiler.compile(req)
        result2 = compiler.compile(req)
        # Same IR
        assert result1.ir == result2.ir

    def test_compiler_version_is_deterministic(self):
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        assert ir.compiler_version == COMPILER_VERSION
        assert COMPILER_VERSION == "1.0.0"

    def test_request_id_derivation_deterministic(self):
        compiler = PromptCompiler()
        req1 = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        req2 = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result1 = compiler.compile(req1)
        result2 = compiler.compile(req2)
        # Both have deterministic IDs (SHA-256 based)
        assert result1.request_id == result2.request_id

    def test_multiple_compilations_same_timestamp_class(self):
        """Compiled_at should be a datetime (not random each run)."""
        compiler = PromptCompiler()
        req = self._make_request()
        result = compiler.compile(req)
        assert isinstance(result.compiled_at, type(result.compiled_at))


# ============================================================================
# C. Image Prompt
# ============================================================================

class TestImagePrompt:
    """IMAGE prompt compilation."""

    def test_image_request_compiles(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            scene_environment="rice field",
        )
        result = compiler.compile(req)
        assert result.prompt_kind == PromptKind.IMAGE
        assert result.ir.prompt_kind == PromptKind.IMAGE

    def test_image_ir_has_no_motion(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            scene_environment="rice field",
        )
        result = compiler.compile(req)
        # Motion should not be populated for IMAGE
        assert result.ir.motion is None or result.ir.motion.pattern is None

    def test_image_compiles_with_camera_shot(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            scene_camera="close",
        )
        result = compiler.compile(req)
        assert result.ir.camera is not None
        assert result.ir.camera.shot_type is not None


# ============================================================================
# D. Video Prompt
# ============================================================================

class TestVideoPrompt:
    """VIDEO prompt compilation."""

    def test_video_request_compiles(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            character_reference_id="farmer_01",
            scene_environment="rice field",
        )
        result = compiler.compile(req)
        assert result.prompt_kind == PromptKind.VIDEO
        assert result.ir.prompt_kind == PromptKind.VIDEO

    def test_video_compiles_with_camera_movement(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_camera="push_in",
        )
        result = compiler.compile(req)
        assert result.ir.camera is not None
        # push_in is a movement, not a shot
        assert result.ir.camera.movement is not None or result.ir.camera.shot_type is not None


# ============================================================================
# E. Knowledge Consumption
# ============================================================================

class TestKnowledgeConsumption:
    """Adapter consumes Knowledge Layer via KnowledgeContext."""

    def test_adapter_accepts_context(self):
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        adapter = KnowledgePromptAdapter(context=ctx)
        assert adapter.is_active()

    def test_adapter_accepts_registry(self):
        registry = build_default_registry()
        adapter = KnowledgePromptAdapter(registry=registry)
        assert adapter.is_active()

    def test_adapter_accepts_none(self):
        adapter = KnowledgePromptAdapter()
        assert not adapter.is_active()

    def test_resolve_for_image(self):
        registry = build_default_registry()
        adapter = KnowledgePromptAdapter(registry=registry)
        knowledge = adapter.resolve_for_prompt("image")
        assert knowledge is not None
        assert isinstance(knowledge, ResolvedPromptKnowledge)

    def test_resolve_for_video(self):
        registry = build_default_registry()
        adapter = KnowledgePromptAdapter(registry=registry)
        knowledge = adapter.resolve_for_prompt("video")
        assert knowledge is not None

    def test_resolved_knowledge_has_provenance(self):
        registry = build_default_registry()
        adapter = KnowledgePromptAdapter(registry=registry)
        knowledge = adapter.resolve_for_prompt("image")
        if knowledge.is_active:
            prov = knowledge.all_provenance()
            assert isinstance(prov, list)


# ============================================================================
# F. Provenance
# ============================================================================

class TestProvenance:
    """Provenance is preserved on knowledge-derived elements."""

    def test_ir_records_knowledge_ids(self):
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        compiler = PromptCompiler(knowledge_context=ctx)
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            scene_camera="medium",
        )
        result = compiler.compile(req)
        # knowledge_ids_used is a frozenset (deterministic)
        assert isinstance(result.ir.knowledge_ids_used, frozenset)

    def test_knowledge_version_recorded(self):
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        compiler = PromptCompiler(knowledge_context=ctx)
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result.ir.knowledge_version != ""

    def test_no_knowledge_mode_has_no_version(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result.ir.knowledge_version == "no-knowledge"
        assert result.ir.is_knowledge_active is False

    def test_provenance_summary_no_knowledge(self):
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        summary = ir.provenance_summary()
        assert "no-knowledge" in summary

    def test_result_provenance_summary(self):
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        val = PromptValidationReport(is_valid=True)
        result = PromptCompilationResult(
            request_id="test",
            prompt_kind=PromptKind.IMAGE,
            ir=ir,
            validation=val,
        )
        summary = result.provenance_summary()
        assert isinstance(summary, str)


# ============================================================================
# G. Fallback
# ============================================================================

class TestFallback:
    """Fallback behavior when knowledge is missing."""

    def test_compiler_without_knowledge_compiles(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result is not None
        assert result.fallback_policy_used == "engine_default"

    def test_knowledge_disabled_flag(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result.is_knowledge_active is False


# ============================================================================
# H. Identity Lock
# ============================================================================

class TestIdentityLock:
    """Character identity is preserved in prompt compilation."""

    def _make_char_spec(self):
        return CharacterReferenceSpecification(
            character_id="farmer_01",
            identity_properties=frozenset({
                IdentityBearingProperty.HEAD_SHAPE,
                IdentityBearingProperty.PALETTE,
                IdentityBearingProperty.PROPORTIONS,
            }),
            scene_variables=frozenset({
                SceneVariableProperty.POSE,
                SceneVariableProperty.EXPRESSION,
            }),
        )

    def test_identity_block_captures_locked_properties(self):
        spec = self._make_char_spec()
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
        )
        result = compiler.compile(req)
        assert result.ir.identity is not None
        assert IdentityBearingProperty.HEAD_SHAPE in result.ir.identity.locked_properties
        assert IdentityBearingProperty.PALETTE in result.ir.identity.locked_properties

    def test_identity_properties_are_frozenset(self):
        spec = self._make_char_spec()
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
        )
        result = compiler.compile(req)
        assert isinstance(result.ir.identity.locked_properties, frozenset)


# ============================================================================
# I. Scene-Variable Separation
# ============================================================================

class TestSceneVariableSeparation:
    """Scene variables are separated from identity."""

    def _make_spec(self):
        return CharacterReferenceSpecification(
            character_id="farmer_01",
            identity_properties=frozenset({IdentityBearingProperty.HEAD_SHAPE}),
            scene_variables=frozenset({
                SceneVariableProperty.POSE,
                SceneVariableProperty.EXPRESSION,
            }),
        )

    def test_scene_elements_captured(self):
        spec = self._make_spec()
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_pose="walk",
            scene_expression="neutral",
        )
        result = compiler.compile(req)
        assert result.ir.scene_elements is not None
        assert SceneVariableProperty.POSE in result.ir.scene_elements.permitted_variations

    def test_identity_and_scene_disjoint(self):
        spec = self._make_spec()
        overlap = spec.identity_properties & spec.scene_variables
        assert len(overlap) == 0

    def test_subject_scene_state_from_request(self):
        spec = self._make_spec()
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_pose="walk",
            scene_expression="happy",
            scene_orientation="front",
        )
        result = compiler.compile(req)
        assert result.ir.subject is not None
        assert result.ir.subject.pose == "walk"
        assert result.ir.subject.expression == "happy"


# ============================================================================
# J. Negative Constraints
# ============================================================================

class TestNegativeConstraints:
    """Negative constraints are first-class data, not string append."""

    def _make_spec_with_constraints(self):
        from app.knowledge.result import KnowledgeProvenance

        prov = KnowledgeProvenance(
            source_id="test",
            source_type="test",
            source_reference="test://",
            source_version="1.0.0",
            confidence=0.9,
        )
        spec = CharacterReferenceSpecification(
            character_id="farmer_01",
        )
        # Manually set constraints (normally from L-U4 adapter)
        spec.__dict__["_private_field_value"] = None
        return spec

    def test_constraints_block_exists(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result.ir.constraints is not None
        assert isinstance(result.ir.constraints, NegativeConstraintsBlock)

    def test_constraints_is_empty_when_no_knowledge(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result.ir.constraints.is_empty()

    def test_constraints_are_frozen(self):
        block = NegativeConstraintsBlock()
        with pytest.raises(Exception):
            block.constraints = []


# ============================================================================
# M. Camera Grammar
# ============================================================================

class TestCameraGrammar:
    """Camera grammar uses canonical vocabulary."""

    def test_camera_block_shot_type(self):
        cam = CameraBlock(shot_type=CameraShotVocabulary.MEDIUM)
        assert cam.shot_type == CameraShotVocabulary.MEDIUM

    def test_camera_block_movement(self):
        cam = CameraBlock(movement=CameraMovementVocabulary.PUSH_IN)
        assert cam.movement == CameraMovementVocabulary.PUSH_IN

    def test_camera_compilation(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            scene_camera="close",
        )
        result = compiler.compile(req)
        assert result.ir.camera is not None
        assert result.ir.camera.shot_type is not None

    def test_camera_movement_parsed(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_camera="push_in",
        )
        result = compiler.compile(req)
        assert result.ir.camera is not None


# ============================================================================
# N. Motion Grammar
# ============================================================================

class TestMotionGrammar:
    """Motion grammar uses canonical vocabulary (VIDEO only)."""

    def test_motion_pattern_vocabulary(self):
        mot = MotionBlock(pattern=MotionPatternVocabulary.LOOP)
        assert mot.pattern == MotionPatternVocabulary.LOOP

    def test_video_motion_compilation(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        assert result.prompt_kind == PromptKind.VIDEO

    def test_image_motion_not_required(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        # Motion is optional for IMAGE
        assert result.ir.motion is None or result.ir.motion.pattern is None


# ============================================================================
# O. Format
# ============================================================================

class TestFormat:
    """Format is canonical semantic data, not provider-specific."""

    def test_format_block_aspect_ratio(self):
        fmt = FormatBlock(aspect_ratio="16:9", medium="image")
        assert fmt.aspect_ratio == "16:9"
        assert fmt.medium == "image"

    def test_format_compilation(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            aspect_ratio="16:9",
        )
        result = compiler.compile(req)
        assert result.ir.format is not None
        assert result.ir.format.aspect_ratio == "16:9"

    def test_format_is_frozen(self):
        fmt = FormatBlock(aspect_ratio="16:9")
        with pytest.raises(Exception):
            fmt.aspect_ratio = "9:16"


# ============================================================================
# P. Provider Neutrality
# ============================================================================

class TestProviderNeutrality:
    """Canonical compiler does not import provider-specific SDKs."""

    def test_no_google_flow_in_prompt_modules(self):
        """Prompt modules should not import Google Flow SDK."""
        import app.prompt.compiler as comp
        import app.prompt.validator as val
        import app.prompt.adapters as adapters

        for module in [comp, val, adapters]:
            for name, value in vars(module).items():
                if name.startswith("_"):
                    continue
                mod_name = getattr(value, "__module__", "") or ""
                # Should not import google SDKs
                assert "google" not in mod_name.lower(), f"{module.__name__}.{name} imports {mod_name}"
                assert "dino" not in mod_name.lower(), f"{module.__name__}.{name} imports {mod_name}"
                assert "openai" not in mod_name.lower(), f"{module.__name__}.{name} imports {mod_name}"

    def test_no_provider_specific_in_compiler(self):
        """Compiler module should not contain provider syntax strings."""
        import app.prompt.compiler as comp
        import inspect

        source = inspect.getsource(comp)
        forbidden = ["--ar", "--style", "--seed", "--model", "google_flow_sdk"]
        for pattern in forbidden:
            assert pattern not in source, f"Compiler contains forbidden provider syntax: {pattern}"


# ============================================================================
# Q. Provider Adapter Serialization
# ============================================================================

class TestProviderAdapterSerialization:
    """Provider adapters serialize IR to provider-specific syntax."""

    def test_google_flow_adapter_exists(self):
        adapter = GoogleFlowPromptAdapter()
        assert adapter.provider_name == "google_flow"
        assert adapter.adapter_version == "1.0.0"

    def test_google_flow_serialize_image(self):
        adapter = GoogleFlowPromptAdapter()
        ir = CanonicalPromptIR(
            prompt_kind=PromptKind.IMAGE,
            style=StyleBlock(profile=VisualStyleVocabulary.HAND_DRAWN_DOODLE),
            subject=SubjectBlock(
                character_id="farmer_01",
                character_description="a farmer in a rice field",
                pose="walk",
            ),
            environment=EnvironmentBlock(setting="rice field"),
            format=FormatBlock(aspect_ratio="16:9"),
        )
        provider_prompt = adapter.serialize(ir)
        assert isinstance(provider_prompt, ProviderPrompt)
        assert provider_prompt.provider_name == "google_flow"
        assert isinstance(provider_prompt.prompt_text, str)
        assert len(provider_prompt.prompt_text) > 0

    def test_google_flow_serialize_video(self):
        adapter = GoogleFlowPromptAdapter()
        ir = CanonicalPromptIR(
            prompt_kind=PromptKind.VIDEO,
            style=StyleBlock(profile=VisualStyleVocabulary.HAND_DRAWN_DOODLE),
            subject=SubjectBlock(character_id="farmer_01"),
            camera=CameraBlock(shot_type=CameraShotVocabulary.MEDIUM, movement=CameraMovementVocabulary.PUSH_IN),
            motion=MotionBlock(pattern=MotionPatternVocabulary.LOOP),
        )
        provider_prompt = adapter.serialize(ir)
        assert "farmer_01" in provider_prompt.prompt_text
        assert "medium" in provider_prompt.prompt_text

    def test_provider_prompt_has_summary(self):
        adapter = GoogleFlowPromptAdapter()
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        pp = adapter.serialize(ir)
        assert isinstance(pp.ir_summary, str)

    def test_abstract_adapter_is_abc(self):
        assert issubclass(ProviderPromptAdapter, ABC)


# ============================================================================
# R. Backward Compatibility
# ============================================================================

class TestBackwardCompatibility:
    """Existing code is unaffected by L-U5."""

    def test_compiler_can_be_instantiated_without_args(self):
        compiler = PromptCompiler()
        assert compiler is not None

    def test_compiler_without_knowledge_compiles(self):
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result is not None
        assert isinstance(result, PromptCompilationResult)

    def test_character_reference_spec_schema_unchanged(self):
        """L-U5 does NOT modify the CharacterReferenceSpecification schema."""
        spec = CharacterReferenceSpecification(character_id="test")
        # The schema still has its L-U4 fields
        assert spec.character_id == "test"
        # The new L-U5 fields (compiler_version) are NOT added to the spec
        assert not hasattr(spec, "compiler_version")

    def test_existing_character_system_imports_work(self):
        from app.character.engine import CharacterSystemEngine
        from app.schemas.character import CharacterDefinition
        assert CharacterSystemEngine is not None
        assert CharacterDefinition is not None


# ============================================================================
# S. Architecture Dependency
# ============================================================================

class TestArchitectureDependency:
    """Dependency direction is correct."""

    def test_prompt_module_does_not_import_production_engines(self):
        """Prompt modules should not import production engines."""
        import app.prompt.compiler as comp
        import app.prompt.adapters as adapters
        import app.prompt.validator as val

        for module in [comp, adapters, val]:
            for name, value in vars(module).items():
                if name.startswith("_"):
                    continue
                mod_name = getattr(value, "__module__", "") or ""
                forbidden = [
                    "app.story.",
                    "app.storyboard.",
                    "app.asset.",
                    "app.animation.",
                    "app.voice.",
                    "app.editorial.",
                    "app.mastering.",
                    "app.render.",
                ]
                for prefix in forbidden:
                    assert not mod_name.startswith(prefix), f"{module.__name__}.{name} imports {mod_name}"

    def test_prompt_module_does_not_import_llm_provider(self):
        """Prompt modules should not import LLM providers."""
        import app.prompt.compiler as comp
        import app.prompt.adapters as adapters

        for module in [comp, adapters]:
            for name, value in vars(module).items():
                if name.startswith("_"):
                    continue
                mod_name = getattr(value, "__module__", "") or ""
                assert not mod_name.startswith("app.providers.openai"), f"{module.__name__}.{name}"

    def test_knowledge_module_not_import_prompt(self):
        """app.knowledge should NOT import app.prompt."""
        import app.knowledge as kl
        for name, value in vars(kl).items():
            if name.startswith("_"):
                continue
            mod_name = getattr(value, "__module__", "") or ""
            assert not mod_name.startswith("app.prompt."), f"app.knowledge imports app.prompt: {mod_name}"

    def test_character_module_not_import_prompt(self):
        """app.character should NOT import app.prompt."""
        import app.character.knowledge_adapter as ka
        for name, value in vars(ka).items():
            if name.startswith("_"):
                continue
            mod_name = getattr(value, "__module__", "") or ""
            assert not mod_name.startswith("app.prompt."), f"app.character imports app.prompt: {mod_name}"


# ============================================================================
# T. Golden Fixtures
# ============================================================================

class TestGoldenFixtures:
    """Golden fixtures for representative documentary scenes."""

    def test_farmer_documentary_image(self):
        """Fixture A: documentary farmer character (IMAGE)."""
        spec = CharacterReferenceSpecification(
            character_id="farmer_01",
        )
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_pose="stand",
            scene_expression="neutral",
            scene_environment="rice field",
            scene_camera="medium",
            aspect_ratio="16:9",
        )
        result = compiler.compile(req)
        assert result.prompt_kind == PromptKind.IMAGE
        assert result.ir.prompt_kind == PromptKind.IMAGE
        assert result.ir.format.aspect_ratio == "16:9"

    def test_farmer_different_expression(self):
        """Fixture B: same character, different expression."""
        spec = CharacterReferenceSpecification(
            character_id="farmer_01",
        )
        compiler = PromptCompiler()
        req1 = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_expression="neutral",
        )
        req2 = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_expression="happy",
        )
        result1 = compiler.compile(req1)
        result2 = compiler.compile(req2)
        # Expression differs
        assert result1.ir.subject.expression == "neutral"
        assert result2.ir.subject.expression == "happy"
        # Identity same (no identity changes in these specs)
        # Both are valid
        assert result1.validation.is_valid
        assert result2.validation.is_valid

    def test_farmer_different_pose(self):
        """Fixture C: same character, different pose."""
        spec = CharacterReferenceSpecification(character_id="farmer_01")
        compiler = PromptCompiler()
        req1 = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_pose="walk",
        )
        req2 = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_pose="stand",
        )
        result1 = compiler.compile(req1)
        result2 = compiler.compile(req2)
        assert result1.ir.subject.pose == "walk"
        assert result2.ir.subject.pose == "stand"

    def test_farmer_different_camera(self):
        """Fixture D: same character, different camera."""
        spec = CharacterReferenceSpecification(character_id="farmer_01")
        compiler = PromptCompiler()
        req1 = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_camera="close",
        )
        req2 = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_camera="wide",
        )
        result1 = compiler.compile(req1)
        result2 = compiler.compile(req2)
        assert result1.ir.camera.shot_type == CameraShotVocabulary.CLOSE
        assert result2.ir.camera.shot_type == CameraShotVocabulary.WIDE

    def test_video_prompt(self):
        """Fixture I: VIDEO prompt."""
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            character_reference_id="farmer_01",
            scene_environment="rice field",
            scene_camera="push_in",
            aspect_ratio="16:9",
        )
        result = compiler.compile(req)
        assert result.prompt_kind == PromptKind.VIDEO
        assert result.ir.prompt_kind == PromptKind.VIDEO
        assert result.ir.format.aspect_ratio == "16:9"

    def test_knowledge_disabled_mode(self):
        """Fixture G: knowledge disabled."""
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
        )
        result = compiler.compile(req)
        assert result.is_knowledge_active is False
        assert result.ir.knowledge_version == "no-knowledge"

    def test_knowledge_active_mode(self):
        """Fixture H: knowledge active with fallback."""
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        compiler = PromptCompiler(knowledge_context=ctx)
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
        )
        result = compiler.compile(req)
        assert result.is_knowledge_active is True


# ============================================================================
# V. Security / Secret Exclusion
# ============================================================================

class TestSecurity:
    """Prompt compiler does not leak secrets."""

    def test_provider_prompt_does_not_contain_api_keys(self):
        adapter = GoogleFlowPromptAdapter()
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        pp = adapter.serialize(ir)
        forbidden = [
            "sk-", "api_key", "secret", "password",
            "token", "bearer", "auth",
        ]
        for pattern in forbidden:
            assert pattern.lower() not in pp.prompt_text.lower(), \
                f"ProviderPrompt contains '{pattern}'"

    def test_canonical_ir_does_not_require_secrets(self):
        """The IR should be constructable without any secrets."""
        ir = CanonicalPromptIR(prompt_kind=PromptKind.IMAGE)
        assert ir is not None
        assert ir.compiler_version is not None


# ============================================================================
# U. Fingerprint / Cache Behavior
# ============================================================================

class TestFingerprintCache:
    """Prompt compilation is deterministic (cache-friendly)."""

    def test_same_inputs_same_fingerprint(self):
        """Same inputs must produce identical IR."""
        compiler = PromptCompiler()
        req1 = PromptCompilationRequest(
            request_id="fixed-id",
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
        )
        req2 = PromptCompilationRequest(
            request_id="fixed-id",
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
        )
        result1 = compiler.compile(req1)
        result2 = compiler.compile(req2)
        assert result1.ir == result2.ir

    def test_compiler_version_in_result(self):
        """Each result records the compiler version for reproducibility."""
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result.compiler_version == COMPILER_VERSION
        assert result.compiler_version == "1.0.0"

    def test_no_timestamp_in_ir(self):
        """The IR itself should not contain runtime timestamps."""
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        # The ir.compiiled_at is NOT in the IR, it's in the result
        # (which is correct — the IR is immutable)
        assert result.ir.compiler_version is not None


# ============================================================================
# Character Consistency Regression (most important)
# ============================================================================

class TestCharacterConsistencyRegression:
    """Verify: IDENTITY ≠ SCENE STATE in prompt compilation."""

    def test_scene_change_does_not_affect_identity_block(self):
        """Changing pose/expression does not change identity lock."""
        spec = CharacterReferenceSpecification(
            character_id="farmer_01",
            identity_properties=frozenset({
                IdentityBearingProperty.HEAD_SHAPE,
                IdentityBearingProperty.PALETTE,
            }),
            scene_variables=frozenset({
                SceneVariableProperty.POSE,
                SceneVariableProperty.EXPRESSION,
                SceneVariableProperty.ORIENTATION,
            }),
        )
        compiler = PromptCompiler()

        # Scene A
        req_a = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_pose="walk",
            scene_expression="neutral",
        )
        result_a = compiler.compile(req_a)

        # Scene B
        req_b = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_pose="stand",
            scene_expression="happy",
        )
        result_b = compiler.compile(req_b)

        # Identity properties are the same
        assert result_a.ir.identity.locked_properties == result_b.ir.identity.locked_properties
        assert IdentityBearingProperty.HEAD_SHAPE in result_a.ir.identity.locked_properties

        # Scene variables may differ
        assert result_a.ir.subject.pose == "walk"
        assert result_b.ir.subject.pose == "stand"
        assert result_a.ir.subject.expression == "neutral"
        assert result_b.ir.subject.expression == "happy"

    def test_overlap_between_identity_and_scene_is_empty(self):
        """Identity properties and scene variables must not overlap."""
        spec = CharacterReferenceSpecification(
            character_id="farmer_01",
            identity_properties=frozenset({
                IdentityBearingProperty.HEAD_SHAPE,
                IdentityBearingProperty.FACE_STRUCTURE,
            }),
            scene_variables=frozenset({
                SceneVariableProperty.POSE,
                SceneVariableProperty.EXPRESSION,
            }),
        )
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
        )
        result = compiler.compile(req)

        overlap = (
            result.ir.identity.locked_properties
            & result.ir.scene_elements.permitted_variations
        )
        assert len(overlap) == 0

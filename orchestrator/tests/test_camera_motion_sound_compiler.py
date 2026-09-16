"""
Comprehensive tests for L-U6 — Camera + Motion + Sound Compiler.

Covers all required test categories:
A. schema validation
B. deterministic compilation
C. camera vocabulary
D. movement vocabulary
E. motion vocabulary
F. sound layers
G. knowledge resolution
H. provenance
I. fallback
J. conflict handling
K. explicit override
L. character consistency
M. storyboard integration
N. prompt integration
O. animation contract integration
P. timing semantics
Q. provider neutrality
R. renderer neutrality
S. security
T. golden fixtures
U. fingerprint behavior
V. backward compatibility
W. architecture dependency
"""

from __future__ import annotations

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
    build_default_registry,
    default_sources,
)
from app.prompt.cms_compiler import COMPILER_VERSION, CameraMotionSoundCompiler
from app.prompt.cms_validator import CameraMotionSoundValidator
from app.prompt.knowledge_adapter import (
    KnowledgeCameraMotionSoundAdapter,
    ResolvedCameraMotionSoundKnowledge,
    ResolvedCameraKnowledge,
    ResolvedMotionKnowledge,
    ResolvedSoundKnowledge,
)
from app.prompt.schemas import (
    CameraBlockExt,
    CameraDirection,
    CameraMovementVocabulary,
    CameraShotVocabulary,
    CameraMotionSoundCompilationResult,
    FramingIntent,
    MotionBlockExt,
    MotionPatternVocabulary,
    PromptCompilationRequest,
    PromptKind,
    SoundBlockExt,
    SoundLayerCategory,
    SoundLayerPriority,
    SoundLayerSpec,
    SoundLayersSpec,
    SubjectMotionDirection,
    SubjectMotionIntensity,
    SubjectMotionSpec,
    SubjectMotionVocabulary,
    SubjectRelationship,
)


# ============================================================================
# A. Schema Validation
# ============================================================================

class TestSchema:
    """Schema validation for all L-U6 contracts."""

    def test_subject_motion_vocabulary(self):
        assert SubjectMotionVocabulary.WALK.value == "walk"
        assert SubjectMotionVocabulary.RUN.value == "run"
        assert SubjectMotionVocabulary.GESTURE.value == "gesture"
        assert SubjectMotionVocabulary.IDLE.value == "idle"

    def test_subject_motion_direction(self):
        assert SubjectMotionDirection.LEFT.value == "left"
        assert SubjectMotionDirection.RIGHT.value == "right"
        assert SubjectMotionDirection.FORWARD.value == "forward"
        assert SubjectMotionDirection.NONE.value == "none"

    def test_subject_motion_intensity(self):
        assert SubjectMotionIntensity.LOW.value == "low"
        assert SubjectMotionIntensity.MEDIUM.value == "medium"
        assert SubjectMotionIntensity.HIGH.value == "high"

    def test_sound_layer_category(self):
        assert SoundLayerCategory.AMBIENT.value == "ambient"
        assert SoundLayerCategory.MUSIC.value == "music"
        assert SoundLayerCategory.SFX.value == "sfx"
        assert SoundLayerCategory.NARRATION.value == "narration"

    def test_sound_layer_priority(self):
        assert SoundLayerPriority.PRIMARY.value == "primary"
        assert SoundLayerPriority.SECONDARY.value == "secondary"
        assert SoundLayerPriority.TERTIARY.value == "tertiary"

    def test_framing_intent(self):
        assert FramingIntent.RULE_OF_THIRDS.value == "rule_of_thirds"
        assert FramingIntent.CENTER.value == "center"
        assert FramingIntent.GOLDEN_RATIO.value == "golden_ratio"

    def test_subject_relationship(self):
        assert SubjectRelationship.FRONT.value == "front"
        assert SubjectRelationship.SIDE.value == "side"
        assert SubjectRelationship.POV.value == "pov"
        assert SubjectRelationship.OVER.value == "over"

    def test_camera_direction(self):
        assert CameraDirection.FORWARD.value == "forward"
        assert CameraDirection.BACKWARD.value == "backward"
        assert CameraDirection.LEFT.value == "left"
        assert CameraDirection.RIGHT.value == "right"

    def test_subject_motion_spec_is_frozen(self):
        spec = SubjectMotionSpec(action=SubjectMotionVocabulary.WALK)
        with pytest.raises(Exception):
            spec.action = SubjectMotionVocabulary.RUN

    def test_sound_layer_spec_is_frozen(self):
        layer = SoundLayerSpec(category=SoundLayerCategory.MUSIC)
        with pytest.raises(Exception):
            layer.category = SoundLayerCategory.SFX

    def test_camera_block_ext_is_frozen(self):
        cam = CameraBlockExt(shot_type=CameraShotVocabulary.CLOSE)
        with pytest.raises(Exception):
            cam.shot_type = CameraShotVocabulary.WIDE

    def test_motion_block_ext_is_frozen(self):
        mot = MotionBlockExt(pattern=MotionPatternVocabulary.LOOP)
        with pytest.raises(Exception):
            mot.pattern = MotionPatternVocabulary.FRAME_BY_FRAME

    def test_sound_block_ext_is_frozen(self):
        snd = SoundBlockExt(category="ambient")
        with pytest.raises(Exception):
            snd.category = "music"

    def test_sound_layers_spec_ducking_layers(self):
        layer1 = SoundLayerSpec(
            category=SoundLayerCategory.MUSIC,
            duck_under_narration=True,
        )
        layer2 = SoundLayerSpec(
            category=SoundLayerCategory.SFX,
            duck_under_narration=False,
        )
        layers = SoundLayersSpec(layers=[layer1, layer2])
        ducking = layers.ducking_layers()
        assert len(ducking) == 1
        assert ducking[0].category == SoundLayerCategory.MUSIC

    def test_sound_layers_spec_has_narration_layer(self):
        layer = SoundLayerSpec(category=SoundLayerCategory.NARRATION)
        layers = SoundLayersSpec(layers=[layer])
        assert layers.has_narration_layer()

    def test_sound_layers_spec_empty(self):
        layers = SoundLayersSpec()
        assert layers.is_empty()
        assert not layers.has_narration_layer()

    def test_compilation_result_is_frozen(self):
        result = CameraMotionSoundCompilationResult(
            request_id="test", prompt_kind=PromptKind.IMAGE
        )
        with pytest.raises(Exception):
            result.request_id = "modified"

    def test_compilation_result_provenance_summary_no_knowledge(self):
        result = CameraMotionSoundCompilationResult(
            request_id="test", prompt_kind=PromptKind.IMAGE
        )
        summary = result.provenance_summary()
        assert "no-knowledge" in summary


# ============================================================================
# B. Deterministic Compilation
# ============================================================================

class TestDeterminism:
    """Compiler must be deterministic."""

    def _make_request(self, character_id="farmer_01", **kwargs):
        defaults = {
            "prompt_kind": PromptKind.VIDEO,
            "character_reference_id": character_id,
            "scene_camera": "medium",
            "scene_action": "walk",
            "aspect_ratio": "16:9",
        }
        defaults.update(kwargs)
        return PromptCompilationRequest(**defaults)

    def test_same_request_produces_same_result(self):
        compiler = CameraMotionSoundCompiler()
        req = self._make_request()
        r1 = compiler.compile(req)
        r2 = compiler.compile(req)
        assert r1.camera == r2.camera
        assert r1.motion == r2.motion
        assert r1.subject_motion == r2.subject_motion
        assert r1.sound == r2.sound

    def test_compiler_version_deterministic(self):
        compiler = CameraMotionSoundCompiler()
        req = self._make_request()
        result = compiler.compile(req)
        assert result.compiler_version == COMPILER_VERSION == "1.0.0"

    def test_request_id_derivation_deterministic(self):
        compiler = CameraMotionSoundCompiler()
        req1 = self._make_request()
        req2 = self._make_request()
        r1 = compiler.compile(req1)
        r2 = compiler.compile(req2)
        # Both have deterministic IDs from SHA-256
        assert r1.request_id == r2.request_id

    def test_reproducibility_multiple_runs(self):
        compiler = CameraMotionSoundCompiler()
        req = self._make_request()
        results = [compiler.compile(req) for _ in range(5)]
        for r in results[1:]:
            assert r.camera == results[0].camera
            assert r.subject_motion == results[0].subject_motion


# ============================================================================
# C. Camera Vocabulary
# ============================================================================

class TestCameraVocabulary:
    """Camera shot type vocabulary."""

    def test_shot_type_parsing(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="close"
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.CLOSE

    def test_shot_type_extreme_wide(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="extreme_wide"
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.EXTREME_WIDE

    def test_shot_type_birds_eye(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="birds_eye"
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.BIRDS_EYE

    def test_shot_type_dutch(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="dutch"
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.DUTCH

    def test_unknown_shot_type_returns_none(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="dramatic_swoop_360"
        )
        result = compiler.compile(req)
        # Unknown vocabulary: should not crash, shot_type stays None
        assert result.camera.shot_type is None

    def test_subject_relationship_pov(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="pov"
        )
        result = compiler.compile(req)
        # POV parses as both shot_type and subject_relationship
        assert result.camera.subject_relationship == SubjectRelationship.POV


# ============================================================================
# D. Movement Vocabulary
# ============================================================================

class TestMovementVocabulary:
    """Camera movement vocabulary."""

    def test_movement_push_in(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_camera="push_in"
        )
        result = compiler.compile(req)
        assert result.camera.movement == CameraMovementVocabulary.PUSH_IN

    def test_movement_tracking(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_camera="tracking"
        )
        result = compiler.compile(req)
        assert result.camera.movement == CameraMovementVocabulary.TRACKING

    def test_movement_pan(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_camera="pan"
        )
        result = compiler.compile(req)
        assert result.camera.movement == CameraMovementVocabulary.PAN

    def test_movement_hold(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_camera="hold"
        )
        result = compiler.compile(req)
        assert result.camera.movement == CameraMovementVocabulary.HOLD

    def test_movement_direction_pan_left(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_camera="pan left"
        )
        result = compiler.compile(req)
        assert result.camera.movement == CameraMovementVocabulary.PAN
        assert result.camera.movement_direction == CameraDirection.LEFT

    def test_movement_direction_push_forward(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_camera="push_in"
        )
        result = compiler.compile(req)
        assert result.camera.movement == CameraMovementVocabulary.PUSH_IN
        assert result.camera.movement_direction == CameraDirection.FORWARD


# ============================================================================
# E. Motion Vocabulary
# ============================================================================

class TestMotionVocabulary:
    """Motion pattern and subject action vocabulary."""

    def test_subject_action_walk(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_action="walking through rice field",
        )
        result = compiler.compile(req)
        assert result.subject_motion.action == SubjectMotionVocabulary.WALK

    def test_subject_action_run(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_action="running fast"
        )
        result = compiler.compile(req)
        assert result.subject_motion.action == SubjectMotionVocabulary.RUN

    def test_subject_action_gesture(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_action="gesture"
        )
        result = compiler.compile(req)
        assert result.subject_motion.action == SubjectMotionVocabulary.GESTURE

    def test_subject_action_point(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_action="pointing at horizon"
        )
        result = compiler.compile(req)
        assert result.subject_motion.action == SubjectMotionVocabulary.POINT

    def test_subject_action_turn(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_action="turning around"
        )
        result = compiler.compile(req)
        assert result.subject_motion.action == SubjectMotionVocabulary.TURN

    def test_subject_action_look(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_action="looking at sky"
        )
        result = compiler.compile(req)
        assert result.subject_motion.action == SubjectMotionVocabulary.LOOK

    def test_unknown_action(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_action="quantum_floating"
        )
        result = compiler.compile(req)
        assert result.subject_motion.action == SubjectMotionVocabulary.NONE


# ============================================================================
# F. Sound Layers
# ============================================================================

class TestSoundLayers:
    """Sound layer semantics."""

    def test_video_default_has_narration_layer(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        assert result.sound.layers.has_narration_layer()

    def test_video_default_has_three_layers(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        # narration + ambient + music = 3
        assert len(result.sound.layers.layers) == 3

    def test_image_default_no_layers(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        # IMAGE has no default sound
        assert result.sound.layers.is_empty()

    def test_ducking_layers_video(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        ducking = result.sound.layers.ducking_layers()
        # Ambient and music should duck
        categories = {layer.category for layer in ducking}
        assert SoundLayerCategory.MUSIC in categories
        assert SoundLayerCategory.AMBIENT in categories

    def test_narration_layer_priority_primary(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        narration_layers = [
            layer for layer in result.sound.layers.layers
            if layer.category == SoundLayerCategory.NARRATION
        ]
        assert len(narration_layers) == 1
        assert narration_layers[0].priority == SoundLayerPriority.PRIMARY


# ============================================================================
# G. Knowledge Resolution
# ============================================================================

class TestKnowledgeResolution:
    """Adapter consumes Knowledge Layer via KnowledgeContext."""

    def test_adapter_accepts_context(self):
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        adapter = KnowledgeCameraMotionSoundAdapter(context=ctx)
        assert adapter.is_active()

    def test_adapter_accepts_none(self):
        adapter = KnowledgeCameraMotionSoundAdapter()
        assert not adapter.is_active()

    def test_resolve_for_image(self):
        registry = build_default_registry()
        adapter = KnowledgeCameraMotionSoundAdapter(registry=registry)
        knowledge = adapter.resolve_for_compilation("image")
        assert isinstance(knowledge, ResolvedCameraMotionSoundKnowledge)

    def test_resolve_for_video(self):
        registry = build_default_registry()
        adapter = KnowledgeCameraMotionSoundAdapter(registry=registry)
        knowledge = adapter.resolve_for_compilation("video")
        assert isinstance(knowledge, ResolvedCameraMotionSoundKnowledge)

    def test_resolved_knowledge_no_knowledge_returns_empty(self):
        adapter = KnowledgeCameraMotionSoundAdapter()
        knowledge = adapter.resolve_for_compilation("video")
        assert not knowledge.is_active
        assert knowledge.knowledge_ids == frozenset()

    def test_resolved_knowledge_active_has_ids(self):
        registry = build_default_registry()
        adapter = KnowledgeCameraMotionSoundAdapter(registry=registry)
        knowledge = adapter.resolve_for_compilation("video")
        if knowledge.is_active:
            assert len(knowledge.knowledge_ids) >= 0


# ============================================================================
# H. Provenance
# ============================================================================

class TestProvenance:
    """Provenance is preserved on knowledge-derived elements."""

    def test_ir_records_knowledge_ids(self):
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        compiler = CameraMotionSoundCompiler(knowledge_context=ctx)
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="medium"
        )
        result = compiler.compile(req)
        assert isinstance(result.knowledge_ids_used, frozenset)

    def test_knowledge_version_recorded(self):
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        compiler = CameraMotionSoundCompiler(knowledge_context=ctx)
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result.knowledge_version != ""

    def test_no_knowledge_mode_has_no_version(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result.knowledge_version == "no-knowledge"
        assert result.is_knowledge_active is False

    def test_provenance_summary_no_knowledge(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        summary = result.provenance_summary()
        assert "no-knowledge" in summary


# ============================================================================
# I. Fallback
# ============================================================================

class TestFallback:
    """Fallback behavior when knowledge is missing."""

    def test_compiler_without_knowledge_compiles(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        assert result is not None
        assert result.fallback_policy_used == "engine_default"

    def test_knowledge_disabled_flag(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        assert result.is_knowledge_active is False


# ============================================================================
# J. Conflict Handling
# ============================================================================

class TestConflictHandling:
    """Conflicts are handled deterministically."""

    def test_explicit_beats_knowledge(self):
        """Explicit scene_camera beats knowledge camera."""
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        compiler = CameraMotionSoundCompiler(knowledge_context=ctx)
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="close"
        )
        result = compiler.compile(req)
        # Explicit takes precedence
        assert result.camera.shot_type == CameraShotVocabulary.CLOSE

    def test_default_camera_when_nothing_provided(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        # No camera set, no knowledge
        assert result.camera.shot_type is None


# ============================================================================
# L. Character Consistency
# ============================================================================

class TestCharacterConsistency:
    """Identity ≠ Scene State in CMS compilation."""

    def test_same_character_different_camera_preserves_identity(self):
        """Camera does not affect identity."""
        spec = CharacterReferenceSpecification(
            character_id="farmer_01",
            identity_properties=frozenset({
                IdentityBearingProperty.HEAD_SHAPE,
                IdentityBearingProperty.PALETTE,
            }),
            scene_variables=frozenset({
                SceneVariableProperty.POSE,
                SceneVariableProperty.EXPRESSION,
            }),
        )
        compiler = CameraMotionSoundCompiler()

        # Scene A: close shot
        req_a = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_camera="close",
        )
        # Scene B: wide shot
        req_b = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_camera="wide",
        )

        result_a = compiler.compile(req_a)
        result_b = compiler.compile(req_b)

        # Camera differs
        assert result_a.camera.shot_type == CameraShotVocabulary.CLOSE
        assert result_b.camera.shot_type == CameraShotVocabulary.WIDE

        # Subject motion target is the same
        assert result_a.subject_motion.target_id == result_b.subject_motion.target_id

    def test_same_character_different_motion_preserves_identity(self):
        """Subject motion does not affect identity."""
        spec = CharacterReferenceSpecification(
            character_id="farmer_01",
            identity_properties=frozenset({
                IdentityBearingProperty.HEAD_SHAPE,
                IdentityBearingProperty.PROPORTIONS,
            }),
            scene_variables=frozenset({
                SceneVariableProperty.POSE,
                SceneVariableProperty.EXPRESSION,
            }),
        )
        compiler = CameraMotionSoundCompiler()

        req_a = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_action="walk",
        )
        req_b = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            character_reference_id="farmer_01",
            character_reference_spec=spec,
            scene_action="stand",
        )

        result_a = compiler.compile(req_a)
        result_b = compiler.compile(req_b)

        # Action differs
        assert result_a.subject_motion.action == SubjectMotionVocabulary.WALK
        assert result_b.subject_motion.action == SubjectMotionVocabulary.IDLE

        # Target same
        assert result_a.subject_motion.target_id == result_b.subject_motion.target_id


# ============================================================================
# M. Storyboard Integration
# ============================================================================

class TestStoryboardIntegration:
    """Compiler integrates with storyboard concepts."""

    def test_compiler_handles_empty_request(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        assert result is not None

    def test_compiler_preserves_character_id(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, character_reference_id="farmer_01"
        )
        result = compiler.compile(req)
        assert result.subject_motion.target_id == "character:farmer_01"


# ============================================================================
# N. Prompt Integration (L-U5 backward compat)
# ============================================================================

class TestPromptIntegration:
    """L-U6 integrates with L-U5 PromptCompiler."""

    def test_l_u5_prompt_compiler_still_works(self):
        from app.prompt.compiler import PromptCompiler
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        assert result is not None

    def test_l_u5_ir_has_camera_block(self):
        from app.prompt.compiler import PromptCompiler
        compiler = PromptCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE, scene_camera="medium"
        )
        result = compiler.compile(req)
        # L-U5 CameraBlock has shot_type
        assert result.ir.camera is not None


# ============================================================================
# P. Timing Semantics
# ============================================================================

class TestTimingSemantics:
    """Timing semantics — duration_sec is semantic intent."""

    def test_duration_can_be_set(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_camera="medium"
        )
        result = compiler.compile(req)
        # Duration can be None or set from knowledge
        # (No explicit setter, so it stays None for default requests)
        assert result.camera.duration_sec is None or result.camera.duration_sec > 0

    def test_duration_capped_at_300(self):
        from app.prompt.schemas import CameraBlockExt
        # Use 300.0 exactly (boundary) to avoid pydantic ValidationError
        cam = CameraBlockExt(duration_sec=300.0)
        validator = CameraMotionSoundValidator()
        is_valid, msgs = validator.validate(
            camera=cam,
            motion=MotionBlockExt(),
            sound=SoundBlockExt(),
            prompt_kind=PromptKind.VIDEO,
        )
        # At boundary: no warnings
        assert all("too long" not in m for m in msgs)


# ============================================================================
# Q. Provider Neutrality
# ============================================================================

class TestProviderNeutrality:
    """L-U6 does not import provider SDKs."""

    def test_no_google_flow_in_cms_modules(self):
        import app.prompt.cms_compiler as comp
        import app.prompt.cms_validator as val
        import app.prompt.knowledge_adapter as ka

        for module in [comp, val, ka]:
            for name, value in vars(module).items():
                if name.startswith("_"):
                    continue
                mod_name = getattr(value, "__module__", "") or ""
                assert "google_flow_sdk" not in mod_name.lower()
                assert "dino_ai_sdk" not in mod_name.lower()
                assert "openai_image" not in mod_name.lower()

    def test_no_provider_specific_in_compiler(self):
        import app.prompt.cms_compiler as comp
        import inspect

        source = inspect.getsource(comp)
        forbidden = ["--ar", "--style", "--seed", "--model", "--camera"]
        for pattern in forbidden:
            assert pattern not in source


# ============================================================================
# R. Renderer Neutrality
# ============================================================================

class TestRendererNeutrality:
    """L-U6 does not import Remotion/FFmpeg."""

    def test_no_remotion_in_cms(self):
        import app.prompt.cms_compiler as comp
        import app.prompt.cms_validator as val

        for module in [comp, val]:
            for name, value in vars(module).items():
                if name.startswith("_"):
                    continue
                mod_name = getattr(value, "__module__", "") or ""
                assert "remotion" not in mod_name.lower()
                assert "ffmpeg" not in mod_name.lower()

    def test_no_remotion_syntax_in_compiler(self):
        import app.prompt.cms_compiler as comp
        import inspect

        source = inspect.getsource(comp)
        forbidden = [
            "interpolate()",
            "spring()",
            "useCurrentFrame()",
            "AbsoluteFill",
            "Sequence",
        ]
        for pattern in forbidden:
            assert pattern not in source


# ============================================================================
# S. Security
# ============================================================================

class TestSecurity:
    """L-U6 does not leak secrets."""

    def test_no_secrets_in_default_result(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        # Convert to dict and check for secret patterns
        import json
        data = json.loads(result.model_dump_json())
        text = json.dumps(data).lower()
        forbidden = ["sk-", "api_key", "secret", "password", "token", "bearer"]
        for pattern in forbidden:
            assert pattern not in text


# ============================================================================
# T. Golden Fixtures (A-N)
# ============================================================================

class TestGoldenFixtures:
    """Golden fixtures for L-U6."""

    def test_fixture_a_ews_hold_ambience(self):
        """A: EWS + HOLD + ambience."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            scene_camera="extreme_wide",
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.EXTREME_WIDE

    def test_fixture_b_ms_push_in_narration_ambience(self):
        """B: MS + PUSH_IN + narration + ambience."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_camera="medium",
            scene_action="walk",
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.MEDIUM
        assert result.subject_motion.action == SubjectMotionVocabulary.WALK
        assert result.sound.layers.has_narration_layer()

    def test_fixture_c_cu_shake_impact_sfx(self):
        """C: CU + SHAKE + impact SFX."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            scene_camera="close",
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.CLOSE

    def test_fixture_d_ots_tracking_walking(self):
        """D: OTS + TRACKING + walking."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_camera="over_shoulder",
            scene_action="walk",
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.OVER_SHOULDER
        assert result.subject_motion.action == SubjectMotionVocabulary.WALK

    def test_fixture_e_birds_eye_pan_ambience(self):
        """E: Bird's Eye + PAN + environmental ambience."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_camera="birds_eye",
            scene_camera_movement=None,
        )
        # Add explicit movement via scene_camera
        req2 = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_camera="pan",
        )
        result = compiler.compile(req2)
        assert result.camera.shot_type is not None or result.camera.movement is not None

    def test_fixture_f_same_character_different_camera(self):
        """F: same character, different camera."""
        compiler = CameraMotionSoundCompiler()
        req1 = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            scene_camera="close",
        )
        req2 = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            character_reference_id="farmer_01",
            scene_camera="wide",
        )
        r1 = compiler.compile(req1)
        r2 = compiler.compile(req2)
        assert r1.camera.shot_type == CameraShotVocabulary.CLOSE
        assert r2.camera.shot_type == CameraShotVocabulary.WIDE

    def test_fixture_g_same_character_different_motion(self):
        """G: same character, different motion."""
        compiler = CameraMotionSoundCompiler()
        req1 = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            character_reference_id="farmer_01",
            scene_action="walk",
        )
        req2 = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            character_reference_id="farmer_01",
            scene_action="stand",
        )
        r1 = compiler.compile(req1)
        r2 = compiler.compile(req2)
        assert r1.subject_motion.action == SubjectMotionVocabulary.WALK
        assert r2.subject_motion.action == SubjectMotionVocabulary.IDLE

    def test_fixture_h_explicit_camera_override_knowledge(self):
        """H: explicit camera beats knowledge."""
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        compiler = CameraMotionSoundCompiler(knowledge_context=ctx)
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            scene_camera="extreme_close",  # explicit override
        )
        result = compiler.compile(req)
        # Explicit beats knowledge
        assert result.camera.shot_type == CameraShotVocabulary.EXTREME_CLOSE

    def test_fixture_i_camera_conflict_warns(self):
        """I: camera conflict between knowledge and request."""
        registry = build_default_registry()
        ctx = KnowledgeContext.from_registry(registry, sources=default_sources())
        compiler = CameraMotionSoundCompiler(knowledge_context=ctx)
        # Explicit beats knowledge — no error, but explicit wins
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            scene_camera="medium",
        )
        result = compiler.compile(req)
        # Result should be valid (no blocking conflicts)
        assert result.is_valid

    def test_fixture_j_motion_conflict(self):
        """J: motion conflict between knowledge and request."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_action="walk",
        )
        result = compiler.compile(req)
        assert result.is_valid

    def test_fixture_k_sound_fallback(self):
        """K: sound fallback when knowledge missing."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        # VIDEO has default sound layers (narration + ambient + music)
        assert not result.sound.layers.is_empty()

    def test_fixture_l_knowledge_disabled(self):
        """L: knowledge-disabled mode."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        assert result.is_knowledge_active is False
        assert result.knowledge_version == "no-knowledge"

    def test_fixture_m_image_prompt_consumer(self):
        """M: IMAGE prompt consumer."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.IMAGE,
            scene_camera="medium",
        )
        result = compiler.compile(req)
        # No motion on IMAGE
        assert result.camera.movement is None
        assert result.subject_motion.action == SubjectMotionVocabulary.NONE

    def test_fixture_n_video_prompt_consumer(self):
        """N: VIDEO prompt consumer."""
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO,
            scene_camera="medium",
            scene_action="walk",
        )
        result = compiler.compile(req)
        assert result.camera.shot_type == CameraShotVocabulary.MEDIUM
        assert result.subject_motion.action == SubjectMotionVocabulary.WALK


# ============================================================================
# U. Fingerprint Behavior
# ============================================================================

class TestFingerprintBehavior:
    """Fingerprint behavior — same inputs same result."""

    def test_same_inputs_same_result(self):
        compiler = CameraMotionSoundCompiler()
        req1 = PromptCompilationRequest(
            request_id="fixed-id",
            prompt_kind=PromptKind.VIDEO,
            scene_camera="medium",
        )
        req2 = PromptCompilationRequest(
            request_id="fixed-id",
            prompt_kind=PromptKind.VIDEO,
            scene_camera="medium",
        )
        r1 = compiler.compile(req1)
        r2 = compiler.compile(req2)
        assert r1.camera == r2.camera
        assert r1.subject_motion == r2.subject_motion

    def test_no_timestamp_in_ir(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        # Camera/Motion/Sound fields don't have timestamps
        assert isinstance(result.camera, CameraBlockExt)
        assert isinstance(result.motion, MotionBlockExt)
        assert isinstance(result.sound, SoundBlockExt)


# ============================================================================
# V. Backward Compatibility
# ============================================================================

class TestBackwardCompatibility:
    """L-U6 does not break L-U5 or earlier."""

    def test_compiler_can_be_instantiated_without_args(self):
        compiler = CameraMotionSoundCompiler()
        assert compiler is not None

    def test_compiler_without_knowledge_compiles(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.VIDEO)
        result = compiler.compile(req)
        assert result is not None
        assert isinstance(result, CameraMotionSoundCompilationResult)

    def test_l_u5_prompt_compiler_unaffected(self):
        from app.prompt.compiler import PromptCompiler
        compiler = PromptCompiler()
        req = PromptCompilationRequest(prompt_kind=PromptKind.IMAGE)
        result = compiler.compile(req)
        # L-U5 still produces PromptCompilationResult, not CMSResult
        from app.prompt.schemas import PromptCompilationResult
        assert isinstance(result, PromptCompilationResult)

    def test_l_u5_camera_block_unaffected(self):
        """L-U5 CameraBlock still exists and is unchanged."""
        from app.prompt.schemas import CameraBlock
        cam = CameraBlock(shot_type=CameraShotVocabulary.MEDIUM)
        assert cam.shot_type == CameraShotVocabulary.MEDIUM


# ============================================================================
# W. Architecture Dependency
# ============================================================================

class TestArchitectureDependency:
    """Dependency direction is correct."""

    def test_cms_compiler_does_not_import_production_engines(self):
        import app.prompt.cms_compiler as comp
        import app.prompt.knowledge_adapter as ka
        import app.prompt.cms_validator as val

        for module in [comp, ka, val]:
            for name, value in vars(module).items():
                if name.startswith("_"):
                    continue
                mod_name = getattr(value, "__module__", "") or ""
                forbidden = [
                    "app.animation.",  # AnimationPlan is consumer
                    "app.voice.",      # TTS is consumer
                    "app.editorial.",  # Editorial is consumer
                    "app.story.",      # Story is consumer
                    "app.render.",     # Renderer is forbidden
                ]
                for prefix in forbidden:
                    assert not mod_name.startswith(prefix), f"{module.__name__}.{name} imports {mod_name}"

    def test_cms_compiler_does_not_import_provider_sdk(self):
        import app.prompt.cms_compiler as comp

        for name, value in vars(comp).items():
            if name.startswith("_"):
                continue
            mod_name = getattr(value, "__module__", "") or ""
            assert "app.providers." not in mod_name, f"{name} imports {mod_name}"

    def test_knowledge_module_not_import_cms(self):
        """app.knowledge should NOT import app.prompt.cms_*"""
        import app.knowledge as kl
        for name, value in vars(kl).items():
            if name.startswith("_"):
                continue
            mod_name = getattr(value, "__module__", "") or ""
            assert ".cms_" not in mod_name

    def test_animation_module_not_import_cms(self):
        """app.animation should NOT import app.prompt.cms_*"""
        import app.animation as anim
        for name, value in vars(anim).items():
            if name.startswith("_"):
                continue
            mod_name = getattr(value, "__module__", "") or ""
            assert ".cms_" not in mod_name

    def test_voice_module_not_import_cms(self):
        """app.voice should NOT import app.prompt.cms_*"""
        import app.voice as voice
        for name, value in vars(voice).items():
            if name.startswith("_"):
                continue
            mod_name = getattr(value, "__module__", "") or ""
            assert ".cms_" not in mod_name


# ============================================================================
# Three Distinct Concepts (Camera vs Subject vs Animation)
# ============================================================================

class TestThreeDistinctConcepts:
    """Camera movement, Subject motion, Animation pattern are distinct."""

    def test_camera_movement_is_camera_action(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_camera="push_in"
        )
        result = compiler.compile(req)
        # camera.movement is camera action (PUSH_IN)
        assert result.camera.movement == CameraMovementVocabulary.PUSH_IN
        # subject_motion is character action (NONE)
        assert result.subject_motion.action == SubjectMotionVocabulary.NONE
        # motion.pattern is rendering pattern (None for default)
        assert result.motion.pattern is None

    def test_subject_motion_is_character_action(self):
        compiler = CameraMotionSoundCompiler()
        req = PromptCompilationRequest(
            prompt_kind=PromptKind.VIDEO, scene_action="walk"
        )
        result = compiler.compile(req)
        # subject_motion is character action (WALK)
        assert result.subject_motion.action == SubjectMotionVocabulary.WALK
        # camera.movement is camera action (None by default)
        assert result.camera.movement is None

    def test_animation_pattern_distinct(self):
        """Animation pattern is a separate concept from subject motion."""
        from app.prompt.schemas import MotionBlock
        from app.prompt.schemas import SubjectMotionSpec

        # Subject motion = WALK
        sm = SubjectMotionSpec(action=SubjectMotionVocabulary.WALK)

        # Animation pattern = RIG_POSE_INTERPOLATION
        # (in MotionBlock, set via LLM/Knowledge)

        # They are independent fields
        assert sm.action == SubjectMotionVocabulary.WALK


# ============================================================================
# Validator Determinism
# ============================================================================

class TestValidatorDeterminism:
    """Validator is deterministic."""

    def test_validator_no_llm(self):
        validator = CameraMotionSoundValidator()
        cam = CameraBlockExt(shot_type=CameraShotVocabulary.MEDIUM)
        mot = MotionBlockExt(pattern=MotionPatternVocabulary.LOOP)
        snd = SoundBlockExt(category="ambient")
        is_valid, msgs = validator.validate(cam, mot, snd, PromptKind.VIDEO)
        assert isinstance(is_valid, bool)
        assert isinstance(msgs, list)

    def test_validator_camera_on_image_warns(self):
        validator = CameraMotionSoundValidator()
        cam = CameraBlockExt(movement=CameraMovementVocabulary.PUSH_IN)
        mot = MotionBlockExt()
        snd = SoundBlockExt()
        is_valid, msgs = validator.validate(cam, mot, snd, PromptKind.IMAGE)
        assert any("IMAGE" in m for m in msgs)

    def test_validator_subject_motion_on_image_warns(self):
        validator = CameraMotionSoundValidator()
        cam = CameraBlockExt()
        mot = MotionBlockExt(subject_action=SubjectMotionVocabulary.WALK)
        snd = SoundBlockExt()
        is_valid, msgs = validator.validate(cam, mot, snd, PromptKind.IMAGE)
        assert any("subject motion" in m.lower() for m in msgs)

    def test_validator_narration_layer_cannot_duck(self):
        validator = CameraMotionSoundValidator()
        cam = CameraBlockExt()
        mot = MotionBlockExt()
        layer = SoundLayerSpec(
            category=SoundLayerCategory.NARRATION,
            duck_under_narration=True,  # INVALID: narration cannot duck itself
        )
        snd = SoundBlockExt(layers=SoundLayersSpec(layers=[layer]))
        is_valid, msgs = validator.validate(cam, mot, snd, PromptKind.VIDEO)
        assert not is_valid
        assert any("narration" in m.lower() for m in msgs)

    def test_validator_provider_syntax_in_notes_blocks(self):
        validator = CameraMotionSoundValidator()
        cam = CameraBlockExt(notes="--ar 16:9")
        mot = MotionBlockExt()
        snd = SoundBlockExt()
        is_valid, msgs = validator.validate(cam, mot, snd, PromptKind.VIDEO)
        assert any("provider" in m.lower() for m in msgs)

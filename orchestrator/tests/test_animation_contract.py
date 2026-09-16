"""
PROMPT 7 — Animation Engine contract tests.

Verifies:
- AnimationPlan schema (validation, serialization)
- AnimationTarget canonical ID format
- Keyframe ordering
- Track targeting
- PoseSegment timing
- PropInteraction anchors
- Interpolation values
"""
from __future__ import annotations

from app.animation.compiler import AnimationCompileError, AnimationCompiler
from app.animation.schemas import (
    ActionLabel,
    AnimationEvent,
    AnimationPlan,
    AnimationPlanMetadata,
    AnimationTarget,
    AnimationTrack,
    CameraAnimation,
    CharacterAnimation,
    Interpolation,
    Keyframe,
    PoseSegment,
    PoseTransition,
    PropAnimation,
    PropInteraction,
    TargetKind,
    TransformProperty,
    WalkCycleParams,
)


def test_animation_plan_minimal_valid():
    """Empty characters/props, just metadata + duration."""
    plan = AnimationPlan(
        metadata=AnimationPlanMetadata(
            plan_id="p1", scene_id="s1", duration_sec=5.0,
        ),
        duration_sec=5.0,
    )
    assert plan.duration_sec == 5.0
    assert plan.characters == []
    assert plan.props == []
    assert plan.warnings == []
    assert plan.failures == []


def test_animation_plan_rejects_zero_duration():
    import pytest
    with pytest.raises(ValueError):
        AnimationPlan(
            metadata=AnimationPlanMetadata(
                plan_id="p1", scene_id="s1", duration_sec=0.0,
            ),
            duration_sec=0.0,
        )


def test_animation_target_character_helper():
    t = AnimationTarget.for_character("alice")
    assert t.target_id == "character:alice"
    assert t.kind == TargetKind.CHARACTER


def test_animation_target_prop_helper():
    t = AnimationTarget.for_prop("spear", instance_id="i1")
    assert t.target_id == "prop:spear"
    assert t.instance_id == "i1"


def test_animation_target_camera_helper():
    t = AnimationTarget.for_camera()
    assert t.target_id == "camera:main"
    assert t.kind == TargetKind.CAMERA


def test_animation_target_rejects_whitespace():
    import pytest
    with pytest.raises(ValueError):
        AnimationTarget(target_id="char alice", kind=TargetKind.CHARACTER)


def test_keyframe_rejects_negative_time():
    import pytest
    with pytest.raises(ValueError):
        Keyframe(time_sec=-1.0, value=0.0)


def test_animation_track_sorts_keyframes():
    track = AnimationTrack(
        track_id="t1",
        target=AnimationTarget.for_character("alice"),
        property=TransformProperty.X,
        keyframes=[
            Keyframe(time_sec=2.0, value=20.0),
            Keyframe(time_sec=1.0, value=10.0),
            Keyframe(time_sec=3.0, value=30.0),
        ],
    )
    times = [kf.time_sec for kf in track.keyframes]
    assert times == [1.0, 2.0, 3.0]


def test_animation_track_priority_bounds():
    import pytest
    with pytest.raises(ValueError):
        AnimationTrack(
            track_id="t1",
            target=AnimationTarget.for_character("alice"),
            property=TransformProperty.X,
            priority=200,
        )


def test_pose_segment_rejects_zero_duration():
    import pytest
    with pytest.raises(ValueError):
        PoseSegment(
            start_sec=1.0, end_sec=1.0, action=ActionLabel.WALK, pose="walk",
        )


def test_prop_interaction_requires_time_range():
    import pytest
    with pytest.raises(ValueError):
        PropInteraction(
            interaction_id="i1",
            character_id="alice", prop_id="spear",
            character_anchor="hand_left", prop_anchor="grip",
            start_sec=2.0, end_sec=1.0,
        )


def test_animation_event_beyond_duration_is_validated_at_compile():
    """Events beyond duration should be caught at compile time, not construction."""
    compiler = AnimationCompiler()
    plan = AnimationPlan(
        metadata=AnimationPlanMetadata(plan_id="p", scene_id="s", duration_sec=2.0),
        duration_sec=2.0,
        events=[AnimationEvent(event_id="e1", at_sec=10.0, kind="x")],
    )
    import pytest
    with pytest.raises(AnimationCompileError):
        compiler.compile(plan)


def test_animation_plan_serialization_roundtrip():
    plan = AnimationPlan(
        metadata=AnimationPlanMetadata(plan_id="p1", scene_id="s1", duration_sec=5.0),
        duration_sec=5.0,
        camera=CameraAnimation(start_pan_x=0.3, end_pan_x=0.7, easing=Interpolation.EASE_IN_OUT),
        characters=[CharacterAnimation(
            character_id="alice",
            pose_sequence=[PoseSegment(start_sec=0.0, end_sec=2.0, action=ActionLabel.WALK, pose="walk")],
            walk_cycle_params=WalkCycleParams(),
        )],
        props=[PropAnimation(prop_id="spear")],
    )
    as_dict = plan.to_dict()
    plan2 = AnimationPlan.model_validate(as_dict)
    assert plan2.camera.start_pan_x == 0.3
    assert plan2.characters[0].character_id == "alice"
    assert plan2.props[0].prop_id == "spear"


def test_animation_target_kind_required():
    import pytest
    with pytest.raises(ValueError):
        AnimationTarget(target_id="character:alice", kind=None)  # type: ignore


def test_pose_transition_enum_values():
    assert PoseTransition.CUT.value == "cut"
    assert PoseTransition.SWAP.value == "swap"
    assert PoseTransition.FADE.value == "fade"


def test_interpolation_enum_values():
    assert Interpolation.LINEAR.value == "linear"
    assert Interpolation.EASE_IN.value == "ease_in"
    assert Interpolation.EASE_OUT.value == "ease_out"
    assert Interpolation.EASE_IN_OUT.value == "ease_in_out"
    assert Interpolation.HOLD.value == "hold"

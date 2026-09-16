"""
PROMPT 7 — Animation determinism & failure tests.

Verifies:
- Same plan → same normalized output
- Replayability: rendering frame N twice gives same state
- Seekability: frame N is computed without playing from frame 0
- Failure handling: unknown target, missing anchor, invalid timeline
"""
from __future__ import annotations

import pytest

from app.animation.compiler import (
    AnimationCompileError,
    AnimationCompiler,
)
from app.animation.interpolation import interpolate_keyframes, interpolate_value
from app.animation.schemas import (
    ActionLabel,
    AnimationEvent,
    AnimationPlan,
    AnimationPlanMetadata,
    AnimationTarget,
    AnimationTrack,
    CharacterAnimation,
    Interpolation,
    Keyframe,
    PoseSegment,
    PropAnimation,
    PropInteraction,
    TargetKind,
    TransformProperty,
)


# ---- Determinism ----

def test_same_plan_same_normalized_output():
    """The same plan → byte-equivalent normalized representation."""
    compiler = AnimationCompiler(known_characters={"alice"})
    plan = AnimationPlan(
        metadata=AnimationPlanMetadata(plan_id="p", scene_id="s", duration_sec=5.0),
        duration_sec=5.0,
        characters=[
            CharacterAnimation(
                character_id="alice",
                pose_sequence=[
                    PoseSegment(start_sec=0.0, end_sec=5.0, action=ActionLabel.WALK, pose="walk"),
                ],
            ),
        ],
        tracks=[
            AnimationTrack(
                track_id="t1",
                target=AnimationTarget.for_character("alice"),
                property=TransformProperty.X,
                keyframes=[
                    Keyframe(time_sec=3.0, value=30.0),
                    Keyframe(time_sec=1.0, value=10.0),
                ],
            ),
        ],
    )
    compiler.compile(plan)
    output1 = plan.to_dict()

    plan2 = AnimationPlan.model_validate(output1)
    compiler2 = AnimationCompiler(known_characters={"alice"})
    compiler2.compile(plan2)
    output2 = plan2.to_dict()

    # Compare sorted JSON for byte-equivalence.
    import json
    assert json.dumps(output1, sort_keys=True) == json.dumps(output2, sort_keys=True)


def test_interpolation_deterministic_across_runs():
    """Same inputs → same outputs, regardless of run."""
    results = []
    for _ in range(5):
        v = interpolate_value(0.0, 100.0, 0.5, Interpolation.EASE_IN_OUT)
        results.append(v)
    assert len(set(results)) == 1


# ---- Replayability ----

def test_keyframe_replayability():
    """Computing the same keyframe twice gives the same result."""
    kfs = [
        Keyframe(time_sec=0.0, value=0.0, interpolation=Interpolation.LINEAR),
        Keyframe(time_sec=1.0, value=100.0, interpolation=Interpolation.LINEAR),
    ]
    results = [interpolate_keyframes(kfs, 0.5) for _ in range(10)]
    assert len(set(results)) == 1


# ---- Seekability ----

def test_interpolation_seekability():
    """Computing frame N is independent of frames 0..N-1."""
    kfs = [
        Keyframe(time_sec=0.0, value=0.0, interpolation=Interpolation.LINEAR),
        Keyframe(time_sec=10.0, value=100.0, interpolation=Interpolation.LINEAR),
    ]
    # Forward playback: compute each frame in order.
    forward = [interpolate_keyframes(kfs, t) for t in range(11)]
    # Reverse seek: compute each frame in reverse order.
    reverse = [interpolate_keyframes(kfs, t) for t in reversed(range(11))]
    assert forward == list(reversed(reverse))


# ---- Failure handling ----

def test_failure_unknown_target():
    compiler = AnimationCompiler(known_characters={"alice"})
    plan = AnimationPlan(
        metadata=AnimationPlanMetadata(plan_id="p", scene_id="s", duration_sec=5.0),
        duration_sec=5.0,
        characters=[
            CharacterAnimation(
                character_id="alice",
                motion_tracks=[
                    AnimationTrack(
                        track_id="t1",
                        target=AnimationTarget(target_id="character:bob", kind=TargetKind.CHARACTER),
                        property=TransformProperty.X,
                        keyframes=[Keyframe(time_sec=0.0, value=0.0)],
                    ),
                ],
            ),
        ],
    )
    with pytest.raises(AnimationCompileError):
        compiler.compile(plan)


def test_failure_missing_anchor():
    compiler = AnimationCompiler(
        known_characters={"alice"},
        known_props={"spear"},
        character_skeleton={"alice": {"hand_left"}},
        prop_anchors={"spear": {"grip"}},
    )
    plan = AnimationPlan(
        metadata=AnimationPlanMetadata(plan_id="p", scene_id="s", duration_sec=5.0),
        duration_sec=5.0,
        characters=[CharacterAnimation(character_id="alice")],
        props=[
            PropAnimation(
                prop_id="spear",
                interactions=[
                    PropInteraction(
                        interaction_id="i1",
                        character_id="alice", prop_id="spear",
                        character_anchor="FOOT",  # not in skeleton
                        prop_anchor="grip",
                        start_sec=0.0, end_sec=1.0,
                    ),
                ],
            ),
        ],
    )
    with pytest.raises(AnimationCompileError) as exc_info:
        compiler.compile(plan)
    assert any("FOOT" in e for e in exc_info.value.errors)


def test_failure_invalid_timeline_event_beyond_duration():
    compiler = AnimationCompiler()
    plan = AnimationPlan(
        metadata=AnimationPlanMetadata(plan_id="p", scene_id="s", duration_sec=2.0),
        duration_sec=2.0,
        events=[AnimationEvent(event_id="e", at_sec=100.0, kind="x")],
    )
    with pytest.raises(AnimationCompileError):
        compiler.compile(plan)


def test_failure_invalid_pose_segment():
    """PoseSegment with end_sec <= start_sec fails at construction time."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        PoseSegment(start_sec=3.0, end_sec=1.0, action=ActionLabel.WALK, pose="walk")


def test_failure_unsupported_interpolation_not_possible():
    """Interpolation enum rejects non-canonical modes."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        Keyframe(time_sec=0.0, value=0.0, interpolation="bezier")  # type: ignore


def test_failure_empty_interaction_range():
    """PropInteraction with end_sec == start_sec fails at construction time."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        PropInteraction(
            interaction_id="i1",
            character_id="alice", prop_id="spear",
            character_anchor="hand_left", prop_anchor="grip",
            start_sec=2.0, end_sec=2.0,
        )

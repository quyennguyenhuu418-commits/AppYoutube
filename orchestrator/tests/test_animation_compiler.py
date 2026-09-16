"""
PROMPT 7 — Animation Compiler tests.

Verifies:
- Validation: unknown targets, missing anchors, invalid times
- Normalization: keyframe sorting, target ID lowercasing
- Conflict resolution: highest-priority track wins
- compiler_from_packages helper
"""
from __future__ import annotations

import pytest

from app.animation.compiler import (
    AnimationCompileError,
    AnimationCompiler,
    compiler_from_packages,
)
from app.animation.schemas import (
    AnimationEvent,
    AnimationPlan,
    AnimationPlanMetadata,
    AnimationTarget,
    AnimationTrack,
    CharacterAnimation,
    Interpolation,
    Keyframe,
    PoseSegment,
    ActionLabel,
    PropAnimation,
    PropInteraction,
    TargetKind,
    TransformProperty,
    WalkCycleParams,
)


def make_plan(**overrides) -> AnimationPlan:
    defaults = dict(
        metadata=AnimationPlanMetadata(plan_id="p", scene_id="s", duration_sec=5.0),
        duration_sec=5.0,
    )
    defaults.update(overrides)
    return AnimationPlan(**defaults)


# ---- Reference validation ----

def test_compiler_passes_valid_plan():
    compiler = AnimationCompiler(
        known_characters={"alice"},
        known_props={"spear"},
    )
    plan = make_plan(
        characters=[
            CharacterAnimation(character_id="alice", pose_sequence=[
                PoseSegment(start_sec=0.0, end_sec=5.0, action=ActionLabel.STAND, pose="stand"),
            ]),
        ],
        props=[PropAnimation(prop_id="spear")],
    )
    compiler.compile(plan)
    assert len(plan.failures) == 0


def test_compiler_rejects_unknown_character():
    compiler = AnimationCompiler(known_characters={"alice"})
    plan = make_plan(
        characters=[CharacterAnimation(character_id="bob")],
    )
    with pytest.raises(AnimationCompileError) as exc_info:
        compiler.compile(plan)
    assert any("bob" in e for e in exc_info.value.errors)


def test_compiler_rejects_unknown_prop():
    compiler = AnimationCompiler(known_props={"spear"})
    plan = make_plan(
        props=[PropAnimation(prop_id="unknown_prop")],
    )
    with pytest.raises(AnimationCompileError) as exc_info:
        compiler.compile(plan)
    assert any("unknown_prop" in e for e in exc_info.value.errors)


# ---- Interaction validation ----

def test_compiler_validates_character_anchor():
    compiler = AnimationCompiler(
        known_characters={"alice"},
        known_props={"spear"},
        character_skeleton={"alice": {"hand_left", "head"}},
        prop_anchors={"spear": {"grip"}},
    )
    plan = make_plan(
        characters=[CharacterAnimation(character_id="alice")],
        props=[
            PropAnimation(
                prop_id="spear",
                interactions=[
                    PropInteraction(
                        interaction_id="i1",
                        character_id="alice", prop_id="spear",
                        character_anchor="elbow",  # NOT in skeleton
                        prop_anchor="grip",
                        start_sec=0.0, end_sec=1.0,
                    ),
                ],
            ),
        ],
    )
    with pytest.raises(AnimationCompileError) as exc_info:
        compiler.compile(plan)
    assert any("elbow" in e for e in exc_info.value.errors)


def test_compiler_validates_prop_anchor():
    compiler = AnimationCompiler(
        known_characters={"alice"},
        known_props={"spear"},
        character_skeleton={"alice": {"hand_left"}},
        prop_anchors={"spear": {"grip"}},
    )
    plan = make_plan(
        characters=[CharacterAnimation(character_id="alice")],
        props=[
            PropAnimation(
                prop_id="spear",
                interactions=[
                    PropInteraction(
                        interaction_id="i1",
                        character_id="alice", prop_id="spear",
                        character_anchor="hand_left",
                        prop_anchor="nub",  # NOT on prop
                        start_sec=0.0, end_sec=1.0,
                    ),
                ],
            ),
        ],
    )
    with pytest.raises(AnimationCompileError) as exc_info:
        compiler.compile(plan)
    assert any("nub" in e for e in exc_info.value.errors)


def test_compiler_passes_valid_interaction():
    compiler = AnimationCompiler(
        known_characters={"alice"},
        known_props={"spear"},
        character_skeleton={"alice": {"hand_left"}},
        prop_anchors={"spear": {"grip"}},
    )
    plan = make_plan(
        characters=[CharacterAnimation(character_id="alice")],
        props=[
            PropAnimation(
                prop_id="spear",
                interactions=[
                    PropInteraction(
                        interaction_id="i1",
                        character_id="alice", prop_id="spear",
                        character_anchor="hand_left",
                        prop_anchor="grip",
                        start_sec=0.0, end_sec=1.0,
                    ),
                ],
            ),
        ],
    )
    compiler.compile(plan)
    assert len(plan.failures) == 0


# ---- Temporal validation ----

def test_compiler_rejects_event_beyond_duration():
    compiler = AnimationCompiler()
    plan = make_plan(
        events=[AnimationEvent(event_id="e1", at_sec=10.0, kind="x")],
    )
    with pytest.raises(AnimationCompileError) as exc_info:
        compiler.compile(plan)
    assert any("exceeds plan duration" in e for e in exc_info.value.errors)


def test_compiler_rejects_negative_keyframe_time():
    compiler = AnimationCompiler()
    # Pydantic enforces non-negative at construction.
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        Keyframe(time_sec=-1.0, value=0.0)


# ---- Normalization ----

def test_compiler_sorts_keyframes_within_tracks():
    compiler = AnimationCompiler()
    plan = make_plan(
        tracks=[
            AnimationTrack(
                track_id="t1",
                target=AnimationTarget.for_camera(),
                property=TransformProperty.X,
                keyframes=[
                    Keyframe(time_sec=3.0, value=30.0),
                    Keyframe(time_sec=1.0, value=10.0),
                    Keyframe(time_sec=2.0, value=20.0),
                ],
            ),
        ],
    )
    compiler.compile(plan)
    times = [kf.time_sec for kf in plan.tracks[0].keyframes]
    assert times == [1.0, 2.0, 3.0]


def test_compiler_normalizes_target_id_to_lowercase():
    compiler = AnimationCompiler(known_characters={"alice"})
    plan = make_plan(
        characters=[
            CharacterAnimation(
                character_id="alice",
                motion_tracks=[
                    AnimationTrack(
                        track_id="t1",
                        target=AnimationTarget(target_id="character:alice", kind=TargetKind.CHARACTER),
                        property=TransformProperty.X,
                        keyframes=[Keyframe(time_sec=0.0, value=0.0)],
                    ),
                ],
            ),
        ],
    )
    compiler.compile(plan)
    assert plan.characters[0].motion_tracks[0].target.target_id == "character:alice"


def test_compiler_sorts_events_by_time():
    compiler = AnimationCompiler()
    plan = make_plan(
        events=[
            AnimationEvent(event_id="e1", at_sec=3.0, kind="x"),
            AnimationEvent(event_id="e2", at_sec=1.0, kind="y"),
            AnimationEvent(event_id="e3", at_sec=2.0, kind="z"),
        ],
    )
    compiler.compile(plan)
    assert [e.event_id for e in plan.events] == ["e2", "e3", "e1"]


# ---- Conflict resolution ----

def test_resolve_track_conflicts_higher_priority_wins():
    compiler = AnimationCompiler()
    low = AnimationTrack(
        track_id="t_low",
        target=AnimationTarget.for_character("alice"),
        property=TransformProperty.X,
        priority=0,
        keyframes=[Keyframe(time_sec=0.0, value=0.0)],
    )
    high = AnimationTrack(
        track_id="t_high",
        target=AnimationTarget.for_character("alice"),
        property=TransformProperty.X,
        priority=10,
        keyframes=[Keyframe(time_sec=0.0, value=10.0)],
    )
    survivors = compiler.resolve_track_conflicts([low, high])
    assert len(survivors) == 1
    assert survivors[0].track_id == "t_high"


def test_resolve_track_conflicts_ties_by_track_id():
    compiler = AnimationCompiler()
    a = AnimationTrack(
        track_id="aaa",
        target=AnimationTarget.for_character("alice"),
        property=TransformProperty.X,
        priority=0,
        keyframes=[],
    )
    b = AnimationTrack(
        track_id="bbb",
        target=AnimationTarget.for_character("alice"),
        property=TransformProperty.X,
        priority=0,
        keyframes=[],
    )
    survivors = compiler.resolve_track_conflicts([a, b])
    assert survivors[0].track_id == "aaa"


# ---- compiler_from_packages helper ----

def test_compiler_from_packages_populates_knowns():
    class FakeCharSystemPackage:
        characters = [
            type("C", (), {"character_id": "alice", "skeleton": type("S", (), {"joints": [type("J", (), {"joint_id": "head"})(), type("J", (), {"joint_id": "hand_left"})()]})()})(),
        ]

    class FakeAssetSystemPackage:
        environments = [type("E", (), {"asset_id": "ice_age_plains"})()]
        props = [
            type("P", (), {
                "asset_id": "spear",
                "anchor_points": [type("A", (), {"anchor_id": "grip"})()],
            })(),
        ]

    compiler = compiler_from_packages(
        character_system_package=FakeCharSystemPackage(),
        asset_system_package=FakeAssetSystemPackage(),
    )
    assert "alice" in compiler.known_characters
    assert "spear" in compiler.known_props
    assert "ice_age_plains" in compiler.known_environments
    assert "head" in compiler.character_skeleton["alice"]
    assert "hand_left" in compiler.character_skeleton["alice"]
    assert "grip" in compiler.prop_anchors["spear"]

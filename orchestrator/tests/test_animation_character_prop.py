"""
PROMPT 7 — Character & Prop animation tests.

Verifies:
- Pose transition behavior (segments, walk cycle)
- Walk cycle parameters
- Prop interaction (attach / detach / hold / release)
- Action mapper
"""
from __future__ import annotations

from app.animation.action_mapper import apply_action_to_character, map_action
from app.animation.schemas import (
    ActionLabel,
    CharacterAnimation,
    Interpolation,
    PoseSegment,
    PropAnimation,
    PropInteraction,
    WalkCycleParams,
)


# ---- PoseSegment / CharacterAnimation ----

def test_character_animation_with_pose_sequence():
    char = CharacterAnimation(
        character_id="alice",
        pose_sequence=[
            PoseSegment(start_sec=0.0, end_sec=2.0, action=ActionLabel.WALK, pose="walk"),
            PoseSegment(start_sec=2.0, end_sec=4.0, action=ActionLabel.POINT, pose="point"),
        ],
    )
    assert len(char.pose_sequence) == 2
    assert char.character_id == "alice"


def test_walk_cycle_params_defaults():
    p = WalkCycleParams()
    assert p.walk_speed > 0
    assert p.step_frequency > 0
    assert p.stride_length >= 0
    assert p.body_bob >= 0
    assert p.arm_swing >= 0


def test_walk_cycle_params_bounds():
    import pytest
    with pytest.raises(ValueError):
        WalkCycleParams(walk_speed=-1.0)


# ---- Action mapper ----

def test_action_mapper_walk():
    seg, walk, warnings = map_action("walks", 0.0, 5.0, 5.0)
    assert seg.action == ActionLabel.WALK
    assert seg.pose == "walk"
    assert walk is not None
    assert len(warnings) == 0


def test_action_mapper_runs_away():
    seg, walk, warnings = map_action("runs away", 0.0, 5.0, 5.0)
    assert seg.action == ActionLabel.RUN
    assert walk is not None
    assert walk.walk_speed > 100  # runs away is faster


def test_action_mapper_point():
    seg, walk, _ = map_action("points at", 0.0, 1.0, 1.0)
    assert seg.action == ActionLabel.POINT
    assert walk is None


def test_action_mapper_think():
    seg, walk, _ = map_action("thinks", 0.0, 1.0, 1.0)
    assert seg.action == ActionLabel.THINK


def test_action_mapper_celebrate():
    seg, walk, _ = map_action("celebrates", 0.0, 1.0, 1.0)
    assert seg.action == ActionLabel.CELEBRATE


def test_action_mapper_unknown_warns_but_does_not_randomize():
    """Unknown actions → STAND + warning, NEVER random motion."""
    seg, walk, warnings = map_action("xyzzy", 0.0, 1.0, 1.0)
    assert seg.action == ActionLabel.STAND
    assert len(warnings) == 1
    assert "xyzzy" in warnings[0]
    assert walk is None


def test_action_mapper_partial_match():
    """Longest-prefix matching for partial phrases."""
    seg, _, _ = map_action("walks toward village", 0.0, 5.0, 5.0)
    assert seg.action == ActionLabel.WALK


def test_apply_action_to_character():
    char = CharacterAnimation(character_id="alice")
    warnings = []
    apply_action_to_character(char, "walks", 0.0, 5.0, warnings)
    assert len(char.pose_sequence) == 1
    assert char.pose_sequence[0].action == ActionLabel.WALK
    assert char.walk_cycle_params is not None


def test_apply_action_to_character_accumulates():
    char = CharacterAnimation(character_id="alice")
    warnings = []
    apply_action_to_character(char, "stands", 0.0, 2.0, warnings)
    apply_action_to_character(char, "walks", 2.0, 4.0, warnings)
    assert len(char.pose_sequence) == 2


# ---- PropInteraction ----

def test_prop_interaction_attach():
    i = PropInteraction(
        interaction_id="i1",
        character_id="alice", prop_id="spear",
        character_anchor="hand_left", prop_anchor="grip",
        start_sec=0.0, end_sec=2.0,
        kind="attach",
    )
    assert i.kind == "attach"
    assert i.start_sec == 0.0
    assert i.end_sec == 2.0


def test_prop_interaction_hold():
    i = PropInteraction(
        interaction_id="i1",
        character_id="alice", prop_id="spear",
        character_anchor="hand_left", prop_anchor="grip",
        start_sec=0.0, end_sec=2.0,
        kind="hold",
    )
    assert i.kind == "hold"


def test_prop_interaction_release():
    i = PropInteraction(
        interaction_id="i1",
        character_id="alice", prop_id="spear",
        character_anchor="hand_left", prop_anchor="grip",
        start_sec=5.0, end_sec=6.0,
        kind="release",
    )
    assert i.kind == "release"


def test_prop_animation_with_interactions():
    pa = PropAnimation(
        prop_id="spear",
        interactions=[
            PropInteraction(
                interaction_id="i1",
                character_id="alice", prop_id="spear",
                character_anchor="hand_left", prop_anchor="grip",
                start_sec=0.0, end_sec=2.0,
                kind="hold",
            ),
        ],
    )
    assert len(pa.interactions) == 1

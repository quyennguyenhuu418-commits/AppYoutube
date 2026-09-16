"""Action Mapper — semantic narrative → canonical animation clips.

PROMPT 7 §14: Map semantic storyboard actions to canonical animation clips.

The action mapper is a deterministic lookup table from a narrative verb
phrase (or canonical ActionLabel) to a deterministic animation clip
(PoseSegment + optional WalkCycleParams).

Unknown actions must not produce random motion. They are mapped to a
SAFE default (ActionLabel.STAND) and a warning is recorded.
"""
from __future__ import annotations

from app.animation.schemas import (
    ActionLabel,
    CharacterAnimation,
    Interpolation,
    PoseSegment,
    WalkCycleParams,
)


# ============================================================================
# Mapping table
# ============================================================================

# Narrative verbs → canonical ActionLabel + pose + optional walk params.
_NARRATIVE_MAP: dict[str, tuple[ActionLabel, str, WalkCycleParams | None]] = {
    # walks
    "walk": (ActionLabel.WALK, "walk",
              WalkCycleParams(walk_speed=60.0, step_frequency=2.0,
                              stride_length=0.15, body_bob=0.02, arm_swing=0.05)),
    "walks": (ActionLabel.WALK, "walk",
               WalkCycleParams(walk_speed=60.0, step_frequency=2.0,
                               stride_length=0.15, body_bob=0.02, arm_swing=0.05)),
    "walks toward": (ActionLabel.WALK, "walk",
                      WalkCycleParams(walk_speed=60.0, step_frequency=2.0,
                                      stride_length=0.15, body_bob=0.02, arm_swing=0.05)),
    "walking": (ActionLabel.WALK, "walk",
                 WalkCycleParams(walk_speed=60.0, step_frequency=2.0,
                                 stride_length=0.15, body_bob=0.02, arm_swing=0.05)),
    "strolls": (ActionLabel.WALK, "walk",
                 WalkCycleParams(walk_speed=40.0, step_frequency=1.5,
                                 stride_length=0.12, body_bob=0.015, arm_swing=0.04)),
    # runs
    "run": (ActionLabel.RUN, "run",
             WalkCycleParams(walk_speed=120.0, step_frequency=3.5,
                             stride_length=0.25, body_bob=0.04, arm_swing=0.10)),
    "runs": (ActionLabel.RUN, "run",
              WalkCycleParams(walk_speed=120.0, step_frequency=3.5,
                              stride_length=0.25, body_bob=0.04, arm_swing=0.10)),
    "runs away": (ActionLabel.RUN, "run",
                   WalkCycleParams(walk_speed=140.0, step_frequency=4.0,
                                   stride_length=0.28, body_bob=0.05, arm_swing=0.12)),
    "running": (ActionLabel.RUN, "run",
                 WalkCycleParams(walk_speed=120.0, step_frequency=3.5,
                                 stride_length=0.25, body_bob=0.04, arm_swing=0.10)),
    "sprints": (ActionLabel.RUN, "run",
                 WalkCycleParams(walk_speed=160.0, step_frequency=4.5,
                                 stride_length=0.30, body_bob=0.06, arm_swing=0.13)),
    # poses
    "point": (ActionLabel.POINT, "point", None),
    "points": (ActionLabel.POINT, "point", None),
    "points at": (ActionLabel.POINT, "point", None),
    "points to": (ActionLabel.POINT, "point", None),
    "thinks": (ActionLabel.THINK, "think", None),
    "think": (ActionLabel.THINK, "think", None),
    "celebrates": (ActionLabel.CELEBRATE, "celebrate", None),
    "celebrate": (ActionLabel.CELEBRATE, "celebrate", None),
    "hides": (ActionLabel.HIDE, "hide", None),
    "hide": (ActionLabel.HIDE, "hide", None),
    "sits": (ActionLabel.SIT, "sit", None),
    "sit": (ActionLabel.SIT, "sit", None),
    # transitions
    "enters": (ActionLabel.ENTER, "stand", None),
    "enter": (ActionLabel.ENTER, "stand", None),
    "exits": (ActionLabel.EXIT, "stand", None),
    "exit": (ActionLabel.EXIT, "stand", None),
    # static
    "stands": (ActionLabel.STAND, "stand", None),
    "stand": (ActionLabel.STAND, "stand", None),
}


def map_action(
    action_phrase: str,
    start_sec: float,
    end_sec: float,
    duration_sec: float,
) -> tuple[PoseSegment, WalkCycleParams | None, list[str]]:
    """Map a narrative action phrase to a deterministic clip.

    Returns:
        (PoseSegment, optional WalkCycleParams, warnings)

    Unknown actions map to ActionLabel.STAND and a warning is recorded.
    Never produces random motion.
    """
    warnings: list[str] = []
    key = action_phrase.lower().strip()

    # Try exact match first.
    if key in _NARRATIVE_MAP:
        action, pose, walk = _NARRATIVE_MAP[key]
        return (
            PoseSegment(start_sec=start_sec, end_sec=end_sec,
                         action=action, pose=pose),
            walk,
            warnings,
        )

    # Try partial match (longest prefix wins).
    candidates = sorted(
        [(k, v) for k, v in _NARRATIVE_MAP.items() if key.startswith(k)],
        key=lambda x: -len(x[0]),
    )
    if candidates:
        matched_key, (action, pose, walk) = candidates[0]
        return (
            PoseSegment(start_sec=start_sec, end_sec=end_sec,
                         action=action, pose=pose),
            walk,
            warnings,
        )

    # Unknown — return STAND with a warning. NEVER randomize.
    warnings.append(
        f"Unknown action '{action_phrase}' mapped to STAND (no random motion)."
    )
    return (
        PoseSegment(start_sec=start_sec, end_sec=end_sec,
                     action=ActionLabel.STAND, pose="stand"),
        None,
        warnings,
    )


def apply_action_to_character(
    character: CharacterAnimation,
    action_phrase: str,
    start_sec: float,
    end_sec: float,
    warnings: list[str],
) -> None:
    """Apply a mapped action to a CharacterAnimation in place.

    Appends a PoseSegment and (if walk/run) sets walk_cycle_params.
    """
    seg, walk, ws = map_action(action_phrase, start_sec, end_sec,
                                end_sec - start_sec)
    warnings.extend(ws)
    character.pose_sequence.append(seg)
    if walk is not None:
        character.walk_cycle_params = walk

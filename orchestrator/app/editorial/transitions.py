"""
PROMPT 10 — Transitions canonical rules.

This module centralises transition validation so both the compiler and
the validator reach the same conclusions.

Rules (PROMPT 10 §13):
  - No negative durations (enforced by schema).
  - CUT must have duration=0 (enforced by schema).
  - Transition duration must not exceed the source scene's duration,
    unless overlap with the *next* scene is explicit (handled by compiler).
"""
from __future__ import annotations

from .schemas import EditorialScene, Transition, TransitionKind


def validate_transition_pair(prev: EditorialScene, nxt: EditorialScene) -> list[str]:
    """Validate the transition OUT(prev) -> IN(nxt) pair.

    Returns a list of error messages (empty on success).
    """
    errs: list[str] = []
    out = prev.transition_out
    inn = nxt.transition_in

    if out is None and inn is None:
        return errs
    # If both exist, they MUST match kind and duration.
    if out is not None and inn is not None:
        if out.kind != inn.kind:
            errs.append(
                f"transition kind mismatch between scene {prev.scene_id}.transition_out "
                f"({out.kind.value}) and scene {nxt.scene_id}.transition_in ({inn.kind.value})"
            )
        if abs(out.duration_sec - inn.duration_sec) > 1e-6:
            errs.append(
                f"transition duration mismatch: {prev.scene_id}.transition_out "
                f"({out.duration_sec}s) != {nxt.scene_id}.transition_in "
                f"({inn.duration_sec}s)"
            )

    if out is not None and out.kind != TransitionKind.CUT and out.duration_sec > prev.source_scene_duration_sec:
        errs.append(
            f"transition_out of scene {prev.scene_id} ({out.duration_sec}s) "
            f"exceeds scene duration ({prev.source_scene_duration_sec}s)."
        )
    if inn is not None and inn.kind != TransitionKind.CUT and inn.duration_sec > nxt.source_scene_duration_sec:
        errs.append(
            f"transition_in of scene {nxt.scene_id} ({inn.duration_sec}s) "
            f"exceeds scene duration ({nxt.source_scene_duration_sec}s)."
        )
    return errs


def validate_all_transitions(scenes: list[EditorialScene]) -> list[str]:
    errs: list[str] = []
    sorted_scenes = sorted(scenes, key=lambda s: s.order)
    for i in range(len(sorted_scenes) - 1):
        errs.extend(validate_transition_pair(sorted_scenes[i], sorted_scenes[i + 1]))
    return errs


__all__ = ["validate_transition_pair", "validate_all_transitions", "TransitionKind"]

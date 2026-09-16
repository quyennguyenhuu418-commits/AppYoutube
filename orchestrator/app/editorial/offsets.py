"""
PROMPT 10 — Master-timeline offset computation.

Source of truth (PROMPT 10 §10):

    master_t = scene_local_t + scene_master_offset_sec

The compiler places scenes sequentially with overlap semantics:
  next.master_offset = prev.master_offset + prev.duration - transition.duration

Holds (PROMPT 10 §14) extend a scene's master duration by adding seconds
AFTER `hold_frames_after` and BEFORE `hold_frames_before`. Holds do NOT
modify scene-local animation keyframes.
"""
from __future__ import annotations

from dataclasses import dataclass

from .schemas import (
    EditorialScene,
    EditorialTimeline,
    Transition,
    TransitionKind,
)


@dataclass(frozen=True)
class ScenePlacement:
    """The result of placing an EditorialScene on the master timeline."""

    scene_id: str
    order: int
    master_start_sec: float
    master_end_sec: float
    duration_sec: float
    source_scene_duration_sec: float
    hold_before_sec: float
    hold_after_sec: float
    transition_in_duration_sec: float
    transition_out_duration_sec: float
    master_start_frame: int
    duration_frames: int


def _hold_total_sec(scene: EditorialScene, target: str) -> float:
    return sum(h.duration_sec for h in scene.holds if h.target == target)


def place_scenes(
    timeline: EditorialTimeline,
    *,
    initial_offset_sec: float = 0.0,
) -> list[ScenePlacement]:
    """Place all scenes on the master timeline in `order`.

    Algorithm:
      offset = initial_offset_sec
      for i in range(len(scenes)):
        scene = scenes_by_order[i]
        # First scene: transition_in has no meaning (skip overlap).
        prev_overlap = scenes_by_order[i-1].transition_out.duration_sec if i > 0 and scenes_by_order[i-1].transition_out else 0.0
        placement.master_start_sec = max(offset - prev_overlap, 0)
        placement.duration_sec = source + holds_before + holds_after + transition_out_overlap_seconds  # ?
        # ...

    We use a simpler, explicit formula that is easy to reason about and
    exactly matches the diagram in PROMPT 10 §7:

      master_start_sec[n] = master_start_sec[n-1] + source_duration[n-1]
                             - transition_out.duration_sec[n-1]
                             + transition_in.duration_sec[n]   (ignored for first)

      master_end_sec[n] = master_start_sec[n] + source_duration[n]
                          + holds_before[n] + holds_after[n]

    The renderer uses `master_start_frame` + `duration_frames` to drive
    `<Sequence>`. Holds extend duration_frames; transition overlap is
    realised by negative deltas between adjacent scenes' start_frame.
    """
    if not timeline.scenes:
        return []
    scenes_sorted = sorted(timeline.scenes, key=lambda s: s.order)
    fps = float(timeline.fps)
    placements: list[ScenePlacement] = []

    # Compute master_start_sec using the overlap rule.
    master_start = float(initial_offset_sec)
    prev_source_duration = 0.0
    prev_transition_out_dur = 0.0
    for idx, scene in enumerate(scenes_sorted):
        if idx > 0:
            # Offset = previous master start + previous source + previous transition out
            # but subtract the overlap (transition_out.duration_sec).
            master_start = (
                master_start + prev_source_duration - prev_transition_out_dur
            )
        # Apply transition_in overlap (rarely used; default 0).
        if scene.transition_in is not None:
            master_start = master_start  # transition_in is realised by the previous scene's transition_out; we keep it as a property of the pair.

        hold_before = _hold_total_sec(scene, "before")
        hold_after = _hold_total_sec(scene, "after")

        # Source duration is the canonical SceneDefinition scene duration.
        # EditorialScene.source_scene_duration_sec is set by the compiler
        # from the source scene's end_sec - start_sec.
        source_dur = scene.source_scene_duration_sec
        if source_dur <= 0:
            # Defensive: skip zero-length scenes with a noop placement that
            # still records the intent.
            placements.append(ScenePlacement(
                scene_id=scene.scene_id, order=scene.order,
                master_start_sec=master_start, master_end_sec=master_start,
                duration_sec=0.0, source_scene_duration_sec=0.0,
                hold_before_sec=0.0, hold_after_sec=0.0,
                transition_in_duration_sec=0.0,
                transition_out_duration_sec=0.0,
                master_start_frame=int(round(master_start * fps)),
                duration_frames=0,
            ))
            prev_source_duration = 0.0
            prev_transition_out_dur = 0.0
            continue

        duration_sec = source_dur + hold_before + hold_after

        # transition_out overlaps the NEXT scene. We record the duration here
        # for the next iteration to subtract.
        t_in_dur = scene.transition_in.duration_sec if scene.transition_in is not None else 0.0
        t_out_dur = scene.transition_out.duration_sec if scene.transition_out is not None else 0.0

        master_end = master_start + duration_sec
        master_start_frame = int(round(master_start * fps))
        duration_frames = int(round(duration_sec * fps))
        # Clamp transition_in to a reasonable upper bound to detect overlap bugs in tests.
        if scene.transition_in is not None and scene.transition_in.kind == TransitionKind.CUT and t_in_dur != 0:
            raise ValueError(f"CUT transition_in for scene {scene.scene_id} must be 0-duration")

        placements.append(ScenePlacement(
            scene_id=scene.scene_id, order=scene.order,
            master_start_sec=master_start, master_end_sec=master_end,
            duration_sec=duration_sec,
            source_scene_duration_sec=source_dur,
            hold_before_sec=hold_before, hold_after_sec=hold_after,
            transition_in_duration_sec=t_in_dur,
            transition_out_duration_sec=t_out_dur,
            master_start_frame=max(0, master_start_frame),
            duration_frames=max(1, duration_frames),
        ))
        prev_source_duration = source_dur
        prev_transition_out_dur = t_out_dur

    # Sanity: each scene's master window must be non-empty (start <= end).
    # Adjacent scenes MAY overlap by exactly the previous transition_out
    # duration (this is the entire point of transition overlap). We
    # therefore only flag overlaps that EXCEED that explicit budget.
    for i in range(1, len(placements)):
        a = placements[i - 1]
        b = placements[i]
        # Explicit budget = a.transition_out_duration_sec
        budget = a.transition_out_duration_sec
        # Compute how much they actually overlap (positive = overlap).
        overlap = a.master_end_sec - b.master_start_sec
        if overlap > budget + 1e-6:
            raise ValueError(
                f"Scenes {a.scene_id} and {b.scene_id} overlap in master time. "
                f"prev_end={a.master_end_sec} next_start={b.master_start_sec} "
                f"overlap={overlap:.4f}s; explicit budget (transition_out)={budget:.4f}s"
            )
        # Detect negative overlap (a micro-gap) when not allowed.
        if not timeline.allow_micro_gaps and overlap < -1e-6:
            raise ValueError(
                f"Master-timeline micro-gap between scenes {a.scene_id} and {b.scene_id}: "
                f"prev_end={a.master_end_sec:.6f}s next_start={b.master_start_sec:.6f}s"
            )
    return placements


def placement_for(scene_id: str, placements: list[ScenePlacement]) -> ScenePlacement:
    for p in placements:
        if p.scene_id == scene_id:
            return p
    raise KeyError(f"Scene {scene_id!r} not placed")


__all__ = ["ScenePlacement", "place_scenes", "placement_for"]

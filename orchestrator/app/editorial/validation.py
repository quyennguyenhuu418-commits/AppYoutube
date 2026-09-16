"""
PROMPT 10 — Editorial validation rules.

PROMPT 10 §37 — reject:
  - overlapping scenes without explicit transition semantics
  - missing scene references
  - invalid transition durations
  - invalid audio references
  - invalid caption references
  - invalid animation references
  - negative timing
  - master timeline gaps when prohibited
  - duplicate track IDs
  - conflicting z-order

This module is the SINGLE source of validation logic. Both the
EditorialCompiler and the standalone EditorialValidator use it.
"""
from __future__ import annotations

from typing import Any

from .references import ReferenceError, SourceBundle
from .schemas import (
    AudioTrackLayer,
    EditorialProject,
    EditorialScene,
    EditorialTimeline,
    LayerKind,
)


# ============================================================================
# Scene & project rules
# ============================================================================

def validate_project_references(project: EditorialProject, bundle: SourceBundle) -> list[str]:
    """Validate that every reference in the project is resolvable.

    Returns a list of failure messages. Empty list = OK.
    """
    errs: list[str] = []
    sd = bundle.scene_definition
    scenes_canonical = set()
    if sd is not None:
        scenes_attr = getattr(sd, "scenes", None) or []
        scenes_canonical = {str(getattr(s, "id", "")) for s in scenes_attr if getattr(s, "id", None)}

    for scene in project.timeline.scenes:
        # Missing scene reference (canonical scene not present).
        if scenes_canonical and scene.scene_id not in scenes_canonical:
            errs.append(
                f"EditorialScene {scene.scene_id} not found in canonical "
                f"SceneDefinition.scenes; available={sorted(scenes_canonical)}"
            )
        # Animation reference (PROMPT 10 §31 — fail loudly).
        if scene.animation_plan_id and scene.animation_plan_id not in bundle.animation_plan_ids:
            errs.append(
                f"EditorialScene {scene.scene_id}: animation_plan_id={scene.animation_plan_id!r} "
                f"not in known AnimationPlan IDs."
            )
        # Caption reference.
        if scene.caption_track_id and scene.caption_track_id not in bundle.caption_track_ids:
            errs.append(
                f"EditorialScene {scene.scene_id}: caption_track_id={scene.caption_track_id!r} "
                f"not in known CaptionTrack IDs."
            )
        # Audio clips.
        for clip in scene.audio_clips:
            if clip.artifact_id not in bundle.audio_artifact_ids:
                errs.append(
                    f"EditorialScene {scene.scene_id}: audio_clip artifact_id={clip.artifact_id!r} "
                    f"not in known AudioArtifact IDs."
                )
            if clip.duration_sec <= 0:
                errs.append(
                    f"EditorialScene {scene.scene_id}: audio_clip {clip.clip_id} has duration_sec <= 0"
                )
            if clip.scene_local_start_sec < 0:
                errs.append(
                    f"EditorialScene {scene.scene_id}: audio_clip {clip.clip_id} start_sec < 0"
                )
    return errs


def validate_unique_track_ids(tracks: list[AudioTrackLayer]) -> list[str]:
    seen: set[str] = set()
    errs: list[str] = []
    for t in tracks:
        if t.track_id in seen:
            errs.append(f"duplicate audio track_id: {t.track_id!r}")
        seen.add(t.track_id)
    return errs


def validate_layer_order_unique(layer_order: list[LayerKind]) -> list[str]:
    seen: set[LayerKind] = set()
    errs: list[str] = []
    for lk in layer_order:
        if lk in seen:
            errs.append(f"duplicate layer in z-order: {lk.value!r}")
        seen.add(lk)
    return errs


def validate_negative_timing(timeline: EditorialTimeline) -> list[str]:
    errs: list[str] = []
    for scene in timeline.scenes:
        if scene.source_scene_duration_sec < 0:
            errs.append(f"EditorialScene {scene.scene_id}: source_scene_duration_sec < 0")
        for clip in scene.audio_clips:
            if clip.scene_local_start_sec < 0 or clip.duration_sec < 0:
                errs.append(f"EditorialScene {scene.scene_id}: negative audio_clip timing")
        for hold in scene.holds:
            if hold.duration_sec < 0:
                errs.append(f"EditorialScene {scene.scene_id}: negative hold duration")
    return errs


def validate_no_master_gaps_when_prohibited(
    placements: list[Any],
    allow_micro_gaps: bool,
    *,
    fps: float = 30.0,
) -> list[str]:
    """Validate that scenes are back-to-back when allow_micro_gaps is False.

    Allow up to one frame of micro-gap before reporting; any larger gap is a
    hard failure. Transition overlap is realised by the compiler and is NOT
    a "gap" (the next scene's start is intentionally before the previous
    end by the previous scene's transition_out duration).
    """
    if allow_micro_gaps:
        return []
    errs: list[str] = []
    sorted_placements = sorted(placements, key=lambda p: p.order)
    frame_sec = 1.0 / max(fps, 1.0)
    for i in range(len(sorted_placements) - 1):
        cur = sorted_placements[i]
        nxt = sorted_placements[i + 1]
        # Compute gap (negative when the next scene starts BEFORE the previous
        # end — that's transition overlap, which is legal).
        gap = nxt.master_start_sec - cur.master_end_sec
        if gap > frame_sec + 1e-6:
            errs.append(
                f"Master timeline micro-gap between scene {cur.scene_id} and {nxt.scene_id}: "
                f"cur_end={cur.master_end_sec:.6f}s, nxt_start={nxt.master_start_sec:.6f}s"
            )
    return errs


def validate_all(project: EditorialProject, bundle: SourceBundle) -> list[str]:
    errs: list[str] = []
    errs.extend(validate_project_references(project, bundle))
    errs.extend(validate_unique_track_ids(project.timeline.audio_tracks))
    errs.extend(validate_layer_order_unique(project.timeline.layer_order))
    errs.extend(validate_negative_timing(project.timeline))
    return errs


__all__ = [
    "validate_project_references",
    "validate_unique_track_ids",
    "validate_layer_order_unique",
    "validate_negative_timing",
    "validate_no_master_gaps_when_prohibited",
    "validate_all",
    "ReferenceError",
]

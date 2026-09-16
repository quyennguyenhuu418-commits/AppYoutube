"""
PROMPT 10 — Audio mixing + ducking computation.

The compiler does NOT analyse waveform; it uses canonical NarrationTimeline
entries to mark narration-active intervals and reduces other tracks'
gain during those windows (PROMPT 10 §17, §18, §20).

This module is pure: it takes existing clip placements and emits a list
of `RenderAudioClip`s with duck annotations.
"""
from __future__ import annotations

from dataclasses import dataclass

from .schemas import (
    AudioClipRef,
    AudioMixingPolicy,
    AudioTrackKind,
    AudioTrackLayer,
)


@dataclass(frozen=True)
class NarrationActiveWindow:
    scene_id: str | None
    clip_id: str
    master_start_sec: float
    master_end_sec: float


def collect_narration_windows(
    clips: list[AudioClipRef],
    *,
    clip_master_starts: dict[str, float],
) -> list[NarrationActiveWindow]:
    """Filter narration clips and project their scene-local times into master time."""
    out: list[NarrationActiveWindow] = []
    for clip in clips:
        if clip.track_kind in (AudioTrackKind.NARRATION, AudioTrackKind.DIALOGUE):
            start = clip_master_starts.get(clip.clip_id)
            if start is None:
                continue
            end = start + clip.duration_sec
            out.append(NarrationActiveWindow(
                scene_id=None,
                clip_id=clip.clip_id,
                master_start_sec=start, master_end_sec=end,
            ))
    out.sort(key=lambda w: (w.master_start_sec, w.master_end_sec))
    return out


def is_in_any_window(time_sec: float, windows: list[NarrationActiveWindow]) -> bool:
    for w in windows:
        if w.master_start_sec <= time_sec < w.master_end_sec:
            return True
    return False


def project_to_master(
    clip: AudioClipRef,
    scene_master_offset_sec: float,
) -> tuple[float, float]:
    """Transform scene-local → master-time coordinates.

    Returns (master_start_sec, master_end_sec) on the master timeline.
    """
    start = scene_master_offset_sec + clip.scene_local_start_sec
    return start, start + clip.duration_sec


def compute_ducking_for_clip(
    clip: AudioClipRef,
    master_start_sec: float,
    master_end_sec: float,
    *,
    policy: AudioMixingPolicy,
    narration_windows: list[NarrationActiveWindow],
    track: AudioTrackLayer,
) -> tuple[float, list[str], float]:
    """Compute the effective gain for an audio clip.

    Returns (effective_gain_db, duck_target_track_ids, duck_gain_db).
    For non-ducks (narration / dialogue), duck_target_track_ids is empty.
    """
    track_kind = clip.track_kind
    # Determine if this clip overlaps any narration window.
    base_gain_db = policy.base_gain_db.get(track_kind, -6.0) + clip.gain_db
    if track_kind in (AudioTrackKind.NARRATION, AudioTrackKind.DIALOGUE):
        return base_gain_db, [], None

    # Does the clip overlap with any narration window?
    overlaps = False
    for w in narration_windows:
        if not (master_end_sec <= w.master_start_sec or master_start_sec >= w.master_end_sec):
            overlaps = True
            break

    if not overlaps:
        return base_gain_db, [], None

    # Apply ducking: if track has its own duck_gain_db, use it; else use policy.
    duck_db = track.duck_gain_db if track.duck_gain_db is not None else policy.narration_duck_gain_db
    target_kinds = [k.value for k in track.duck_active_track_kinds]
    return base_gain_db + duck_db, target_kinds, duck_db


__all__ = [
    "NarrationActiveWindow",
    "collect_narration_windows",
    "is_in_any_window",
    "project_to_master",
    "compute_ducking_for_clip",
]

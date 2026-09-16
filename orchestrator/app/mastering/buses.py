"""
PROMPT 11 — Mix-bus architecture (PROMPT 11 §14).

Defines the explicit mix-bus list and helper functions for building the
bus plan from a `RenderPlan`.

Buses:
  - Narration Bus
  - Dialogue Bus
  - Music Bus
  - SFX Bus
  - Ambience Bus
  - Master Bus (post-mix)

All mixing happens OFFLINE in MediaProcessor (PROMPT 11 §13, §44);
Remotion is not in the audio graph.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from app.editorial.schemas import AudioTrackKind, RenderAudioClip, RenderPlan

# Re-export for convenience
__all__ = [
    "BusKind",
    "MixBus",
    "MixPlan",
    "build_mix_plan",
    "group_clips_by_bus",
]


class BusKind(str):
    """String constants for the five named buses + the master bus."""

    NARRATION = "narration"
    DIALOGUE = "dialogue"
    MUSIC = "music"
    SFX = "sfx"
    AMBIENCE = "ambience"
    MASTER = "master"


@dataclass(frozen=True)
class MixBus:
    """A single named bus."""

    bus_id: str
    kind: str  # one of BusKind values
    priority: int  # 0 = highest priority (narration first)


@dataclass(frozen=True)
class MixPlan:
    """The full bus plan for one editorial composition."""

    buses: tuple[MixBus, ...]
    clips_by_bus: dict[str, tuple[RenderAudioClip, ...]]

    def bus_for(self, kind: str) -> MixBus | None:
        for bus in self.buses:
            if bus.kind == kind:
                return bus
        return None


def group_clips_by_bus(plan: RenderPlan | list | dict) -> dict[str, tuple[RenderAudioClip, ...]]:
    """Group every RenderAudioClip by its track_kind into a bus.

    Accepts a RenderPlan (with .audio_clips) or a plain list/dict with
    `audio_clips` key (cross-runtime / duck-typed).
    """
    out: dict[str, list[RenderAudioClip]] = {
        BusKind.NARRATION: [],
        BusKind.DIALOGUE: [],
        BusKind.MUSIC: [],
        BusKind.SFX: [],
        BusKind.AMBIENCE: [],
    }
    if isinstance(plan, dict):
        clips = plan.get("audio_clips", [])
    elif isinstance(plan, list):
        clips = plan
    else:
        clips = getattr(plan, "audio_clips", [])
    for clip in clips:
        # Support both Pydantic models and plain dicts (cross-runtime / duck-typed).
        if isinstance(clip, dict):
            kind_raw = clip.get("track_kind")
        else:
            kind_raw = getattr(clip, "track_kind", None)
        kind = kind_raw if kind_raw is not None else _coerce_kind(clip)
        key = _kind_to_bus(kind)
        if key in out:
            out[key].append(clip)
    return {k: tuple(v) for k, v in out.items() if v}


def _coerce_kind(clip: RenderAudioClip) -> str:
    kind_attr = getattr(clip, "track_kind", None)
    if kind_attr is None:
        return BusKind.MUSIC
    if isinstance(kind_attr, AudioTrackKind):
        return _kind_to_bus(kind_attr)
    return str(kind_attr)


def _kind_to_bus(kind: AudioTrackKind | str) -> str:
    s = str(getattr(kind, "value", kind))
    s_lower = s.lower()
    mapping = {
        "narration": BusKind.NARRATION,
        "dialogue": BusKind.DIALOGUE,
        "music": BusKind.MUSIC,
        "sfx": BusKind.SFX,
        "ambience": BusKind.AMBIENCE,
    }
    return mapping.get(s_lower, BusKind.MUSIC)


def build_mix_plan(plan: RenderPlan) -> MixPlan:
    """Construct the MixPlan from a RenderPlan.

    Priority order is the canonical PROMPT 11 §19 default:
      Narration > Dialogue > SFX > Music > Ambience
    """
    buses = (
        MixBus(bus_id="bus_narration", kind=BusKind.NARRATION, priority=0),
        MixBus(bus_id="bus_dialogue", kind=BusKind.DIALOGUE, priority=1),
        MixBus(bus_id="bus_sfx", kind=BusKind.SFX, priority=2),
        MixBus(bus_id="bus_music", kind=BusKind.MUSIC, priority=3),
        MixBus(bus_id="bus_ambience", kind=BusKind.AMBIENCE, priority=4),
        MixBus(bus_id="bus_master", kind=BusKind.MASTER, priority=99),
    )
    clips_by_bus = group_clips_by_bus(plan)
    return MixPlan(buses=buses, clips_by_bus=clips_by_bus)


def bus_input_for_clip(
    clip: RenderAudioClip | dict,
    *,
    artifact_path: str,
    narration_active: bool = False,
    default_duck_db: float = -9.0,
) -> dict:
    """Return a `bus_input` dict for MediaProcessor.mix_buses.

    Applies editorial ducking (PROMPT 11 §16) by reducing gain when
    `narration_active=True` and the clip is ducked under narration.
    """
    if isinstance(clip, dict):
        base_gain = float(clip.get("gain_db", 0.0) or 0.0)
        is_ducked = bool(clip.get("duck_under_narration", False))
        clip_id = clip.get("clip_id")
        track_kind = clip.get("track_kind", "music")
    else:
        base_gain = float(getattr(clip, "gain_db", 0.0))
        is_ducked = bool(getattr(clip, "duck_under_narration", False))
        clip_id = getattr(clip, "clip_id", None)
        track_kind = getattr(clip, "track_kind", "music")
    if is_ducked and narration_active:
        effective = base_gain + default_duck_db
    else:
        effective = base_gain
    return {
        "path": artifact_path,
        "gain_db": effective,
        "duck_under_narration": is_ducked,
        "label": str(track_kind),
        "clip_id": clip_id,
    }

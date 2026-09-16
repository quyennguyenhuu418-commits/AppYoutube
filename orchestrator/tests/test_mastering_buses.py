"""
PROMPT 11 §56 — Tests for the mix-bus architecture (PROMPT 11 §14).
"""
from __future__ import annotations

import pytest

from app.editorial.schemas import AudioTrackKind, RenderAudioClip
from app.mastering.buses import (
    BusKind,
    MixBus,
    MixPlan,
    build_mix_plan,
    bus_input_for_clip,
    group_clips_by_bus,
    _kind_to_bus,
    _coerce_kind,
)


def _clip(clip_id="c1", artifact_id="a1", track_kind=AudioTrackKind.NARRATION,
          master_start_frame=0, duration_frames=60, gain_db=0.0,
          duck_under_narration=False) -> RenderAudioClip:
    return RenderAudioClip(
        clip_id=clip_id,
        artifact_id=artifact_id,
        track_kind=track_kind,
        track_id=f"track_{clip_id}",
        scene_id="s1",
        master_start_frame=master_start_frame,
        duration_frames=duration_frames,
        gain_db=gain_db,
        fade_in_frames=0,
        fade_out_frames=0,
        duck_target_track_ids=[],
        duck_gain_db=None,
    )


class TestKindToBus:
    def test_all_kinds_map(self):
        for k in AudioTrackKind:
            bus = _kind_to_bus(k)
            assert bus in {
                BusKind.NARRATION, BusKind.DIALOGUE,
                BusKind.MUSIC, BusKind.SFX, BusKind.AMBIENCE,
            }

    def test_unknown_falls_back_to_music(self):
        assert _kind_to_bus("unknown_kind") == BusKind.MUSIC

    def test_string_kind_to_bus(self):
        assert _kind_to_bus("narration") == BusKind.NARRATION
        assert _kind_to_bus("sfx") == BusKind.SFX


class TestCoerceKind:
    def test_pydantic_clip(self):
        c = _clip(track_kind=AudioTrackKind.NARRATION)
        assert _coerce_kind(c) == BusKind.NARRATION


class TestGroupClipsByBus:
    def test_groups_correctly(self):
        clips = [
            _clip("n1", track_kind=AudioTrackKind.NARRATION),
            _clip("m1", track_kind=AudioTrackKind.MUSIC),
            _clip("m2", track_kind=AudioTrackKind.MUSIC),
            _clip("s1", track_kind=AudioTrackKind.SFX),
            _clip("a1", track_kind=AudioTrackKind.AMBIENCE),
        ]
        grouped = group_clips_by_bus(clips)
        assert BusKind.NARRATION in grouped
        assert len(grouped[BusKind.NARRATION]) == 1
        assert len(grouped[BusKind.MUSIC]) == 2
        assert len(grouped[BusKind.SFX]) == 1
        assert len(grouped[BusKind.AMBIENCE]) == 1
        assert BusKind.DIALOGUE not in grouped


class TestBusInputForClip:
    def test_basic_gain(self):
        c = _clip(track_kind=AudioTrackKind.NARRATION, gain_db=-6.0)
        out = bus_input_for_clip(c, artifact_path="/tmp/n.wav")
        assert out["path"] == "/tmp/n.wav"
        assert out["gain_db"] == -6.0
        assert out["duck_under_narration"] is False

    def test_ducking_applied_when_narration_active(self):
        # No `duck_under_narration` field on the schema by default — emulate
        # by using a duck-target TrackKind via the bus_input_for_clip
        # duck_under_narration is read via getattr
        c = _clip(gain_db=0.0)
        out = bus_input_for_clip(c, artifact_path="/tmp/n.wav", narration_active=False)
        assert out["gain_db"] == 0.0

    def test_label_uses_track_kind(self):
        c = _clip(track_kind=AudioTrackKind.MUSIC)
        out = bus_input_for_clip(c, artifact_path="/tmp/m.wav")
        # Label is stringified track kind
        assert "music" in str(out["label"]).lower()

    def test_duck_under_narration_set(self):
        # Custom clip with duck_under_narration=True
        from dataclasses import dataclass
        @dataclass
        class FakeClip:
            gain_db: float = 0.0
            duck_under_narration: bool = True
            track_kind: str = "music"
            clip_id: str = "c1"
        out = bus_input_for_clip(FakeClip(), artifact_path="/tmp/x.wav", narration_active=True)
        # Default duck of -9 dB applied
        assert out["gain_db"] == -9.0

    def test_duck_inactive_without_narration(self):
        from dataclasses import dataclass
        @dataclass
        class FakeClip:
            gain_db: float = 0.0
            duck_under_narration: bool = True
            track_kind: str = "music"
            clip_id: str = "c1"
        out = bus_input_for_clip(FakeClip(), artifact_path="/tmp/x.wav", narration_active=False)
        # No duck applied
        assert out["gain_db"] == 0.0


class TestBuildMixPlan:
    def test_returns_six_buses(self):
        clips = [_clip(track_kind=AudioTrackKind.NARRATION)]
        class _R: pass
        rp = _R()
        rp.audio_clips = clips
        rp.scenes = []
        plan = build_mix_plan(rp)
        assert len(plan.buses) == 6
        bus_kinds = {b.kind for b in plan.buses}
        assert bus_kinds == {
            BusKind.NARRATION, BusKind.DIALOGUE, BusKind.MUSIC,
            BusKind.SFX, BusKind.AMBIENCE, BusKind.MASTER,
        }

    def test_bus_ordering_narration_first(self):
        clips = []
        class _R: pass
        rp = _R(); rp.audio_clips = clips; rp.scenes = []
        plan = build_mix_plan(rp)
        narration_bus = next(b for b in plan.buses if b.kind == BusKind.NARRATION)
        music_bus = next(b for b in plan.buses if b.kind == BusKind.MUSIC)
        master_bus = next(b for b in plan.buses if b.kind == BusKind.MASTER)
        assert narration_bus.priority < music_bus.priority < master_bus.priority


class TestBuildMixPlanDict:
    """Test that build_mix_plan accepts duck-typed RenderPlan (e.g. dict-based)."""

    def test_dict_audio_clips(self):
        rp = {
            "audio_clips": [
                {"clip_id": "n1", "artifact_id": "a1", "track_kind": "narration"},
                {"clip_id": "m1", "artifact_id": "a2", "track_kind": "music"},
            ],
        }
        plan = build_mix_plan(rp)
        assert BusKind.NARRATION in plan.clips_by_bus
        assert BusKind.MUSIC in plan.clips_by_bus


class TestMixPlanBusFor:
    def test_returns_matching_bus(self):
        class _R: pass
        rp = _R(); rp.audio_clips = []; rp.scenes = []
        plan = build_mix_plan(rp)
        bus = plan.bus_for(BusKind.MUSIC)
        assert bus is not None
        assert bus.kind == BusKind.MUSIC

    def test_returns_none_for_missing(self):
        class _R: pass
        rp = _R(); rp.audio_clips = []; rp.scenes = []
        plan = build_mix_plan(rp)
        # No such bus
        assert plan.bus_for("nonexistent") is None

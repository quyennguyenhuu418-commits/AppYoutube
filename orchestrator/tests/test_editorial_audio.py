"""PROMPT 10 — Editorial transitions + audio mixing tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.editorial.audio import (
    NarrationActiveWindow,
    compute_ducking_for_clip,
    collect_narration_windows,
    is_in_any_window,
    project_to_master,
)
from app.editorial.schemas import (
    AudioClipRef,
    AudioMixingPolicy,
    AudioPriority,
    AudioTrackKind,
    AudioTrackLayer,
    EditorialScene,
    Transition,
    TransitionKind,
)
from app.editorial.transitions import (
    validate_all_transitions,
    validate_transition_pair,
)


def _scn(order: int, duration: float, **kw) -> EditorialScene:
    return EditorialScene(
        scene_id=f"s{order}", order=order,
        source_scene_duration_sec=duration, **kw,
    )


def _clip(clip_id: str, kind: AudioTrackKind, start: float, duration: float = 1.0) -> AudioClipRef:
    return AudioClipRef(
        clip_id=clip_id, artifact_id=f"aa-{clip_id}", track_kind=kind,
        priority=int(AudioPriority[kind.name]), scene_local_start_sec=start,
        duration_sec=duration, gain_db=0.0,
    )


# ============================================================================
# Transition validation
# ============================================================================

def test_transition_pair_matching() -> None:
    fade = Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=0.5)
    s0 = _scn(0, 3.0, transition_out=fade)
    s1 = _scn(1, 2.0, transition_in=fade)
    errs = validate_transition_pair(s0, s1)
    assert errs == []


def test_transition_pair_kind_mismatch() -> None:
    fade = Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=0.5)
    cut = Transition(transition_id="t2", kind=TransitionKind.CUT, duration_sec=0.0)
    s0 = _scn(0, 3.0, transition_out=fade)
    s1 = _scn(1, 2.0, transition_in=cut)
    errs = validate_transition_pair(s0, s1)
    assert any("kind mismatch" in e for e in errs)


def test_transition_pair_duration_mismatch() -> None:
    fade_a = Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=0.3)
    fade_b = Transition(transition_id="t2", kind=TransitionKind.FADE, duration_sec=0.5)
    errs = validate_transition_pair(
        _scn(0, 3.0, transition_out=fade_a),
        _scn(1, 2.0, transition_in=fade_b),
    )
    assert any("duration mismatch" in e for e in errs)


def test_transition_exceeds_scene_duration() -> None:
    """Either the schema-level validator OR the pair-level validator must
    reject a transition whose duration exceeds the source scene duration.
    In our design, schema-level catches `transition_in` immediately (it is
    an error to declare a transition_in longer than the scene it covers).
    """
    big = Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=5.0)
    # Schema-level rejection (transition_in = 5s, scene = 3s).
    with pytest.raises(ValidationError):
        _scn(1, 3.0, transition_in=big)
    # Pair-level rejection on transition_out (no schema-level rule).
    s_prev = _scn(0, 2.0, transition_out=big)
    s_next = _scn(2, 3.0)
    errs = validate_transition_pair(s_prev, s_next)
    assert any("exceeds scene duration" in e for e in errs)


def test_validate_all_transitions_three_scenes() -> None:
    fade = Transition(transition_id="t", kind=TransitionKind.FADE, duration_sec=0.3)
    scenes = [_scn(0, 2.0, transition_out=fade), _scn(1, 2.0, transition_out=fade), _scn(2, 2.0)]
    assert validate_all_transitions(scenes) == []


# ============================================================================
# Audio mixing
# ============================================================================

def test_project_to_master_basic() -> None:
    clip = _clip("c1", AudioTrackKind.MUSIC, start=1.0, duration=2.0)
    s, e = project_to_master(clip, 10.0)
    assert s == 11.0 and e == 13.0


def test_collect_narration_windows_filters_kind() -> None:
    clips = [
        _clip("c1", AudioTrackKind.NARRATION, start=0.0, duration=2.0),
        _clip("c2", AudioTrackKind.MUSIC, start=0.5, duration=2.0),
    ]
    starts = {"c1": 5.0, "c2": 6.0}
    windows = collect_narration_windows(clips, clip_master_starts=starts)
    assert len(windows) == 1
    assert windows[0].master_start_sec == 5.0
    assert windows[0].master_end_sec == 7.0


def test_is_in_any_window() -> None:
    windows = [
        NarrationActiveWindow(scene_id=None, clip_id="x",
                              master_start_sec=5.0, master_end_sec=7.0),
    ]
    assert is_in_any_window(5.5, windows)
    assert not is_in_any_window(7.0, windows)  # exclusive upper
    assert not is_in_any_window(4.9, windows)


def test_compute_ducking_when_overlap_with_narration() -> None:
    policy = AudioMixingPolicy()
    track = AudioTrackLayer(track_id="trk-music", kind=AudioTrackKind.MUSIC)
    clip = _clip("c1", AudioTrackKind.MUSIC, start=0.0, duration=10.0)
    windows = [
        NarrationActiveWindow(scene_id=None, clip_id="x",
                              master_start_sec=2.0, master_end_sec=6.0),
    ]
    eff, duck_targets, duck_db = compute_ducking_for_clip(
        clip, 0.0, 10.0, policy=policy, narration_windows=windows, track=track,
    )
    # -12 + -9 = -21
    assert eff == pytest.approx(-21.0)
    assert duck_db == -9.0
    assert "narration" in duck_targets


def test_compute_ducking_when_no_overlap() -> None:
    policy = AudioMixingPolicy()
    track = AudioTrackLayer(track_id="trk-music", kind=AudioTrackKind.MUSIC)
    clip = _clip("c1", AudioTrackKind.MUSIC, start=0.0, duration=2.0)
    windows = [
        NarrationActiveWindow(scene_id=None, clip_id="x",
                              master_start_sec=100.0, master_end_sec=110.0),
    ]
    eff, duck_targets, duck_db = compute_ducking_for_clip(
        clip, 0.0, 2.0, policy=policy, narration_windows=windows, track=track,
    )
    assert eff == pytest.approx(-12.0)
    assert duck_targets == []


def test_narration_is_not_ducked() -> None:
    policy = AudioMixingPolicy()
    track = AudioTrackLayer(track_id="trk-narration", kind=AudioTrackKind.NARRATION)
    clip = _clip("c1", AudioTrackKind.NARRATION, start=0.0, duration=2.0)
    eff, _, duck_db = compute_ducking_for_clip(
        clip, 0.0, 2.0, policy=policy, narration_windows=[], track=track,
    )
    assert eff == pytest.approx(0.0)
    assert duck_db is None

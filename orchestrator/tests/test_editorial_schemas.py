"""PROMPT 10 — Editorial schemas unit tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.editorial.schemas import (
    AudioClipRef,
    AudioMixingPolicy,
    AudioTrackKind,
    AudioTrackLayer,
    EditorialHold,
    EditorialProject,
    EditorialQualityScore,
    EditorialScene,
    EditorialTimeline,
    LayerKind,
    RenderAudioClip,
    RenderPlan,
    TitleCardSpec,
    Transition,
    TransitionKind,
)


def _scene(*, order: int, duration: float, **kw) -> EditorialScene:
    return EditorialScene(
        scene_id=f"s{order}",
        order=order,
        source_scene_duration_sec=duration,
        **kw,
    )


def test_transition_kind_enum_values() -> None:
    assert TransitionKind.CUT.value == "cut"
    assert TransitionKind.FADE.value == "fade"
    assert TransitionKind.CROSSFADE.value == "crossfade"
    assert TransitionKind.DISSOLVE.value == "dissolve"
    assert TransitionKind.DIP_TO_BLACK.value == "dip_to_black"
    assert TransitionKind.DIP_TO_WHITE.value == "dip_to_white"


def test_transition_cut_must_have_zero_duration() -> None:
    with pytest.raises(ValidationError):
        Transition(transition_id="t1", kind=TransitionKind.CUT, duration_sec=0.5)


def test_transition_duration_must_be_nonnegative() -> None:
    with pytest.raises(ValidationError):
        Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=-0.1)


def test_transition_huge_duration_rejected() -> None:
    with pytest.raises(ValidationError):
        Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=120.0)


def test_hold_must_have_target_in() -> None:
    with pytest.raises(ValidationError):
        EditorialHold(hold_id="h", target="middle", duration_sec=1.0, reason="x")


def test_hold_huge_duration_rejected() -> None:
    with pytest.raises(ValidationError):
        EditorialHold(hold_id="h", target="before", duration_sec=60.0, reason="x")


def test_audio_clip_gain_bounds() -> None:
    AudioClipRef(
        clip_id="c1", artifact_id="aa1", track_kind=AudioTrackKind.NARRATION,
        priority=0,  # AudioPriority.NARRATION
        scene_local_start_sec=0.0, duration_sec=1.0, gain_db=0.0,
    )


def test_audio_clip_gain_out_of_bounds_rejected() -> None:
    with pytest.raises(ValidationError):
        AudioClipRef(
            clip_id="c1", artifact_id="aa1", track_kind=AudioTrackKind.MUSIC,
            priority=3, scene_local_start_sec=0.0, duration_sec=1.0, gain_db=-120.0,
        )


def test_editorial_scene_zero_duration_rejected() -> None:
    with pytest.raises(ValidationError):
        _scene(order=0, duration=0.0)


def test_editorial_scene_rejects_huge_transition() -> None:
    t_in = Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=10.0)
    with pytest.raises(ValidationError):
        _scene(order=0, duration=2.0, transition_in=t_in)


def test_editorial_scene_negative_order_rejected() -> None:
    with pytest.raises(ValidationError):
        _scene(order=-1, duration=1.0)


def test_editorial_timeline_unique_orders() -> None:
    with pytest.raises(ValidationError):
        EditorialTimeline(
            timeline_id="tl", fps=30, width=1280, height=720,
            scenes=[_scene(order=0, duration=2.0), _scene(order=0, duration=2.0)],
        )


def test_editorial_timeline_unique_scene_ids() -> None:
    s1 = _scene(order=0, duration=2.0)
    s2 = _scene(order=1, duration=2.0)
    s2.scene_id = s1.scene_id
    with pytest.raises(ValidationError):
        EditorialTimeline(
            timeline_id="tl", fps=30, width=1280, height=720,
            scenes=[s1, s2],
        )


def test_editorial_timeline_unique_track_ids() -> None:
    t1 = AudioTrackLayer(track_id="trk1", kind=AudioTrackKind.MUSIC)
    t2 = AudioTrackLayer(track_id="trk1", kind=AudioTrackKind.SFX)
    with pytest.raises(ValidationError):
        EditorialTimeline(
            timeline_id="tl", fps=30, width=1280, height=720,
            scenes=[_scene(order=0, duration=2.0)],
            audio_tracks=[t1, t2],
        )


def test_layer_order_default_is_canonical() -> None:
    t = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720,
        scenes=[_scene(order=0, duration=2.0)],
    )
    assert t.layer_order[0] == LayerKind.BACKGROUND
    assert t.layer_order[-1] == LayerKind.TITLE_CARDS


def test_layer_order_unique_rejects_duplicates() -> None:
    with pytest.raises(ValidationError):
        EditorialTimeline(
            timeline_id="tl", fps=30, width=1280, height=720,
            scenes=[_scene(order=0, duration=2.0)],
            layer_order=[LayerKind.BACKGROUND, LayerKind.BACKGROUND, LayerKind.ENVIRONMENT],
        )


def test_quality_score_overall_matches_axes_mean() -> None:
    axes = dict(
        timeline_validity=1.0, scene_continuity=0.9, transition_consistency=0.8,
        audio_continuity=1.0, caption_alignment=0.7, animation_alignment=0.6,
        asset_integrity=0.5, pacing_consistency=0.4,
    )
    mean = sum(axes.values()) / len(axes)
    EditorialQualityScore(overall=mean, reasons=[], **axes)
    with pytest.raises(ValidationError):
        EditorialQualityScore(overall=mean + 0.5, reasons=[], **axes)


def test_render_audio_clip_frozen() -> None:
    clip = RenderAudioClip(
        clip_id="c", artifact_id="aa", track_kind=AudioTrackKind.NARRATION,
        track_id="trk", scene_id="s", master_start_frame=0,
        duration_frames=10, gain_db=0.0,
        fade_in_frames=0, fade_out_frames=0,
    )
    with pytest.raises(ValidationError):
        clip.gain_db = 999.0  # type: ignore[misc]


def test_render_plan_minimum_fields_required() -> None:
    rp = RenderPlan(
        plan_id="rp_x", project_id="p", job_id="j", topic="T",
        fps=30, width=1280, height=720, total_duration_frames=100,
        total_duration_sec=3.33, scenes=[], layers=[], audio_clips=[],
        audio_track_ids=[], title_cards=[], layer_order=list(LayerKind),
        source_fingerprint="fp_abcdefgh",
    )
    assert rp.plan_id == "rp_x"
    assert rp.total_duration_frames == 100


def test_render_plan_short_fingerprint_rejected() -> None:
    with pytest.raises(ValidationError):
        RenderPlan(
            plan_id="rp_x", project_id="p", job_id="j", topic="T",
            fps=30, width=1280, height=720, total_duration_frames=100,
            total_duration_sec=3.33, scenes=[], layers=[], audio_clips=[],
            audio_track_ids=[], title_cards=[], layer_order=list(LayerKind),
            source_fingerprint="short",
        )


def test_title_card_spec_kind_enum() -> None:
    TitleCardSpec(
        card_id="tc1", kind="intro", title="Hello",
        master_start_sec=0.0, duration_sec=2.0,
    )
    with pytest.raises(ValidationError):
        TitleCardSpec(
            card_id="tc1", kind="weird", title="Hello",
            master_start_sec=0.0, duration_sec=2.0,
        )


def test_audio_mixing_policy_default() -> None:
    p = AudioMixingPolicy()
    assert p.base_gain_db[AudioTrackKind.NARRATION] == 0.0
    assert p.base_gain_db[AudioTrackKind.MUSIC] == -12.0
    assert p.narration_duck_gain_db == -9.0

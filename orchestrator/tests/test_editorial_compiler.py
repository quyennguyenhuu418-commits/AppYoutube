"""PROMPT 10 — EditorialCompiler end-to-end + determinism tests."""
from __future__ import annotations

import pytest

from app.editorial.compiler import CompileResult, EditorialCompiler
from app.editorial.references import (
    build_source_bundle,
    extend_bundle,
)
from app.editorial.schemas import (
    AudioClipRef,
    AudioPriority,
    AudioTrackKind,
    AudioTrackLayer,
    EditorialProject,
    EditorialScene,
    EditorialTimeline,
    PacingCategory,
    TitleCardSpec,
    Transition,
    TransitionKind,
)

from .editorial_stub import make_scene_definition


def _scene(order: int, duration: float, *, animation_plan_id: str | None = None,
           caption_track_id: str | None = None,
           transition_in: Transition | None = None,
           transition_out: Transition | None = None,
           audio_clips: list[AudioClipRef] | None = None) -> EditorialScene:
    return EditorialScene(
        scene_id=f"scene_{order+1}", order=order,
        source_scene_duration_sec=duration,
        animation_plan_id=animation_plan_id,
        caption_track_id=caption_track_id,
        transition_in=transition_in,
        transition_out=transition_out,
        audio_clips=audio_clips or [],
    )


def _clip(clip_id: str, kind: AudioTrackKind, start: float, duration: float = 1.0,
          artifact: str | None = None) -> AudioClipRef:
    return AudioClipRef(
        clip_id=clip_id, artifact_id=artifact or f"aa-{clip_id}",
        track_kind=kind, priority=int(AudioPriority[kind.name]),
        scene_local_start_sec=start, duration_sec=duration, gain_db=0.0,
    )


# ============================================================================
# Basic compilation
# ============================================================================

def test_compile_simple_two_scenes() -> None:
    sd = make_scene_definition(n_scenes=2, scene_durations=(3.0, 2.0))
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(
        bundle,
        animation_plan_ids={"ap-1", "ap-2"},
        caption_track_ids={"cap-1", "cap-2"},
        audio_artifact_ids={"aa-narration", "aa-narration2"},
    )
    s0 = _scene(0, 3.0, animation_plan_id="ap-1", caption_track_id="cap-1",
                audio_clips=[_clip("narration", AudioTrackKind.NARRATION, 0.0, 3.0,
                                   "aa-narration")])
    s1 = _scene(1, 2.0, animation_plan_id="ap-2", caption_track_id="cap-2",
                audio_clips=[_clip("narration2", AudioTrackKind.NARRATION, 0.0, 2.0,
                                   "aa-narration2")])
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0, s1],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="Test", timeline=tl,
        target_total_duration_sec=5.0,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res: CompileResult = compiler.compile(project)
    assert res.ok, res.failures
    assert res.plan is not None
    assert len(res.plan.scenes) == 2
    assert res.plan.total_duration_sec == pytest.approx(5.0)
    assert res.plan.fps == 30
    assert res.plan.source_fingerprint.startswith("fp_")


def test_compile_three_scenes_with_transitions_and_ducking() -> None:
    fade = Transition(transition_id="f1", kind=TransitionKind.FADE, duration_sec=0.5)
    sd = make_scene_definition(n_scenes=3, scene_durations=(2.0, 2.0, 2.0))
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(
        bundle,
        animation_plan_ids={"ap"},
        caption_track_ids={"cap"},
        audio_artifact_ids={"aa-narration", "aa-music"},
    )
    s0 = _scene(0, 2.0, animation_plan_id="ap", caption_track_id="cap",
                transition_out=fade,
                audio_clips=[
                    _clip("nar-1", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration"),
                    _clip("mus-1", AudioTrackKind.MUSIC, 0.0, 2.0, "aa-music"),
                ])
    s1 = _scene(1, 2.0, animation_plan_id="ap", caption_track_id="cap",
                transition_in=fade, transition_out=fade,
                audio_clips=[_clip("nar-2", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration")])
    s2 = _scene(2, 2.0, animation_plan_id="ap", caption_track_id="cap",
                transition_in=fade,
                audio_clips=[_clip("nar-3", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration")])
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0, s1, s2],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="Test", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert res.ok, res.failures
    # Ducking should have been applied to the music clip during scene 1 (where narration is active).
    plan = res.plan
    music_clips = [c for c in plan.audio_clips if c.track_kind == AudioTrackKind.MUSIC]
    assert len(music_clips) >= 1
    # Music in scene 1 (narration overlap) gets -12 + -9 = -21 dB
    assert any(c.gain_db == pytest.approx(-21.0) for c in music_clips)


def test_compile_unknown_animation_reference_fails() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(bundle, caption_track_ids={"cap"}, audio_artifact_ids=set())
    s0 = _scene(0, 1.0, animation_plan_id="ap-missing")
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="Test", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert not res.ok
    assert any("animation_plan_id" in f for f in res.failures)


def test_compile_unknown_caption_reference_fails() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(bundle, animation_plan_ids=set(), audio_artifact_ids=set())
    s0 = _scene(0, 1.0, caption_track_id="cap-missing")
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="Test", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert not res.ok
    assert any("caption_track_id" in f for f in res.failures)


def test_compile_unknown_audio_artifact_fails() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(bundle, animation_plan_ids=set(), caption_track_ids=set(), audio_artifact_ids={"aa-real"})
    s0 = _scene(0, 1.0, audio_clips=[_clip("c1", AudioTrackKind.MUSIC, 0.0, 1.0, "aa-missing")])
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="Test", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert not res.ok
    assert any("audio_clip artifact_id" in f for f in res.failures)


def test_compile_missing_scene_reference_fails() -> None:
    sd = make_scene_definition(n_scenes=1)  # only scene_1 exists
    bundle = build_source_bundle(sd)
    s0 = _scene(99, 1.0)  # scene_100 — not in canonical sd
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="Test", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert not res.ok
    assert any("not found" in f for f in res.failures)


def test_compile_layer_order_propagates_to_renderplan() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scene(0, 1.0)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="Test", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert res.ok
    assert len(res.plan.layers) == 8  # one per LayerKind
    # z_order is increasing per layer_kind.
    z_orders = [l.z_order for l in res.plan.layers]
    assert z_orders == sorted(z_orders)


def test_compile_title_cards_extend_total_duration() -> None:
    sd = make_scene_definition(n_scenes=1, scene_durations=(2.0,))
    bundle = build_source_bundle(sd)
    s0 = _scene(0, 2.0)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    title = TitleCardSpec(
        card_id="intro", kind="intro", title="Hello",
        master_start_sec=0.0, duration_sec=1.0,
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
        title_cards=[title],
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert res.ok
    # max(scene end, title card end) = 2.0; in 30fps = 60 frames
    assert res.plan.total_duration_frames == 60


def test_compile_quality_score_axes_within_bounds() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scene(0, 1.0)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert res.ok
    qs = res.quality_score
    assert 0.0 <= qs.overall <= 1.0
    for axis in (
        "timeline_validity", "scene_continuity", "transition_consistency",
        "audio_continuity", "caption_alignment", "animation_alignment",
        "asset_integrity", "pacing_consistency",
    ):
        v = getattr(qs, axis)
        assert 0.0 <= v <= 1.0


# ============================================================================
# Determinism
# ============================================================================

def test_compile_is_deterministic() -> None:
    sd = make_scene_definition(n_scenes=3, scene_durations=(2.0, 2.0, 2.0))
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(
        bundle,
        animation_plan_ids={"ap"},
        caption_track_ids={"cap"},
        audio_artifact_ids={"aa"},
    )
    fade = Transition(transition_id="f", kind=TransitionKind.FADE, duration_sec=0.5)
    s0 = _scene(0, 2.0, animation_plan_id="ap", caption_track_id="cap",
                audio_clips=[_clip("nar", AudioTrackKind.NARRATION, 0.0, 2.0)],
                transition_out=fade)
    s1 = _scene(1, 2.0, animation_plan_id="ap", caption_track_id="cap",
                audio_clips=[_clip("nar2", AudioTrackKind.NARRATION, 0.0, 2.0)],
                transition_in=fade, transition_out=fade)
    s2 = _scene(2, 2.0, animation_plan_id="ap", caption_track_id="cap",
                audio_clips=[_clip("nar3", AudioTrackKind.NARRATION, 0.0, 2.0)],
                transition_in=fade)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0, s1, s2],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    compiler1 = EditorialCompiler(bundle=bundle, now_iso="2026-01-01T00:00:00Z")
    compiler2 = EditorialCompiler(bundle=bundle, now_iso="2026-01-01T00:00:00Z")
    res1 = compiler1.compile(project)
    res2 = compiler2.compile(project)
    assert res1.plan is not None and res2.plan is not None
    # Same fingerprint, same plan_id, same scenes, same audio_clips.
    assert res1.plan.source_fingerprint == res2.plan.source_fingerprint
    assert res1.plan.plan_id == res2.plan.plan_id
    assert len(res1.plan.scenes) == len(res2.plan.scenes)
    for s_a, s_b in zip(res1.plan.scenes, res2.plan.scenes):
        assert s_a.model_dump() == s_b.model_dump()
    for c_a, c_b in zip(res1.plan.audio_clips, res2.plan.audio_clips):
        assert c_a.model_dump() == c_b.model_dump()


def test_pacing_category_persists() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scene(0, 1.0)
    s0.pacing_category = PacingCategory.IMPACT
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert res.plan.scenes[0].pacing_category == PacingCategory.IMPACT


def test_corrupt_renderplan_via_missing_transition_pair_fails() -> None:
    sd = make_scene_definition(n_scenes=2)
    bundle = build_source_bundle(sd)
    fade = Transition(transition_id="f", kind=TransitionKind.FADE, duration_sec=0.5)
    cut = Transition(transition_id="c", kind=TransitionKind.CUT, duration_sec=0.0)
    s0 = _scene(0, 2.0, transition_out=cut)
    s1 = _scene(1, 2.0, transition_in=fade)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0, s1],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    compiler = EditorialCompiler(bundle=bundle)
    res = compiler.compile(project)
    assert not res.ok
    assert any("kind mismatch" in f for f in res.failures)

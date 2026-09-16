"""PROMPT 10 — Editorial validation + failure-recovery tests."""
from __future__ import annotations

import pytest

from app.editorial.offsets import ScenePlacement
from app.editorial.compiler import EditorialCompiler
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
    LayerKind,
    PacingCategory,
    TitleCardSpec,
    Transition,
    TransitionKind,
)
from app.editorial.validation import (
    validate_no_master_gaps_when_prohibited,
    validate_project_references,
    validate_unique_track_ids,
    validate_all,
)

from .editorial_stub import make_scene_definition


def _scn(order: int, duration: float, **kw) -> EditorialScene:
    return EditorialScene(
        scene_id=f"scene_{order+1}", order=order,
        source_scene_duration_sec=duration, **kw,
    )


def _clip(c, k, s, d, a=None) -> AudioClipRef:
    return AudioClipRef(
        clip_id=c, artifact_id=a or f"aa-{c}",
        track_kind=k, priority=int(AudioPriority[k.name]),
        scene_local_start_sec=s, duration_sec=d, gain_db=0.0,
    )


# ============================================================================
# Reference validation
# ============================================================================

def test_validate_references_unknown_animation() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scn(0, 1.0, animation_plan_id="ap-missing")
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    errs = validate_project_references(project, bundle)
    assert any("animation_plan_id" in e for e in errs)


def test_validate_references_unknown_caption() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scn(0, 1.0, caption_track_id="cap-missing")
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    errs = validate_project_references(project, bundle)
    assert any("caption_track_id" in e for e in errs)


def test_validate_references_negative_audio_start() -> None:
    """EditorialScene schema-level validator rejects negative starts directly.

    This test ensures that the upstream schema catches the issue early so
    the runtime validator never has to deal with invalid timings.
    """
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        AudioClipRef(
            clip_id="c1", artifact_id="aa-x",
            track_kind=AudioTrackKind.MUSIC,
            priority=int(AudioPriority.MUSIC),
            scene_local_start_sec=-1.0, duration_sec=1.0, gain_db=0.0,
        )


def test_failure_message_for_corrupt_track_id() -> None:
    """Duplicate track IDs at timeline level must raise a clear error."""
    from pydantic import ValidationError
    s0 = _scn(0, 1.0)
    t1 = AudioTrackLayer(track_id="trk", kind=AudioTrackKind.MUSIC)
    t2 = AudioTrackLayer(track_id="trk", kind=AudioTrackKind.SFX)
    with pytest.raises(ValidationError) as exc_info:
        EditorialTimeline(
            timeline_id="tl", fps=30, width=1280, height=720,
            scenes=[s0], audio_tracks=[t1, t2],
        )
    assert "audio track ids unique" in str(exc_info.value)


def test_validate_unique_track_ids_detects_dupes() -> None:
    t1 = AudioTrackLayer(track_id="trk1", kind=AudioTrackKind.MUSIC)
    t2 = AudioTrackLayer(track_id="trk1", kind=AudioTrackKind.SFX)
    errs = validate_unique_track_ids([t1, t2])
    assert any("duplicate audio track_id" in e for e in errs)


def test_validate_all_aggregates() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(bundle, animation_plan_ids=set(), caption_track_ids=set(),
                            audio_artifact_ids=set())
    s0 = _scn(0, 1.0, animation_plan_id="ap-bad", caption_track_id="cap-bad",
              audio_clips=[_clip("c", AudioTrackKind.MUSIC, 0.0, 1.0, "aa-bad")])
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    errs = validate_all(project, bundle)
    # All three references (anim/caption/audio) should be reported.
    assert len(errs) >= 3


# ============================================================================
# Micro-gap detection
# ============================================================================

def test_validate_no_micro_gaps_when_allow_flag_off() -> None:
    p1 = ScenePlacement(scene_id="s1", order=0,
                        master_start_sec=0.0, master_end_sec=3.0,
                        duration_sec=3.0, source_scene_duration_sec=3.0,
                        hold_before_sec=0.0, hold_after_sec=0.0,
                        transition_in_duration_sec=0.0,
                        transition_out_duration_sec=0.0,
                        master_start_frame=0, duration_frames=90)
    p2 = ScenePlacement(scene_id="s2", order=1,
                        master_start_sec=3.1, master_end_sec=5.0,  # 0.1s gap
                        duration_sec=1.9, source_scene_duration_sec=2.0,
                        hold_before_sec=0.0, hold_after_sec=0.0,
                        transition_in_duration_sec=0.0,
                        transition_out_duration_sec=0.0,
                        master_start_frame=93, duration_frames=57)
    errs = validate_no_master_gaps_when_prohibited([p1, p2], allow_micro_gaps=False)
    assert any("micro-gap" in e for e in errs)


def test_validate_no_micro_gaps_when_allow_flag_on() -> None:
    p1 = ScenePlacement(scene_id="s1", order=0,
                        master_start_sec=0.0, master_end_sec=3.0,
                        duration_sec=3.0, source_scene_duration_sec=3.0,
                        hold_before_sec=0.0, hold_after_sec=0.0,
                        transition_in_duration_sec=0.0,
                        transition_out_duration_sec=0.0,
                        master_start_frame=0, duration_frames=90)
    p2 = ScenePlacement(scene_id="s2", order=1,
                        master_start_sec=3.5, master_end_sec=5.0,
                        duration_sec=1.5, source_scene_duration_sec=1.5,
                        hold_before_sec=0.0, hold_after_sec=0.0,
                        transition_in_duration_sec=0.0,
                        transition_out_duration_sec=0.0,
                        master_start_frame=105, duration_frames=45)
    errs = validate_no_master_gaps_when_prohibited([p1, p2], allow_micro_gaps=True)
    assert errs == []


def test_validate_back_to_back_when_no_gap() -> None:
    p1 = ScenePlacement(scene_id="s1", order=0,
                        master_start_sec=0.0, master_end_sec=3.0,
                        duration_sec=3.0, source_scene_duration_sec=3.0,
                        hold_before_sec=0.0, hold_after_sec=0.0,
                        transition_in_duration_sec=0.0,
                        transition_out_duration_sec=0.0,
                        master_start_frame=0, duration_frames=90)
    p2 = ScenePlacement(scene_id="s2", order=1,
                        master_start_sec=3.0, master_end_sec=5.0,
                        duration_sec=2.0, source_scene_duration_sec=2.0,
                        hold_before_sec=0.0, hold_after_sec=0.0,
                        transition_in_duration_sec=0.0,
                        transition_out_duration_sec=0.0,
                        master_start_frame=90, duration_frames=60)
    errs = validate_no_master_gaps_when_prohibited([p1, p2], allow_micro_gaps=False)
    assert errs == []


# ============================================================================
# Failure recovery — every failure must be explicit (PROMPT 10 §49)
# ============================================================================

def test_failure_message_for_missing_scene() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scn(99, 1.0)  # not in canonical sd
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    res = EditorialCompiler(bundle=bundle).compile(project)
    assert not res.ok
    # Failure mentions the missing scene id so it's actionable.
    assert any("scene_100" in f for f in res.failures)


def test_failure_message_for_invalid_transition() -> None:
    sd = make_scene_definition(n_scenes=2)
    bundle = build_source_bundle(sd)
    fade = Transition(transition_id="f", kind=TransitionKind.FADE, duration_sec=0.5)
    cut = Transition(transition_id="c", kind=TransitionKind.CUT, duration_sec=0.0)
    s0 = _scn(0, 2.0, transition_out=cut)
    s1 = _scn(1, 2.0, transition_in=fade)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0, s1],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    res = EditorialCompiler(bundle=bundle).compile(project)
    assert not res.ok
    assert any("transition" in f.lower() for f in res.failures)


def test_failure_message_for_corrupt_track_id() -> None:
    """Duplicate track IDs at timeline level must raise a clear error."""
    from pydantic import ValidationError
    s0 = _scn(0, 1.0)
    t1 = AudioTrackLayer(track_id="trk", kind=AudioTrackKind.MUSIC)
    t2 = AudioTrackLayer(track_id="trk", kind=AudioTrackKind.SFX)
    with pytest.raises(ValidationError) as exc_info:
        EditorialTimeline(
            timeline_id="tl", fps=30, width=1280, height=720,
            scenes=[s0], audio_tracks=[t1, t2],
        )
    assert "audio track ids unique" in str(exc_info.value)


# ============================================================================
# Asset integrity
# ============================================================================

def test_asset_integrity_score_degrades_for_reference_failures() -> None:
    """Asset integrity axis should drop when references are unresolved."""
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scn(0, 1.0, animation_plan_id="ap-missing")
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    res = EditorialCompiler(bundle=bundle).compile(project)
    qs = res.quality_score
    assert qs.asset_integrity < 1.0


# ============================================================================
# Title cards
# ============================================================================

def test_title_card_intro_chapter_section_outro() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scn(0, 2.0)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0],
    )
    cards = [
        TitleCardSpec(card_id="i", kind="intro", title="Hello", master_start_sec=0.0, duration_sec=1.0),
        TitleCardSpec(card_id="o", kind="outro", title="Bye", master_start_sec=10.0, duration_sec=1.0),
    ]
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl, title_cards=cards,
    )
    res = EditorialCompiler(bundle=bundle).compile(project)
    assert res.ok
    # outro at 10s → total_duration_frames = 11 * 30 = 330
    assert res.plan.total_duration_frames == 330


# ============================================================================
# Pacing categories
# ============================================================================

def test_pacing_persists_all_categories() -> None:
    sd = make_scene_definition(n_scenes=4)
    bundle = build_source_bundle(sd)
    cats = [PacingCategory.SLOW, PacingCategory.NORMAL,
            PacingCategory.FAST, PacingCategory.IMPACT]
    scenes = []
    for i, c in enumerate(cats):
        s = _scn(i, 1.0)
        s.pacing_category = c
        scenes.append(s)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=scenes,
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    res = EditorialCompiler(bundle=bundle).compile(project)
    assert res.ok
    out_cats = [r.pacing_category for r in res.plan.scenes]
    assert out_cats == cats


# ============================================================================
# Layer ordering
# ============================================================================

def test_layer_order_custom_order() -> None:
    sd = make_scene_definition(n_scenes=1)
    bundle = build_source_bundle(sd)
    s0 = _scn(0, 1.0)
    custom_order = [LayerKind.TITLE_CARDS, LayerKind.CAPTIONS, LayerKind.CHARACTERS,
                    LayerKind.ENVIRONMENT, LayerKind.BACKGROUND]
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720,
        scenes=[s0], layer_order=custom_order,
    )
    project = EditorialProject(
        project_id="p", job_id="j", topic="T", timeline=tl,
    )
    res = EditorialCompiler(bundle=bundle).compile(project)
    assert res.ok
    assert res.plan.layer_order == custom_order

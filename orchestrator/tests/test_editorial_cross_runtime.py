"""PROMPT 10 — Cross-runtime contract (Python RenderPlan ↔ TS RenderPlan).

Verifies that the canonical JSON shape produced by `EditorialCompiler`
parses back into the expected Pydantic schema (round-trip parity).
"""
from __future__ import annotations

import json

from app.editorial.compiler import EditorialCompiler
from app.editorial.references import (
    build_source_bundle, extend_bundle,
)
from app.editorial.schemas import (
    AudioClipRef, AudioPriority, AudioTrackKind, AudioTrackLayer,
    EditorialProject, EditorialScene, EditorialTimeline,
    RenderAudioClip, RenderLayer, RenderPlan, RenderScene, Transition, TransitionKind,
)

from .editorial_stub import make_scene_definition


def _scene(order: int, duration: float, **kw) -> EditorialScene:
    return EditorialScene(
        scene_id=f"scene_{order+1}", order=order,
        source_scene_duration_sec=duration, **kw,
    )


def _clip(clip_id: str, kind: AudioTrackKind, start: float, duration: float = 1.0,
          artifact: str | None = None) -> AudioClipRef:
    return AudioClipRef(
        clip_id=clip_id, artifact_id=artifact or f"aa-{clip_id}",
        track_kind=kind, priority=int(AudioPriority[kind.name]),
        scene_local_start_sec=start, duration_sec=duration, gain_db=0.0,
    )


def _make_three_scene_project() -> EditorialProject:
    sd = make_scene_definition(n_scenes=3, scene_durations=(2.0, 2.0, 2.0))
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(
        bundle,
        animation_plan_ids={"ap"},
        caption_track_ids={"cap"},
        audio_artifact_ids={"aa-narration", "aa-music"},
    )
    fade = Transition(transition_id="f", kind=TransitionKind.FADE, duration_sec=0.5)
    s0 = _scene(0, 2.0, animation_plan_id="ap", caption_track_id="cap",
                audio_clips=[_clip("nar1", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration")],
                transition_out=fade)
    s1 = _scene(1, 2.0, animation_plan_id="ap", caption_track_id="cap",
                audio_clips=[_clip("nar2", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration")],
                transition_in=fade, transition_out=fade)
    s2 = _scene(2, 2.0, animation_plan_id="ap", caption_track_id="cap",
                audio_clips=[_clip("nar3", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration")],
                transition_in=fade)
    tl = EditorialTimeline(
        timeline_id="tl", fps=30, width=1280, height=720, scenes=[s0, s1, s2],
    )
    return EditorialProject(
        project_id="p", job_id="j", topic="Test", timeline=tl,
    ), bundle


def test_renderplan_json_round_trip() -> None:
    project, bundle = _make_three_scene_project()
    res = EditorialCompiler(bundle=bundle, now_iso="2026-01-01T00:00:00Z").compile(project)
    assert res.ok, res.failures
    blob = res.plan.model_dump_json()
    parsed = json.loads(blob)
    # Re-parse into RenderPlan to ensure no field loss.
    plan2 = RenderPlan.model_validate_json(json.dumps(parsed))
    assert plan2.plan_id == res.plan.plan_id
    assert plan2.source_fingerprint == res.plan.source_fingerprint
    assert len(plan2.scenes) == len(res.plan.scenes)
    assert len(plan2.layers) == len(res.plan.layers)
    assert len(plan2.audio_clips) == len(res.plan.audio_clips)


def test_renderplan_required_fields_present_in_json() -> None:
    project, bundle = _make_three_scene_project()
    res = EditorialCompiler(bundle=bundle, now_iso="2026-01-01T00:00:00Z").compile(project)
    blob = res.plan.model_dump_json()
    parsed = json.loads(blob)
    # Verify canonical fields required by the TS consumer exist.
    expected_top_level = {
        "version", "plan_id", "project_id", "job_id", "topic",
        "fps", "width", "height", "total_duration_frames", "total_duration_sec",
        "scenes", "layers", "audio_clips", "audio_track_ids",
        "title_cards", "layer_order", "source_fingerprint",
    }
    assert expected_top_level.issubset(parsed.keys())


def test_render_scene_required_fields_present() -> None:
    project, bundle = _make_three_scene_project()
    res = EditorialCompiler(bundle=bundle, now_iso="2026-01-01T00:00:00Z").compile(project)
    blob = json.loads(res.plan.model_dump_json())
    s0 = blob["scenes"][0]
    expected = {
        "scene_id", "order", "master_start_frame", "duration_frames",
        "source_scene_duration_frames", "transition_in", "transition_out",
        "hold_frames_before", "hold_frames_after", "animation_plan_id",
        "caption_track_id", "pacing_category", "emphasis_level",
    }
    assert expected.issubset(s0.keys())


def test_render_audio_clip_required_fields_present() -> None:
    project, bundle = _make_three_scene_project()
    res = EditorialCompiler(bundle=bundle, now_iso="2026-01-01T00:00:00Z").compile(project)
    blob = json.loads(res.plan.model_dump_json())
    c0 = blob["audio_clips"][0]
    expected = {
        "clip_id", "artifact_id", "track_kind", "track_id", "scene_id",
        "master_start_frame", "duration_frames", "gain_db",
        "fade_in_frames", "fade_out_frames",
        "duck_target_track_ids", "duck_gain_db",
    }
    assert expected.issubset(c0.keys())


def test_render_layer_required_fields_present() -> None:
    project, bundle = _make_three_scene_project()
    res = EditorialCompiler(bundle=bundle, now_iso="2026-01-01T00:00:00Z").compile(project)
    blob = json.loads(res.plan.model_dump_json())
    l0 = blob["layers"][0]
    expected = {"layer_id", "kind", "z_order", "scene_id",
                "master_start_frame", "duration_frames", "payload"}
    assert expected.issubset(l0.keys())

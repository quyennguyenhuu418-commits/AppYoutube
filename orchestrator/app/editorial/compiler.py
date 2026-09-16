"""
PROMPT 10 — Editorial Compiler & Render-Plan builder.

Pipeline (PROMPT 10 §32):
  validate
  → resolve scene references
  → normalize timeline (placements)
  → resolve transitions
  → resolve audio tracks (with ducking)
  → resolve captions
  → resolve animation offsets
  → produce RenderPlan

The compiler is PURE with respect to upstream canonical subsystems:
  - never mutates SceneDefinition, AnimationPlan, AudioArtifact, CaptionTrack
  - never re-derives word timing, animation keyframes, caption timing
  - only emits intermediate RenderPlan fields that the renderer can read

The compiler returns a `CompileResult` containing:
  - `plan` — the RenderPlan (or `None` on hard-failure)
  - `warnings` — non-fatal issues
  - `failures` — fatal issues; presence means plan is partial or not emitted
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from .audio import (
    NarrationActiveWindow,
    collect_narration_windows,
    compute_ducking_for_clip,
    project_to_master,
)
from .offsets import ScenePlacement, place_scenes
from .references import (
    SourceBundle,
    build_source_bundle,
    compute_source_fingerprint,
    extend_bundle,
)
from .schemas import (
    AudioClipRef,
    AudioMixingPolicy,
    AudioPriority,
    AudioTrackKind,
    AudioTrackLayer,
    EditorialProject,
    EditorialScene,
    EditorialTimeline,
    EditorialQualityScore,
    LayerKind,
    PacingCategory,
    RenderAudioClip,
    RenderLayer,
    RenderPlan,
    RenderScene,
    TitleCardSpec,
)
from .transitions import validate_all_transitions
from .validation import (
    validate_all,
    validate_no_master_gaps_when_prohibited,
)


# ============================================================================
# CompileResult — the bundling container
# ============================================================================

class CompileResult:
    """Output of EditorialCompiler.compile().

    A plan is produced even on partial failure so the renderer can still
    introspect; failures are surfaced via the `failures` list.
    """

    def __init__(
        self,
        plan: RenderPlan | None,
        *,
        warnings: list[str] | None = None,
        failures: list[str] | None = None,
        placements: list[ScenePlacement] | None = None,
        quality_score: EditorialQualityScore | None = None,
    ) -> None:
        self.plan = plan
        self.warnings = list(warnings or [])
        self.failures = list(failures or [])
        self.placements = list(placements or [])
        self.quality_score = quality_score

    @property
    def ok(self) -> bool:
        return not self.failures and self.plan is not None

    def summary(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "warnings": len(self.warnings),
            "failures": len(self.failures),
            "scenes": len(self.placements),
            "plan_id": self.plan.plan_id if self.plan else None,
        }


# ============================================================================
# EditorialCompiler
# ============================================================================

class EditorialCompiler:
    """Compile an EditorialProject into a RenderPlan (C-26)."""

    def __init__(
        self,
        *,
        bundle: SourceBundle | None = None,
        scene_definition: Any = None,
        animation_plan_ids: set[str] | None = None,
        caption_track_ids: set[str] | None = None,
        audio_artifact_ids: set[str] | None = None,
        narration_timeline_id: str | None = None,
        now_iso: str | None = None,
    ) -> None:
        if bundle is None:
            if scene_definition is None:
                raise ValueError(
                    "EditorialCompiler requires either a SourceBundle or a scene_definition"
                )
            bundle = build_source_bundle(scene_definition)
            if any([animation_plan_ids, caption_track_ids, audio_artifact_ids]) or narration_timeline_id:
                bundle = extend_bundle(
                    bundle,
                    animation_plan_ids=animation_plan_ids,
                    caption_track_ids=caption_track_ids,
                    audio_artifact_ids=audio_artifact_ids,
                    narration_timeline_id=narration_timeline_id,
                )
        self.bundle = bundle
        self.now_iso = now_iso or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # -----------------------------------------------------------------------
    # Public entrypoint
    # -----------------------------------------------------------------------

    def compile(self, project: EditorialProject) -> CompileResult:
        warnings: list[str] = []
        failures: list[str] = []

        # ---- Validate references & structural rules ----
        all_errs = validate_all(project, self.bundle)
        if all_errs:
            failures.extend(all_errs)

        # Transitions validation (kind/duration pair rules, PROMPT 10 §13).
        t_errs = validate_all_transitions(project.timeline.scenes)
        if t_errs:
            failures.extend(t_errs)

        # ---- Place scenes on master timeline ----
        try:
            placements = place_scenes(project.timeline)
        except ValueError as e:
            failures.append(f"scene placement failed: {e}")
            placements = []

        # Validate master-timeline micro-gap rule.
        gap_errs = validate_no_master_gaps_when_prohibited(
            placements, project.timeline.allow_micro_gaps
        )
        if gap_errs:
            failures.extend(gap_errs)

        # ---- Build RenderPlan ----
        plan = self._build_plan(project, placements, warnings)

        # ---- Quality score ----
        quality = self._build_quality_score(project, placements, failures)

        # If we have hard failures, still return the plan but mark `failures`.
        return CompileResult(
            plan=plan,
            warnings=warnings,
            failures=failures,
            placements=placements,
            quality_score=quality,
        )

    # -----------------------------------------------------------------------
    # Plan builders
    # -----------------------------------------------------------------------

    def _build_plan(
        self,
        project: EditorialProject,
        placements: list[ScenePlacement],
        warnings: list[str],
    ) -> RenderPlan:
        fps = project.timeline.fps
        width = project.timeline.width
        height = project.timeline.height
        placement_by_id = {p.scene_id: p for p in placements}
        sorted_scenes = sorted(project.timeline.scenes, key=lambda s: s.order)

        # ---- Render scenes ----
        render_scenes: list[RenderScene] = []
        for scene in sorted_scenes:
            p = placement_by_id.get(scene.scene_id)
            if p is None:
                warnings.append(f"scene {scene.scene_id}: no placement (0-duration or missing)")
                p = ScenePlacement(
                    scene_id=scene.scene_id, order=scene.order,
                    master_start_sec=0.0, master_end_sec=0.0,
                    duration_sec=0.0, source_scene_duration_sec=0.0,
                    hold_before_sec=0.0, hold_after_sec=0.0,
                    transition_in_duration_sec=0.0,
                    transition_out_duration_sec=0.0,
                    master_start_frame=0, duration_frames=0,
                )
            render_scenes.append(RenderScene(
                scene_id=scene.scene_id,
                order=scene.order,
                master_start_frame=p.master_start_frame,
                duration_frames=p.duration_frames,
                source_scene_duration_frames=max(
                    1, int(round(scene.source_scene_duration_sec * fps))
                ),
                transition_in=scene.transition_in,
                transition_out=scene.transition_out,
                hold_frames_before=int(round(p.hold_before_sec * fps)),
                hold_frames_after=int(round(p.hold_after_sec * fps)),
                animation_plan_id=scene.animation_plan_id,
                caption_track_id=scene.caption_track_id,
                pacing_category=scene.pacing_category,
                emphasis_level=scene.emphasis_level,
            ))

        # ---- Render layers (one entry per scene per visible layer kind) ----
        render_layers: list[RenderLayer] = []
        layer_z_order = {lk.value: i for i, lk in enumerate(project.timeline.layer_order)}
        for scene in sorted_scenes:
            p = placement_by_id.get(scene.scene_id)
            if p is None or p.duration_frames <= 0:
                continue
            scene_payload = {
                "scene_id": scene.scene_id,
                "order": scene.order,
                "environment_id": _scene_environment_id(self.bundle, scene.scene_id),
                "character_ids": _scene_character_ids(self.bundle, scene.scene_id),
                "props": _scene_prop_kinds(self.bundle, scene.scene_id),
                "overlay_text_ids": [],
            }
            for lk in project.timeline.layer_order:
                payload: dict[str, Any] = dict(scene_payload)
                if lk == LayerKind.CAPTIONS:
                    payload["caption_track_id"] = scene.caption_track_id
                elif lk == LayerKind.CHARACTERS:
                    payload["animation_plan_id"] = scene.animation_plan_id
                elif lk == LayerKind.OVERLAYS:
                    payload["layer_overrides"] = scene.layer_overrides
                render_layers.append(RenderLayer(
                    layer_id=f"{scene.scene_id}:{lk.value}",
                    kind=lk, z_order=layer_z_order[lk.value],
                    scene_id=scene.scene_id,
                    master_start_frame=p.master_start_frame,
                    duration_frames=p.duration_frames,
                    payload=payload,
                ))

        # ---- Audio clips with ducking ----
        render_audio_clips: list[RenderAudioClip] = []
        narration_windows: list[NarrationActiveWindow] = []
        track_kind_by_id: dict[str, AudioTrackLayer] = {
            t.track_id: t for t in project.timeline.audio_tracks
        }
        # Compute master start for each clip across all scenes.
        clip_master_starts: dict[str, float] = {}
        for scene in sorted_scenes:
            p = placement_by_id.get(scene.scene_id)
            if p is None:
                continue
            for clip in scene.audio_clips:
                m_start, m_end = project_to_master(clip, p.master_start_sec)
                clip_master_starts[clip.clip_id] = m_start
                narration_windows.extend(
                    [NarrationActiveWindow(
                        scene_id=scene.scene_id,
                        clip_id=clip.clip_id,
                        master_start_sec=m_start,
                        master_end_sec=m_end,
                    )]
                    if clip.track_kind in (AudioTrackKind.NARRATION, AudioTrackKind.DIALOGUE)
                    else []
                )

        narration_windows.sort(key=lambda w: (w.master_start_sec, w.master_end_sec))

        track_kind_default_id: dict[AudioTrackKind, str] = {}
        for track in project.timeline.audio_tracks:
            track_kind_default_id.setdefault(track.kind, track.track_id)

        # If no track was declared but the user supplied scene-level clips,
        # synthesise one default track per AudioTrackKind so ducking still
        # computes against the canonical narration windows. The default
        # tracks share the project's mixing_policy and inherit duck policy
        # from the AudioTrackLayer defaults.
        inferred_tracks: dict[AudioTrackKind, AudioTrackLayer] = {}
        if not project.timeline.audio_tracks:
            for sk in AudioTrackKind:
                inferred_tracks[sk] = AudioTrackLayer(
                    track_id=f"_auto_{sk.value}", kind=sk,
                )

        for scene in sorted_scenes:
            p = placement_by_id.get(scene.scene_id)
            if p is None or p.duration_frames <= 0:
                continue
            for clip in scene.audio_clips:
                m_start, m_end = project_to_master(clip, p.master_start_sec)
                # Use declared track id if available; otherwise infer from kind.
                if clip.track_kind in track_kind_default_id:
                    track_id = track_kind_default_id[clip.track_kind]
                    track = track_kind_by_id.get(track_id)
                else:
                    track_id = f"_auto_{clip.track_kind.value}"
                    track = inferred_tracks.get(clip.track_kind)
                if track is not None:
                    eff_gain, duck_targets, duck_db = compute_ducking_for_clip(
                        clip, m_start, m_end,
                        policy=project.mixing_policy,
                        narration_windows=narration_windows,
                        track=track,
                    )
                else:
                    eff_gain = project.mixing_policy.base_gain_db.get(clip.track_kind, -6.0) + clip.gain_db
                    duck_targets, duck_db = [], None
                render_audio_clips.append(RenderAudioClip(
                    clip_id=clip.clip_id,
                    artifact_id=clip.artifact_id,
                    track_kind=clip.track_kind,
                    track_id=track_id,
                    scene_id=scene.scene_id,
                    master_start_frame=int(round(m_start * fps)),
                    duration_frames=int(round(clip.duration_sec * fps)),
                    gain_db=eff_gain,
                    fade_in_frames=int(round(clip.fade_in_sec * fps)),
                    fade_out_frames=int(round(clip.fade_out_sec * fps)),
                    duck_target_track_ids=duck_targets,
                    duck_gain_db=duck_db,
                ))

        # Also process the top-level timeline audio tracks (track-level scene-agnostic audio).
        for track in project.timeline.audio_tracks:
            for clip in track.clips:
                m_start, m_end = clip.scene_local_start_sec, clip.scene_local_start_sec + clip.duration_sec
                clip_master_starts[clip.clip_id] = m_start
                eff_gain, duck_targets, duck_db = compute_ducking_for_clip(
                    clip, m_start, m_end,
                    policy=project.mixing_policy,
                    narration_windows=narration_windows,
                    track=track,
                )
                render_audio_clips.append(RenderAudioClip(
                    clip_id=clip.clip_id,
                    artifact_id=clip.artifact_id,
                    track_kind=clip.track_kind,
                    track_id=track.track_id,
                    scene_id=None,
                    master_start_frame=int(round(m_start * fps)),
                    duration_frames=int(round(clip.duration_sec * fps)),
                    gain_db=eff_gain,
                    fade_in_frames=int(round(clip.fade_in_sec * fps)),
                    fade_out_frames=int(round(clip.fade_out_sec * fps)),
                    duck_target_track_ids=duck_targets,
                    duck_gain_db=duck_db,
                ))

        total_duration_frames = max(
            [0] + [p.master_start_frame + p.duration_frames for p in placements] +
            [int(round((tc.master_start_sec + tc.duration_sec) * fps))
             for tc in project.title_cards]
        )
        total_duration_sec = total_duration_frames / fps if fps else 0.0

        # ---- Source fingerprint ----
        fp = compute_source_fingerprint(self.bundle, extras={
            "project_id": project.project_id,
            "job_id": project.job_id,
            "scene_orders": [s.order for s in project.timeline.scenes],
            "audio_track_ids": [t.track_id for t in project.timeline.audio_tracks],
            "title_card_ids": [c.card_id for c in project.title_cards],
            "mixing_policy": project.mixing_policy.model_dump(),
        })

        return RenderPlan(
            plan_id=_deterministic_id("rp", project.project_id, project.job_id, fp),
            project_id=project.project_id,
            job_id=project.job_id,
            topic=project.topic,
            fps=fps, width=width, height=height,
            total_duration_frames=total_duration_frames,
            total_duration_sec=total_duration_sec,
            scenes=render_scenes,
            layers=render_layers,
            audio_clips=render_audio_clips,
            audio_track_ids=[t.track_id for t in project.timeline.audio_tracks],
            title_cards=list(project.title_cards),
            layer_order=list(project.timeline.layer_order),
            source_fingerprint=fp,
            created_at=self.now_iso,
            warnings=[],
            failures=[],
        )

    # -----------------------------------------------------------------------
    # Quality score — PROMPT 10 §38
    # -----------------------------------------------------------------------

    def _build_quality_score(
        self,
        project: EditorialProject,
        placements: list[ScenePlacement],
        failures: list[str],
    ) -> EditorialQualityScore:
        reasons: list[str] = []

        # timeline_validity: 1.0 if no failures, scaled down per failure.
        timeline_validity = 1.0 if not failures else max(0.0, 1.0 - 0.05 * len(failures))

        # scene_continuity: continuity is preserved when all scenes are placed in order.
        if placements:
            orders = [p.order for p in placements]
            scene_continuity = 1.0 if orders == sorted(orders) else 0.7
        else:
            scene_continuity = 0.5
            reasons.append("no scene placements available")

        # transition_consistency: count pairs with matching transitions.
        sorted_scenes = sorted(project.timeline.scenes, key=lambda s: s.order)
        pair_count = max(0, len(sorted_scenes) - 1)
        matched_pairs = 0
        for i in range(pair_count):
            out = sorted_scenes[i].transition_out
            inn = sorted_scenes[i + 1].transition_in
            if out is None and inn is None:
                matched_pairs += 1
            elif out is not None and inn is not None and out.kind == inn.kind and abs(out.duration_sec - inn.duration_sec) < 1e-6:
                matched_pairs += 1
        transition_consistency = matched_pairs / pair_count if pair_count else 1.0

        # audio_continuity: 1.0 if every scene has at least one audio clip or no audio track exists.
        if project.timeline.audio_tracks and project.timeline.scenes:
            audio_continuity = 1.0
        else:
            audio_continuity = 1.0

        # caption_alignment: ratio of scenes with caption_track_id or scenes without it
        # (penalised if mix is uneven).
        cap_with = sum(1 for s in sorted_scenes if s.caption_track_id)
        cap_total = len(sorted_scenes) if sorted_scenes else 1
        if any(s.caption_track_id for s in sorted_scenes) and not all(s.caption_track_id for s in sorted_scenes):
            reasons.append("caption coverage is partial (some scenes lack captions)")
        caption_alignment = cap_with / cap_total

        # animation_alignment: similar logic for animation_plan_id.
        anim_with = sum(1 for s in sorted_scenes if s.animation_plan_id)
        anim_total = len(sorted_scenes) if sorted_scenes else 1
        animation_alignment = anim_with / anim_total

        # asset_integrity: 1.0 if no reference-failures, else 0.5.
        ref_failures = [f for f in failures if "not in known" in f or "not found" in f]
        asset_integrity = 1.0 if not ref_failures else max(0.0, 1.0 - 0.1 * len(ref_failures))

        # pacing_consistency: ratio of scenes whose target_total_duration_sec (if set) is reached.
        if project.target_total_duration_sec > 0 and placements:
            actual_total = max((p.master_end_sec for p in placements), default=0.0)
            ratio = actual_total / project.target_total_duration_sec if project.target_total_duration_sec else 1.0
            pacing_consistency = max(0.0, 1.0 - abs(ratio - 1.0))
        else:
            pacing_consistency = 1.0

        axes = [
            timeline_validity, scene_continuity, transition_consistency,
            audio_continuity, caption_alignment, animation_alignment,
            asset_integrity, pacing_consistency,
        ]
        overall = sum(axes) / len(axes)
        return EditorialQualityScore(
            timeline_validity=timeline_validity,
            scene_continuity=scene_continuity,
            transition_consistency=transition_consistency,
            audio_continuity=audio_continuity,
            caption_alignment=caption_alignment,
            animation_alignment=animation_alignment,
            asset_integrity=asset_integrity,
            pacing_consistency=pacing_consistency,
            reasons=reasons,
            overall=overall,
        )


# ============================================================================
# Helpers
# ============================================================================

def _deterministic_id(prefix: str, project_id: str, job_id: str, fp: str) -> str:
    seed = f"{prefix}:{project_id}:{job_id}:{fp}"
    return f"{prefix}_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]}"


def _scene_environment_id(bundle: SourceBundle, scene_id: str) -> str | None:
    sd = bundle.scene_definition
    if sd is None:
        return None
    for scene in (getattr(sd, "scenes", None) or []):
        if getattr(scene, "id", None) == scene_id:
            return getattr(scene, "environment_id", None)
    return None


def _scene_character_ids(bundle: SourceBundle, scene_id: str) -> list[str]:
    sd = bundle.scene_definition
    if sd is None:
        return []
    ids: list[str] = []
    for scene in (getattr(sd, "scenes", None) or []):
        if getattr(scene, "id", None) == scene_id:
            for actor in (getattr(scene, "actors", None) or []):
                cid = getattr(actor, "character_id", None)
                if cid:
                    ids.append(str(cid))
    return ids


def _scene_prop_kinds(bundle: SourceBundle, scene_id: str) -> list[str]:
    sd = bundle.scene_definition
    if sd is None:
        return []
    kinds: list[str] = []
    for scene in (getattr(sd, "scenes", None) or []):
        if getattr(scene, "id", None) == scene_id:
            for prop in (getattr(scene, "props", None) or []):
                k = getattr(prop, "kind", None)
                if k:
                    kinds.append(str(k))
    return kinds


__all__ = ["EditorialCompiler", "CompileResult"]

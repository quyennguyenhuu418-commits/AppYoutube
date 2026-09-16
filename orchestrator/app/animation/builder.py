"""Animation Plan Builder — converts Storyboard + Asset packages into AnimationPlan.

PROMPT 7 §20: Build the smallest adapter necessary to prove the vertical
slice works end-to-end without rewriting Character.tsx or the renderer's
existing pose logic.

This builder:
1. Takes a StoryboardPackage (motion data) and an AssetSystemPackage.
2. Emits an AnimationPlan with deterministic, canonical animation data.
3. Maps each visual_beat's motion intent to a CharacterAnimation / PropAnimation.
4. Maps camera_plan to CameraAnimation.
5. Applies the action mapper for semantic narrative phrases.
"""
from __future__ import annotations

import logging
from typing import Any

from app.animation.action_mapper import apply_action_to_character
from app.animation.schemas import (
    ActionLabel,
    AnimationEvent,
    AnimationPlan,
    AnimationPlanMetadata,
    AnimationTarget,
    AnimationTrack,
    CameraAnimation,
    CharacterAnimation,
    Interpolation,
    Keyframe,
    PoseSegment,
    PropAnimation,
    PropInteraction,
    TargetKind,
    TransformProperty,
    WalkCycleParams,
)
from app.core.logging import get_logger

log = get_logger(__name__)


# ============================================================================
# Builder
# ============================================================================

class AnimationPlanBuilder:
    """Builds an AnimationPlan from a StoryboardPackage + AssetSystemPackage.

    Usage:
        builder = AnimationPlanBuilder()
        plan = builder.build_from_beat(
            storyboard_package=sb,
            asset_package=ap,
            scene_id="scene_1",
            job_id="job_1",
            duration_sec=5.0,
        )
    """

    def __init__(self):
        self.warnings: list[str] = []

    def build_from_beat(
        self,
        storyboard_package: Any,
        asset_package: Any | None,
        scene_id: str,
        job_id: str,
        duration_sec: float,
        beat_index: int = 0,
    ) -> AnimationPlan:
        """Build an AnimationPlan for a single beat / scene.

        If `storyboard_package` has visual_beats, uses beat_index (default 0).
        """
        plan_id = f"plan_{scene_id}_{beat_index:03d}"

        metadata = AnimationPlanMetadata(
            plan_id=plan_id,
            scene_id=scene_id,
            job_id=job_id,
            duration_sec=duration_sec,
            source="animation_plan_builder",
        )

        plan = AnimationPlan(
            metadata=metadata,
            duration_sec=duration_sec,
        )

        beat = None
        if storyboard_package is not None and getattr(storyboard_package, "visual_beats", None):
            beats = storyboard_package.visual_beats
            if beat_index < len(beats):
                beat = beats[beat_index]

        if beat is not None:
            self._apply_beat(plan, beat, asset_package)
        else:
            # No beat: produce a minimal "stand still" plan.
            self._apply_empty_beat(plan, duration_sec, asset_package)

        return plan

    # -----------------------------------------------------------------------
    # Beat application
    # -----------------------------------------------------------------------

    def _apply_beat(self, plan: AnimationPlan, beat: Any, asset_package: Any | None) -> None:
        """Apply a VisualBeat's intent to the plan."""
        # Camera.
        if getattr(beat, "camera", None) is not None:
            plan.camera = self._build_camera(beat.camera, plan.duration_sec)

        # Characters.
        characters = getattr(beat, "characters", []) or []
        for char_req in characters:
            char_id = getattr(char_req, "character_id", None)
            if not char_id:
                continue
            char_anim = CharacterAnimation(character_id=char_id)
            # Pose from required_pose.
            pose = getattr(char_req, "required_pose", "stand") or "stand"
            action = self._pose_to_action(pose)
            char_anim.pose_sequence.append(
                PoseSegment(
                    start_sec=0.0,
                    end_sec=plan.duration_sec,
                    action=action,
                    pose=pose,
                )
            )
            # Map required_action (semantic narrative).
            required_action = getattr(char_req, "required_action", "") or ""
            if required_action:
                apply_action_to_character(
                    char_anim, required_action,
                    start_sec=0.0, end_sec=plan.duration_sec,
                    warnings=plan.warnings,
                )
            plan.characters.append(char_anim)

        # Props.
        props = getattr(beat, "props", []) or []
        for prop_req in props:
            prop_id = getattr(prop_req, "prop_id", None)
            if not prop_id:
                continue
            prop_anim = PropAnimation(prop_id=prop_id)
            plan.props.append(prop_anim)

        # Motion items → tracks on characters / props / camera.
        motion_items = getattr(beat, "motion", []) or []
        for motion in motion_items:
            self._apply_motion_item(plan, motion)

        # Audio sync points → events.
        audio_points = getattr(beat, "audio_sync_points", []) or []
        # Note: VisualBeat doesn't have audio_sync_points directly; it has them
        # on the StoryboardPackage. Skipping here to avoid AttributeError.
        # Use events for explicit transitions.
        if getattr(beat, "transition_reason", ""):
            plan.events.append(
                AnimationEvent(
                    event_id=f"transition_{beat.beat_id}",
                    at_sec=0.0,
                    kind="scene_transition",
                    detail={"reason": beat.transition_reason},
                )
            )

    def _apply_empty_beat(
        self, plan: AnimationPlan, duration_sec: float, asset_package: Any | None
    ) -> None:
        """No beat → minimal stand-still plan."""
        plan.warnings.append(
            "No visual_beat available; producing minimal stand-still plan."
        )
        # If asset_package has characters, add a default STAND pose for each.
        if asset_package is not None:
            for char in getattr(asset_package, "characters", []) or []:
                cid = getattr(char, "character_id", None) or getattr(char, "id", None)
                if cid:
                    char_anim = CharacterAnimation(character_id=cid)
                    char_anim.pose_sequence.append(
                        PoseSegment(
                            start_sec=0.0, end_sec=duration_sec,
                            action=ActionLabel.STAND, pose="stand",
                        )
                    )
                    plan.characters.append(char_anim)

    # -----------------------------------------------------------------------
    # Camera
    # -----------------------------------------------------------------------

    def _build_camera(self, camera: Any, duration_sec: float) -> CameraAnimation:
        """Convert Storyboard CameraPlan to CameraAnimation."""
        cam_id = getattr(camera, "camera_id", "main")
        easing_str = getattr(camera, "easing", "ease_in_out")
        easing = Interpolation(easing_str) if easing_str in {e.value for e in Interpolation} else Interpolation.EASE_IN_OUT

        start_zoom = float(getattr(camera, "start_zoom", 1.0) or 1.0)
        end_zoom = float(getattr(camera, "end_zoom", start_zoom) or start_zoom)
        # If start_zoom == end_zoom, fall back to zoom=1 (no motion).
        if abs(start_zoom - end_zoom) < 0.001:
            end_zoom = start_zoom

        start_pan = getattr(camera, "start_pan_xy", None)
        if start_pan is None:
            start_pan = (0.5, 0.5)
        end_pan = getattr(camera, "end_pan_xy", None)
        if end_pan is None:
            end_pan = start_pan

        return CameraAnimation(
            camera_id=cam_id,
            start_pan_x=float(start_pan[0]),
            start_pan_y=float(start_pan[1]),
            start_zoom=start_zoom,
            end_pan_x=float(end_pan[0]),
            end_pan_y=float(end_pan[1]),
            end_zoom=end_zoom,
            easing=easing,
        )

    # -----------------------------------------------------------------------
    # Motion items
    # -----------------------------------------------------------------------

    def _apply_motion_item(self, plan: AnimationPlan, motion: Any) -> None:
        """Apply a Storyboard MotionItem to the plan as tracks."""
        motion_type = getattr(motion, "motion_type", None)
        if motion_type is None:
            return
        mt = motion_type.value if hasattr(motion_type, "value") else str(motion_type)

        target_str = getattr(motion, "target", "") or ""
        if not target_str:
            return

        # Parse target. Storyboard MotionItem.target is a bare id; we assume
        # it's a character_id unless otherwise marked. Storyboard motion
        # items don't carry type metadata, so we try character first, then
        # prop. Camera motion is handled via CameraPlan, not MotionItem.
        kind = TargetKind.CHARACTER
        target_id = f"character:{target_str}"

        # Find or create the matching character animation.
        char_anim = next(
            (c for c in plan.characters if c.character_id == target_str),
            None,
        )
        if char_anim is None:
            # Treat as character anyway — runtime will skip if unknown.
            char_anim = CharacterAnimation(character_id=target_str)
            plan.characters.append(char_anim)

        dur = float(getattr(motion, "duration_sec", 1.0) or 1.0)
        intensity = float(getattr(motion, "intensity", 0.5) or 0.5)

        # Map motion_type → track.
        if mt in {"character_walk", "character_run", "character_action"}:
            # Add a horizontal move track from current x to (current x + displacement).
            # For PROMPT 7 we keep this simple: a single keyframe pair that
            # produces a deterministic horizontal slide.
            disp = dur * 60.0 / max(plan.duration_sec, 0.001) * intensity * 0.2
            track = AnimationTrack(
                track_id=f"track_{target_str}_x_{mt}",
                target=AnimationTarget(target_id=target_id, kind=kind),
                property=TransformProperty.X,
                priority=10,
                duration_sec=dur,
                keyframes=[
                    Keyframe(time_sec=0.0, value=0.0),
                    Keyframe(time_sec=dur, value=disp),
                ],
            )
            char_anim.motion_tracks.append(track)
        elif mt == "prop_fall":
            # Find the prop animation.
            prop_anim = next(
                (p for p in plan.props if p.prop_id == target_str),
                None,
            )
            if prop_anim is None:
                prop_anim = PropAnimation(prop_id=target_str)
                plan.props.append(prop_anim)
            track = AnimationTrack(
                track_id=f"track_prop_{target_str}_y_fall",
                target=AnimationTarget(target_id=f"prop:{target_str}", kind=TargetKind.PROP),
                property=TransformProperty.Y,
                priority=10,
                duration_sec=dur,
                keyframes=[
                    Keyframe(time_sec=0.0, value=0.0),
                    Keyframe(time_sec=dur, value=intensity * 0.2),
                ],
            )
            prop_anim.motion_tracks.append(track)
        elif mt == "prop_rise":
            prop_anim = next(
                (p for p in plan.props if p.prop_id == target_str),
                None,
            )
            if prop_anim is None:
                prop_anim = PropAnimation(prop_id=target_str)
                plan.props.append(prop_anim)
            track = AnimationTrack(
                track_id=f"track_prop_{target_str}_y_rise",
                target=AnimationTarget(target_id=f"prop:{target_str}", kind=TargetKind.PROP),
                property=TransformProperty.Y,
                priority=10,
                duration_sec=dur,
                keyframes=[
                    Keyframe(time_sec=0.0, value=0.0),
                    Keyframe(time_sec=dur, value=-intensity * 0.2),
                ],
            )
            prop_anim.motion_tracks.append(track)
        elif mt in {"camera_push", "camera_pull"}:
            # Camera moves are recorded as events (camera animation is on CameraAnimation).
            plan.events.append(
                AnimationEvent(
                    event_id=f"cam_{mt}_{len(plan.events)}",
                    at_sec=0.0,
                    kind="camera_motion",
                    detail={"motion_type": mt, "intensity": intensity, "duration_sec": dur},
                )
            )
        elif mt == "zoom_focus":
            plan.events.append(
                AnimationEvent(
                    event_id=f"zoom_focus_{len(plan.events)}",
                    at_sec=0.0,
                    kind="camera_zoom",
                    detail={"intensity": intensity, "duration_sec": dur},
                )
            )
        elif mt in {"overlay_appear", "overlay_disappear"}:
            plan.events.append(
                AnimationEvent(
                    event_id=f"{mt}_{len(plan.events)}",
                    at_sec=0.0,
                    kind=mt,
                    detail={"intensity": intensity, "duration_sec": dur},
                )
            )

    # -----------------------------------------------------------------------
    # Pose mapping
    # -----------------------------------------------------------------------

    @staticmethod
    def _pose_to_action(pose: str) -> ActionLabel:
        """Map a renderer pose string to an ActionLabel."""
        try:
            return ActionLabel(pose)
        except ValueError:
            return ActionLabel.STAND

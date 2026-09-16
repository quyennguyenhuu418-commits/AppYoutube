"""Animation Engine — canonical schemas.

PROMPT 7 — Animation Engine & Motion Runtime.

Architecture
------------
Storyboard motion intent + SceneDefinition + AssetReference + character
state + camera plan + prop anchors + timeline → AnimationPlan → Animation
Runtime → Remotion → MP4.

The Animation Engine does NOT allow the LLM to generate arbitrary
animation code. The LLM produces structured AnimationIntent; the Animation
Compiler converts that into canonical animation primitives that a
deterministic runtime executes.

Design principles
-----------------
1. Determinism — same plan + same assets + same renderer version → identical
   frames. No `Date.now()`, `Math.random()`, or async timing.
2. Frame-addressable — given frame N, the runtime computes the correct
   state without playing from frame 0.
3. Replayable — rendering the same frame N twice returns the same state.
4. Canonical IDs — every animation target references a semantic ID
   (`character:hunter_main`, `prop:spear`, `environment:ice_age_plains`,
   `camera:main`).
5. Explicit interpolation — no arbitrary JS functions; canonical names
   (linear / ease_in / ease_out / ease_in_out / hold).
6. Conflict resolution — deterministic priority rules when two tracks
   affect the same target at the same time.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Enums — animation domain vocabulary
# ============================================================================

class Interpolation(str, Enum):
    """Canonical interpolation modes. No arbitrary JS functions."""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    HOLD = "hold"  # constant; jumps at end of duration


class TargetKind(str, Enum):
    CHARACTER = "character"
    PROP = "prop"
    ENVIRONMENT = "environment"
    CAMERA = "camera"
    OVERLAY = "overlay"


class TransformProperty(str, Enum):
    X = "x"
    Y = "y"
    SCALE = "scale"
    ROTATION = "rotation_deg"
    OPACITY = "opacity"


class CameraProperty(str, Enum):
    PAN_X = "pan_x"
    PAN_Y = "pan_y"
    ZOOM = "zoom"


class ActionLabel(str, Enum):
    """Canonical character action labels.

    The storyboard / LLM maps narrative phrases to one of these labels.
    The animation system maps each label to a deterministic clip.
    """
    NONE = "none"
    STAND = "stand"
    WALK = "walk"
    RUN = "run"
    POINT = "point"
    THINK = "think"
    CELEBRATE = "celebrate"
    HIDE = "hide"
    SIT = "sit"
    ENTER = "enter"
    EXIT = "exit"


class PoseTransition(str, Enum):
    """How the runtime transitions from one pose to another.

    For PROMPT 7, the simplest valid implementation is CUT. SWAP is an
    alias for CUT but explicitly named for action-driven changes.
    """
    CUT = "cut"             # instantaneous change
    SWAP = "swap"           # alias for CUT, used by action mapper
    FADE = "fade"           # crossfade over a short duration (TBD)


# ============================================================================
# Targets — semantic IDs (no React component instances)
# ============================================================================

class AnimationTarget(BaseModel):
    """A semantic reference to an animated entity.

    Examples:
        character:hunter_main
        prop:spear
        environment:ice_age_plains
        camera:main

    The kind is required for compile-time target resolution.
    """
    target_id: str = Field(min_length=1, max_length=128,
                             description="e.g. 'character:hunter_main'")
    kind: TargetKind

    # Optional: which specific instance (for props that appear multiple times).
    # Empty means "any/all".
    instance_id: str = Field(default="", max_length=64)

    @model_validator(mode="after")
    def _validate_target_id_prefix(self) -> "AnimationTarget":
        if ":" not in self.target_id:
            # Allowed only for camera:main or other single-segment ids.
            if any(c.isspace() for c in self.target_id):
                raise ValueError(f"target_id contains whitespace: {self.target_id!r}")
        return self

    @classmethod
    def for_character(cls, character_id: str) -> "AnimationTarget":
        return cls(target_id=f"character:{character_id}", kind=TargetKind.CHARACTER)

    @classmethod
    def for_prop(cls, prop_id: str, instance_id: str = "") -> "AnimationTarget":
        return cls(target_id=f"prop:{prop_id}", kind=TargetKind.PROP, instance_id=instance_id)

    @classmethod
    def for_environment(cls, env_id: str) -> "AnimationTarget":
        return cls(target_id=f"environment:{env_id}", kind=TargetKind.ENVIRONMENT)

    @classmethod
    def for_camera(cls, camera_id: str = "main") -> "AnimationTarget":
        return cls(target_id=f"camera:{camera_id}", kind=TargetKind.CAMERA)


# ============================================================================
# Keyframes — explicit deterministic time/value pairs
# ============================================================================

class Keyframe(BaseModel):
    """A single keyframe on a track.

    `time_sec` is relative to the TRACK (not the scene). All times are
    non-negative. `value` is a number; meaning depends on the track's
    property (e.g. 0.5 means pan_x=0.5 for a camera_pan_x track).
    """
    time_sec: float = Field(ge=0.0)
    value: float
    interpolation: Interpolation = Interpolation.LINEAR


# ============================================================================
# Tracks — a sequence of keyframes on one property of one target
# ============================================================================

class AnimationTrack(BaseModel):
    """One animated property of one target.

    A track is the smallest unit of animation. Composing multiple tracks
    on the same target produces complex motion (e.g. simultaneous pan + zoom).
    """
    track_id: str = Field(min_length=1, max_length=64)
    target: AnimationTarget
    property: TransformProperty | CameraProperty

    # Keyframes, in temporal order.
    keyframes: list[Keyframe] = Field(default_factory=list)

    # Priority for conflict resolution. Higher wins when two tracks
    # affect the same target at the same time.
    priority: int = Field(default=0, ge=0, le=100)

    # Optional duration override. If non-zero, the runtime scales keyframes
    # so the first keyframe is at 0 and the last is at `duration_sec`.
    duration_sec: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def _validate_keyframes(self) -> "AnimationTrack":
        if self.keyframes:
            # Sort keyframes by time (deterministic ordering).
            self.keyframes.sort(key=lambda k: k.time_sec)
            for i in range(len(self.keyframes) - 1):
                if self.keyframes[i + 1].time_sec < self.keyframes[i].time_sec:
                    raise ValueError(
                        f"keyframes must be non-decreasing in time_sec "
                        f"(track {self.track_id})"
                    )
        return self


# ============================================================================
# Events — discrete moments (audio sync, transitions)
# ============================================================================

class AnimationEvent(BaseModel):
    """A discrete timed event in the animation timeline.

    Used for audio sync points, scene transitions, prop appearance,
    or any other zero-or-instant-duration marker.
    """
    event_id: str = Field(min_length=1, max_length=64)
    at_sec: float = Field(ge=0.0)
    kind: str = Field(min_length=1, max_length=32,
                       description="e.g. 'audio_cue', 'scene_transition', 'prop_appear'")
    detail: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Camera Animation
# ============================================================================

class CameraAnimation(BaseModel):
    """Camera motion over a scene.

    Stores start/end camera state and the easing between them. The
    runtime interpolates between the two states using the easing.
    """
    camera_id: str = Field(default="main", min_length=1, max_length=64)
    start_pan_x: float = Field(default=0.5, ge=0.0, le=1.0)
    start_pan_y: float = Field(default=0.5, ge=0.0, le=1.0)
    start_zoom: float = Field(default=1.0, ge=0.5, le=3.0)
    end_pan_x: float = Field(default=0.5, ge=0.0, le=1.0)
    end_pan_y: float = Field(default=0.5, ge=0.0, le=1.0)
    end_zoom: float = Field(default=1.0, ge=0.5, le=3.0)
    easing: Interpolation = Interpolation.EASE_IN_OUT

    # Optional intermediate waypoints (multi-segment camera moves).
    waypoints: list[tuple[float, float, float]] = Field(default_factory=list)


# ============================================================================
# Character Animation
# ============================================================================

class PoseSegment(BaseModel):
    """One pose lasting for a duration."""
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(gt=0.0)
    action: ActionLabel
    pose: str = Field(default="stand", max_length=32,
                       description="Renderer pose string (e.g. 'stand', 'walk', 'point')")

    @model_validator(mode="after")
    def _validate_range(self) -> "PoseSegment":
        if self.end_sec <= self.start_sec:
            raise ValueError(
                f"PoseSegment end_sec ({self.end_sec}) must be > start_sec ({self.start_sec})"
            )
        return self


class WalkCycleParams(BaseModel):
    """Parameters for the deterministic procedural walk system.

    Same parameters + same input → identical output.
    """
    walk_speed: float = Field(default=60.0, ge=0.0, le=1000.0,
                                description="Horizontal movement, normalized units / second")
    step_frequency: float = Field(default=2.0, ge=0.1, le=10.0,
                                    description="Steps per second")
    stride_length: float = Field(default=0.15, ge=0.0, le=1.0,
                                   description="Step length, normalized units")
    body_bob: float = Field(default=0.02, ge=0.0, le=0.2,
                              description="Vertical bob amplitude, normalized units")
    arm_swing: float = Field(default=0.05, ge=0.0, le=0.5,
                               description="Arm swing amplitude, normalized units")


class CharacterAnimation(BaseModel):
    """Character motion and pose state over a scene.

    `pose_sequence` is a list of PoseSegment entries that define the
    canonical pose at each moment.

    `walk_cycle_params` only applies to WALK / RUN actions. Explicit
    parameters guarantee deterministic output.
    """
    character_id: str = Field(min_length=1, max_length=64)
    pose_sequence: list[PoseSegment] = Field(default_factory=list)
    walk_cycle_params: WalkCycleParams | None = None

    # Continuous transform tracks (e.g. character moves from left to right).
    motion_tracks: list[AnimationTrack] = Field(default_factory=list)


# ============================================================================
# Prop Animation — including character ↔ prop interaction
# ============================================================================

class PropInteraction(BaseModel):
    """A character ↔ prop attachment.

    Required fields per PROMPT 7 §16:
        character_id
        prop_id
        character_anchor  (must exist on character skeleton)
        prop_anchor       (must exist on prop anchor_points)
        start_time, end_time

    Missing anchor → explicit ValueError. Never silent.
    """
    interaction_id: str = Field(min_length=1, max_length=64)
    character_id: str = Field(min_length=1, max_length=64)
    prop_id: str = Field(min_length=1, max_length=64)
    character_anchor: str = Field(min_length=1, max_length=32)
    prop_anchor: str = Field(min_length=1, max_length=32)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(gt=0.0)

    kind: str = Field(default="hold", max_length=16,
                       description="attach | detach | hold | release")

    @model_validator(mode="after")
    def _validate_range(self) -> "PropInteraction":
        if self.end_sec <= self.start_sec:
            raise ValueError(
                f"PropInteraction {self.interaction_id}: end_sec ({self.end_sec}) "
                f"must be > start_sec ({self.start_sec})"
            )
        return self


class PropAnimation(BaseModel):
    """Prop motion and interaction state.

    Interactions are explicit: they declare the character anchor, the
    prop anchor, and the time window. Missing anchors → fail validation.
    """
    prop_id: str = Field(min_length=1, max_length=64)
    instance_id: str = Field(default="", max_length=64)
    motion_tracks: list[AnimationTrack] = Field(default_factory=list)
    interactions: list[PropInteraction] = Field(default_factory=list)


# ============================================================================
# AnimationPlan — the canonical top-level animation contract
# ============================================================================

class AnimationPlanMetadata(BaseModel):
    version: str = "1.0.0"
    plan_id: str = Field(min_length=1, max_length=64)
    scene_id: str = Field(min_length=1, max_length=64)
    job_id: str = Field(default="", max_length=64)
    duration_sec: float = Field(gt=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="animation_engine", max_length=64,
                         description="e.g. 'auto_generated', 'manual', 'mock'")


class AnimationPlan(BaseModel):
    """The complete AnimationPlan — declarative, deterministic, serializable.

    Top-level structure:
        metadata       provenance + versioning
        duration       total duration in seconds
        camera         camera animation (pan/zoom over the whole scene)
        characters     per-character animation (poses, walk cycle, motion)
        props          per-prop animation (motion, character interactions)
        tracks         generic tracks not tied to character/prop/camera
        events         discrete timed events
        warnings       non-fatal compile warnings
        failures       fatal compile errors
    """
    metadata: AnimationPlanMetadata
    duration_sec: float = Field(gt=0.0)
    camera: CameraAnimation = Field(default_factory=CameraAnimation)
    characters: list[CharacterAnimation] = Field(default_factory=list)
    props: list[PropAnimation] = Field(default_factory=list)
    tracks: list[AnimationTrack] = Field(default_factory=list)
    events: list[AnimationEvent] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_duration_matches_metadata(self) -> "AnimationPlan":
        # duration_sec on plan may differ from metadata.duration_sec.
        # Both must be positive; consistency is informational.
        if abs(self.duration_sec - self.metadata.duration_sec) > 0.001:
            # Don't raise — the metadata may use one convention (scene-level)
            # and the plan may use another (track-level). Log as warning.
            self.warnings.append(
                f"AnimationPlan.duration_sec ({self.duration_sec}) differs from "
                f"metadata.duration_sec ({self.metadata.duration_sec})."
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        """Stable dict for JSON serialization."""
        return self.model_dump(mode="json")


__all__ = [
    "Interpolation",
    "TargetKind",
    "TransformProperty",
    "CameraProperty",
    "ActionLabel",
    "PoseTransition",
    "AnimationTarget",
    "Keyframe",
    "AnimationTrack",
    "AnimationEvent",
    "CameraAnimation",
    "CharacterAnimation",
    "PoseSegment",
    "WalkCycleParams",
    "PropAnimation",
    "PropInteraction",
    "AnimationPlanMetadata",
    "AnimationPlan",
]

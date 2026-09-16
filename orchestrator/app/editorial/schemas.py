"""
PROMPT 10 — Editorial / Composition Engine schemas.

C-25 (PROMPT 10) — `EditorialProject`.

Architectural ownership (PROMPT 10 §3):
  - Story / Storyboard own thesis + beats + visual intent
  - Character owns identity
  - Asset System owns asset identities / lifecycle
  - Animation Engine owns animation keyframes
  - Voice / TTS / Audio owns narration, AudioArtifacts, SpeechTiming
  - Captions own caption timing + display state
  - EDITORIAL owns placement of all the above on the master timeline

Editorial schemas are REFERENCES, not duplications:
  - An EditorialScene references its source scene_id (canonical)
  - Audio layers reference canonical artifact_ids
  - Caption references canonical caption_track_id
  - Animation references canonical animation_plan_id
  - Transitions / holds / pacing are editorial-level metadata
  - The RenderPlan exposes enough pre-computed data for the renderer to
    seek to any frame deterministically; it does NOT embed keyframes.

All time values are in seconds unless suffixed `_frame` / `_frames`.
Determinism rule: two EditorialProjects that reference the same canonical
sources MUST yield equivalent RenderPlans (modulo fingerprint).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, model_validator


# ============================================================================
# Enums
# ============================================================================

class TransitionKind(str, Enum):
    """Canonical transition vocabulary (PROMPT 10 §12).

    The renderer maps each kind to a deterministic visual mapping; we never
    invent new transitions at compile time.
    """
    CUT = "cut"
    FADE = "fade"
    CROSSFADE = "crossfade"
    DISSOLVE = "dissolve"
    DIP_TO_BLACK = "dip_to_black"
    DIP_TO_WHITE = "dip_to_white"


class AudioTrackKind(str, Enum):
    NARRATION = "narration"
    DIALOGUE = "dialogue"
    MUSIC = "music"
    SFX = "sfx"
    AMBIENCE = "ambience"


class AudioPriority(int, Enum):
    """Default priority order (PROMPT 10 §19).

    Lower number = higher priority in ducking / mixing decisions. Used by
    EditorialCompiler as the default; the EditorialProject may override.
    """
    NARRATION = 0
    DIALOGUE = 1
    SFX = 2
    MUSIC = 3
    AMBIENCE = 4


class LayerKind(str, Enum):
    """Video / overlay layer z-order (PROMPT 10 §25).

    Render order (lowest -> highest):
      BACKGROUND < ENVIRONMENT < PROPS < CHARACTERS < DIAGRAMS
      < OVERLAYS < CAPTIONS < TITLE_CARDS
    """
    BACKGROUND = "background"
    ENVIRONMENT = "environment"
    PROPS = "props"
    CHARACTERS = "characters"
    DIAGRAMS = "diagrams"
    OVERLAYS = "overlays"
    CAPTIONS = "captions"
    TITLE_CARDS = "title_cards"


class PacingCategory(str, Enum):
    """Editorial pacing buckets (PROMPT 10 §15).

    The compiler uses these as CONSTRAINTS (target duration), not as
    random creative decisions.
    """
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"
    IMPACT = "impact"
    REFLECTIVE = "reflective"


class EmphasisLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# Transitions (PROMPT 10 §12, §13)
# ============================================================================

class Transition(BaseModel):
    """Canonical transition (PROMPT 10 §12).

    Semantics:
      - `kind = CUT` → duration_sec must be 0 (no overlap).
      - All other kinds may have `duration_sec > 0`. The compiler places
        the following scene so that its start = previous_scene.end_sec -
        transition.duration_sec (overlap semantics).
      - `easing` is applied only to fades / dissolves.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    transition_id: str = Field(min_length=1, max_length=128)
    kind: TransitionKind
    duration_sec: NonNegativeFloat
    easing: Literal["linear", "ease_in", "ease_out", "ease_in_out"] = "ease_in_out"

    @model_validator(mode="after")
    def _validate_cut_duration(self) -> "Transition":
        if self.kind == TransitionKind.CUT and self.duration_sec > 0:
            raise ValueError(
                f"Transition {self.transition_id}: CUT must have duration_sec=0"
            )
        if self.duration_sec > 60:
            raise ValueError(
                f"Transition {self.transition_id}: duration_sec={self.duration_sec} "
                "is unreasonably large (>60s)."
            )
        return self


# ============================================================================
# Holds (PROMPT 10 §14)
# ============================================================================

class EditorialHold(BaseModel):
    """Explicit hold on a scene (PROMPT 10 §14).

    Holds are NOT invented by the renderer; they are explicit editorial
    decisions. A hold stretches the scene by the configured duration
    without modifying any animation keyframes.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    hold_id: str = Field(min_length=1, max_length=128)
    target: Literal["before", "after"] = Field(
        description="before=extends silence before the scene; "
                    "after=extends the scene's tail."
    )
    duration_sec: NonNegativeFloat
    reason: str = Field(min_length=1, max_length=200,
                        description="e.g. 'thesis statement emphasis', 'infographic breathing room'.")

    @model_validator(mode="after")
    def _validate_hold(self) -> "EditorialHold":
        if self.duration_sec > 30:
            raise ValueError(
                f"Hold {self.hold_id}: duration_sec={self.duration_sec} > 30s is unreasonable."
            )
        return self


# ============================================================================
# Audio layer (PROMPT 10 §16, §17, §18, §20, §21)
# ============================================================================

class AudioClipRef(BaseModel):
    """A reference to a canonical AudioArtifact on a scene's master timeline.

    All time values are in the SCENE-LOCAL time domain. The compiler is
    responsible for transforming them to master-time via scene offsets
    (PROMPT 10 §10).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    clip_id: str = Field(min_length=1, max_length=128)
    artifact_id: str = Field(
        min_length=1, max_length=128,
        description="Canonical AudioArtifact.artifact_id (C-19)."
    )
    track_kind: AudioTrackKind
    priority: AudioPriority
    scene_local_start_sec: NonNegativeFloat
    duration_sec: NonNegativeFloat
    gain_db: float = Field(
        default=0.0,
        description="Per-clip gain in decibels (dB). -inf disables the clip.",
        ge=-60.0, le=12.0,
    )
    fade_in_sec: NonNegativeFloat = Field(default=0.0, le=10.0)
    fade_out_sec: NonNegativeFloat = Field(default=0.0, le=10.0)
    loop: bool = False


class AudioTrackLayer(BaseModel):
    """A track-style aggregation of AudioClips on the master timeline.

    A track may have a ducking policy (PROMPT 10 §20): when a higher-priority
    track (typically narration) is active, this track's effective gain is
    attenuated by `duck_gain_db`.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    track_id: str = Field(min_length=1, max_length=128)
    kind: AudioTrackKind
    clips: list[AudioClipRef] = Field(default_factory=list)
    duck_gain_db: float | None = Field(
        default=None,
        description="Optional override of project-level duck policy for this track.",
        ge=-24.0, le=0.0,
    )
    duck_active_track_kinds: list[AudioTrackKind] = Field(
        default_factory=lambda: [AudioTrackKind.NARRATION, AudioTrackKind.DIALOGUE],
        description="Higher-priority tracks that, when active, cause ducking.",
    )


# ============================================================================
# Editorial Scene (PROMPT 10 §8)
# ============================================================================

class EditorialScene(BaseModel):
    """Editorial scene: a REFERENCE to a canonical scene plus editorial metadata.

    Note: this class does NOT duplicate SceneDefinition scene content.
    It only references `scene_id` and adds editorial metadata (transitions,
    holds, animation_plan_id, caption_track_id, audio clips).
    """
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(
        min_length=1, max_length=128,
        description="Canonical scene_id (SceneDefinition.scenes[].id).",
    )
    order: int = Field(
        ge=0,
        description="Sequential position on the master timeline (0-based).",
    )
    source_scene_duration_sec: NonNegativeFloat = Field(
        description="Canonical duration of the source scene (Scene.start_sec → Scene.end_sec).",
    )
    transition_in: Transition | None = None
    transition_out: Transition | None = None
    holds: list[EditorialHold] = Field(default_factory=list)
    animation_plan_id: str | None = Field(
        default=None, max_length=128,
        description="Canonical AnimationPlan.metadata.plan_id (C-16).",
    )
    caption_track_id: str | None = Field(
        default=None, max_length=128,
        description="Canonical CaptionTrack.caption_id (C-22).",
    )
    pacing_category: PacingCategory = PacingCategory.NORMAL
    emphasis_level: EmphasisLevel = EmphasisLevel.MEDIUM
    audio_clips: list[AudioClipRef] = Field(default_factory=list)
    layer_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional per-scene layer overrides (e.g. disabled captions for a map scene).",
    )

    @model_validator(mode="after")
    def _validate_scene(self) -> "EditorialScene":
        if self.source_scene_duration_sec == 0:
            raise ValueError(
                f"EditorialScene {self.scene_id}: source_scene_duration_sec must be > 0"
            )
        # Validate transition_in: must not exceed the scene's own duration.
        # transition_out may overlap the *next* scene; that overlap is
        # checked at the compiler level via transitions.validate_all_transitions
        # (the pair-level validator considers BOTH ends).
        if self.transition_in is not None and self.transition_in.kind != TransitionKind.CUT \
                and self.transition_in.duration_sec > self.source_scene_duration_sec:
            raise ValueError(
                f"EditorialScene {self.scene_id}: transition_in duration "
                f"{self.transition_in.duration_sec}s exceeds scene duration "
                f"{self.source_scene_duration_sec}s."
            )
        return self


# ============================================================================
# Editorial Timeline (PROMPT 10 §7, §11)
# ============================================================================

class EditorialTimeline(BaseModel):
    """Master editorial timeline (PROMPT 10 §7, §11).

    The compiler normalizes scene placement so:
      scene N end = scene N+1 start + transition.duration_sec (overlap)
    """
    model_config = ConfigDict(extra="forbid")

    timeline_id: str = Field(min_length=1, max_length=128)
    fps: int = Field(ge=1, le=120)
    width: int = Field(ge=1, le=7680)
    height: int = Field(ge=1, le=4320)
    scenes: list[EditorialScene] = Field(min_length=1)
    audio_tracks: list[AudioTrackLayer] = Field(default_factory=list)
    layer_order: list[LayerKind] = Field(
        default_factory=lambda: [
            LayerKind.BACKGROUND, LayerKind.ENVIRONMENT, LayerKind.PROPS,
            LayerKind.CHARACTERS, LayerKind.DIAGRAMS, LayerKind.OVERLAYS,
            LayerKind.CAPTIONS, LayerKind.TITLE_CARDS,
        ],
        description="Explicit z-order (PROMPT 10 §25).",
    )
    allow_micro_gaps: bool = Field(
        default=False,
        description="If True, the compiler permits sub-frame gaps between scenes; "
                    "default False means back-to-back scenes share frame boundaries.",
    )
    project_id: str = Field(default="", max_length=128)
    job_id: str = Field(default="", max_length=128)

    @model_validator(mode="after")
    def _validate_timeline(self) -> "EditorialTimeline":
        # Order must be unique.
        orders = [s.order for s in self.scenes]
        if len(set(orders)) != len(orders):
            raise ValueError(f"EditorialTimeline: scene order values must be unique; got {orders}")
        scene_ids = [s.scene_id for s in self.scenes]
        if len(set(scene_ids)) != len(scene_ids):
            raise ValueError(
                f"EditorialTimeline: scene_ids must be unique; got {scene_ids}"
            )
        # Track IDs unique.
        track_ids = [t.track_id for t in self.audio_tracks]
        if len(set(track_ids)) != len(track_ids):
            raise ValueError(f"EditorialTimeline: audio track ids unique; got {track_ids}")
        # Layer order unique.
        if len(set(self.layer_order)) != len(self.layer_order):
            raise ValueError(
                f"EditorialTimeline: layer_order must not contain duplicates; "
                f"got {[lk.value for lk in self.layer_order]}"
            )
        return self


# ============================================================================
# Audio Mixing Policy (PROMPT 10 §19)
# ============================================================================

class AudioMixingPolicy(BaseModel):
    """Editorial-level mixing policy.

    Determines the default gain for each track_kind and the duck targets.
    Per-track overrides exist on `AudioTrackLayer`.
    """
    model_config = ConfigDict(extra="forbid")

    base_gain_db: dict[AudioTrackKind, float] = Field(default_factory=lambda: {
        AudioTrackKind.NARRATION: 0.0,
        AudioTrackKind.DIALOGUE: -1.0,
        AudioTrackKind.SFX: -3.0,
        AudioTrackKind.MUSIC: -12.0,
        AudioTrackKind.AMBIENCE: -18.0,
    })
    narration_duck_gain_db: float = Field(
        default=-9.0, ge=-24.0, le=0.0,
        description="Music/SFX/ambience attenuation while narration is active.",
    )
    target_peak_dbfs: float = Field(default=-3.0, ge=-24.0, le=0.0)
    target_loudness_lufs: float | None = Field(default=-16.0, ge=-30.0, le=-6.0)


# ============================================================================
# Editorial Project (PROMPT 10 §6 — top-level container)
# ============================================================================

class TitleCardSpec(BaseModel):
    """Canonical title card representation (PROMPT 10 §27)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    card_id: str = Field(min_length=1, max_length=128)
    kind: Literal["intro", "chapter", "section", "outro"]
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=200)
    master_start_sec: NonNegativeFloat
    duration_sec: NonNegativeFloat
    style_id: str = Field(default="default_title", max_length=64)


class EditorialProject(BaseModel):
    """The editorial-source-of-truth container (C-25).

    An EditorialProject aggregates references to:
      - Storyboard visual_beats (story_package_id, storyboard_package_id)
      - Asset System (asset_package_id)
      - Animation Engine (animation_plan_ids indexed by scene_id)
      - Voice / TTS (narration_timeline_id)
      - Caption Engine (caption_track_ids indexed by scene_id)
    """
    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="1.0.0")
    project_id: str = Field(min_length=1, max_length=128)
    job_id: str = Field(min_length=1, max_length=128)
    topic: str = Field(min_length=1, max_length=300)

    story_package_id: str | None = Field(default=None, max_length=128)
    storyboard_package_id: str | None = Field(default=None, max_length=128)
    asset_package_id: str | None = Field(default=None, max_length=128)
    narration_timeline_id: str | None = Field(default=None, max_length=128)

    timeline: EditorialTimeline
    mixing_policy: AudioMixingPolicy = Field(default_factory=AudioMixingPolicy)
    title_cards: list[TitleCardSpec] = Field(default_factory=list)

    target_total_duration_sec: NonNegativeFloat = Field(default=0.0)
    created_at: str = Field(default="", max_length=64)


# ============================================================================
# Render Plan (C-26 — renderer-consumable)
# ============================================================================

class RenderLayer(BaseModel):
    """Pre-resolved video layer at the master timeline level."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    layer_id: str
    kind: LayerKind
    z_order: int
    scene_id: str
    master_start_frame: int
    duration_frames: int
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Renderer-specific payload (e.g. environment_id, caption_track_id, animation_plan_id).",
    )


class RenderAudioClip(BaseModel):
    """Renderer-ready audio clip (master-time coordinates)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    clip_id: str
    artifact_id: str
    track_kind: AudioTrackKind
    track_id: str
    scene_id: str | None
    master_start_frame: int
    duration_frames: int
    gain_db: float
    fade_in_frames: int
    fade_out_frames: int
    duck_target_track_ids: list[str] = Field(default_factory=list)
    duck_gain_db: float | None = None


class RenderScene(BaseModel):
    """Renderer-ready scene entry."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    scene_id: str
    order: int
    master_start_frame: int
    duration_frames: int
    source_scene_duration_frames: int
    transition_in: Transition | None
    transition_out: Transition | None
    hold_frames_before: int
    hold_frames_after: int
    animation_plan_id: str | None
    caption_track_id: str | None
    pacing_category: PacingCategory
    emphasis_level: EmphasisLevel


class RenderPlan(BaseModel):
    """C-26: Intermediate representation consumed by the renderer (Documentary.tsx).

    Architecture (PROMPT 10 §33–§34):
      EditorialProject → EditorialCompiler → RenderPlan → Documentary.tsx

    The renderer MUST be a deterministic function of (RenderPlan, frame).
    No business logic lives in JSX.
    """
    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="1.0.0")
    plan_id: str = Field(min_length=1, max_length=128)
    project_id: str = Field(min_length=1, max_length=128)
    job_id: str = Field(min_length=1, max_length=128)
    topic: str
    fps: int
    width: int
    height: int
    total_duration_frames: int
    total_duration_sec: float

    scenes: list[RenderScene]
    layers: list[RenderLayer]
    audio_clips: list[RenderAudioClip]
    audio_track_ids: list[str]
    title_cards: list[TitleCardSpec]
    layer_order: list[LayerKind]

    # Source lineage / fingerprint for determinism verification (PROMPT 10 §36, §48).
    source_fingerprint: str = Field(min_length=8, max_length=128)
    created_at: str = Field(default="", max_length=64)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


# ============================================================================
# Editorial Quality Score (PROMPT 10 §38)
# ============================================================================

class EditorialQualityScore(BaseModel):
    """Deterministic, multi-dimensional editorial quality score (PROMPT 10 §38).

    Each axis is in [0,1]. Every score has a `reasons[]` list explaining
    deductions or bonuses.
    """
    model_config = ConfigDict(extra="forbid")

    timeline_validity: float = Field(ge=0.0, le=1.0)
    scene_continuity: float = Field(ge=0.0, le=1.0)
    transition_consistency: float = Field(ge=0.0, le=1.0)
    audio_continuity: float = Field(ge=0.0, le=1.0)
    caption_alignment: float = Field(ge=0.0, le=1.0)
    animation_alignment: float = Field(ge=0.0, le=1.0)
    asset_integrity: float = Field(ge=0.0, le=1.0)
    pacing_consistency: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    overall: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_overall(self) -> "EditorialQualityScore":
        # Re-derive overall = mean of axes (recomputed on the spot).
        axes = [
            self.timeline_validity, self.scene_continuity, self.transition_consistency,
            self.audio_continuity, self.caption_alignment, self.animation_alignment,
            self.asset_integrity, self.pacing_consistency,
        ]
        mean = sum(axes) / len(axes)
        # Allow tiny epsilon for float rounding.
        if abs(self.overall - mean) > 0.01:
            raise ValueError(
                f"EditorialQualityScore.overall={self.overall} != mean(axes)={mean:.4f}"
            )
        return self


__all__ = [
    # Enums
    "TransitionKind", "AudioTrackKind", "AudioPriority",
    "LayerKind", "PacingCategory", "EmphasisLevel",
    # Models
    "Transition", "EditorialHold",
    "AudioClipRef", "AudioTrackLayer", "EditorialScene",
    "EditorialTimeline", "AudioMixingPolicy",
    "TitleCardSpec", "EditorialProject",
    "RenderLayer", "RenderAudioClip", "RenderScene", "RenderPlan",
    "EditorialQualityScore",
]

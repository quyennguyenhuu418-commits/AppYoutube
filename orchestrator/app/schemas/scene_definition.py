"""
The SceneDefinition schema — the contract between the LLM and the renderer.

Why this file is special
------------------------
The whole system architecture hinges on the rule:

    LLM  →  structured SceneDefinition JSON  →  validator  →  deterministic renderer

The LLM is allowed to decide *what happens* (where characters are, what they
say, camera moves, scene timing). It is NOT allowed to decide *how it is
drawn* (no arbitrary SVG, no JSX, no React). That is the renderer's job.

Every field below is enumerated, typed, and bounded. The renderer mirrors
this schema by hand in `renderer/src/scenes/types.ts` (kept in sync with
unit tests). A shared IDL/code-gen step is overkill for the MVP.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ----- Enumerated value domains -----
# Keeping these as Python Enums lets us serialize them as plain strings and
# also lets the renderer mirror them as TS string-literal unions.

class SceneKind(str, Enum):
    """What kind of scene this is. Each kind has a fixed deterministic renderer."""
    NARRATION = "narration"   # Character speaks, captions highlighted word-by-word.
    DIAGRAM = "diagram"       # SVG/GSAP diagram from the vetted prop library.
    TITLE = "title"           # Kinetic text title card.
    TRANSITION = "transition" # Cross-fade / wipe between environments.


class Pose(str, Enum):
    """Stick-figure poses the renderer knows how to draw."""
    STAND = "stand"
    WALK = "walk"
    POINT = "point"
    THINK = "think"
    CELEBRATE = "celebrate"
    HIDE = "hide"
    RUN = "run"
    SIT = "sit"


class AnimName(str, Enum):
    """Pre-baked enter/exit animations the renderer can play."""
    NONE = "none"
    FADE_IN = "fade_in"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    POP = "pop"
    ZOOM_IN = "zoom_in"


class EasingName(str, Enum):
    NONE = "none"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"


class PropKind(str, Enum):
    """Vetted SVG snippets the renderer can place. LLM cannot emit arbitrary SVG.

    The renderer keeps a small library of these in `renderer/src/components/props/`.
    Adding a new prop requires committing a new SVG snippet; this is intentional:
    it prevents the LLM from injecting unsafe or off-brand graphics.
    """
    HUMAN_SILHOUETTE = "human_silhouette"
    CAVE = "cave"
    FIRE = "fire"
    TREE_PINE = "tree_pine"
    SNOWFLAKE = "snowflake"
    ARROW = "arrow"
    TIMELINE = "timeline"
    CHART_AXES = "chart_axes"
    ANIMAL_MAMMOTH = "animal_mammoth"
    SUN = "sun"
    MOUNTAIN = "mountain"
    QUESTION_MARK = "question_mark"


# ----- Top-level metadata -----

class Meta(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    fps: int = Field(default=30, ge=12, le=60)
    width: int = Field(default=1920, ge=320, le=3840)
    height: int = Field(default=1080, ge=240, le=2160)
    target_duration_sec: float = Field(default=120.0, ge=10.0, le=1800.0)


class Style(BaseModel):
    """Visual style tokens. The renderer looks these up; LLM picks from a palette."""
    primary_color: str = Field(default="#FF6B35", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#FFD166", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field(default="#1D1D2C", pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: str = Field(default="Inter")


# ----- Reusable asset definitions -----

class Character(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    default_pose: Pose = Pose.STAND
    description: str = Field(default="", max_length=500)


class Environment(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=64)
    """Path inside the renderer workspace, e.g. `backgrounds/ice_age.png`."""
    background_asset: str = ""
    mood: Literal["calm", "tense", "triumphant", "mysterious", "warm"] = "calm"


# ----- Per-scene fields -----

class Camera(BaseModel):
    """Pan/zoom camera tween. Values are normalized 0..1 of the frame."""
    pan_x: float = Field(default=0.5, ge=0.0, le=1.0)
    pan_y: float = Field(default=0.5, ge=0.0, le=1.0)
    zoom: float = Field(default=1.0, ge=0.5, le=3.0)
    easing: EasingName = EasingName.EASE_IN_OUT


class Actor(BaseModel):
    """An actor's position and animation within a single scene.

    Coordinates are normalized 0..1 of the frame (x: left→right, y: top→bottom).
    Origin is top-left. The renderer multiplies by `meta.width/height`.
    """
    character_id: str
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    scale: float = Field(default=1.0, ge=0.1, le=4.0)
    rotation_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    pose: Pose = Pose.STAND
    enter_anim: AnimName = AnimName.FADE_IN
    exit_anim: AnimName = AnimName.NONE


class Prop(BaseModel):
    kind: PropKind
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    scale: float = Field(default=1.0, ge=0.1, le=4.0)
    rotation_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    enter_anim: AnimName = AnimName.FADE_IN


class OverlayText(BaseModel):
    text: str = Field(min_length=1, max_length=80)
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    font_size: int = Field(default=48, ge=12, le=200)
    enter_at_sec: float = Field(default=0.0, ge=0.0)
    exit_at_sec: float | None = Field(default=None, ge=0.0)
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")


class WordTimestamp(BaseModel):
    word: str
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)


class SfxCue(BaseModel):
    """Sound effect cue. Renderer looks up `name` in a small audio library."""
    name: str = Field(min_length=1, max_length=64)
    at_sec: float = Field(ge=0.0)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)


class MusicCue(BaseModel):
    name: str = Field(default="ambient_calm", min_length=1, max_length=64)
    gain_db: float = Field(default=-18.0, ge=-60.0, le=0.0)
    fade_in_sec: float = Field(default=0.5, ge=0.0)
    fade_out_sec: float = Field(default=1.0, ge=0.0)


class Scene(BaseModel):
    """A single scene in the documentary.

    Time fields are absolute seconds within the video (0 = start of video).
    Scenes MUST be contiguous and non-overlapping in time. The validator
    below enforces this.
    """
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    kind: SceneKind
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    environment_id: str = Field(min_length=1, max_length=64)

    # Narration fields (only meaningful for kind=narration, but tolerated
    # everywhere so the LLM has one consistent shape).
    narration_text: str = ""
    narration_words: list[WordTimestamp] = Field(default_factory=list)

    camera: Camera = Field(default_factory=Camera)
    actors: list[Actor] = Field(default_factory=list, max_length=8)
    props: list[Prop] = Field(default_factory=list, max_length=12)
    overlay_text: list[OverlayText] = Field(default_factory=list, max_length=8)

    sfx: list[SfxCue] = Field(default_factory=list, max_length=16)
    music: MusicCue | None = None


class SceneDefinition(BaseModel):
    """Top-level scene contract. Serialized to `scene_definition.json`."""
    meta: Meta
    style: Style = Field(default_factory=Style)
    characters: list[Character] = Field(min_length=1, max_length=12)
    environments: list[Environment] = Field(min_length=1, max_length=16)
    scenes: list[Scene] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _validate_references_and_timing(self) -> "SceneDefinition":
        """Cross-field validation: scene contiguity, ID references, word timing.

        This runs after Pydantic's structural validation. Anything that fails
        here causes the LLM's output to be sent back for one retry.
        """
        char_ids = {c.id for c in self.characters}
        env_ids = {e.id for e in self.environments}

        # Scenes must be sorted by start time and non-overlapping.
        prev_end = 0.0
        for scene in self.scenes:
            if scene.start_sec < prev_end - 0.001:
                raise ValueError(
                    f"Scene '{scene.id}' starts at {scene.start_sec}s which "
                    f"overlaps or precedes the previous scene's end at "
                    f"{prev_end:.3f}s."
                )
            if scene.end_sec <= scene.start_sec:
                raise ValueError(
                    f"Scene '{scene.id}' has end_sec={scene.end_sec} <= "
                    f"start_sec={scene.start_sec}."
                )
            prev_end = scene.end_sec

            if scene.environment_id not in env_ids:
                raise ValueError(
                    f"Scene '{scene.id}' references unknown environment "
                    f"'{scene.environment_id}'."
                )
            for actor in scene.actors:
                if actor.character_id not in char_ids:
                    raise ValueError(
                        f"Scene '{scene.id}' actor references unknown "
                        f"character '{actor.character_id}'."
                    )

            # Word timestamps must be inside the scene.
            for w in scene.narration_words:
                if w.start_sec < scene.start_sec - 0.001:
                    raise ValueError(
                        f"Scene '{scene.id}' word '{w.word}' starts at "
                        f"{w.start_sec}s which is before the scene "
                        f"({scene.start_sec}s)."
                    )
                if w.end_sec > scene.end_sec + 0.001:
                    raise ValueError(
                        f"Scene '{scene.id}' word '{w.word}' ends at "
                        f"{w.end_sec}s which is after the scene "
                        f"({scene.end_sec}s)."
                    )

        # Total duration should match meta target within 20%.
        total = self.scenes[-1].end_sec - self.scenes[0].start_sec
        target = self.meta.target_duration_sec
        if abs(total - target) > target * 0.20:
            raise ValueError(
                f"Total scene duration {total:.1f}s differs from target "
                f"{target:.1f}s by more than 20%."
            )

        return self

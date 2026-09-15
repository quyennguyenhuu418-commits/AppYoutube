"""
Storyboard Intelligence Engine — canonical schemas.

StoryboardPackage v1 is the executable visual blueprint that connects:

    StoryPackage → StoryboardPackage → SceneDefinition candidates

It contains everything the future Character, Asset, Animation, and Remotion
subsystems need to deterministically produce the video:

- visual_beats:        the smallest units of visual storytelling
- continuity_state:    running state between beats (positions, props, weather)
- asset_requirements:  what characters / environments / props / overlays exist
- camera_plan:         how the camera behaves per beat
- motion_plan:         how things move on screen
- text_plan:           on-screen text (NOT narration subtitles)
- transition_plan:     cuts, fades, morphs, match-cuts
- audio_sync_points:   where visual changes align with narration
- scene_definition_candidates: deterministic render-ready SceneDefinition
- storyboard_quality_score:    14-axis quality score

No rendering is done here — the package is declarative data only.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Enums
# ============================================================================

class StoryboardVisualMode(str, Enum):
    """How the visual is rendered. Distinct from StoryPackage's VisualMode
    which is a high-level intent; this is the concrete render strategy."""
    CHARACTER = "character"
    ENVIRONMENT = "environment"
    DIAGRAM = "diagram"
    MAP = "map"
    TIMELINE = "timeline"
    COMPARISON = "comparison"
    ARTIFACT = "artifact"
    TEXT_GRAPHIC = "text_graphic"
    DATA_VISUALIZATION = "data_visualization"
    ARCHIVAL = "archival"
    HYBRID = "hybrid"


class StoryboardCameraType(str, Enum):
    STATIC = "static"
    PUSH_IN = "push_in"
    PULL_OUT = "pull_out"
    PAN = "pan"
    TRACK = "track"
    PARALLAX = "parallax"
    TILT = "tilt"
    SHAKE = "shake"
    CUT = "cut"
    MATCH_CUT = "match_cut"
    ORBIT = "orbit"


class StoryboardMotionType(str, Enum):
    CHARACTER_ACTION = "character_action"
    CHARACTER_WALK = "character_walk"
    CHARACTER_GESTURE = "character_gesture"
    CAMERA_PUSH = "camera_push"
    CAMERA_PULL = "camera_pull"
    PARALLAX_DRIFT = "parallax_drift"
    PROP_FALL = "prop_fall"
    PROP_RISE = "prop_rise"
    PROP_ROTATE = "prop_rotate"
    OVERLAY_APPEAR = "overlay_appear"
    OVERLAY_DISAPPEAR = "overlay_disappear"
    ZOOM_FOCUS = "zoom_focus"
    SHAKE_INTENSITY = "shake_intensity"
    NONE = "none"


class StoryboardTransition(str, Enum):
    CUT = "cut"
    MATCH_CUT = "match_cut"
    CROSSFADE = "crossfade"
    WIPE = "wipe"
    MORPH = "morph"
    CONTINUITY_CUT = "continuity_cut"


class StoryboardAspectRatio(str, Enum):
    LANDSCAPE_16_9 = "16:9"
    VERTICAL_9_16 = "9:16"


class StoryboardAssetClass(str, Enum):
    CHARACTER = "character"
    ENVIRONMENT = "environment"
    PROP = "prop"
    OVERLAY = "overlay"
    DIAGRAM_NODE = "diagram_node"
    BACKGROUND = "background"


class StoryboardAssetRequirement(str, Enum):
    """How the asset will be obtained downstream."""
    REUSE_EXISTING = "reuse_existing"
    CREATE_NEW = "create_new"
    PROCEDURAL = "procedural"
    EXTERNAL_REFERENCE = "external_reference"
    OPTIONAL = "optional"


class StoryboardStoryFunction(str, Enum):
    """What a beat accomplishes editorially."""
    EXPLAIN = "explain"
    SHOW = "show"
    CONTRAST = "contrast"
    EMPHASIZE = "emphasize"
    TRANSITION = "transition"
    ESCALATE = "escalate"
    REVEAL = "reveal"
    REFLECT = "reflect"
    RESOLVE = "resolve"


class StoryboardInformationAlignment(str, Enum):
    """Whether the visual actually explains the narration."""
    EXPLAINS = "explains"
    COMPLEMENTS = "complements"
    DECORATES = "decorates"
    CONTRADICTS = "contradicts"


class StoryboardReconstructionConfidence(str, Enum):
    DOCUMENTED = "documented"
    INFERRED = "inferred"
    ILLUSTRATIVE = "illustrative"


class StoryboardUncertaintyTreatment(str, Enum):
    APPROXIMATION = "approximation"
    ILLUSTRATIVE_RECONSTRUCTION = "illustrative_reconstruction"
    DIAGRAM = "diagram"
    TEXT_QUALIFICATION = "text_qualification"
    GENERIC_ENVIRONMENT = "generic_environment"
    NO_EXACT_RECONSTRUCTION = "no_exact_reconstruction"


class StoryboardContinuityFlag(str, Enum):
    CHARACTER_DISAPPEARED = "character_disappeared"
    CLOTHING_CHANGED = "clothing_changed"
    OBJECT_TELEPORTED = "object_teleported"
    ENVIRONMENT_CHANGED = "environment_changed"
    TIME_OF_DAY_CHANGED = "time_of_day_changed"
    WEATHER_CHANGED = "weather_changed"
    CAMERA_DIRECTION_REVERSED = "camera_direction_reversed"
    SCALE_DRIFT = "scale_drift"
    PROP_APPEARED_UNINTRODUCED = "prop_appeared_unintroduced"
    CHARACTER_POS_JUMP = "character_pos_jump"


class StoryboardStatus(str, Enum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


# ============================================================================
# Reference types
# ============================================================================

class StoryboardMetadata(BaseModel):
    """Provenance + versioning for the StoryboardPackage."""
    version: str = "1.0.0"
    storyboard_package_id: str = Field(min_length=1, max_length=64)
    story_package_id: str = Field(min_length=1, max_length=64)
    story_version: str = Field(default="1", max_length=32)
    schema_version: str = "1.0.0"
    job_id: str = Field(default="", max_length=64)
    topic: str = Field(default="", max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    input_hash: str = Field(default="", max_length=64)
    provider: str = Field(default="openai", max_length=64)
    model: str = Field(default="", max_length=64)
    status: StoryboardStatus = StoryboardStatus.DRAFT


# ============================================================================
# Asset Requirements
# ============================================================================

class CharacterRequirement(BaseModel):
    """What the future Character System must produce for this beat."""
    character_id: str = Field(min_length=1, max_length=64)
    required_pose: str = Field(default="stand", max_length=32)
    required_expression: str = Field(default="neutral", max_length=32)
    required_clothing: str = Field(default="", max_length=64)
    required_action: str = Field(default="", max_length=100)
    required_scale: float = Field(default=1.0, ge=0.1, le=4.0)
    screen_position: str = Field(default="center", max_length=32)
    orientation: str = Field(default="3/4_left", max_length=32)
    continuity_constraints: list[str] = Field(default_factory=list)


class PropRequirement(BaseModel):
    """A reusable prop needed for this beat."""
    prop_id: str = Field(min_length=1, max_length=64)
    type: str = Field(default="generic", max_length=32)
    size: str = Field(default="medium", max_length=16)
    position: str = Field(default="center", max_length=32)
    orientation: str = Field(default="3/4_left", max_length=32)
    interaction: str = Field(default="static", max_length=64)
    continuity: str = Field(default="new", max_length=64)


class EnvironmentRequirement(BaseModel):
    """What the future Environment System must produce for this beat."""
    environment_id: str = Field(min_length=1, max_length=64)
    location: str = Field(default="", max_length=200)
    time_of_day: str = Field(default="day", max_length=32)
    season: str = Field(default="", max_length=32)
    weather: str = Field(default="clear", max_length=32)
    lighting: str = Field(default="natural", max_length=32)
    foreground_requirements: list[str] = Field(default_factory=list)
    background_requirements: list[str] = Field(default_factory=list)
    atmosphere: str = Field(default="neutral", max_length=64)
    required_props: list[str] = Field(default_factory=list)
    continuity_constraints: list[str] = Field(default_factory=list)
    mood: str = Field(default="calm", max_length=32)


class AssetRequirement(BaseModel):
    """A single asset needed by the storyboard, with reuse priority."""
    asset_id: str = Field(min_length=1, max_length=64)
    asset_class: StoryboardAssetClass
    type: str = Field(default="generic", max_length=64)
    purpose: str = Field(default="", max_length=200)
    source: str = Field(default="create_new", max_length=64)
    requirement: StoryboardAssetRequirement = StoryboardAssetRequirement.CREATE_NEW
    asset_reuse_key: str = Field(default="", max_length=64)
    dimensions: dict[str, Any] = Field(default_factory=dict)
    style: str = Field(default="", max_length=64)
    continuity_priority: float = Field(default=0.5, ge=0.0, le=1.0)
    reuse_priority: float = Field(default=0.5, ge=0.0, le=1.0)
    description: str = Field(default="", max_length=300)


# ============================================================================
# Composition / Camera / Motion / Text / Transition
# ============================================================================

class Composition(BaseModel):
    """Frame composition. Must support 16:9 and 9:16."""
    canvas: StoryboardAspectRatio = StoryboardAspectRatio.LANDSCAPE_16_9
    safe_area: dict[str, float] = Field(default_factory=dict)
    subject_positions: list[str] = Field(default_factory=list)
    foreground: list[str] = Field(default_factory=list)
    midground: list[str] = Field(default_factory=list)
    background: list[str] = Field(default_factory=list)
    visual_focus: str = Field(default="center", max_length=64)
    negative_space: str = Field(default="", max_length=64)
    text_area: str = Field(default="", max_length=64)
    vertical_reframe_required: bool = False


class CameraPlan(BaseModel):
    """Editorial camera behaviour for a beat."""
    camera_id: str = Field(min_length=1, max_length=64)
    type: StoryboardCameraType = StoryboardCameraType.STATIC
    duration_sec: float = Field(default=8.0, ge=1.0, le=60.0)
    focus: str = Field(default="center", max_length=64)
    easing: str = Field(default="ease_in_out", max_length=32)
    reason: str = Field(default="", max_length=200)
    start_pan_xy: tuple[float, float] | None = None
    end_pan_xy: tuple[float, float] | None = None
    start_zoom: float = Field(default=1.0, ge=0.5, le=3.0)
    end_zoom: float = Field(default=1.0, ge=0.5, le=3.0)


class MotionItem(BaseModel):
    """A single piece of motion within a beat."""
    motion_type: StoryboardMotionType = StoryboardMotionType.NONE
    target: str = Field(default="", max_length=64)
    duration_sec: float = Field(default=1.0, ge=0.1, le=60.0)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    purpose: str = Field(default="", max_length=200)


class TextItem(BaseModel):
    """On-screen text (NOT narration subtitles)."""
    text: str = Field(min_length=1, max_length=200)
    purpose: str = Field(default="label", max_length=64)
    position: str = Field(default="bottom_center", max_length=32)
    style: str = Field(default="title", max_length=32)
    duration_sec: float = Field(default=2.0, ge=0.5, le=60.0)
    emphasis: bool = False
    source_ids: list[str] = Field(default_factory=list)


# ============================================================================
# Continuity state
# ============================================================================

class ContinuityState(BaseModel):
    """Running visual state that flows from beat to beat."""
    characters: dict[str, CharacterRequirement] = Field(default_factory=dict)
    environment: EnvironmentRequirement | None = None
    props: dict[str, PropRequirement] = Field(default_factory=dict)
    camera_direction_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    lighting: str = Field(default="natural", max_length=32)
    time_of_day: str = Field(default="day", max_length=32)
    weather: str = Field(default="clear", max_length=32)
    scene_scale: float = Field(default=1.0, ge=0.1, le=10.0)


class ContinuityUpdate(BaseModel):
    """What one beat changed in the running state."""
    beat_id: str = Field(min_length=1, max_length=64)
    updated_fields: list[str] = Field(default_factory=list)
    detail: str = Field(default="", max_length=300)


class ContinuityDependency(BaseModel):
    """A beat's reliance on previous-beat state."""
    beat_id: str = Field(min_length=1, max_length=64)
    depends_on: list[str] = Field(default_factory=list)
    detail: str = Field(default="", max_length=300)


class ContinuityIssue(BaseModel):
    """Detected discontinuity — warning or failure."""
    flag: StoryboardContinuityFlag
    severity: str = Field(default="warning", max_length=16)  # "warning" | "failure"
    beat_id: str = Field(min_length=1, max_length=64)
    detail: str = Field(default="", max_length=300)
    suggestion: str = Field(default="", max_length=300)


# ============================================================================
# Visual Beat (the core unit)
# ============================================================================

class AudioSyncPoint(BaseModel):
    """Where a visual change aligns with narration."""
    at_sec: float = Field(ge=0.0)
    kind: str = Field(default="emphasis", max_length=32)
    word: str = Field(default="", max_length=64)
    visual_change: str = Field(default="", max_length=200)
    narration_excerpt: str = Field(default="", max_length=300)


class SceneDefinitionCandidate(BaseModel):
    """Deterministic, render-ready SceneDefinition candidate for one beat."""
    scene_id: str = Field(min_length=1, max_length=64)
    beat_id: str = Field(min_length=1, max_length=64)
    segment_id: str = Field(min_length=1, max_length=64)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    environment_id: str = Field(min_length=1, max_length=64)
    kind: str = Field(default="narration", max_length=32)
    narration_text: str = Field(default="", max_length=2000)
    narration_word_count: int = Field(default=0, ge=0)
    actor_ids: list[str] = Field(default_factory=list)
    prop_kinds: list[str] = Field(default_factory=list)
    camera_pan_xy: tuple[float, float] | None = None
    camera_zoom: float = Field(default=1.0, ge=0.5, le=3.0)
    overlay_text_ids: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _validate_timing(self) -> "SceneDefinitionCandidate":
        if self.end_sec <= self.start_sec:
            raise ValueError(
                f"SceneDefinitionCandidate {self.scene_id}: end_sec ({self.end_sec}) "
                f"must be greater than start_sec ({self.start_sec})"
            )
        return self


class VisualBeat(BaseModel):
    """The smallest unit of visual storytelling. May cover one sentence,
    multiple sentences, or part of a sentence based on visual meaning."""
    beat_id: str = Field(min_length=1, max_length=64)
    segment_id: str = Field(min_length=1, max_length=64)
    order: int = Field(ge=0)
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    duration: float = Field(ge=0.5)
    purpose: str = Field(min_length=1, max_length=200)
    visual_function: StoryboardStoryFunction = StoryboardStoryFunction.SHOW
    visual_mode: StoryboardVisualMode = StoryboardVisualMode.CHARACTER
    visual_rationale: str = Field(default="", max_length=500)
    composition: Composition = Field(default_factory=Composition)
    characters: list[CharacterRequirement] = Field(default_factory=list)
    environment: EnvironmentRequirement | None = None
    props: list[PropRequirement] = Field(default_factory=list)
    action: str = Field(default="", max_length=300)
    camera: CameraPlan | None = None
    motion: list[MotionItem] = Field(default_factory=list)
    text: list[TextItem] = Field(default_factory=list)
    transition: StoryboardTransition = StoryboardTransition.CUT
    transition_reason: str = Field(default="", max_length=200)
    source_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_trace: list[str] = Field(default_factory=list)
    continuity_requirements: list[str] = Field(default_factory=list)
    asset_requirements: list[str] = Field(default_factory=list)
    information_alignment: StoryboardInformationAlignment = (
        StoryboardInformationAlignment.EXPLAINS
    )
    information_alignment_note: str = Field(default="", max_length=300)
    reconstruction_confidence: StoryboardReconstructionConfidence = (
        StoryboardReconstructionConfidence.ILLUSTRATIVE
    )
    uncertainty_treatment: StoryboardUncertaintyTreatment | None = None
    scene_definition_candidate: SceneDefinitionCandidate | None = None

    @model_validator(mode="after")
    def _validate_timing(self) -> "VisualBeat":
        if self.end_time <= self.start_time:
            raise ValueError(
                f"VisualBeat {self.beat_id}: end_time ({self.end_time}) "
                f"must be greater than start_time ({self.start_time})"
            )
        if abs(self.duration - (self.end_time - self.start_time)) > 0.01:
            # Keep them consistent.
            object.__setattr__(self, "duration", self.end_time - self.start_time)
        return self


# ============================================================================
# Diagram / Map / Timeline / Comparison / Data specs
# ============================================================================

class DiagramSpec(BaseModel):
    """A node-arrow-label diagram spec."""
    nodes: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    arrows: list[dict[str, str]] = Field(default_factory=list)
    sequence: list[str] = Field(default_factory=list)
    emphasis: list[str] = Field(default_factory=list)
    animation_order: list[str] = Field(default_factory=list)


class MapSpec(BaseModel):
    """Geographic info, semantically positioned."""
    region: str = Field(default="", max_length=200)
    locations: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    relative_positions: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    highlight_areas: list[str] = Field(default_factory=list)
    coordinates_are_real: bool = False


class TimelineSpec(BaseModel):
    """Chronological explanation."""
    events: list[str] = Field(default_factory=list)
    ordering: list[str] = Field(default_factory=list)
    approximate_dates: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    highlighted_period: str = Field(default="", max_length=200)


class ComparisonSpec(BaseModel):
    """Side-by-side comparison."""
    axis: str = Field(default="", max_length=64)
    items: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    units: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class DataVisualizationSpec(BaseModel):
    """Quantitative visualization."""
    metric: str = Field(default="", max_length=64)
    unit: str = Field(default="", max_length=32)
    value: float | str = 0.0
    range: str = Field(default="", max_length=64)
    uncertainty: str = Field(default="", max_length=200)
    source_ids: list[str] = Field(default_factory=list)
    visual_type: str = Field(default="bar", max_length=32)
    annotation: str = Field(default="", max_length=200)


# ============================================================================
# Quality Score
# ============================================================================

class StoryboardQualityScore(BaseModel):
    """14-axis quality score for the StoryboardPackage."""
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_overall(self) -> "StoryboardQualityScore":
        if self.dimension_scores and self.overall_score == 0.0:
            avg = sum(self.dimension_scores.values()) / max(len(self.dimension_scores), 1)
            object.__setattr__(self, "overall_score", round(avg, 3))
        return self


# ============================================================================
# Top-level package
# ============================================================================

class StoryboardPackage(BaseModel):
    """The complete StoryboardPackage v1 — the executable visual blueprint."""
    metadata: StoryboardMetadata
    story_package_id: str = Field(min_length=1, max_length=64)
    story_version: str = Field(default="1", max_length=32)
    segments: list[str] = Field(default_factory=list)  # segment_ids covered
    visual_beats: list[VisualBeat] = Field(default_factory=list)
    continuity_state: ContinuityState = Field(default_factory=ContinuityState)
    continuity_updates: list[ContinuityUpdate] = Field(default_factory=list)
    continuity_dependencies: list[ContinuityDependency] = Field(default_factory=list)
    continuity_issues: list[ContinuityIssue] = Field(default_factory=list)
    asset_requirements: list[AssetRequirement] = Field(default_factory=list)
    camera_plan: list[CameraPlan] = Field(default_factory=list)
    transition_plan: list[dict[str, Any]] = Field(default_factory=list)
    text_plan: list[TextItem] = Field(default_factory=list)
    audio_sync_points: list[AudioSyncPoint] = Field(default_factory=list)
    diagram_specs: list[DiagramSpec] = Field(default_factory=list)
    map_specs: list[MapSpec] = Field(default_factory=list)
    timeline_specs: list[TimelineSpec] = Field(default_factory=list)
    comparison_specs: list[ComparisonSpec] = Field(default_factory=list)
    data_visualization_specs: list[DataVisualizationSpec] = Field(default_factory=list)
    scene_definition_candidates: list[SceneDefinitionCandidate] = Field(default_factory=list)
    storyboard_quality_score: StoryboardQualityScore | None = None
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    status: StoryboardStatus = StoryboardStatus.DRAFT
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _validate_no_overlapping_beats(self) -> "StoryboardPackage":
        beats = sorted(self.visual_beats, key=lambda b: b.start_time)
        for i in range(len(beats) - 1):
            if beats[i].end_time > beats[i + 1].start_time + 0.05:
                raise ValueError(
                    f"Visual beats {beats[i].beat_id} and {beats[i + 1].beat_id} overlap: "
                    f"{beats[i].end_time:.2f}s > {beats[i + 1].start_time:.2f}s"
                )
        return self

    @model_validator(mode="after")
    def _validate_all_assets_referenced(self) -> "StoryboardPackage":
        referenced = set()
        for beat in self.visual_beats:
            referenced.update(beat.asset_requirements)
        declared = {a.asset_id for a in self.asset_requirements}
        missing = referenced - declared
        if missing:
            raise ValueError(
                f"Asset requirements referenced but not declared: {sorted(missing)}"
            )
        return self

    def get_beat(self, beat_id: str) -> VisualBeat | None:
        return next((b for b in self.visual_beats if b.beat_id == beat_id), None)

    def beats_for_segment(self, segment_id: str) -> list[VisualBeat]:
        return [b for b in self.visual_beats if b.segment_id == segment_id]

    def total_duration_sec(self) -> float:
        if not self.visual_beats:
            return 0.0
        return max(b.end_time for b in self.visual_beats)

    def segment_ids_covered(self) -> set[str]:
        return {b.segment_id for b in self.visual_beats}

    def beat_ids(self) -> list[str]:
        return [b.beat_id for b in self.visual_beats]

    def to_dict(self) -> dict[str, Any]:
        """Stable dict for JSON serialization."""
        return self.model_dump(mode="json")

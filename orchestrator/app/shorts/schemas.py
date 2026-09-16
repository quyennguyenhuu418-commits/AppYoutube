"""
P13 — Shorts Production: canonical schemas.

Shorts are 9:16 vertical clips extracted from the 16:9 horizontal video.
The canonical Shorts contract captures:
- Source tracking (which scene, which job)
- Intelligent crop parameters (face detection, subject tracking, composition rules)
- Output format for vertical platforms
- Caption adaptation for vertical
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ShortsAspectRatio(str, Enum):
    """Aspect ratios for short-form content."""

    ASPECT_9_16 = "9:16"   # TikTok, Reels, Shorts (vertical)
    ASPECT_1_1 = "1:1"      # Instagram feed square
    ASPECT_4_5 = "4:5"      # Instagram portrait


class ShortsTargetPlatform(str, Enum):
    """Target platform for the short."""

    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM_REELS = "instagram_reels"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"


class CropMode(str, Enum):
    """How to crop the 16:9 source to 9:16."""

    CENTER = "center"           # Naive center crop
    SMART_FACE = "smart_face"    # Detect faces, center on largest
    SUBJECT_TRACKING = "subject_tracking"  # Follow detected subject
    RULE_OF_THIRDS = "rule_of_thirds"  # Position subject at 1/3
    NARRATION_FOCUS = "narration_focus"  # Prioritize narration content


class ShortsOutputFormat(str, Enum):
    """Output codec/container."""

    H264_AAC_MP4 = "h264_aac_mp4"
    H265_AAC_MP4 = "h265_aac_mp4"
    AV1_OPUS_MP4 = "av1_opus_mp4"


class ShortsQuality(str, Enum):
    """Quality preset."""

    DRAFT = "draft"      # Fast, lower quality (testing)
    STANDARD = "standard"  # Balanced
    HIGH = "high"         # Best quality, larger file
    MAX = "max"           # Maximum quality


# =============================================================================
# Shorts Output Specification
# =============================================================================


class ShortsRenderSettings(BaseModel):
    """Render settings for the shorts output."""

    model_config = {"frozen": True}

    target_resolution: tuple[int, int] = Field(
        default=(1080, 1920),
        description="Output resolution as (width, height)",
    )
    target_fps: float = Field(default=30.0, ge=15.0, le=60.0)
    max_duration_sec: float = Field(default=60.0, ge=1.0, le=180.0)
    min_duration_sec: float = Field(default=15.0, ge=1.0, le=30.0)
    format: ShortsOutputFormat = Field(default=ShortsOutputFormat.H264_AAC_MP4)
    quality: ShortsQuality = Field(default=ShortsQuality.STANDARD)
    audio_bitrate_kbps: int = Field(default=128, ge=64, le=320)
    video_bitrate_kbps: int = Field(default=4000, ge=1000, le=20000)
    codec_preset: str = Field(default="medium", max_length=32)


class CaptionPositionOverride(BaseModel):
    """Override caption position for vertical video."""

    model_config = {"frozen": True}

    # Position as fraction of height (0.0 = top, 1.0 = bottom)
    vertical_position: float = Field(default=0.75, ge=0.0, le=1.0)
    horizontal_align: str = Field(default="center", max_length=16)
    font_scale: float = Field(default=1.0, ge=0.5, le=2.0)
    max_width_pct: float = Field(default=0.9, ge=0.5, le=1.0)


# =============================================================================
# Shorts Source Context
# =============================================================================


class SceneCropSpec(BaseModel):
    """How a specific scene should be cropped."""

    model_config = {"frozen": True}

    scene_id: str = Field(max_length=64)
    scene_label: str = Field(max_length=128)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    crop_mode: CropMode = Field(default=CropMode.SMART_FACE)
    # Center point override (if crop_mode != center)
    focus_x: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    focus_y: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Whether scene has narration/diagrams (narration content should stay in frame)
    has_narration: bool = Field(default=False)
    has_diagram: bool = Field(default=False)
    emotional_intent: Optional[str] = Field(default=None, max_length=64)


class ShortsSourceContext(BaseModel):
    """Canonical source data for a short."""

    model_config = {"frozen": True}

    job_id: str = Field(max_length=64)
    source_video_path: str = Field(max_length=512)
    source_duration_sec: float = Field(ge=0.0)
    source_width: int = Field(ge=1)
    source_height: int = Field(ge=1)
    source_fps: float = Field(ge=1.0)
    source_ar: str = Field(default="16:9", max_length=8)
    scenes: tuple[SceneCropSpec, ...] = Field(default_factory=tuple)
    caption_track_id: Optional[str] = Field(default=None, max_length=64)


# =============================================================================
# Shorts Compilation Result
# =============================================================================


class ShortsCompilationResult(BaseModel):
    """Canonical output of the ShortsCompiler.

    This is the specification that the ShortsRenderer consumes.
    It is NOT the rendered media — that happens in the ShortsStage.
    """

    model_config = {"frozen": True}

    # Identity
    shorts_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)

    # Source
    source: ShortsSourceContext = Field(...)

    # Selected scene for this short
    selected_scene: SceneCropSpec = Field(...)

    # Composition
    crop_mode: CropMode = Field(default=CropMode.SMART_FACE)
    aspect_ratio: ShortsAspectRatio = Field(default=ShortsAspectRatio.ASPECT_9_16)
    render_settings: ShortsRenderSettings = Field(
        default_factory=ShortsRenderSettings,
    )
    caption_override: Optional[CaptionPositionOverride] = Field(default=None)

    # Time boundaries
    clip_start_sec: float = Field(ge=0.0)
    clip_end_sec: float = Field(ge=0.0)
    clip_duration_sec: float = Field(ge=0.0)

    # Composition details
    crop_center_x: float = Field(default=0.5, ge=0.0, le=1.0)
    crop_center_y: float = Field(default=0.5, ge=0.0, le=1.0)
    composition_notes: str = Field(default="", max_length=512)

    # Output path (relative to shorts_dir)
    output_filename: str = Field(max_length=128)

    # Provenance
    compiler_version: str = Field(default="1.0.0")
    compiled_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def output_resolution(self) -> str:
        w, h = self.render_settings.target_resolution
        return f"{w}x{h}"

    @property
    def output_path(self) -> str:
        return f"shorts/{self.output_filename}"


# =============================================================================
# Shorts Plan (for multiple shorts)
# =============================================================================


class ShortsPlan(BaseModel):
    """Plan for generating one or more shorts from a job."""

    model_config = {"frozen": True}

    job_id: str = Field(max_length=64)
    shorts_ids: tuple[str, ...] = Field(default_factory=tuple)
    results: tuple[ShortsCompilationResult, ...] = Field(default_factory=tuple)

    # Strategy
    generate_multiple: bool = Field(default=False)
    max_shorts: int = Field(default=3, ge=1, le=10)
    diversify_scenes: bool = Field(default=True)

    # Platform targets
    target_platforms: tuple[ShortsTargetPlatform, ...] = Field(
        default_factory=lambda: (ShortsTargetPlatform.YOUTUBE_SHORTS,),
    )

    # Render settings (shared across all shorts)
    render_settings: ShortsRenderSettings = Field(
        default_factory=ShortsRenderSettings,
    )

    compiled_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def shorts_count(self) -> int:
        return len(self.results)


# =============================================================================
# Shorts QA
# =============================================================================


class ShortsQAReport(BaseModel):
    """QA report for a rendered short."""

    model_config = {"frozen": True}

    shorts_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)
    output_path: str = Field(max_length=512)

    # Format checks
    format_valid: bool = Field(default=False)
    aspect_ratio_correct: bool = Field(default=False)
    duration_within_limits: bool = Field(default=False)

    # Quality indicators
    has_video: bool = Field(default=False)
    has_audio: bool = Field(default=False)
    audio_level_dbfs: Optional[float] = Field(default=None)

    # Size
    file_size_bytes: int = Field(default=0, ge=0)

    # Overall
    passed: bool = Field(default=False)
    notes: tuple[str, ...] = Field(default_factory=tuple)

    checked_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Public exports
# =============================================================================


__all__ = [
    "ShortsAspectRatio",
    "ShortsTargetPlatform",
    "CropMode",
    "ShortsOutputFormat",
    "ShortsQuality",
    "ShortsRenderSettings",
    "CaptionPositionOverride",
    "SceneCropSpec",
    "ShortsSourceContext",
    "ShortsCompilationResult",
    "ShortsPlan",
    "ShortsQAReport",
]

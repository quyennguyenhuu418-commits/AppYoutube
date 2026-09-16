"""
P14 — Thumbnail: canonical schemas for thumbnail generation.

Thumbnails are static images that represent a video in previews and listings.
They are generated from the final video (or a scene) and optimized for
specific platforms (YouTube, Twitter, etc.).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ThumbnailFormat(str, Enum):
    JPEG = "jpeg"
    WEBP = "webp"
    PNG = "png"


class ThumbnailSize(str, Enum):
    """Standard thumbnail sizes."""

    YOUTUBE_DEFAULT = "youtube_default"   # 1280x720
    YOUTUBE_PREVIEW = "youtube_preview"   # 640x360
    TWITTER_CARD = "twitter_card"        # 1200x628
    INSTAGRAM_SQUARE = "instagram_square" # 1080x1080
    TIKTOK = "tiktok"                    # 1080x1920
    LINKEDIN = "linkedin"                # 1200x627


_THUMBNAIL_DIMENSIONS = {
    ThumbnailSize.YOUTUBE_DEFAULT: (1280, 720),
    ThumbnailSize.YOUTUBE_PREVIEW: (640, 360),
    ThumbnailSize.TWITTER_CARD: (1200, 628),
    ThumbnailSize.INSTAGRAM_SQUARE: (1080, 1080),
    ThumbnailSize.TIKTOK: (1080, 1920),
    ThumbnailSize.LINKEDIN: (1200, 627),
}


class ThumbnailColorScheme(str, Enum):
    """Color scheme for the thumbnail overlay."""

    HIGH_CONTRAST = "high_contrast"      # White text on dark overlay
    DARK_OVERLAY = "dark_overlay"        # Dark semi-transparent overlay
    LIGHT_OVERLAY = "light_overlay"     # Light semi-transparent overlay
    BRAND_COLOR = "brand_color"          # Use brand color from metadata
    MINIMAL = "minimal"                  # No text, just composition


class ThumbnailContentType(str, Enum):
    """What kind of content to include in the thumbnail."""

    SCENE_CAPTURE = "scene_capture"   # Extract a frame from the scene
    TITLE_CARD = "title_card"          # Generate from title text
    COMPOSITE = "composite"            # Scene + title overlay
    DIAGRAM_FOCUS = "diagram_focus"    # Prioritize diagram content
    CHARACTER_PORTRAIT = "character_portrait"  # Show character


# =============================================================================
# Thumbnail Specification
# =============================================================================


class ThumbnailRenderSettings(BaseModel):
    """Render settings for a thumbnail."""

    model_config = {"frozen": True}

    format: ThumbnailFormat = Field(default=ThumbnailFormat.WEBP)
    size: ThumbnailSize = Field(default=ThumbnailSize.YOUTUBE_DEFAULT)
    quality: int = Field(default=85, ge=1, le=100)
    width: int = Field(default=1280, ge=100, le=3840)
    height: int = Field(default=720, ge=100, le=2160)


class ThumbnailTextOverlay(BaseModel):
    """Text overlay on the thumbnail."""

    model_config = {"frozen": True}

    text: str = Field(max_length=80)
    position: str = Field(default="bottom_center", max_length=32)  # top_left, top_center, top_right, bottom_left, bottom_center, bottom_right, center
    font_size: int = Field(default=48, ge=12, le=200)
    color: str = Field(default="#FFFFFF")
    stroke_color: str = Field(default="#000000")
    stroke_width: int = Field(default=2, ge=0, le=10)
    max_lines: int = Field(default=2, ge=1, le=5)
    bold: bool = Field(default=True)
    shadow: bool = Field(default=True)


class ThumbnailSource(BaseModel):
    """Source content for the thumbnail."""

    model_config = {"frozen": True}

    source_type: ThumbnailContentType = Field(
        default=ThumbnailContentType.SCENE_CAPTURE,
    )
    # For SCENE_CAPTURE: which frame/second to capture
    capture_time_sec: float = Field(default=5.0, ge=0.0)
    # For DIAGRAM_FOCUS: which scene has the diagram
    diagram_scene_id: Optional[str] = Field(default=None, max_length=64)
    # For TITLE_CARD: title text
    title_text: Optional[str] = Field(default=None, max_length=80)
    # For CHARACTER_PORTRAIT: which character
    character_id: Optional[str] = Field(default=None, max_length=64)
    # Scene label for context
    scene_label: Optional[str] = Field(default=None, max_length=128)


# =============================================================================
# Thumbnail Compilation Result
# =============================================================================


class ThumbnailCompilationResult(BaseModel):
    """Canonical output of the ThumbnailCompiler.

    This is the specification consumed by the ThumbnailGenerator.
    """

    model_config = {"frozen": True}

    thumbnail_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)
    source: ThumbnailSource = Field(...)

    # Composition
    color_scheme: ThumbnailColorScheme = Field(default=ThumbnailColorScheme.HIGH_CONTRAST)
    text_overlay: Optional[ThumbnailTextOverlay] = Field(default=None)
    include_title: bool = Field(default=True)
    include_topic: bool = Field(default=True)

    # Render settings
    render_settings: ThumbnailRenderSettings = Field(
        default_factory=ThumbnailRenderSettings,
    )

    # Output
    output_filename: str = Field(max_length=128)
    caption: str = Field(default="", max_length=160)  # For alt text / SEO

    # Composition notes
    composition_notes: str = Field(default="", max_length=512)

    # Source tracking
    source_video_path: Optional[str] = Field(default=None, max_length=512)
    source_scene_id: Optional[str] = Field(default=None, max_length=64)

    # Versions for different platforms
    versions: dict[str, str] = Field(
        default_factory=dict,
        description="Platform -> filename mapping for each version",
    )

    # Provenance
    compiler_version: str = Field(default="1.0.0")
    compiled_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def output_path(self) -> str:
        return f"thumbnails/{self.output_filename}"

    @property
    def dimensions(self) -> tuple[int, int]:
        w = self.render_settings.width
        h = self.render_settings.height
        return (w, h)


# =============================================================================
# Thumbnail Plan
# =============================================================================


class ThumbnailPlan(BaseModel):
    """Plan for generating multiple thumbnails."""

    model_config = {"frozen": True}

    job_id: str = Field(max_length=64)
    thumbnails: tuple[ThumbnailCompilationResult, ...] = Field(default_factory=tuple)

    # Strategy
    generate_for_scenes: bool = Field(default=True)
    generate_for_title: bool = Field(default=True)
    generate_for_social: bool = Field(default=True)

    # Default render settings (applied to all unless overridden)
    default_settings: ThumbnailRenderSettings = Field(
        default_factory=ThumbnailRenderSettings,
    )

    compiled_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def thumbnail_count(self) -> int:
        return len(self.thumbnails)


# =============================================================================
# Thumbnail QA
# =============================================================================


class ThumbnailQAReport(BaseModel):
    """QA report for a generated thumbnail."""

    model_config = {"frozen": True}

    thumbnail_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)
    output_path: str = Field(max_length=512)

    # Format checks
    file_exists: bool = Field(default=False)
    format_valid: bool = Field(default=False)
    dimensions_correct: bool = Field(default=False)
    file_size_bytes: int = Field(default=0, ge=0)

    # Content checks
    has_content: bool = Field(default=False)
    has_text: bool = Field(default=False)

    # Quality indicators
    file_size_kb: float = Field(default=0.0)
    aspect_ratio: str = Field(default="", max_length=8)

    # Overall
    passed: bool = Field(default=False)
    notes: tuple[str, ...] = Field(default_factory=tuple)

    checked_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Public exports
# =============================================================================


__all__ = [
    "ThumbnailFormat",
    "ThumbnailSize",
    "ThumbnailColorScheme",
    "ThumbnailContentType",
    "ThumbnailRenderSettings",
    "ThumbnailTextOverlay",
    "ThumbnailSource",
    "ThumbnailCompilationResult",
    "ThumbnailPlan",
    "ThumbnailQAReport",
]

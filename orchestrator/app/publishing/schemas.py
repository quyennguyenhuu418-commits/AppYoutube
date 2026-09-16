"""
P15 — Publishing: canonical schemas for multi-platform video publishing.

Supports three platforms:
- YouTube (long-form + Shorts)
- TikTok (vertical 9:16)
- Facebook / Meta (Reels + feed)

Key concepts:
- PublishingProfile: what to publish (which video/short/thumbnail)
- PlatformMetadata: platform-specific SEO/metadata
- PublishingPlan: what to publish where
- PublishingResult: per-platform result (success/failure)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class Platform(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    FACEBOOK = "facebook"


class PublishStatus(str, Enum):
    DRAFT = "draft"         # Metadata generated, not sent
    PENDING = "pending"     # Submitted, awaiting confirmation
    PUBLISHED = "published"  # Successfully published
    FAILED = "failed"       # Publishing failed
    RATE_LIMITED = "rate_limited"  # Hit rate limit
    DUPLICATE = "duplicate"  # Content already published


class ContentType(str, Enum):
    VIDEO = "video"         # Full documentary
    SHORT = "short"         # 9:16 vertical clip
    REEL = "reel"           # Facebook Reels


class Visibility(str, Enum):
    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"
    SCHEDULE = "schedule"


# =============================================================================
# Platform-specific metadata
# =============================================================================


class YouTubeMetadata(BaseModel):
    """YouTube video metadata."""

    model_config = {"frozen": True}

    # Required
    title: str = Field(max_length=100)
    description: str = Field(max_length=5000)

    # Optional / recommended
    tags: tuple[str, ...] = Field(default_factory=tuple, max_length=500)
    category_id: Optional[int] = Field(default=None)

    # YouTube-specific
    playlist_id: Optional[str] = Field(default=None, max_length=64)
    license: str = Field(default="youtube", max_length=32)
    embeddable: bool = Field(default=True)
    public_stats_viewable: bool = Field(default=True)
    notify_subscribers: bool = Field(default=True)

    # Shorts specific
    is_short: bool = Field(default=False)
    remix_enabled: bool = Field(default=False)


class TikTokMetadata(BaseModel):
    """TikTok video metadata."""

    model_config = {"frozen": True}

    # Required
    title: str = Field(max_length=150)

    # TikTok-specific
    description: str = Field(max_length=2200)

    # Content safety hints
    content_warning: Optional[str] = Field(
        default=None,
        description="none|sensitive|restricted",
    )

    # Interaction settings
    comment_setting: str = Field(default="all", max_length=16)
    duet_setting: str = Field(default="anyone", max_length=16)
    stitch_setting: str = Field(default="anyone", max_length=16)
    download_setting: bool = Field(default=True)

    # Hashtags (TikTok format)
    hashtags: tuple[str, ...] = Field(default_factory=tuple)

    # Mentions
    mentions: tuple[str, ...] = Field(default_factory=tuple)


class FacebookMetadata(BaseModel):
    """Facebook / Meta video metadata."""

    model_config = {"frozen": True}

    # Required
    title: str = Field(max_length=255)
    description: str = Field(max_length=63206)

    # Facebook-specific
    content_category: str = Field(default="entertainment", max_length=64)
    content_tags: tuple[str, ...] = Field(default_factory=tuple)

    # Privacy / distribution
    privacy: str = Field(default="PUBLIC", max_length=32)
    publish_to_feed: bool = Field(default=True)
    publish_to_reels: bool = Field(default=True)
    cross_post_to_instagram: bool = Field(default=False)

    # Engagement
    disable_comments: bool = Field(default=False)
    hide_from_feed: bool = Field(default=False)


# =============================================================================
# Unified metadata
# =============================================================================


class PublishingMetadata(BaseModel):
    """Platform-agnostic metadata, adapted per platform."""

    model_config = {"frozen": True}

    # Core content
    topic: str = Field(max_length=200)
    title_template: str = Field(max_length=150)
    description_template: str = Field(max_length=5000)

    # Tags (canonical)
    canonical_tags: tuple[str, ...] = Field(default_factory=tuple)

    # Scheduling
    publish_at: Optional[datetime] = Field(default=None)
    timezone: str = Field(default="UTC", max_length=32)

    # Visibility
    visibility: Visibility = Field(default=Visibility.PUBLIC)

    # Which content to publish
    content_type: ContentType = Field(default=ContentType.VIDEO)
    video_asset_path: Optional[str] = Field(default=None, max_length=512)
    short_asset_path: Optional[str] = Field(default=None, max_length=512)
    thumbnail_asset_path: Optional[str] = Field(default=None, max_length=512)

    # Audience
    age_restriction: Optional[str] = Field(default=None, max_length=16)
    made_for_kids: bool = Field(default=False)


# =============================================================================
# Publishing Plan
# =============================================================================


class PlatformPublishSpec(BaseModel):
    """What to publish on one platform."""

    model_config = {"frozen": True}

    platform: Platform = Field(...)
    content_type: ContentType = Field(default=ContentType.VIDEO)
    visibility: Visibility = Field(default=Visibility.PUBLIC)
    publish_at: Optional[datetime] = Field(default=None)

    # Platform-specific overrides
    title_override: Optional[str] = Field(default=None, max_length=150)
    description_override: Optional[str] = Field(default=None, max_length=5000)
    tags_override: tuple[str, ...] = Field(default_factory=tuple)

    # Platform-specific metadata
    youtube_meta: Optional[YouTubeMetadata] = Field(default=None)
    tiktok_meta: Optional[TikTokMetadata] = Field(default=None)
    facebook_meta: Optional[FacebookMetadata] = Field(default=None)

    # Asset paths
    video_path: Optional[str] = Field(default=None, max_length=512)
    thumbnail_path: Optional[str] = Field(default=None, max_length=512)


class PublishingPlan(BaseModel):
    """Canonical publishing plan for one job."""

    model_config = {"frozen": True}

    plan_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)

    # Source content
    canonical_metadata: PublishingMetadata = Field(...)

    # Platforms to publish to
    platforms: tuple[PlatformPublishSpec, ...] = Field(default_factory=tuple)

    # Whether to auto-generate platform-specific metadata
    auto_generate_descriptions: bool = Field(default=True)
    auto_generate_tags: bool = Field(default=True)

    # Global thumbnail override
    thumbnail_override_path: Optional[str] = Field(default=None, max_length=512)

    # Provenance
    compiler_version: str = Field(default="1.0.0")
    compiled_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Publishing Result
# =============================================================================


class PlatformPublishResult(BaseModel):
    """Result of publishing to one platform."""

    model_config = {"frozen": True}

    platform: Platform = Field(...)
    content_type: ContentType = Field(...)
    status: PublishStatus = Field(...)

    # Success fields
    published_url: Optional[str] = Field(default=None, max_length=512)
    published_id: Optional[str] = Field(default=None, max_length=128)

    # Failure fields
    error_kind: Optional[str] = Field(default=None, max_length=64)
    error_message: Optional[str] = Field(default=None, max_length=512)
    retry_after_sec: Optional[int] = Field(default=None)

    # Platform-specific response data (safe subset only)
    platform_response: dict[str, str] = Field(default_factory=dict)

    # Timing
    published_at: Optional[datetime] = Field(default=None)
    duration_ms: int = Field(default=0, ge=0)


class PublishingResult(BaseModel):
    """Canonical result of a publishing operation."""

    model_config = {"frozen": True}

    plan_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)

    # Per-platform results
    platform_results: tuple[PlatformPublishResult, ...] = Field(default_factory=tuple)

    # Aggregate
    total_platforms: int = Field(ge=0)
    successful_platforms: int = Field(ge=0)
    failed_platforms: int = Field(ge=0)

    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)

    @property
    def all_succeeded(self) -> bool:
        return self.failed_platforms == 0 and self.successful_platforms == self.total_platforms

    @property
    def any_failed(self) -> bool:
        return self.failed_platforms > 0


# =============================================================================
# QA / Validation
# =============================================================================


class PublishingQAReport(BaseModel):
    """QA report for publishing metadata."""

    model_config = {"frozen": True}

    plan_id: str = Field(max_length=64)
    job_id: str = Field(max_length=64)

    # Metadata checks per platform
    platform_checks: dict[str, dict[str, bool]] = Field(default_factory=dict)

    # Validation results
    title_length_ok: bool = Field(default=True)
    description_length_ok: bool = Field(default=True)
    tags_count_ok: bool = Field(default=True)
    thumbnail_exists: bool = Field(default=True)
    video_exists: bool = Field(default=True)

    # Overall
    passed: bool = Field(default=True)
    issues: tuple[str, ...] = Field(default_factory=tuple)

    checked_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Public exports
# =============================================================================


__all__ = [
    # Enums
    "Platform",
    "PublishStatus",
    "ContentType",
    "Visibility",
    # Platform metadata
    "YouTubeMetadata",
    "TikTokMetadata",
    "FacebookMetadata",
    # Unified
    "PublishingMetadata",
    # Plan + Result
    "PlatformPublishSpec",
    "PublishingPlan",
    "PlatformPublishResult",
    "PublishingResult",
    # QA
    "PublishingQAReport",
]

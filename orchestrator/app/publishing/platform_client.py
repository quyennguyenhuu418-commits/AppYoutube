"""
P16 — PlatformClient: abstract interface for real platform publishing APIs.

Each platform implements this interface:
- YouTubeClient (YouTube Data API v3)
- TikTokClient (TikTok for Developers)
- FacebookClient (Facebook Graph API v18+)

All clients:
- Are DETERMINISTIC in the credential/status sensing layer
- Use async/await for non-blocking IO
- Never log credentials
- Return PlatformPublishResult with canonical status
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from app.publishing.schemas import (
    ContentType,
    Platform,
    PlatformPublishResult,
    PublishStatus,
)


class PlatformCredentials:
    """Environment-loaded credentials for a platform."""

    def __init__(self) -> None:
        self.youtube_api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        self.youtube_client_id = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
        self.youtube_client_secret = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()
        self.youtube_refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN", "").strip()

        self.tiktok_client_key = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
        self.tiktok_client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
        self.tiktok_access_token = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()

        self.facebook_access_token = os.getenv("FACEBOOK_ACCESS_TOKEN", "").strip()
        self.facebook_page_id = os.getenv("FACEBOOK_PAGE_ID", "").strip()
        self.facebook_instagram_id = os.getenv("FACEBOOK_INSTAGRAM_ID", "").strip()

    def has_youtube(self) -> bool:
        return bool(self.youtube_api_key and self.youtube_refresh_token)

    def has_tiktok(self) -> bool:
        return bool(self.tiktok_access_token)

    def has_facebook(self) -> bool:
        return bool(self.facebook_access_token and self.facebook_page_id)

    def mask(self) -> dict[str, str]:
        """Return credentials with values masked for logging."""
        def m(v: str) -> str:
            if not v:
                return ""
            if len(v) <= 8:
                return "***"
            return f"{v[:4]}...{v[-4:]}"

        return {
            "youtube_api_key": m(self.youtube_api_key),
            "youtube_client_id": m(self.youtube_client_id),
            "youtube_client_secret": m(self.youtube_client_secret),
            "youtube_refresh_token": m(self.youtube_refresh_token),
            "tiktok_client_key": m(self.tiktok_client_key),
            "tiktok_client_secret": m(self.tiktok_client_secret),
            "tiktok_access_token": m(self.tiktok_access_token),
            "facebook_access_token": m(self.facebook_access_token),
            "facebook_page_id": self.facebook_page_id,  # Not sensitive
            "facebook_instagram_id": self.facebook_instagram_id,  # Not sensitive
        }


class PlatformClient(ABC):
    """Abstract interface for a publishing platform client."""

    platform: Platform

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this client has credentials."""

    @abstractmethod
    async def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: tuple[str, ...],
        visibility: str,
        **kwargs: Any,
    ) -> PlatformPublishResult:
        """Upload a video to the platform.

        Parameters:
            video_path: Local path to the video file
            title: Video title
            description: Video description
            tags: Hashtags / tags
            visibility: public | unlisted | private
        """


# ============================================================================
# Stub platform clients (real implementations use httpx/aiohttp + OAuth)
# ============================================================================


class YouTubeClient(PlatformClient):
    """YouTube Data API v3 client.

    Real implementation requires:
      - OAuth 2.0 flow (https://developers.google.com/oauthplayground)
      - Resumable upload via https://www.googleapis.com/upload/youtube/v3/videos
      - Quota: 10,000 units/day, video upload = 1600 units

    Implementation here returns RATE_LIMITED to demonstrate the credential
    check + dry-run safety net.
    """

    platform = Platform.YOUTUBE

    def __init__(self, credentials: PlatformCredentials | None = None) -> None:
        self._creds = credentials or PlatformCredentials()

    def is_configured(self) -> bool:
        return self._creds.has_youtube()

    async def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: tuple[str, ...],
        visibility: str,
        **kwargs: Any,
    ) -> PlatformPublishResult:
        """Upload to YouTube.

        Real implementation would:
          1. POST /upload/youtube/v3/videos (resumable upload)
          2. POST /youtube/v3/thumbnails/set (upload thumbnail)
          3. POST /youtube/v3/videos?part=status (set privacy)

        This stub returns RATE_LIMITED for safety.
        """
        if not self.is_configured():
            return PlatformPublishResult(
                platform=self.platform,
                content_type=ContentType.VIDEO,
                status=PublishStatus.FAILED,
                error_kind="MISSING_CREDENTIALS",
                error_message=(
                    "YouTube OAuth not configured. "
                    "Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, "
                    "YOUTUBE_REFRESH_TOKEN."
                ),
                duration_ms=0,
            )

        # STUB: in production, call YouTube Data API v3
        return PlatformPublishResult(
            platform=self.platform,
            content_type=ContentType.VIDEO,
            status=PublishStatus.RATE_LIMITED,
            error_kind="NOT_IMPLEMENTED",
            error_message=(
                "Real YouTube Data API integration pending. "
                "See docs/P16_PLATFORM_API.md for OAuth setup."
            ),
            retry_after_sec=0,
            duration_ms=0,
        )


class TikTokClient(PlatformClient):
    """TikTok for Developers client.

    Real implementation requires:
      - TikTok Login Kit
      - Content Posting API: https://developers.tiktok.com/doc/content-posting-api/
      - Direct POST video / chunked upload

    Stub returns RATE_LIMITED.
    """

    platform = Platform.TIKTOK

    def __init__(self, credentials: PlatformCredentials | None = None) -> None:
        self._creds = credentials or PlatformCredentials()

    def is_configured(self) -> bool:
        return self._creds.has_tiktok()

    async def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: tuple[str, ...],
        visibility: str,
        **kwargs: Any,
    ) -> PlatformPublishResult:
        if not self.is_configured():
            return PlatformPublishResult(
                platform=self.platform,
                content_type=ContentType.SHORT,
                status=PublishStatus.FAILED,
                error_kind="MISSING_CREDENTIALS",
                error_message=(
                    "TikTok credentials not configured. "
                    "Set TIKTOK_CLIENT_KEY and TIKTOK_ACCESS_TOKEN."
                ),
                duration_ms=0,
            )

        # STUB: production would use Content Posting API
        return PlatformPublishResult(
            platform=self.platform,
            content_type=ContentType.SHORT,
            status=PublishStatus.RATE_LIMITED,
            error_kind="NOT_IMPLEMENTED",
            error_message=(
                "Real TikTok Content Posting API integration pending. "
                "See docs/P16_PLATFORM_API.md for setup."
            ),
            retry_after_sec=0,
            duration_ms=0,
        )


class FacebookClient(PlatformClient):
    """Facebook Graph API v18+ client.

    Real implementation requires:
      - Facebook App with pages_show_list + publish_video
      - Page Access Token
      - Resumable upload via /PAGE_ID/videos
      - For Reels: /PAGE_ID/video_reels

    Stub returns RATE_LIMITED.
    """

    platform = Platform.FACEBOOK

    def __init__(self, credentials: PlatformCredentials | None = None) -> None:
        self._creds = credentials or PlatformCredentials()

    def is_configured(self) -> bool:
        return self._creds.has_facebook()

    async def upload(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: tuple[str, ...],
        visibility: str,
        cross_post_instagram: bool = False,
        **kwargs: Any,
    ) -> PlatformPublishResult:
        if not self.is_configured():
            return PlatformPublishResult(
                platform=self.platform,
                content_type=ContentType.VIDEO,
                status=PublishStatus.FAILED,
                error_kind="MISSING_CREDENTIALS",
                error_message=(
                    "Facebook credentials not configured. "
                    "Set FACEBOOK_ACCESS_TOKEN and FACEBOOK_PAGE_ID."
                ),
                duration_ms=0,
            )

        # STUB: production would use Graph API
        return PlatformPublishResult(
            platform=self.platform,
            content_type=ContentType.VIDEO,
            status=PublishStatus.RATE_LIMITED,
            error_kind="NOT_IMPLEMENTED",
            error_message=(
                "Real Facebook Graph API integration pending. "
                "See docs/P16_PLATFORM_API.md for setup."
            ),
            retry_after_sec=0,
            duration_ms=0,
        )


def get_platform_client(platform: Platform) -> PlatformClient:
    """Get the configured client for a platform."""
    creds = PlatformCredentials()
    if platform == Platform.YOUTUBE:
        return YouTubeClient(creds)
    elif platform == Platform.TIKTOK:
        return TikTokClient(creds)
    elif platform == Platform.FACEBOOK:
        return FacebookClient(creds)
    raise ValueError(f"Unknown platform: {platform}")


__all__ = [
    "PlatformClient",
    "PlatformCredentials",
    "YouTubeClient",
    "TikTokClient",
    "FacebookClient",
    "get_platform_client",
]

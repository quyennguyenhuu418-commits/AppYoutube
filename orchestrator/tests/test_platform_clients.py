"""
P16 — Real Platform API Integration tests.
"""

from __future__ import annotations

import os
import pytest

from app.publishing.platform_client import (
    FacebookClient,
    PlatformCredentials,
    TikTokClient,
    YouTubeClient,
    get_platform_client,
)
from app.publishing.schemas import (
    ContentType,
    Platform,
    PublishStatus,
)


# =============================================================================
# PlatformCredentials
# =============================================================================


class TestPlatformCredentials:
    def test_default_no_credentials(self):
        creds = PlatformCredentials()
        # By default no env vars are set
        assert isinstance(creds.mask(), dict)

    def test_mask_empty(self):
        creds = PlatformCredentials()
        masked = creds.mask()
        # All empty values masked as ""
        assert masked["youtube_api_key"] == ""

    def test_mask_real_value(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "AIzaSyDx_aBcDeF1234567890")
        creds = PlatformCredentials()
        masked = creds.mask()
        assert masked["youtube_api_key"].startswith("AIza")
        assert "..." in masked["youtube_api_key"]

    def test_no_credentials_youtube(self):
        creds = PlatformCredentials()
        assert not creds.has_youtube()

    def test_no_credentials_tiktok(self):
        creds = PlatformCredentials()
        assert not creds.has_tiktok()

    def test_no_credentials_facebook(self):
        creds = PlatformCredentials()
        assert not creds.has_facebook()


# =============================================================================
# Platform Clients
# =============================================================================


class TestYouTubeClient:
    def test_not_configured(self):
        client = YouTubeClient(PlatformCredentials())
        assert not client.is_configured()
        assert client.platform == Platform.YOUTUBE

    def test_upload_without_credentials(self):
        client = YouTubeClient(PlatformCredentials())
        result = await_test(
            client.upload,
            video_path="/fake/video.mp4",
            title="Test",
            description="Desc",
            tags=("test",),
            visibility="public",
        )
        assert result.status == PublishStatus.FAILED
        assert result.error_kind == "MISSING_CREDENTIALS"
        assert "YOUTUBE_CLIENT_ID" in (result.error_message or "")


class TestTikTokClient:
    def test_not_configured(self):
        client = TikTokClient(PlatformCredentials())
        assert not client.is_configured()
        assert client.platform == Platform.TIKTOK

    def test_upload_without_credentials(self):
        client = TikTokClient(PlatformCredentials())
        result = await_test(
            client.upload,
            video_path="/fake/short.mp4",
            title="Short",
            description="Desc",
            tags=("viral",),
            visibility="public",
        )
        assert result.status == PublishStatus.FAILED
        assert result.error_kind == "MISSING_CREDENTIALS"
        assert "TIKTOK" in (result.error_message or "")


class TestFacebookClient:
    def test_not_configured(self):
        client = FacebookClient(PlatformCredentials())
        assert not client.is_configured()
        assert client.platform == Platform.FACEBOOK

    def test_upload_without_credentials(self):
        client = FacebookClient(PlatformCredentials())
        result = await_test(
            client.upload,
            video_path="/fake/video.mp4",
            title="Test",
            description="Desc",
            tags=("test",),
            visibility="public",
        )
        assert result.status == PublishStatus.FAILED
        assert result.error_kind == "MISSING_CREDENTIALS"
        assert "FACEBOOK" in (result.error_message or "")


# =============================================================================
# get_platform_client
# =============================================================================


class TestGetPlatformClient:
    def test_youtube(self):
        client = get_platform_client(Platform.YOUTUBE)
        assert isinstance(client, YouTubeClient)
        assert client.platform == Platform.YOUTUBE

    def test_tiktok(self):
        client = get_platform_client(Platform.TIKTOK)
        assert isinstance(client, TikTokClient)
        assert client.platform == Platform.TIKTOK

    def test_facebook(self):
        client = get_platform_client(Platform.FACEBOOK)
        assert isinstance(client, FacebookClient)
        assert client.platform == Platform.FACEBOOK

    def test_invalid_platform(self):
        with pytest.raises(ValueError):
            get_platform_client("invalid")  # type: ignore


# =============================================================================
# Helper for async tests
# =============================================================================


import asyncio


def await_test(coro_func, *args, **kwargs):
    """Run an async function synchronously."""
    return asyncio.run(coro_func(*args, **kwargs))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
P15 — Publishing tests: schemas, metadata generators, QA.
"""

from __future__ import annotations

import pytest

from app.publishing.metadata_generator import (
    FacebookMetadataGenerator,
    PublishingMetadataCompiler,
    PublishingPlanBuilder,
    TikTokMetadataGenerator,
    YouTubeMetadataGenerator,
)
from app.publishing.schemas import (
    ContentType,
    FacebookMetadata,
    Platform,
    PublishingMetadata,
    TikTokMetadata,
    Visibility,
    YouTubeMetadata,
)


# =============================================================================
# Schemas
# =============================================================================


class TestPublishingSchemas:
    def test_publishing_metadata_defaults(self):
        meta = PublishingMetadata(
            topic="Climate Change",
            title_template="Understanding Climate Change",
            description_template="A documentary about climate change.",
        )
        assert meta.topic == "Climate Change"
        assert meta.visibility == Visibility.PUBLIC
        assert meta.content_type == ContentType.VIDEO

    def test_publishing_metadata_frozen(self):
        meta = PublishingMetadata(
            topic="Science",
            title_template="Test",
            description_template="Test desc",
        )
        with pytest.raises(Exception):
            meta.topic = "Changed"

    def test_youtube_metadata(self):
        yt = YouTubeMetadata(
            title="My Documentary",
            description="A great documentary.",
            tags=("doc", "science"),
            is_short=False,
        )
        assert yt.title == "My Documentary"
        assert yt.is_short is False
        assert yt.notify_subscribers is True

    def test_tiktok_metadata(self):
        tt = TikTokMetadata(
            title="Cool Video",
            description="Check this out!",
            hashtags=("viral", "fyp"),
        )
        assert tt.title == "Cool Video"
        assert len(tt.hashtags) == 2
        assert tt.download_setting is True

    def test_facebook_metadata(self):
        fb = FacebookMetadata(
            title="My Video",
            description="A great video.",
        )
        assert fb.privacy == "PUBLIC"
        assert fb.publish_to_feed is True
        assert fb.publish_to_reels is True

    def test_content_type_enum(self):
        assert ContentType.VIDEO.value == "video"
        assert ContentType.SHORT.value == "short"
        assert ContentType.REEL.value == "reel"

    def test_platform_enum(self):
        assert Platform.YOUTUBE.value == "youtube"
        assert Platform.TIKTOK.value == "tiktok"
        assert Platform.FACEBOOK.value == "facebook"

    def test_visibility_enum(self):
        assert Visibility.PUBLIC.value == "public"
        assert Visibility.UNLISTED.value == "unlisted"
        assert Visibility.PRIVATE.value == "private"


# =============================================================================
# YouTube Generator
# =============================================================================


class TestYouTubeGenerator:
    def test_generate_full_video(self):
        gen = YouTubeMetadataGenerator()
        canonical = PublishingMetadata(
            topic="AI Science",
            title_template="The Future of AI",
            description_template="An in-depth look at artificial intelligence.",
            canonical_tags=("ai", "science", "technology"),
        )
        yt = gen.generate(canonical)
        assert yt.title == "The Future of AI"
        assert len(yt.tags) >= 1
        assert "ai" in yt.tags
        assert yt.is_short is False

    def test_generate_short_adds_shorts_tag(self):
        gen = YouTubeMetadataGenerator()
        canonical = PublishingMetadata(
            topic="Science",
            title_template="Quick Science Fact",
            description_template="A short science fact.",
            canonical_tags=("science",),
        )
        yt = gen.generate(canonical, is_short=True)
        assert "#shorts" in yt.title
        assert "shorts" in yt.tags

    def test_title_truncation(self):
        gen = YouTubeMetadataGenerator()
        long_title = "A" * 150
        canonical = PublishingMetadata(
            topic="Test",
            title_template=long_title,
            description_template="Desc",
        )
        yt = gen.generate(canonical)
        assert len(yt.title) <= 100

    def test_description_with_tags(self):
        gen = YouTubeMetadataGenerator()
        canonical = PublishingMetadata(
            topic="Documentary",
            title_template="My Doc",
            description_template="An amazing documentary.",
            canonical_tags=("doc", "film", "ai"),
        )
        yt = gen.generate(canonical)
        assert "An amazing documentary" in yt.description
        assert "#doc" in yt.description or "#ai" in yt.description

    def test_category_inference_science(self):
        gen = YouTubeMetadataGenerator()
        canonical = PublishingMetadata(
            topic="Science and Technology",
            title_template="Tech Today",
            description_template="Tech news.",
        )
        yt = gen.generate(canonical)
        assert yt.category_id == 28  # Science & Technology

    def test_category_inference_default(self):
        gen = YouTubeMetadataGenerator()
        canonical = PublishingMetadata(
            topic="Random Topic",
            title_template="Something",
            description_template="Something else.",
        )
        yt = gen.generate(canonical)
        assert yt.category_id == 1  # Default: Film & Animation


# =============================================================================
# TikTok Generator
# =============================================================================


class TestTikTokGenerator:
    def test_generate(self):
        gen = TikTokMetadataGenerator()
        canonical = PublishingMetadata(
            topic="Viral Dance",
            title_template="Amazing Dance Move",
            description_template="Check out this dance!",
            canonical_tags=("dance", "viral", "fun"),
        )
        tt = gen.generate(canonical)
        assert tt.title == "Amazing Dance Move"
        assert len(tt.hashtags) >= 1
        assert tt.content_warning == "none"
        assert tt.comment_setting == "all"

    def test_title_truncation(self):
        gen = TikTokMetadataGenerator()
        # Use a title that's 140 chars (leaves room for #shorts if added)
        long_title = "B" * 140
        canonical = PublishingMetadata(
            topic="Test",
            title_template=long_title,
            description_template="Desc",
        )
        tt = gen.generate(canonical)
        assert len(tt.title) <= 150

    def test_hashtags_from_tags(self):
        gen = TikTokMetadataGenerator()
        canonical = PublishingMetadata(
            topic="Food",
            title_template="Delicious Recipe",
            description_template="Try this recipe!",
            canonical_tags=("food", "recipe", "cooking"),
        )
        tt = gen.generate(canonical)
        assert "food" in tt.hashtags
        assert "documentary" in tt.hashtags  # Always added

    def test_description_with_hashtags(self):
        gen = TikTokMetadataGenerator()
        canonical = PublishingMetadata(
            topic="Art",
            title_template="Amazing Art",
            description_template="Look at this art!",
            canonical_tags=("art",),
        )
        tt = gen.generate(canonical)
        # TikTok description replaces title_template text, adds hashtags
        assert "art" in tt.description.lower()


# =============================================================================
# Facebook Generator
# =============================================================================


class TestFacebookGenerator:
    def test_generate(self):
        gen = FacebookMetadataGenerator()
        canonical = PublishingMetadata(
            topic="News",
            title_template="Breaking News",
            description_template="Latest news update.",
            canonical_tags=("news", "breaking"),
        )
        fb = gen.generate(canonical)
        assert fb.title == "Breaking News"
        assert fb.privacy == "PUBLIC"
        assert fb.publish_to_feed is True
        assert fb.publish_to_reels is True

    def test_description_with_topic(self):
        gen = FacebookMetadataGenerator()
        canonical = PublishingMetadata(
            topic="Technology",
            title_template="Tech Update",
            description_template="New tech developments.",
        )
        fb = gen.generate(canonical)
        assert "Technology" in fb.description


# =============================================================================
# PublishingMetadataCompiler
# =============================================================================


class TestPublishingMetadataCompiler:
    def test_compile_all_platforms(self):
        compiler = PublishingMetadataCompiler()
        canonical = PublishingMetadata(
            topic="Documentary",
            title_template="My Documentary",
            description_template="A great documentary.",
            canonical_tags=("doc",),
        )
        specs = [
            {"platform": "youtube", "content_type": "video"},
            {"platform": "tiktok", "content_type": "short"},
            {"platform": "facebook", "content_type": "video"},
        ]
        results = compiler.compile(canonical, specs)

        assert Platform.YOUTUBE in results
        assert Platform.TIKTOK in results
        assert Platform.FACEBOOK in results

        yt = results[Platform.YOUTUBE]
        assert isinstance(yt["metadata"], YouTubeMetadata)
        assert yt["content_type"] == ContentType.VIDEO

        tt = results[Platform.TIKTOK]
        assert isinstance(tt["metadata"], TikTokMetadata)
        assert tt["content_type"] == ContentType.SHORT

    def test_compile_with_overrides(self):
        compiler = PublishingMetadataCompiler()
        canonical = PublishingMetadata(
            topic="Test",
            title_template="Original Title",
            description_template="Original desc.",
            canonical_tags=("test",),
        )
        specs = [
            {
                "platform": "youtube",
                "content_type": "video",
                "title_override": "Custom YouTube Title",
            }
        ]
        results = compiler.compile(canonical, specs)
        yt = results[Platform.YOUTUBE]["metadata"]
        assert yt.title == "Custom YouTube Title"


# =============================================================================
# PublishingPlanBuilder
# =============================================================================


class TestPublishingPlanBuilder:
    def test_build_plan(self):
        builder = PublishingPlanBuilder()
        plan = builder.build_plan(
            job_id="job_001",
            topic="Science Documentary",
            title="The Science of Everything",
            description="An exploration of science.",
            canonical_tags=("science", "documentary", "education"),
            platforms=(Platform.YOUTUBE, Platform.TIKTOK, Platform.FACEBOOK),
            video_path="/path/to/final.mp4",
        )
        assert plan["job_id"] == "job_001"
        assert plan["plan_id"] == "publish_job_001"
        assert plan["canonical_metadata"]["topic"] == "Science Documentary"
        assert len(plan["platforms"]) == 3

    def test_build_plan_youtube_video(self):
        builder = PublishingPlanBuilder()
        plan = builder.build_plan(
            job_id="job_002",
            topic="History",
            title="History of the World",
            description="A history documentary.",
            canonical_tags=("history",),
            platforms=(Platform.YOUTUBE,),
            video_path="/path/to/video.mp4",
        )
        yt_spec = plan["platforms"][0]
        assert yt_spec["platform"] == "youtube"
        assert yt_spec["content_type"] == "video"
        assert yt_spec["video_path"] == "/path/to/video.mp4"

    def test_build_plan_tiktok_short(self):
        builder = PublishingPlanBuilder()
        plan = builder.build_plan(
            job_id="job_003",
            topic="Fun",
            title="Funny Moment",
            description="A funny clip.",
            canonical_tags=("fun",),
            platforms=(Platform.TIKTOK,),
            short_paths={"scene_1": "/path/to/short.mp4"},
        )
        tt_spec = plan["platforms"][0]
        assert tt_spec["platform"] == "tiktok"
        assert tt_spec["content_type"] == "short"
        # TikTok gets short content
        assert tt_spec["video_path"] is not None


# =============================================================================
# Publishing QA
# =============================================================================


class TestPublishingQA:
    def test_publishing_qa_all_ok(self):
        from app.publishing.schemas import PublishingQAReport
        qa = PublishingQAReport(
            plan_id="publish_001",
            job_id="job_001",
            title_length_ok=True,
            description_length_ok=True,
            tags_count_ok=True,
            thumbnail_exists=True,
            video_exists=True,
        )
        assert qa.passed is True
        assert len(qa.issues) == 0

    def test_publishing_qa_with_issues(self):
        from app.publishing.schemas import PublishingQAReport
        qa = PublishingQAReport(
            plan_id="publish_001",
            job_id="job_001",
            title_length_ok=False,
            description_length_ok=True,
            tags_count_ok=True,
            thumbnail_exists=False,
            video_exists=True,
            passed=False,  # Must be explicitly set since default=True
            issues=("title_too_long", "thumbnail_missing"),
        )
        assert qa.passed is False
        assert len(qa.issues) == 2


# =============================================================================
# Publishing Result
# =============================================================================


class TestPublishingResult:
    def test_all_succeeded(self):
        from app.publishing.schemas import PlatformPublishResult, PublishingResult, PublishStatus

        yt_result = PlatformPublishResult(
            platform=Platform.YOUTUBE,
            content_type=ContentType.VIDEO,
            status=PublishStatus.PUBLISHED,
            published_url="https://youtube.com/watch?v=abc",
            duration_ms=5000,
        )
        tt_result = PlatformPublishResult(
            platform=Platform.TIKTOK,
            content_type=ContentType.SHORT,
            status=PublishStatus.PUBLISHED,
            published_url="https://tiktok.com/@user/video/123",
            duration_ms=3000,
        )
        result = PublishingResult(
            plan_id="publish_001",
            job_id="job_001",
            platform_results=(yt_result, tt_result),
            total_platforms=2,
            successful_platforms=2,
            failed_platforms=0,
        )
        assert result.all_succeeded is True
        assert result.any_failed is False

    def test_some_failed(self):
        from app.publishing.schemas import PlatformPublishResult, PublishingResult, PublishStatus

        yt_result = PlatformPublishResult(
            platform=Platform.YOUTUBE,
            content_type=ContentType.VIDEO,
            status=PublishStatus.PUBLISHED,
            duration_ms=5000,
        )
        tt_result = PlatformPublishResult(
            platform=Platform.TIKTOK,
            content_type=ContentType.SHORT,
            status=PublishStatus.FAILED,
            error_kind="RATE_LIMIT",
            error_message="Rate limit exceeded",
            duration_ms=1000,
        )
        result = PublishingResult(
            plan_id="publish_001",
            job_id="job_001",
            platform_results=(yt_result, tt_result),
            total_platforms=2,
            successful_platforms=1,
            failed_platforms=1,
        )
        assert result.all_succeeded is False
        assert result.any_failed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

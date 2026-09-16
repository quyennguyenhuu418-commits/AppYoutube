"""
P15 — PublishingMetadataGenerator: platform-specific metadata from canonical data.

Generates YouTube, TikTok, Facebook metadata from:
- StoryPackage (topic, title)
- ShortsPlan / ThumbnailPlan (content references)
- PublishingMetadata (canonical)

This module does NOT call any publishing APIs. It only generates metadata.
Actual API publishing is in the PublishingClient.
"""

from __future__ import annotations

from typing import Any

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
# YouTube Generator
# =============================================================================


class YouTubeMetadataGenerator:
    """Generate YouTube video metadata from canonical data."""

    # YouTube category IDs
    CATEGORIES = {
        "science": 28,
        "technology": 28,
        "education": 27,
        "entertainment": 24,
        "news": 25,
        "music": 10,
        "gaming": 20,
        "sports": 17,
        "travel": 19,
        "food": 22,
        "comedy": 23,
        "howto": 26,
        "documentary": 1,
    }

    def generate(
        self,
        canonical: PublishingMetadata,
        title_override: str | None = None,
        description_override: str | None = None,
        tags_override: tuple[str, ...] | None = None,
        is_short: bool = False,
    ) -> YouTubeMetadata:
        """Generate YouTube metadata.

        Args:
            canonical: Platform-agnostic metadata
            title_override: Override the auto-generated title
            description_override: Override the auto-generated description
            tags_override: Override the auto-generated tags
            is_short: Whether this is a YouTube Short
        """
        title = title_override or self._build_title(
            canonical.title_template, is_short=is_short
        )
        description = description_override or self._build_description(
            canonical.description_template,
            canonical.topic,
            canonical.canonical_tags,
            include_short_note=is_short,
        )
        tags = tags_override or self._build_tags(
            canonical.canonical_tags,
            canonical.topic,
            is_short=is_short,
        )
        category_id = self._infer_category(canonical.topic)

        return YouTubeMetadata(
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
            is_short=is_short,
            notify_subscribers=not is_short,
        )

    @staticmethod
    def _build_title(template: str, is_short: bool) -> str:
        """Build YouTube-optimized title."""
        title = template
        if is_short and "#shorts" not in title.lower():
            title = f"{title} #shorts"
        # Truncate to 100 chars
        if len(title) > 100:
            title = title[:97] + "..."
        return title

    @staticmethod
    def _build_description(
        template: str,
        topic: str,
        tags: tuple[str, ...],
        include_short_note: bool = False,
    ) -> str:
        """Build YouTube-optimized description.

        Format:
        [short intro if applicable]
        [canonical description]
        ---
        [canonical tags as hashtags]
        [topic footer]
        """
        lines = []

        if include_short_note:
            lines.append("🎬 Short version of my latest documentary!\n")

        lines.append(template)

        if tags:
            lines.append("\n---\n")
            hashtag_lines = [f"#{t.strip().replace(' ', '')}" for t in tags[:10]]
            lines.append(" ".join(hashtag_lines))

        lines.append(f"\n\n📌 Topic: {topic}")

        # YouTube max description is 5000 chars
        full = "\n".join(lines)
        if len(full) > 5000:
            full = full[:4997] + "..."

        return full

    @staticmethod
    def _build_tags(
        canonical_tags: tuple[str, ...],
        topic: str,
        is_short: bool,
    ) -> tuple[str, ...]:
        """Build YouTube tags."""
        tags = list(canonical_tags[:15])  # Max 500 chars total for tags

        # Add topic as a tag
        if topic and topic not in tags:
            tags.append(topic)

        if is_short and "shorts" not in tags:
            tags.append("shorts")

        return tuple(tags[:30])  # YouTube max 30 tags

    @staticmethod
    def _infer_category(topic: str) -> int | None:
        """Infer YouTube category from topic."""
        topic_lower = topic.lower()
        cats = YouTubeMetadataGenerator.CATEGORIES
        for keyword, cat_id in cats.items():
            if keyword in topic_lower:
                return cat_id
        return 1  # Default: Film & Animation


# =============================================================================
# TikTok Generator
# =============================================================================


class TikTokMetadataGenerator:
    """Generate TikTok video metadata from canonical data."""

    def generate(
        self,
        canonical: PublishingMetadata,
        title_override: str | None = None,
        description_override: str | None = None,
        hashtags_override: tuple[str, ...] | None = None,
    ) -> TikTokMetadata:
        """Generate TikTok metadata.

        Args:
            canonical: Platform-agnostic metadata
            title_override: Override the auto-generated title
            description_override: Override the auto-generated description
            hashtags_override: Override the auto-generated hashtags
        """
        # TikTok title = description (they're the same field)
        title = title_override or self._build_title(canonical.title_template)
        description = description_override or self._build_description(
            canonical.title_template,
            canonical.canonical_tags,
        )
        hashtags = hashtags_override or self._build_hashtags(
            canonical.canonical_tags,
            canonical.topic,
        )

        return TikTokMetadata(
            title=title,
            description=description,
            hashtags=hashtags,
            content_warning="none",
            comment_setting="all",
            duet_setting="anyone",
            stitch_setting="anyone",
            download_setting=True,
        )

    @staticmethod
    def _build_title(template: str) -> str:
        """Build TikTok title (max 150 chars)."""
        title = template
        if len(title) > 150:
            title = title[:147] + "..."
        return title

    @staticmethod
    def _build_description(
        template: str,
        tags: tuple[str, ...],
    ) -> str:
        """Build TikTok description with hashtags.

        TikTok description = title + hashtags.
        Max 2200 chars.
        """
        lines = [template]

        if tags:
            tag_lines = [f"#{t.strip().replace(' ', '')}" for t in tags[:10]]
            lines.append(" ".join(tag_lines))

        full = "\n".join(lines)
        if len(full) > 2200:
            full = full[:2197] + "..."
        return full

    @staticmethod
    def _build_hashtags(
        canonical_tags: tuple[str, ...],
        topic: str,
    ) -> tuple[str, ...]:
        """Build TikTok hashtags (max ~100 chars of hashtags recommended)."""
        hashtags = []

        # Top 5 canonical tags
        for tag in canonical_tags[:5]:
            clean = tag.strip().replace(" ", "").lower()
            if clean:
                hashtags.append(clean)

        # Topic as hashtag
        topic_clean = topic.strip().replace(" ", "").lower()
        if topic_clean and topic_clean not in hashtags:
            hashtags.append(topic_clean)

        # Always add documentary
        if "documentary" not in hashtags:
            hashtags.append("documentary")

        return tuple(hashtags[:10])


# =============================================================================
# Facebook Generator
# =============================================================================


class FacebookMetadataGenerator:
    """Generate Facebook video metadata from canonical data."""

    def generate(
        self,
        canonical: PublishingMetadata,
        title_override: str | None = None,
        description_override: str | None = None,
        tags_override: tuple[str, ...] | None = None,
    ) -> FacebookMetadata:
        """Generate Facebook metadata.

        Args:
            canonical: Platform-agnostic metadata
            title_override: Override the auto-generated title
            description_override: Override the auto-generated description
            tags_override: Override the auto-generated content tags
        """
        title = title_override or canonical.title_template
        description = description_override or self._build_description(
            canonical.description_template,
            canonical.topic,
        )
        tags = tags_override or self._build_tags(
            canonical.canonical_tags,
            canonical.topic,
        )

        return FacebookMetadata(
            title=title,
            description=description,
            content_tags=tags,
            content_category="entertainment",
            privacy="PUBLIC",
            publish_to_feed=True,
            publish_to_reels=True,
            cross_post_to_instagram=False,
            disable_comments=False,
        )

    @staticmethod
    def _build_description(
        template: str,
        topic: str,
    ) -> str:
        """Build Facebook description.

        Facebook allows up to 63206 chars — plenty of room.
        """
        lines = [template]
        lines.append(f"\n\n📌 Topic: {topic}")

        full = "\n".join(lines)
        if len(full) > 63206:
            full = full[:63203] + "..."

        return full

    @staticmethod
    def _build_tags(
        canonical_tags: tuple[str, ...],
        topic: str,
    ) -> tuple[str, ...]:
        """Build Facebook content tags (max 10 recommended)."""
        tags = list(canonical_tags[:10])

        if topic and topic not in tags:
            tags.append(topic)

        return tuple(tags[:10])


# =============================================================================
# PublishingMetadataCompiler
# =============================================================================


class PublishingMetadataCompiler:
    """Compile platform-specific metadata from canonical publishing data."""

    def __init__(self) -> None:
        self.youtube_gen = YouTubeMetadataGenerator()
        self.tiktok_gen = TikTokMetadataGenerator()
        self.facebook_gen = FacebookMetadataGenerator()

    def compile(
        self,
        canonical: PublishingMetadata,
        platform_specs: list[dict[str, Any]],
    ) -> dict[Platform, dict[str, Any]]:
        """Compile platform-specific metadata for all platforms.

        Args:
            canonical: Platform-agnostic metadata
            platform_specs: List of platform specifications

        Returns:
            Dict mapping Platform → {content_type, metadata}
        """
        results: dict[Platform, dict[str, Any]] = {}

        for spec in platform_specs:
            platform = Platform(spec.get("platform", "youtube"))
            content_type = ContentType(spec.get("content_type", "video"))
            title_override = spec.get("title_override")
            desc_override = spec.get("description_override")
            tags_override = spec.get("tags_override")

            if platform == Platform.YOUTUBE:
                is_short = content_type == ContentType.SHORT
                meta = self.youtube_gen.generate(
                    canonical,
                    title_override=title_override,
                    description_override=desc_override,
                    tags_override=tags_override,
                    is_short=is_short,
                )
                results[platform] = {
                    "content_type": content_type,
                    "metadata": meta,
                }

            elif platform == Platform.TIKTOK:
                meta = self.tiktok_gen.generate(
                    canonical,
                    title_override=title_override,
                    description_override=desc_override,
                    hashtags_override=tags_override,
                )
                results[platform] = {
                    "content_type": content_type,
                    "metadata": meta,
                }

            elif platform == Platform.FACEBOOK:
                meta = self.facebook_gen.generate(
                    canonical,
                    title_override=title_override,
                    description_override=desc_override,
                    tags_override=tags_override,
                )
                results[platform] = {
                    "content_type": content_type,
                    "metadata": meta,
                }

        return results


# =============================================================================
# Publishing Plan Builder
# =============================================================================


class PublishingPlanBuilder:
    """Build a PublishingPlan from job data."""

    def __init__(self) -> None:
        self._compiler = PublishingMetadataCompiler()

    def build_plan(
        self,
        job_id: str,
        topic: str,
        title: str,
        description: str,
        canonical_tags: tuple[str, ...],
        platforms: tuple[Platform, ...],
        video_path: str | None = None,
        short_paths: dict[str, str] | None = None,
        thumbnail_paths: dict[str, str] | None = None,
        visibility: Visibility = Visibility.PUBLIC,
    ) -> dict[str, Any]:
        """Build a complete PublishingPlan dict from job data.

        This produces the plan data that can be serialized to JSON
        and consumed by a publishing client.
        """
        from app.publishing.schemas import (
            ContentType,
            PlatformPublishSpec,
            PublishingMetadata,
            PublishingPlan,
        )

        canonical = PublishingMetadata(
            topic=topic,
            title_template=title,
            description_template=description,
            canonical_tags=canonical_tags,
            visibility=visibility,
            content_type=ContentType.VIDEO,
            video_asset_path=video_path,
        )

        platform_specs: list[PlatformPublishSpec] = []
        for platform in platforms:
            if platform == Platform.TIKTOK:
                # TikTok always gets short content
                short_path = None
                if short_paths:
                    short_path = next(iter(short_paths.values()), None)
                spec = PlatformPublishSpec(
                    platform=platform,
                    content_type=ContentType.SHORT,
                    visibility=visibility,
                    video_path=short_path,
                )
            elif platform in (Platform.YOUTUBE, Platform.FACEBOOK):
                spec = PlatformPublishSpec(
                    platform=platform,
                    content_type=ContentType.VIDEO,
                    visibility=visibility,
                    video_path=video_path,
                )
            else:
                spec = PlatformPublishSpec(
                    platform=platform,
                    content_type=ContentType.VIDEO,
                    visibility=visibility,
                    video_path=video_path,
                )
            platform_specs.append(spec)

        plan = PublishingPlan(
            plan_id=f"publish_{job_id}",
            job_id=job_id,
            canonical_metadata=canonical,
            platforms=tuple(platform_specs),
            auto_generate_descriptions=True,
            auto_generate_tags=True,
        )
        return plan.model_dump(mode="json")


__all__ = [
    "YouTubeMetadataGenerator",
    "TikTokMetadataGenerator",
    "FacebookMetadataGenerator",
    "PublishingMetadataCompiler",
    "PublishingPlanBuilder",
]

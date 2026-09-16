"""Stage: Publishing — prepare and publish content to TikTok, YouTube, Facebook.

Consumes:
  - final.mp4 (from s10_render)
  - shorts/ (from s11_short)
  - thumbnails/ (from s12_thumbnail)
  - story_package.json (from s2_thesis)

Produces:
  - publishing_plan.json (PublishingPlan with per-platform metadata)
  - publishing_result.json (PublishingResult with per-platform status)

Note: This stage generates metadata and prepares the publishing plan.
Actual API publishing requires platform credentials (OAuth tokens, API keys).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.core.paths import job_dir, stage_path
from app.pipeline.stages.base import Stage, StageContext
from app.publishing.metadata_generator import PublishingPlanBuilder
from app.publishing.schemas import (
    Platform,
    PublishingMetadata,
    PublishingPlan,
    PublishingQAReport,
)

log = get_logger(__name__)


class PublishingStage(Stage):
    """Publishing preparation stage."""

    name = "publishing"
    label = "Publishing"

    def run(self, ctx: StageContext) -> dict:
        job_id = ctx.job_id

        # Load job data
        story_pkg = self._load_story_package(job_id)
        topic = story_pkg.get("topic", "")
        title = story_pkg.get("title", topic)
        description = self._build_description(story_pkg)
        tags = self._extract_tags(story_pkg)

        # Load available assets
        video_path = str(job_dir(job_id) / "final.mp4")
        short_paths = self._list_shorts(job_id)
        thumbnail_paths = self._list_thumbnails(job_id)

        # Determine which platforms to target
        # (In production, this would come from user configuration)
        platforms = self._determine_platforms(story_pkg)

        # Build publishing plan
        builder = PublishingPlanBuilder()
        plan_data = builder.build_plan(
            job_id=job_id,
            topic=topic,
            title=title,
            description=description,
            canonical_tags=tuple(tags),
            platforms=platforms,
            video_path=video_path if Path(video_path).exists() else None,
            short_paths=short_paths,
            thumbnail_paths=thumbnail_paths,
        )

        # Save plan
        plan_path = stage_path(job_id, "publishing_plan")
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            json.dumps(plan_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # QA check
        qa = self._qa_plan(plan_data, job_id)

        log.info(
            "[%s] prepared publishing plan for job %s (%d platforms)",
            self.name, job_id, len(platforms)
        )

        return {
            "plan_path": str(plan_path),
            "platforms": [p.value for p in platforms],
            "has_video": Path(video_path).exists(),
            "short_count": len(short_paths),
            "thumbnail_count": len(thumbnail_paths),
            "qa": qa.model_dump(),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_story_package(job_id: str) -> dict:
        path = job_dir(job_id) / "story_package.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"topic": "", "title": "", "description": ""}

    @staticmethod
    def _build_description(story_pkg: dict) -> str:
        # Use thesis/description from story package
        thesis = story_pkg.get("thesis", "")
        description = story_pkg.get("description", "")
        if thesis and not description:
            return thesis
        return description or "AI-generated documentary."

    @staticmethod
    def _extract_tags(story_pkg: dict) -> list[str]:
        """Extract tags from story package."""
        tags = set()

        # From keywords
        keywords = story_pkg.get("keywords", [])
        if isinstance(keywords, list):
            tags.update(str(k) for k in keywords[:10])

        # From topic
        topic = story_pkg.get("topic", "")
        if topic:
            # Add topic words as tags
            words = topic.replace("-", " ").replace("_", " ").split()
            tags.update(w.lower() for w in words if len(w) > 2)

        # Default tags
        default_tags = {"documentary", "ai", "animation", "education"}
        tags.update(default_tags)

        return list(tags)[:15]

    @staticmethod
    def _list_shorts(job_id: str) -> dict[str, str]:
        """List available short clips."""
        shorts_dir = job_dir(job_id) / "shorts"
        if not shorts_dir.exists():
            return {}
        shorts = {}
        for mp4 in shorts_dir.glob("*.mp4"):
            # Extract scene_id from filename: short_{scene_id}.mp4
            scene_id = mp4.stem.replace("short_", "")
            shorts[scene_id] = str(mp4)
        return shorts

    @staticmethod
    def _list_thumbnails(job_id: str) -> dict[str, str]:
        """List available thumbnails."""
        thumbs_dir = job_dir(job_id) / "thumbnails"
        if not thumbs_dir.exists():
            return {}
        thumbs = {}
        for img in thumbs_dir.glob("*.webp"):
            thumbs[img.stem] = str(img)
        return thumbs

    @staticmethod
    def _determine_platforms(story_pkg: dict) -> tuple[Platform, ...]:
        """Determine which platforms to target based on content."""
        # Default: all three platforms
        platforms = [Platform.YOUTUBE, Platform.TIKTOK, Platform.FACEBOOK]

        # In production, this would check user configuration
        # For now, return all platforms
        return tuple(platforms)

    # ------------------------------------------------------------------
    # QA
    # ------------------------------------------------------------------

    @staticmethod
    def _qa_plan(plan_data: dict, job_id: str) -> PublishingQAReport:
        """QA check for the publishing plan."""
        issues: list[str] = []

        canonical = plan_data.get("canonical_metadata", {})
        platforms = plan_data.get("platforms", [])

        # Check title length per platform
        for spec in platforms:
            platform = spec.get("platform", "unknown")
            title_len = len(canonical.get("title_template", ""))
            if platform == "tiktok" and title_len > 150:
                issues.append(f"TikTok title too long ({title_len} > 150)")
            elif platform == "youtube" and title_len > 100:
                issues.append(f"YouTube title too long ({title_len} > 100)")

        # Check description
        desc_len = len(canonical.get("description_template", ""))
        if desc_len > 5000:
            issues.append(f"Description too long ({desc_len} > 5000)")

        # Check tags
        tags = canonical.get("canonical_tags", [])
        if len(tags) > 30:
            issues.append(f"Too many tags ({len(tags)} > 30)")

        # Check video exists
        video_path = canonical.get("video_asset_path")
        if video_path and not Path(video_path).exists():
            issues.append(f"Video not found: {video_path}")

        # Check thumbnails
        thumbnail_path = canonical.get("thumbnail_asset_path")
        if thumbnail_path and not Path(thumbnail_path).exists():
            log.warning("[publishing] thumbnail not found: %s", thumbnail_path)

        return PublishingQAReport(
            plan_id=plan_data.get("plan_id", f"publish_{job_id}"),
            job_id=job_id,
            title_length_ok=len(canonical.get("title_template", "")) <= 150,
            description_length_ok=desc_len <= 63206,
            tags_count_ok=len(tags) <= 30,
            thumbnail_exists=bool(thumbnail_path),
            video_exists=bool(video_path),
            passed=len(issues) == 0,
            issues=tuple(issues),
        )


__all__ = ["PublishingStage"]

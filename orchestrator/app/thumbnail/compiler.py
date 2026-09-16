"""
P14 — ThumbnailCompiler: deterministic thumbnail composition planning.

Takes the full pipeline output and produces a ThumbnailPlan with
one or more thumbnails for different platforms and use cases.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.thumbnail.schemas import (
    ThumbnailColorScheme,
    ThumbnailCompilationResult,
    ThumbnailContentType,
    ThumbnailPlan,
    ThumbnailRenderSettings,
    ThumbnailSource,
    ThumbnailTextOverlay,
)


# =============================================================================
# ThumbnailCompiler
# =============================================================================


class ThumbnailCompiler:
    """Compile a ThumbnailPlan from pipeline output."""

    def __init__(
        self,
        default_settings: ThumbnailRenderSettings | None = None,
        generate_for_scenes: bool = True,
        generate_for_title: bool = True,
        generate_for_social: bool = True,
    ) -> None:
        self.default_settings = default_settings or ThumbnailRenderSettings()
        self.generate_for_scenes = generate_for_scenes
        self.generate_for_title = generate_for_title
        self.generate_for_social = generate_for_social

    def compile(
        self,
        job_id: str,
        source_video_path: str | None,
        story_package: dict[str, Any] | None = None,
        scene_definition: dict[str, Any] | None = None,
        title: str = "",
        topic: str = "",
    ) -> ThumbnailPlan:
        """Compile a ThumbnailPlan.

        Parameters:
            job_id: Job identifier
            source_video_path: Path to final.mp4 (for scene captures)
            story_package: StoryPackage for topic/title
            scene_definition: SceneDefinition for scene thumbnails
            title: Video title (for title card)
            topic: Video topic (for context text)

        Returns:
            ThumbnailPlan with one or more thumbnails
        """
        thumbnails: list[ThumbnailCompilationResult] = []
        short_title = self._truncate_title(title or topic or "Documentary", max_len=60)

        # 1. Title thumbnail (YouTube default)
        if self.generate_for_title and title:
            tn = self._build_title_thumbnail(
                job_id=job_id,
                title=title,
                topic=topic,
                source_video_path=source_video_path,
                index=0,
            )
            thumbnails.append(tn)

        # 2. Scene thumbnails (one per scene, max 5)
        if self.generate_for_scenes and scene_definition and source_video_path:
            scenes = scene_definition.get("scenes", [])
            for i, scene in enumerate(scenes[:5]):
                if scene.get("kind") in ("narration", "diagram", "title"):
                    tn = self._build_scene_thumbnail(
                        job_id=job_id,
                        scene=scene,
                        topic=topic,
                        source_video_path=source_video_path,
                        index=i + 1,
                    )
                    thumbnails.append(tn)

        # 3. Social thumbnails (Twitter, Instagram)
        if self.generate_for_social:
            for platform, size, width, height in [
                ("twitter", "twitter_card", 1200, 628),
                ("instagram", "instagram_square", 1080, 1080),
            ]:
                tn = self._build_social_thumbnail(
                    job_id=job_id,
                    title=short_title,
                    topic=topic,
                    source_video_path=source_video_path,
                    platform=platform,
                    size=size,
                    width=width,
                    height=height,
                    index=len(thumbnails),
                )
                thumbnails.append(tn)

        return ThumbnailPlan(
            job_id=job_id,
            thumbnails=tuple(thumbnails),
            generate_for_scenes=self.generate_for_scenes,
            generate_for_title=self.generate_for_title,
            generate_for_social=self.generate_for_social,
            default_settings=self.default_settings,
        )

    def _build_title_thumbnail(
        self,
        job_id: str,
        title: str,
        topic: str,
        source_video_path: str | None,
        index: int,
    ) -> ThumbnailCompilationResult:
        short_title = self._truncate_title(title, 50)
        return ThumbnailCompilationResult(
            thumbnail_id=f"thumb_{job_id}_title",
            job_id=job_id,
            source=ThumbnailSource(
                source_type=ThumbnailContentType.TITLE_CARD,
                title_text=title,
                scene_label=topic,
            ),
            color_scheme=ThumbnailColorScheme.HIGH_CONTRAST,
            text_overlay=ThumbnailTextOverlay(
                text=short_title,
                position="bottom_center",
                font_size=52,
                max_lines=2,
                bold=True,
                shadow=True,
            ),
            include_title=True,
            include_topic=True,
            render_settings=self.default_settings,
            output_filename=f"thumb_{job_id}_title.webp",
            caption=f"{title} | {topic}",
            composition_notes=f"Title card thumbnail for job {job_id}",
            source_video_path=source_video_path,
        )

    def _build_scene_thumbnail(
        self,
        job_id: str,
        scene: dict[str, Any],
        topic: str,
        source_video_path: str | None,
        index: int,
    ) -> ThumbnailCompilationResult:
        scene_id = str(scene.get("id", f"scene_{index}"))
        kind = scene.get("kind", "unknown")
        label = str(scene.get("label", scene.get("kind", "scene")))
        start = float(scene.get("start_sec", 5.0))

        content_type = (
            ThumbnailContentType.DIAGRAM_FOCUS
            if kind == "diagram"
            else ThumbnailContentType.SCENE_CAPTURE
        )

        overlay_text = self._truncate_title(label, 40)

        return ThumbnailCompilationResult(
            thumbnail_id=f"thumb_{job_id}_scene_{scene_id}",
            job_id=job_id,
            source=ThumbnailSource(
                source_type=content_type,
                capture_time_sec=start,
                diagram_scene_id=scene_id if kind == "diagram" else None,
                scene_label=label,
            ),
            color_scheme=ThumbnailColorScheme.HIGH_CONTRAST,
            text_overlay=ThumbnailTextOverlay(
                text=overlay_text,
                position="bottom_left",
                font_size=36,
                max_lines=2,
                bold=True,
                shadow=True,
            ),
            include_title=False,
            include_topic=True,
            render_settings=self.default_settings,
            output_filename=f"thumb_{job_id}_scene_{scene_id}.webp",
            caption=f"{topic} — {label}",
            composition_notes=f"Scene capture for {kind} scene {scene_id}",
            source_video_path=source_video_path,
            source_scene_id=scene_id,
        )

    def _build_social_thumbnail(
        self,
        job_id: str,
        title: str,
        topic: str,
        source_video_path: str | None,
        platform: str,
        size: str,
        width: int,
        height: int,
        index: int,
    ) -> ThumbnailCompilationResult:
        short_title = self._truncate_title(title, 40)
        color = (
            ThumbnailColorScheme.DARK_OVERLAY
            if platform == "instagram"
            else ThumbnailColorScheme.HIGH_CONTRAST
        )
        render_settings = ThumbnailRenderSettings(
            width=width, height=height,
        )
        return ThumbnailCompilationResult(
            thumbnail_id=f"thumb_{job_id}_{platform}",
            job_id=job_id,
            source=ThumbnailSource(
                source_type=ThumbnailContentType.SCENE_CAPTURE,
                capture_time_sec=5.0,
                scene_label=topic,
            ),
            color_scheme=color,
            text_overlay=ThumbnailTextOverlay(
                text=short_title,
                position="center",
                font_size=44,
                max_lines=2,
                bold=True,
                shadow=True,
            ),
            include_title=True,
            include_topic=True,
            render_settings=render_settings,
            output_filename=f"thumb_{job_id}_{platform}.webp",
            caption=f"{title} | {topic}",
            composition_notes=f"Social thumbnail for {platform}",
            source_video_path=source_video_path,
        )

    @staticmethod
    def _truncate_title(title: str, max_len: int = 50) -> str:
        if len(title) <= max_len:
            return title
        return title[: max_len - 3].rstrip() + "..."


# =============================================================================
# ThumbnailGenerator: FFmpeg-based thumbnail extraction
# =============================================================================


class ThumbnailGenerator:
    """Generate thumbnail images using FFmpeg."""

    def __init__(self) -> None:
        self._ffmpeg: str | None = None

    @property
    def ffmpeg(self) -> str:
        import shutil
        if self._ffmpeg is None:
            found = shutil.which("ffmpeg")
            if not found:
                raise RuntimeError("ffmpeg not found on PATH")
            self._ffmpeg = found
        return self._ffmpeg

    def generate(
        self,
        source_video: str | Path,
        output_path: str | Path,
        capture_time_sec: float = 5.0,
        width: int = 1280,
        height: int = 720,
        format: str = "webp",
        quality: int = 85,
    ) -> dict[str, Any]:
        """Generate a thumbnail by extracting a frame.

        Parameters:
            source_video: Path to source video
            output_path: Output thumbnail path
            capture_time_sec: Which second to capture
            width: Output width
            height: Output height
            format: Output format (webp, jpeg, png)
            quality: Quality 1-100

        Returns:
            Dict with output path and metadata
        """
        import subprocess

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # FFmpeg frame extraction
        argv = [
            self.ffmpeg, "-y",
            "-ss", f"{capture_time_sec:.3f}",
            "-i", str(source_video),
            "-vframes", "1",
            "-vf", f"scale={width}:{height}:flags=lanczos",
            "-q:v", str(max(2, 31 - quality // 4)),  # Map quality 1-100 to q:v 2-31
            "-f", "image2",
            str(out),
        ]

        try:
            proc = subprocess.run(
                argv, shell=False, check=True,
                capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError:
            raise RuntimeError("ffmpeg not found on PATH")
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"ffmpeg failed: {exc.stderr[-500:]}")

        return {
            "output_path": str(out),
            "width": width,
            "height": height,
            "format": format,
            "capture_time_sec": capture_time_sec,
            "file_size_bytes": out.stat().st_size if out.exists() else 0,
        }


# =============================================================================
# Fingerprint
# =============================================================================


def thumbnail_plan_fingerprint(plan: ThumbnailPlan) -> str:
    """Deterministic fingerprint for a ThumbnailPlan."""
    parts = [
        plan.job_id,
        str(plan.generate_for_scenes),
        str(plan.generate_for_title),
        str(plan.generate_for_social),
        str(len(plan.thumbnails)),
    ]
    for t in plan.thumbnails:
        parts.extend([
            t.thumbnail_id,
            t.source.source_type.value,
            str(t.color_scheme.value),
        ])
    text = "|".join(parts)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


__all__ = [
    "ThumbnailCompiler",
    "ThumbnailGenerator",
    "thumbnail_plan_fingerprint",
]

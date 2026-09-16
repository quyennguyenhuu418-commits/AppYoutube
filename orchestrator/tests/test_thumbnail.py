"""
P14 — Thumbnail tests: compiler, schemas, generator.
"""

from __future__ import annotations

import pytest

from app.thumbnail.compiler import ThumbnailCompiler, thumbnail_plan_fingerprint
from app.thumbnail.schemas import (
    ThumbnailColorScheme,
    ThumbnailCompilationResult,
    ThumbnailContentType,
    ThumbnailFormat,
    ThumbnailPlan,
    ThumbnailQAReport,
    ThumbnailRenderSettings,
    ThumbnailSource,
    ThumbnailTextOverlay,
)


# =============================================================================
# Schemas
# =============================================================================


class TestThumbnailSchemas:
    def test_render_settings_defaults(self):
        rs = ThumbnailRenderSettings()
        assert rs.format == ThumbnailFormat.WEBP
        assert rs.width == 1280
        assert rs.height == 720
        assert rs.quality == 85

    def test_render_settings_frozen(self):
        rs = ThumbnailRenderSettings()
        with pytest.raises(Exception):
            rs.width = 640

    def test_thumbnail_source(self):
        src = ThumbnailSource(
            source_type=ThumbnailContentType.SCENE_CAPTURE,
            capture_time_sec=5.0,
        )
        assert src.source_type == ThumbnailContentType.SCENE_CAPTURE
        assert src.capture_time_sec == 5.0

    def test_text_overlay(self):
        overlay = ThumbnailTextOverlay(
            text="Test Title",
            position="bottom_center",
            font_size=48,
        )
        assert overlay.text == "Test Title"
        assert overlay.bold is True
        assert overlay.shadow is True

    def test_compilation_result(self):
        result = ThumbnailCompilationResult(
            thumbnail_id="thumb_001",
            job_id="job_001",
            source=ThumbnailSource(
                source_type=ThumbnailContentType.TITLE_CARD,
                title_text="My Documentary",
            ),
            output_filename="thumb_001.webp",
            caption="Test caption",
        )
        assert result.thumbnail_id == "thumb_001"
        assert result.output_path == "thumbnails/thumb_001.webp"

    def test_thumbnail_plan(self):
        plan = ThumbnailPlan(
            job_id="job_001",
            thumbnails=(),
        )
        assert plan.thumbnail_count == 0


# =============================================================================
# Compiler
# =============================================================================


class TestThumbnailCompiler:
    def test_compile_with_title(self):
        compiler = ThumbnailCompiler()
        plan = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            story_package={"topic": "Science"},
            title="My Documentary",
            topic="Science",
        )
        assert plan.job_id == "job_001"
        # Should have title thumbnail
        assert plan.thumbnail_count >= 1
        assert plan.generate_for_title is True

    def test_compile_scene_thumbnails(self):
        compiler = ThumbnailCompiler()
        scene_def = {
            "scenes": [
                {"id": "s1", "kind": "narration", "start_sec": 0, "end_sec": 30},
                {"id": "s2", "kind": "diagram", "start_sec": 30, "end_sec": 60},
                {"id": "s3", "kind": "title", "start_sec": 0, "end_sec": 5},
            ]
        }
        plan = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            story_package={"topic": "Science"},
            scene_definition=scene_def,
            title="My Documentary",
            topic="Science",
        )
        # Should have title + 2 scene thumbnails (narration, diagram)
        assert plan.thumbnail_count >= 2

    def test_truncate_long_title(self):
        compiler = ThumbnailCompiler()
        long_title = "This is a very very long title that should be truncated"
        result = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            title=long_title,
            topic="",
        )
        # Should not crash
        assert result.job_id == "job_001"

    def test_compile_without_source_video(self):
        compiler = ThumbnailCompiler()
        plan = compiler.compile(
            job_id="job_001",
            source_video_path=None,
            title="My Documentary",
            topic="Science",
        )
        # Should still produce a plan (with title thumbnail)
        assert plan.job_id == "job_001"


# =============================================================================
# Fingerprint
# =============================================================================


class TestThumbnailFingerprint:
    def test_same_input_same_fingerprint(self):
        compiler = ThumbnailCompiler()
        plan1 = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            title="My Documentary",
            topic="Science",
        )
        plan2 = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            title="My Documentary",
            topic="Science",
        )
        fp1 = thumbnail_plan_fingerprint(plan1)
        fp2 = thumbnail_plan_fingerprint(plan2)
        assert fp1 == fp2

    def test_different_job_different_fingerprint(self):
        compiler = ThumbnailCompiler()
        plan1 = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            title="My Documentary",
            topic="Science",
        )
        plan2 = compiler.compile(
            job_id="job_002",
            source_video_path="/fake.mp4",
            title="My Documentary",
            topic="Science",
        )
        fp1 = thumbnail_plan_fingerprint(plan1)
        fp2 = thumbnail_plan_fingerprint(plan2)
        assert fp1 != fp2


# =============================================================================
# QA
# =============================================================================


class TestThumbnailQA:
    def test_qa_defaults(self):
        qa = ThumbnailQAReport(
            thumbnail_id="thumb_001",
            job_id="job_001",
            output_path="/fake/thumb.webp",
        )
        assert qa.passed is False
        assert qa.file_exists is False


# =============================================================================
# Color scheme
# =============================================================================


class TestThumbnailColorScheme:
    def test_all_schemes(self):
        assert ThumbnailColorScheme.HIGH_CONTRAST.value == "high_contrast"
        assert ThumbnailColorScheme.DARK_OVERLAY.value == "dark_overlay"
        assert ThumbnailColorScheme.LIGHT_OVERLAY.value == "light_overlay"
        assert ThumbnailColorScheme.BRAND_COLOR.value == "brand_color"
        assert ThumbnailColorScheme.MINIMAL.value == "minimal"


# =============================================================================
# Format
# =============================================================================


class TestThumbnailFormat:
    def test_all_formats(self):
        assert ThumbnailFormat.JPEG.value == "jpeg"
        assert ThumbnailFormat.WEBP.value == "webp"
        assert ThumbnailFormat.PNG.value == "png"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

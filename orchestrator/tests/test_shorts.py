"""
P13 — Shorts tests: compiler, schemas, caption adapter.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.shorts.compiler import ShortsCompiler, shorts_plan_fingerprint
from app.shorts.schemas import (
    CaptionPositionOverride,
    CropMode,
    SceneCropSpec,
    ShortsAspectRatio,
    ShortsCompilationResult,
    ShortsPlan,
    ShortsQuality,
    ShortsRenderSettings,
    ShortsSourceContext,
    ShortsTargetPlatform,
    ShortsQAReport,
)
from app.shorts.vertical_caption_adapter import VerticalCaptionAdapter


# =============================================================================
# Schemas
# =============================================================================


class TestShortsSchemas:
    def test_render_settings_defaults(self):
        rs = ShortsRenderSettings()
        assert rs.target_resolution == (1080, 1920)
        assert rs.target_fps == 30.0
        assert rs.max_duration_sec == 60.0
        assert rs.min_duration_sec == 15.0

    def test_render_settings_frozen(self):
        rs = ShortsRenderSettings()
        with pytest.raises(Exception):
            rs.max_duration_sec = 30.0

    def test_scene_crop_spec(self):
        scene = SceneCropSpec(
            scene_id="scene_001",
            scene_label="Opening narration",
            start_sec=0.0,
            end_sec=30.0,
            crop_mode=CropMode.SMART_FACE,
        )
        assert scene.scene_id == "scene_001"
        assert scene.crop_mode == CropMode.SMART_FACE

    def test_compilation_result(self):
        source = ShortsSourceContext(
            job_id="job_001",
            source_video_path="/path/to/final.mp4",
            source_duration_sec=300.0,
            source_width=1280,
            source_height=720,
            source_fps=30.0,
        )
        scene = SceneCropSpec(
            scene_id="scene_001",
            scene_label="Test",
            start_sec=10.0,
            end_sec=40.0,
        )
        result = ShortsCompilationResult(
            shorts_id="short_001",
            job_id="job_001",
            source=source,
            selected_scene=scene,
            clip_start_sec=10.0,
            clip_end_sec=40.0,
            clip_duration_sec=30.0,
            output_filename="short_scene_001.mp4",
        )
        assert result.shorts_id == "short_001"
        assert result.output_resolution == "1080x1920"
        assert result.clip_duration_sec == 30.0

    def test_shorts_plan(self):
        plan = ShortsPlan(
            job_id="job_001",
            shorts_ids=("short_001",),
            results=(),
        )
        assert plan.job_id == "job_001"
        assert plan.shorts_count == 0


# =============================================================================
# Compiler — scene scoring
# =============================================================================


def _build_minimal_scene_def(
    scenes: list[dict],
    duration: float = 300.0,
) -> dict:
    return {
        "scenes": scenes,
        "meta": {"target_duration_sec": duration},
    }


class TestShortsCompilerSceneScoring:
    def test_prefers_narration_scenes(self):
        compiler = ShortsCompiler()
        scene_def = _build_minimal_scene_def([
            {
                "id": "scene_a",
                "kind": "b_roll",
                "start_sec": 0,
                "end_sec": 30,
            },
            {
                "id": "scene_b",
                "kind": "narration",
                "start_sec": 60,
                "end_sec": 90,
                "has_narration": True,
            },
        ])
        plan = compiler.compile(
            job_id="test_job",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        assert plan.shorts_count >= 1
        selected_ids = [r.selected_scene.scene_id for r in plan.results]
        assert "scene_b" in selected_ids  # narration scene should be selected

    def test_prefers_emotional_scenes(self):
        compiler = ShortsCompiler()
        scene_def = _build_minimal_scene_def([
            {
                "id": "scene_neutral",
                "kind": "narration",
                "start_sec": 0,
                "end_sec": 30,
                "emotional_intent": "setup",
            },
            {
                "id": "scene_triumph",
                "kind": "narration",
                "start_sec": 60,
                "end_sec": 90,
                "emotional_intent": "triumphant",
                "has_narration": True,
            },
        ])
        plan = compiler.compile(
            job_id="test_job",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        selected_ids = [r.selected_scene.scene_id for r in plan.results]
        assert "scene_triumph" in selected_ids

    def test_diversified_selection(self):
        compiler = ShortsCompiler(max_shorts=3, diversify_scenes=True)
        scene_def = _build_minimal_scene_def([
            {
                "id": "s1",
                "kind": "narration",
                "start_sec": 0,
                "end_sec": 30,
                "has_narration": True,
            },
            {
                "id": "s2",
                "kind": "narration",
                "start_sec": 50,
                "end_sec": 80,
                "has_narration": True,
            },
            {
                "id": "s3",
                "kind": "diagram",
                "start_sec": 100,
                "end_sec": 130,
                "has_diagram": True,
            },
            {
                "id": "s4",
                "kind": "narration",
                "start_sec": 200,
                "end_sec": 230,
                "has_narration": True,
            },
        ])
        plan = compiler.compile(
            job_id="test_job",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        # Should select up to 3 scenes
        assert plan.shorts_count <= 3

    def test_fallback_to_middle_scene(self):
        compiler = ShortsCompiler()
        scene_def = _build_minimal_scene_def([
            {
                "id": "only_scene",
                "kind": "unknown",
                "start_sec": 0,
                "end_sec": 30,
            },
        ])
        plan = compiler.compile(
            job_id="test_job",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        assert plan.shorts_count >= 1

    def test_empty_scene_definition(self):
        compiler = ShortsCompiler()
        scene_def = _build_minimal_scene_def([])
        plan = compiler.compile(
            job_id="test_job",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        assert plan is not None


# =============================================================================
# Compiler — crop composition
# =============================================================================


class TestShortsCompilerComposition:
    def test_crop_center_from_focus(self):
        compiler = ShortsCompiler()
        scene_def = _build_minimal_scene_def([{
            "id": "scene_1",
            "kind": "narration",
            "start_sec": 0,
            "end_sec": 30,
            "has_narration": True,
            "focus_x": 0.3,
            "focus_y": 0.4,
        }])
        plan = compiler.compile(
            job_id="test_job",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        result = plan.results[0]
        assert result.crop_center_x == 0.3
        assert result.crop_center_y == 0.4

    def test_caption_override_applied(self):
        compiler = ShortsCompiler()
        scene_def = _build_minimal_scene_def([{
            "id": "scene_1",
            "kind": "narration",
            "start_sec": 0,
            "end_sec": 30,
            "has_narration": True,
        }])
        plan = compiler.compile(
            job_id="test_job",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        result = plan.results[0]
        assert result.caption_override is not None
        assert result.caption_override.vertical_position == 0.78


# =============================================================================
# Fingerprint determinism
# =============================================================================


class TestShortsFingerprint:
    def test_same_input_same_fingerprint(self):
        scene_def = _build_minimal_scene_def([{
            "id": "scene_1",
            "kind": "narration",
            "start_sec": 0,
            "end_sec": 30,
            "has_narration": True,
        }])
        compiler = ShortsCompiler()

        plan1 = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        plan2 = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            scene_definition=scene_def,
        )
        fp1 = shorts_plan_fingerprint(plan1)
        fp2 = shorts_plan_fingerprint(plan2)
        assert fp1 == fp2

    def test_different_input_different_fingerprint(self):
        scene_def_1 = _build_minimal_scene_def([{
            "id": "scene_1",
            "kind": "narration",
            "start_sec": 0,
            "end_sec": 30,
        }])
        scene_def_2 = _build_minimal_scene_def([{
            "id": "scene_2",
            "kind": "diagram",
            "start_sec": 50,
            "end_sec": 80,
        }])
        compiler = ShortsCompiler()

        plan1 = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            scene_definition=scene_def_1,
        )
        plan2 = compiler.compile(
            job_id="job_001",
            source_video_path="/fake.mp4",
            scene_definition=scene_def_2,
        )
        fp1 = shorts_plan_fingerprint(plan1)
        fp2 = shorts_plan_fingerprint(plan2)
        assert fp1 != fp2


# =============================================================================
# Vertical Caption Adapter
# =============================================================================


class TestVerticalCaptionAdapter:
    def test_adapt_center_caption(self):
        adapter = VerticalCaptionAdapter()
        caption_track = {
            "segments": [
                {
                    "x": 0.5,
                    "y": 0.5,
                    "font_size": 24,
                    "line_width": 0.8,
                    "words": [
                        {"text": "Hello", "start_sec": 0.0, "end_sec": 1.0}
                    ],
                }
            ]
        }
        adapted = adapter.adapt(
            caption_track,
            source_height=720,
            source_width=1280,
            target_height=1920,
            target_width=1080,
            crop_center_x=0.5,
            crop_center_y=0.5,
        )
        seg = adapted["segments"][0]
        # Center captions should move to lower third
        assert seg["y"] > 0.5  # Lower on screen
        assert "_vertical_adapted" in adapted
        assert adapted["_vertical_adapted"] is True

    def test_lower_third_caption_preserved(self):
        adapter = VerticalCaptionAdapter()
        caption_track = {
            "segments": [
                {
                    "x": 0.5,
                    "y": 0.85,
                    "font_size": 20,
                    "line_width": 0.7,
                    "words": [
                        {"text": "Subtitle", "start_sec": 0.0, "end_sec": 2.0}
                    ],
                }
            ]
        }
        adapted = adapter.adapt(
            caption_track,
            source_height=720,
            source_width=1280,
            target_height=1920,
            target_width=1080,
        )
        seg = adapted["segments"][0]
        # Lower-third captions stay in lower third
        assert seg["y"] > 0.7

    def test_srt_export(self):
        from app.shorts.vertical_caption_adapter import export_vertical_srt
        caption_track = {
            "segments": [
                {
                    "x": 0.5,
                    "y": 0.5,
                    "font_size": 24,
                    "words": [
                        {"text": "Hello", "start_sec": 1.5, "end_sec": 2.5}
                    ],
                }
            ]
        }
        srt = export_vertical_srt(caption_track, 1920, 1080)
        assert "Hello" in srt
        assert "-->" in srt


# =============================================================================
# Quality gate
# =============================================================================


class TestShortsQA:
    def test_qa_report_defaults(self):
        qa = ShortsQAReport(
            shorts_id="short_001",
            job_id="job_001",
            output_path="/fake/path.mp4",
        )
        assert qa.passed is False  # Defaults to False
        assert qa.format_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

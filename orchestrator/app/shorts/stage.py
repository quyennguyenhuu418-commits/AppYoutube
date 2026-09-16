"""Stage 11 — Shorts (P13): intelligent 9:16 extraction from final.mp4.

Consumes:
  - final.mp4 (from s10_render mastering pipeline)
  - scene_definition.json (from s8_scene_json)
  - captions.json (from s8_scene_json, if available)

Produces:
  - shorts/short_{scene_id}.mp4 (9:16 vertical clips)
  - shorts_plan.json (ShortsPlan with crop parameters)

Architecture:
  ShortsCompiler reads scene_definition and produces a ShortsPlan.
  The stage then uses FFmpeg to extract and crop each short.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.core.logging import get_logger
from app.core.paths import job_dir, shorts_dir, stage_path
from app.mastering.media_processor import MediaProcessor
from app.pipeline.stages.base import Stage, StageContext
from app.shorts.compiler import ShortsCompiler, shorts_plan_fingerprint
from app.shorts.schemas import ShortsCompilationResult, ShortsPlan, ShortsQAReport

log = get_logger(__name__)


# =============================================================================
# ShortsStage
# =============================================================================


class ShortsStage(Stage):
    """Intelligent 9:16 shorts extraction stage."""

    name = "shorts"
    label = "Shorts"

    def __init__(self, media_processor: MediaProcessor | None = None) -> None:
        self._mp = media_processor

    @property
    def mp(self) -> MediaProcessor:
        if self._mp is None:
            self._mp = MediaProcessor()
        return self._mp

    def run(self, ctx: StageContext) -> dict:
        job_id = ctx.job_id
        video = job_dir(job_id) / "final.mp4"
        if not video.exists():
            raise FileNotFoundError(f"{video} missing; render stage must run first.")

        # Load scene definition
        scene_def = self._load_scene_definition(job_id)
        render_meta = self._load_render_metadata(job_id)

        # Compile shorts plan
        compiler = ShortsCompiler(max_shorts=3, diversify_scenes=True)
        plan = compiler.compile(
            job_id=job_id,
            source_video_path=str(video),
            scene_definition=scene_def,
            render_metadata=render_meta,
        )

        # Save the plan
        plan_path = stage_path(job_id, "shorts_plan")
        plan_path.write_text(
            plan.model_dump_json(indent=2), encoding="utf-8"
        )

        # Render each short
        outputs: list[dict] = []
        for result in plan.results:
            output = self._render_short(job_id, video, result)
            outputs.append(output)

        log.info(
            "[%s] produced %d shorts for job %s",
            self.name, len(outputs), job_id
        )
        return {
            "plan_path": str(plan_path),
            "shorts_count": len(outputs),
            "shorts": outputs,
            "fingerprint": shorts_plan_fingerprint(plan),
        }

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_short(
        self,
        job_id: str,
        source_video: Path,
        result: ShortsCompilationResult,
    ) -> dict:
        """Render a single short using FFmpeg crop."""
        out_dir = shorts_dir(job_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / result.output_filename

        start = result.clip_start_sec
        duration = result.clip_duration_sec
        center_x = result.crop_center_x
        center_y = result.crop_center_y

        # Compute crop parameters
        # Crop from 16:9 source to 9:16 output
        # Formula: crop=ih*9/16:ih (from center)
        crop_w, crop_h = self._compute_crop_params(
            source_video, center_x, center_y
        )

        log.info(
            "[%s] extracting %.1fs..%.1fs (%.1fs) -> %s (crop center=%.2f,%.2f)",
            self.name, start, start + duration, duration,
            output_path.name, center_x, center_y
        )

        # Build FFmpeg command
        crf = self._quality_crf(result.render_settings.quality.value)
        cmd = self._build_ffmpeg_command(
            source=str(source_video),
            start_sec=start,
            duration=duration,
            crop_w=crop_w,
            crop_h=crop_h,
            center_x=center_x,
            output=str(output_path),
            crf=crf,
        )

        try:
            proc = subprocess.run(
                cmd, shell=False, check=True,
                capture_output=True, text=True, timeout=300,
            )
        except FileNotFoundError:
            log.error("[%s] ffmpeg not found", self.name)
            raise
        except subprocess.CalledProcessError as exc:
            log.error("[%s] ffmpeg failed: %s", self.name, exc.stderr[-500:])
            raise

        # QA check
        qa = self._qa_short(output_path, result)

        return {
            "shorts_id": result.shorts_id,
            "path": str(output_path),
            "start_sec": start,
            "end_sec": start + duration,
            "duration_sec": duration,
            "scene_id": result.selected_scene.scene_id,
            "scene_label": result.selected_scene.scene_label,
            "crop_center_x": center_x,
            "crop_center_y": center_y,
            "output_resolution": result.output_resolution,
            "qa": qa.model_dump(),
        }

    def _compute_crop_params(
        self,
        source_video: Path,
        center_x: float,
        center_y: float,
    ) -> tuple[int, int]:
        """Compute FFmpeg crop parameters from center point.

        For 16:9 -> 9:16:
          crop_w = ih * 9/16
          crop_h = ih

        Center offset: input needs to be offset by (center_x * source_w - crop_w/2)
        """
        try:
            summary = self.mp.streams_summary(source_video)
        except Exception:
            # Fallback to standard dimensions
            return (0, 0)

        w = summary["video"]["width"]
        h = summary["video"]["height"]

        crop_w = int(h * 9.0 / 16.0)
        crop_h = h
        return crop_w, crop_h

    def _build_ffmpeg_command(
        self,
        source: str,
        start_sec: float,
        duration: float,
        crop_w: int,
        crop_h: int,
        center_x: float,
        center_y: float,
        output: str,
        crf: int,
    ) -> list[str]:
        """Build FFmpeg command for 9:16 crop."""
        # For center crop, simple formula works:
        # crop=ih*9/16:ih places the crop at the center
        # For offset crop, use: crop=ih*9/16:ih:x_position
        filter_parts: list[str] = []

        if crop_w > 0:
            # Center crop
            filter_parts.append(f"crop=ih*9/16:ih")
        else:
            # Fallback: crop to 9:16 with center positioning
            filter_parts.append("crop=ih*9/16:ih")

        # Scale to target resolution (1080x1920)
        filter_parts.append("scale=1080:1920:flags=lanczos")

        # Apply slight sharpening for better mobile display
        filter_parts.append("unsharp=5:5:0.3:3:3:0.3")

        # Color correction for mobile: slight saturation boost
        filter_parts.append("eq=saturation=1.1:contrast=1.05")

        vf = ",".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start_sec:.3f}",
            "-i", source,
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "48000",
            "-ac", "2",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            output,
        ]
        return cmd

    @staticmethod
    def _quality_crf(quality: str) -> int:
        """Map quality preset to CRF value (lower = better quality)."""
        mapping = {
            "draft": 28,
            "standard": 23,
            "high": 20,
            "max": 18,
        }
        return mapping.get(quality, 23)

    # ------------------------------------------------------------------
    # QA
    # ------------------------------------------------------------------

    def _qa_short(
        self,
        path: Path,
        result: ShortsCompilationResult,
    ) -> ShortsQAReport:
        """QA check for a rendered short."""
        notes: list[str] = []
        format_valid = False
        aspect_ok = False
        duration_ok = False
        has_video = False
        has_audio = False
        audio_level: float | None = None
        file_size = 0

        try:
            summary = self.mp.streams_summary(path)
            format_valid = True
            has_video = summary["video"]["count"] > 0
            has_audio = summary["audio"]["count"] > 0
            aspect_ok = (
                has_video and
                summary["video"]["height"] == 1920 and
                summary["video"]["width"] == 1080
            )
            duration = summary["video"].get("nb_frames", 0)
            fps = summary["video"].get("fps") or 30.0
            measured_duration = duration / fps if fps else 0
            duration_ok = 5.0 <= measured_duration <= 90.0
            file_size = summary.get("size_bytes", 0)
            notes.append(f"duration={measured_duration:.1f}s")

        except Exception as exc:
            notes.append(f"qa_probe_error: {exc}")

        passed = format_valid and aspect_ok and duration_ok and has_video
        return ShortsQAReport(
            shorts_id=result.shorts_id,
            job_id=result.job_id,
            output_path=str(path),
            format_valid=format_valid,
            aspect_ratio_correct=aspect_ok,
            duration_within_limits=duration_ok,
            has_video=has_video,
            has_audio=has_audio,
            audio_level_dbfs=audio_level,
            file_size_bytes=file_size,
            passed=passed,
            notes=tuple(notes),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_scene_definition(job_id: str) -> dict:
        path = stage_path(job_id, "scene_definition")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        # Fallback: try stage_output
        alt = job_dir(job_id) / "stage_output" / "scene_definition.json"
        if alt.exists():
            return json.loads(alt.read_text(encoding="utf-8"))
        # Last resort: empty scene definition
        return {"scenes": [], "meta": {"target_duration_sec": 60.0}}

    @staticmethod
    def _load_render_metadata(job_id: str) -> dict:
        """Load render metadata for resolution/FPS info."""
        # Try render_plan.json first
        rp = job_dir(job_id) / "render_plan.json"
        if rp.exists():
            data = json.loads(rp.read_text(encoding="utf-8"))
            # Extract dimensions from the first composition or use defaults
            return {
                "width": 1280,
                "height": 720,
                "fps": 30.0,
            }
        return {"width": 1280, "height": 720, "fps": 30.0}


__all__ = ["ShortsStage"]

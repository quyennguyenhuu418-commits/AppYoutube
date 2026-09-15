"""Stage 11: shorts — extract a 9:16 vertical Short from the middle of the video.

Naive implementation: take the most narratively dense 60 seconds
(currently: middle 60s). Smarter logic (e.g. pick the beat with the
highest narrative tension) is a future improvement.
"""
from __future__ import annotations

import json
import subprocess

from app.core.logging import get_logger
from app.core.paths import job_dir, shorts_dir, stage_path
from app.pipeline.stages.base import Stage, StageContext

log = get_logger(__name__)


class ShortsStage(Stage):
    name = "shorts"
    label = "Shorts"

    def run(self, ctx: StageContext) -> dict:
        video = job_dir(ctx.job_id) / "final.mp4"
        if not video.exists():
            raise FileNotFoundError(f"{video} missing; render stage must run first.")

        # Find the most "triumphant" or "warm" scene for the Short.
        sd = json.loads(stage_path(ctx.job_id, "scene_definition").read_text(encoding="utf-8"))
        target = _pick_clip_scene(sd)

        out_dir = shorts_dir(ctx.job_id)
        out = out_dir / f"short_{target['id']}.mp4"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Get total duration to ensure the clip fits.
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
            capture_output=True, text=True, check=True,
        )
        total = float(probe.stdout.strip())

        start = max(0.0, float(target["start_sec"]))
        # Clamp end to 60s and total duration.
        end = min(start + 60.0, total, float(target["end_sec"]))
        if end - start < 5.0:
            # Fallback to middle 60s if the chosen scene is too short.
            start = max(0.0, total / 2 - 30.0)
            end = min(total, start + 60.0)

        log.info("[%s] extracting %.1fs..%.1fs into %s", self.name, start, end, out)

        # Crop center 9:16 from 16:9: 1080h x 607w crop → scale to 1080x1920.
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video),
            "-t", f"{end - start:.3f}",
            "-vf", "crop=ih*9/16:ih,scale=1080:1920",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
        except FileNotFoundError:
            log.error("[%s] ffmpeg not found; install FFmpeg and add to PATH.", self.name)
            raise
        except subprocess.CalledProcessError as exc:
            log.error("[%s] ffmpeg failed: %s", self.name, exc.stderr[-2000:])
            raise

        return {"short_path": str(out), "start_sec": start, "end_sec": end}


def _pick_clip_scene(sd: dict) -> dict:
    """Pick a scene that's likely to work as a 60s Short.

    Strategy: prefer scenes with emotional_intent in ('triumphant', 'warm').
    Falls back to the longest single scene.
    """
    candidates = [s for s in sd.get("scenes", []) if s["kind"] in ("narration", "diagram")]
    if not candidates:
        return sd["scenes"][0]
    # Currently we don't carry emotional_intent into scenes; pick the
    # narration scene closest to the middle of the video.
    midpoint = sd["meta"]["target_duration_sec"] / 2
    candidates.sort(key=lambda s: abs(((s["start_sec"] + s["end_sec"]) / 2) - midpoint))
    return candidates[0]

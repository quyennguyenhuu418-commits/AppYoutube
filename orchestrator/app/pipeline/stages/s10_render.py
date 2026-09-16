"""
Stage 10: render — invokes the Node/Remotion renderer as a subprocess, then
passes the raw output through the P11 MasteringPipeline to produce the
canonical final.mp4.

Single canonical render path (PROMPT 12 §17):
  s10_render
      ↓
  Remotion (raw.mp4)
      ↓
  MasteringPipeline (skip_renderer=True)
      ↓
  audio mix → master → mux → QA → atomic finalize
      ↓
  final.mp4 (only after QA passes)

Note: in production, the RenderOrchestrator drives the full pipeline.
In the 11-stage pipeline, this stage now produces the final.mp4 through
the MasteringPipeline. If raw.mp4 is already present (cached), mastering
is still re-run to produce a fresh final.mp4.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import job_dir
from app.mastering.media_processor import MediaProcessor
from app.mastering.pipeline import MasteringPipeline
from app.mastering.qa import MediaQAEngine
from app.mastering.schemas import MasteringProfile, RenderProfile
from app.pipeline.stages.base import Stage, StageContext

log = get_logger(__name__)

# Default profiles — production would get these from the orchestrator
_DEFAULT_RENDER_PROFILE = RenderProfile(
    profile_id="rp_pipeline_default",
    profile_version=1,
    width=1280,
    height=720,
    fps=30.0,
)


def _get_renderer_version() -> str:
    import json

    try:
        pkg = settings.renderer_path / "package.json"
        if pkg.exists():
            ver = json.loads(pkg.read_text(encoding="utf-8")).get("version", "unknown")
            return f"remotion-{ver}"
    except Exception:
        pass
    return "remotion-unknown"


def _get_ffmpeg_version() -> str:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10,
        )
        ver = proc.stdout.split("\n")[0].strip().split()[-1] if proc.stdout else "unknown"
        return f"ffmpeg-{ver}"
    except Exception:
        return "ffmpeg-unknown"


class RenderStage(Stage):
    name = "render"
    label = "Render"

    def run(self, ctx: StageContext) -> dict:
        jd = job_dir(ctx.job_id)
        out = jd / "final.mp4"

        # ── Step 1: Remotion render (raw.mp4) ────────────────────────
        raw = jd / "raw.mp4"
        if raw.exists() and raw.stat().st_size > 0:
            log.info("[%s] raw.mp4 cached, skipping Remotion", self.name)
        else:
            cmd_parts = settings.renderer_entry.split()
            cmd = [*cmd_parts, ctx.job_id]
            cwd = settings.renderer_path
            log.info("[%s] running: %s (cwd=%s)", self.name, " ".join(cmd), cwd)
            try:
                proc = subprocess.run(
                    cmd, cwd=str(cwd), check=True, capture_output=True, text=True, timeout=900,
                )
            except subprocess.CalledProcessError as exc:
                log.error("[%s] renderer exited %d\nstdout: %s\nstderr: %s",
                          self.name, exc.returncode, exc.stdout[-2000:], exc.stderr[-2000:])
                raise
            except subprocess.TimeoutExpired:
                log.error("[%s] renderer timed out after 15 minutes", self.name)
                raise RuntimeError("Renderer timed out") from None
            except FileNotFoundError as exc:
                log.error("[%s] renderer not found: %s", self.name, exc)
                raise
            log.info("[%s] renderer done. tail: %s", self.name, proc.stdout[-500:])
            if not raw.exists():
                raise RuntimeError(
                    f"Renderer finished but {raw} not produced. "
                    "See renderer stdout for details."
                )

        # ── Step 2: MasteringPipeline (skip Remotion — raw.mp4 ready) ──
        log.info("[%s] running MasteringPipeline on raw.mp4", self.name)
        processor = MediaProcessor()
        qa_engine = MediaQAEngine(processor=processor)
        pipeline = MasteringPipeline(processor=processor, qa_engine=qa_engine)

        renderer_ver = _get_renderer_version()
        ffmpeg_ver = _get_ffmpeg_version()
        render_profile = _DEFAULT_RENDER_PROFILE
        mastering_profile = MasteringProfile(profile_id="mp_pipeline_default", profile_version=1)

        # RenderPlan already written by previous stages or minimal smoke
        render_plan_path = jd / "render_plan.json"
        render_plan_dict = {}
        if render_plan_path.exists():
            import json as _json

            render_plan_dict = _json.loads(render_plan_path.read_text(encoding="utf-8"))

        # Load RenderPlan from editorial schemas (same model MasteringPipeline expects)
        from app.editorial.schemas import RenderPlan as EditorialRenderPlan

        plan_obj = None
        if render_plan_dict:
            try:
                plan_obj = EditorialRenderPlan.model_validate(render_plan_dict)
            except Exception:
                pass

        # Run mastering pipeline (skip renderer since raw.mp4 exists)
        pipeline_result = pipeline.run_full_pipeline(
            job_dir=jd,
            render_plan_path=render_plan_path,
            render_plan=plan_obj or render_plan_dict,
            render_profile=render_profile,
            mastering_profile=mastering_profile,
            audio_artifact_paths={},  # no audio clips in pipeline render
            renderer_version=f"{renderer_ver}/{ffmpeg_ver}",
            source_fingerprint=render_plan_dict.get("fingerprint", f"plan-{ctx.job_id}"),
            skip_renderer=True,  # raw.mp4 already produced above
        )

        if not pipeline_result.success:
            raise RuntimeError(
                f"MasteringPipeline failed: {pipeline_result.error}\n" +
                "\n".join(pipeline_result.log[-10:])
            )

        if not out.exists():
            raise RuntimeError(
                f"MasteringPipeline succeeded but {out} not produced."
            )

        log.info("[%s] final.mp4 ready at %s (%d bytes)",
                 self.name, out, out.stat().st_size)

        return {"video_path": str(out), "raw_path": str(raw)}


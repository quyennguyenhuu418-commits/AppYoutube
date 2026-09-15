"""Stage 10: render — invokes the Node/Remotion renderer as a subprocess."""
from __future__ import annotations

import subprocess

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import job_dir
from app.pipeline.stages.base import Stage, StageContext

log = get_logger(__name__)


class RenderStage(Stage):
    name = "render"
    label = "Render"

    def run(self, ctx: StageContext) -> dict:
        out = job_dir(ctx.job_id) / "final.mp4"
        if out.exists() and out.stat().st_size > 0:
            log.info("[%s] cached, skipping", self.name)
            return {"video_path": str(out)}

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
            log.error("[%s] renderer not found: %s (is Node/npm installed?)", self.name, exc)
            raise

        log.info("[%s] renderer done. tail: %s", self.name, proc.stdout[-500:])
        if not out.exists():
            raise RuntimeError(
                f"Renderer finished but {out} not produced. See renderer stdout for details."
            )
        return {"video_path": str(out)}

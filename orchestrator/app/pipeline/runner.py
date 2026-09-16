"""
Pipeline runner — orchestrates the 11 stages for a single job.

The MVP runs synchronously in the FastAPI process (no Celery). For larger
deployments, wrap `run_job` in a Celery task — the stage code is already
pure and side-effect-bounded.
"""
from __future__ import annotations

from datetime import datetime

from app.core.logging import get_logger
from app.db import store
from app.pipeline.stages.base import StageContext
from app.pipeline.stages.s1_research import ResearchStage
from app.pipeline.stages.s2_thesis import ThesisStage
from app.pipeline.stages.s3_titles import TitlesStage
from app.pipeline.stages.s4_script import ScriptStage
from app.pipeline.stages.s5_storyboard import StoryboardStage
from app.pipeline.stages.s6_assets import AssetsStage
from app.pipeline.stages.s6b_video_assets import VideoAssetsStage
from app.pipeline.stages.s7_narration import NarrationStage
from app.pipeline.stages.s8_scene_json import SceneJsonStage
from app.pipeline.stages.s9_validate import ValidateStage
from app.pipeline.stages.s10_render import RenderStage
from app.pipeline.stages.s11_short import ShortsStage
from app.publishing.stage import PublishingStage
from app.thumbnail.stage import ThumbnailStage
from app.schemas.job import JobDetail, StageInfo, StageStatus

log = get_logger(__name__)

# Ordered list — order matters because later stages depend on earlier outputs.
STAGES = [
    ResearchStage(),
    ThesisStage(),
    TitlesStage(),
    ScriptStage(),
    StoryboardStage(),
    AssetsStage(),
    VideoAssetsStage(),       # Optional: AI B-roll video (no-op nếu không bật)
    NarrationStage(),
    SceneJsonStage(),
    ValidateStage(),
    RenderStage(),
    ShortsStage(),
    ThumbnailStage(),
    PublishingStage(),
]


def run_job(detail: JobDetail) -> None:
    """Run the full pipeline for a job. Updates job state on disk as it goes.

    Designed to be safe to retry: each stage writes its own output file
    and the cache layer skips completed stages on the next run.
    """
    ctx = StageContext(job_id=detail.id, topic=detail.topic, state={})
    store.mark_running(detail.id)
    log.info("[runner] starting job %s topic=%s", detail.id, detail.topic)

    for stage in STAGES:
        info = StageInfo(name=stage.name, label=stage.label, status=StageStatus.RUNNING,
                         started_at=datetime.utcnow())
        store.update_stage_sync(detail.id, info)
        try:
            out = stage.run(ctx)
        except Exception as exc:  # noqa: BLE001 — we want to capture everything
            log.exception("[runner] stage %s failed", stage.name)
            info.status = StageStatus.FAILED
            info.finished_at = datetime.utcnow()
            info.error = f"{type(exc).__name__}: {exc}"
            store.update_stage_sync(detail.id, info)
            store.mark_failed(detail.id, info.error)
            return

        ctx.state[stage.name] = out
        info.status = StageStatus.COMPLETED
        info.finished_at = datetime.utcnow()
        store.update_stage_sync(detail.id, info)
        log.info("[runner] stage %s done", stage.name)

    # Pick the chosen title to surface in the job summary.
    chosen_title = None
    if "titles" in ctx.state:
        titles = ctx.state["titles"]
        chosen_title = titles["candidates"][titles["chosen_index"]]["title"]
    store.mark_completed(detail.id, chosen_title)
    log.info("[runner] job %s completed", detail.id)

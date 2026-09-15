"""
JSON-file-backed job store.

Each job is persisted as `workspace/<job_id>/job.json`. This is a
deliberately simple store so the MVP runs without a database. The public
API is async-friendly (returns Pydantic models) so swapping in a real DB
later is a contained change.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from app.core.config import settings
from app.core.paths import job_dir, read_json, write_json
from app.schemas.job import JobCreateRequest, JobDetail, JobStatus, StageInfo, StageStatus


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def create_job(req: JobCreateRequest) -> JobDetail:
    job_id = str(uuid.uuid4())
    jd = job_dir(job_id)
    detail = JobDetail(
        id=job_id,
        topic=req.topic,
        title=req.title_hint,
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
        stages=[],
        artifacts={},
    )
    write_json(jd / "job.json", detail.model_dump(mode="json"))
    return detail


def load_job(job_id: str) -> JobDetail | None:
    path = job_dir(job_id) / "job.json"
    if not path.exists():
        return None
    raw = read_json(path)
    return JobDetail.model_validate(raw)


def save_job(detail: JobDetail) -> None:
    write_json(job_dir(detail.id) / "job.json", detail.model_dump(mode="json"))


def list_jobs() -> list[JobDetail]:
    ws = settings.workspace_path
    if not ws.exists():
        return []
    out: list[JobDetail] = []
    for child in ws.iterdir():
        if not child.is_dir():
            continue
        jp = child / "job.json"
        if not jp.exists():
            continue
        try:
            out.append(JobDetail.model_validate(read_json(jp)))
        except Exception:
            continue
    out.sort(key=lambda j: j.created_at, reverse=True)
    return out


# ---- Stage updates ----

async def update_stage(job_id: str, stage: StageInfo) -> None:
    """Persist a stage status change.

    File I/O is sync under the hood; we wrap with `asyncio.to_thread` so
    the API handler doesn't block on disk writes.
    """
    def _sync() -> None:
        detail = load_job(job_id)
        if detail is None:
            return
        # Replace-or-insert by name.
        idx = next((i for i, s in enumerate(detail.stages) if s.name == stage.name), None)
        if idx is None:
            detail.stages.append(stage)
        else:
            detail.stages[idx] = stage
        save_job(detail)

    await asyncio.to_thread(_sync)


def update_stage_sync(job_id: str, stage: StageInfo) -> None:
    """Synchronous version for use inside the pipeline runner thread."""
    detail = load_job(job_id)
    if detail is None:
        return
    idx = next((i for i, s in enumerate(detail.stages) if s.name == stage.name), None)
    if idx is None:
        detail.stages.append(stage)
    else:
        detail.stages[idx] = stage
    save_job(detail)


def mark_running(job_id: str) -> None:
    detail = load_job(job_id)
    if detail is None:
        return
    detail.status = JobStatus.RUNNING
    save_job(detail)


def mark_completed(job_id: str, title: str | None = None) -> None:
    detail = load_job(job_id)
    if detail is None:
        return
    detail.status = JobStatus.COMPLETED
    detail.finished_at = datetime.utcnow()
    if title:
        detail.title = title
    save_job(detail)


def mark_failed(job_id: str, error: str) -> None:
    detail = load_job(job_id)
    if detail is None:
        return
    detail.status = JobStatus.FAILED
    detail.finished_at = datetime.utcnow()
    detail.error = error
    save_job(detail)

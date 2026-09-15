"""Jobs API: create, list, fetch, and inspect jobs."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.db import store
from app.pipeline.runner import run_job
from app.schemas.job import JobCreateRequest, JobDetail, JobSummary

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobDetail, status_code=201)
async def create_job(req: JobCreateRequest, background: BackgroundTasks) -> JobDetail:
    detail = store.create_job(req)
    # Run the pipeline in the background so the HTTP request returns immediately.
    background.add_task(_run_in_thread, detail.model_dump())
    return detail


def _run_in_thread(detail_dict: dict) -> None:
    detail = JobDetail.model_validate(detail_dict)
    try:
        run_job(detail)
    except Exception:
        # runner.py already writes failure state; this is the safety net.
        pass


@router.get("", response_model=list[JobSummary])
def list_jobs() -> list[JobSummary]:
    return [
        JobSummary(
            id=j.id, topic=j.topic, title=j.title, status=j.status,
            created_at=j.created_at, finished_at=j.finished_at, error=j.error,
        )
        for j in store.list_jobs()
    ]


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str) -> JobDetail:
    detail = store.load_job(job_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    # Augment with artifact URLs (relative to API root).
    detail.artifacts = {
        "research": f"/jobs/{job_id}/artifacts/research.json",
        "thesis": f"/jobs/{job_id}/artifacts/thesis.json",
        "titles": f"/jobs/{job_id}/artifacts/titles.json",
        "script": f"/jobs/{job_id}/artifacts/script.json",
        "storyboard": f"/jobs/{job_id}/artifacts/storyboard.json",
        "scene_definition": f"/jobs/{job_id}/artifacts/scene_definition.json",
        "narration_words": f"/jobs/{job_id}/artifacts/narration.words.json",
        "video": f"/jobs/{job_id}/artifacts/final.mp4",
        "shorts_dir": f"/jobs/{job_id}/artifacts/shorts/",
    }
    return detail

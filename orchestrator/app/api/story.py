"""
Story Intelligence API — inspect StoryPackage artifacts.

Provides read access to all story package sections plus human-review
endpoints for approving or rejecting a story.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.core.paths import job_dir, read_json, write_json
from app.schemas.story import StoryPackage, ReviewStatus

log = get_logger(__name__)
router = APIRouter(prefix="/story", tags=["story"])


def _load_package(job_id: str) -> StoryPackage:
    """Load and validate a StoryPackage from disk."""
    path = job_dir(job_id) / "story_package.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Story package not found for job {job_id}")
    return StoryPackage.model_validate(read_json(path))


def _save_package(job_id: str, pkg: StoryPackage) -> None:
    """Persist updated package to disk."""
    path = job_dir(job_id) / "story_package.json"
    write_json(path, pkg.model_dump())


# ---- Endpoints ----

@router.get("/{job_id}/package")
def get_package(job_id: str) -> StoryPackage:
    """Return the full StoryPackage for a job."""
    return _load_package(job_id)


@router.get("/{job_id}/thesis")
def get_thesis(job_id: str):
    """Return thesis selection with candidates."""
    pkg = _load_package(job_id)
    return pkg.thesis


@router.get("/{job_id}/angles")
def get_angles(job_id: str):
    """Return angle selection with candidates."""
    pkg = _load_package(job_id)
    return pkg.angle


@router.get("/{job_id}/titles")
def get_titles(job_id: str):
    """Return title selection with candidates."""
    pkg = _load_package(job_id)
    return pkg.title


@router.get("/{job_id}/script")
def get_script(job_id: str):
    """Return active script version."""
    pkg = _load_package(job_id)
    active = pkg.script.get_active()
    if not active:
        raise HTTPException(status_code=404, detail="No active script version found")
    return active


@router.get("/{job_id}/critique")
def get_critique(job_id: str):
    """Return script critique."""
    pkg = _load_package(job_id)
    if not pkg.critique:
        raise HTTPException(status_code=404, detail="Script critique not yet available")
    return pkg.critique


@router.get("/{job_id}/quality")
def get_quality(job_id: str):
    """Return story quality score."""
    pkg = _load_package(job_id)
    if not pkg.quality_score:
        raise HTTPException(status_code=404, detail="Quality score not yet available")
    return pkg.quality_score


@router.post("/{job_id}/approve")
def approve_story(job_id: str) -> StoryPackage:
    """Approve the story. Sets review_status = APPROVED."""
    pkg = _load_package(job_id)
    pkg.metadata.review_status = ReviewStatus.APPROVED
    _save_package(job_id, pkg)
    log.info("[story] story %s approved", job_id)
    return pkg


@router.post("/{job_id}/reject")
def reject_story(job_id: str, notes: str = "") -> StoryPackage:
    """Reject the story. Sets review_status = REJECTED."""
    pkg = _load_package(job_id)
    pkg.metadata.review_status = ReviewStatus.REJECTED
    # Append reviewer notes if provided
    existing_notes = pkg.thesis.review_notes or ""
    if notes:
        pkg.thesis.review_notes = (existing_notes + "\n" + notes).strip()
    _save_package(job_id, pkg)
    log.info("[story] story %s rejected: %s", job_id, notes or "(no notes)")
    return pkg

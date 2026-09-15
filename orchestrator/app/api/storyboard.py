"""
Storyboard Intelligence API.

Provides read access to the StoryboardPackage plus human-review endpoints
for approving / rejecting / regenerating a storyboard.

Endpoints follow the existing API conventions (no version prefix,
singular path params, see docs/API_CONTRACTS.md).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.core.paths import job_dir, read_json, write_json
from app.schemas.storyboard import StoryboardPackage, StoryboardStatus

log = get_logger(__name__)
router = APIRouter(prefix="/storyboard", tags=["storyboard"])


def _load_package(job_id: str) -> StoryboardPackage:
    """Load and validate the canonical StoryboardPackage from disk."""
    path = job_dir(job_id) / "storyboard_package.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Storyboard package not found for job {job_id}",
        )
    return StoryboardPackage.model_validate(read_json(path))


def _save_package(job_id: str, pkg: StoryboardPackage) -> None:
    """Persist updated package to disk."""
    path = job_dir(job_id) / "storyboard_package.json"
    write_json(path, pkg.to_dict())


# ---- Endpoints ----

@router.get("/{job_id}/package")
def get_package(job_id: str) -> StoryboardPackage:
    """Return the full StoryboardPackage for a job."""
    return _load_package(job_id)


@router.get("/{job_id}/beats")
def get_beats(job_id: str) -> dict:
    """Return just the visual beats."""
    pkg = _load_package(job_id)
    return {"beats": [b.model_dump(mode="json") for b in pkg.visual_beats]}


@router.get("/{job_id}/assets")
def get_assets(job_id: str) -> dict:
    """Return asset requirements."""
    pkg = _load_package(job_id)
    return {"assets": [a.model_dump(mode="json") for a in pkg.asset_requirements]}


@router.get("/{job_id}/quality")
def get_quality(job_id: str) -> dict:
    """Return storyboard quality score."""
    pkg = _load_package(job_id)
    if not pkg.storyboard_quality_score:
        raise HTTPException(
            status_code=404, detail="Storyboard quality score not available"
        )
    return pkg.storyboard_quality_score.model_dump(mode="json")


@router.get("/{job_id}/continuity")
def get_continuity(job_id: str) -> dict:
    """Return continuity state and issues."""
    pkg = _load_package(job_id)
    return {
        "state": pkg.continuity_state.model_dump(mode="json"),
        "issues": [i.model_dump(mode="json") for i in pkg.continuity_issues],
        "updates": [u.model_dump(mode="json") for u in pkg.continuity_updates],
        "dependencies": [
            d.model_dump(mode="json") for d in pkg.continuity_dependencies
        ],
    }


@router.get("/{job_id}/preview")
def get_preview(job_id: str) -> dict:
    """Return a preview summary — beats, quality, asset count."""
    pkg = _load_package(job_id)
    return {
        "storyboard_package_id": pkg.metadata.storyboard_package_id,
        "story_package_id": pkg.story_package_id,
        "status": pkg.status.value,
        "beat_count": len(pkg.visual_beats),
        "scene_candidate_count": len(pkg.scene_definition_candidates),
        "asset_count": len(pkg.asset_requirements),
        "continuity_issue_count": len(pkg.continuity_issues),
        "quality_overall": (
            pkg.storyboard_quality_score.overall_score
            if pkg.storyboard_quality_score
            else 0.0
        ),
        "warnings": pkg.warnings,
        "failures": pkg.failures,
    }


@router.post("/{job_id}/approve")
def approve_storyboard(job_id: str) -> StoryboardPackage:
    """Approve the storyboard. Sets status = APPROVED."""
    pkg = _load_package(job_id)
    pkg.metadata.status = StoryboardStatus.APPROVED
    pkg.status = StoryboardStatus.APPROVED
    pkg.metadata.updated_at = pkg.metadata.updated_at  # no change
    _save_package(job_id, pkg)
    log.info("[storyboard] storyboard %s approved", job_id)
    return pkg


@router.post("/{job_id}/reject")
def reject_storyboard(job_id: str, notes: str = "") -> StoryboardPackage:
    """Reject the storyboard. Sets status = REJECTED and stores notes."""
    pkg = _load_package(job_id)
    pkg.metadata.status = StoryboardStatus.REJECTED
    pkg.status = StoryboardStatus.REJECTED
    if notes:
        pkg.warnings.append(f"REVIEWER: {notes}")
    _save_package(job_id, pkg)
    log.info("[storyboard] storyboard %s rejected: %s", job_id, notes or "(no notes)")
    return pkg


@router.post("/{job_id}/regenerate")
def regenerate_storyboard(job_id: str) -> dict:
    """Mark the storyboard for regeneration.

    This does not run the engine directly (that happens in s5_storyboard).
    It clears any cached storyboard.json so the pipeline will rerun.
    """
    pkg = _load_package(job_id)
    pkg.metadata.status = StoryboardStatus.DRAFT
    pkg.status = StoryboardStatus.DRAFT
    _save_package(job_id, pkg)
    log.info("[storyboard] storyboard %s marked for regeneration", job_id)
    return {"status": "draft", "message": "Storyboard marked for regeneration"}

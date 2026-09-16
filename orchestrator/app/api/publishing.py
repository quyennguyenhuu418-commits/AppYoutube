"""
P15 — FastAPI Publishing API.

Endpoints:
  POST /publishing/preflight  — Validate publishing plan
  POST /publishing/finalize   — Trigger publishing (generates plan)
  GET  /publishing/{job_id}/plan    — Get publishing plan
  GET  /publishing/{job_id}/result — Get publishing result

Security:
  - No credentials stored in API responses
  - No OAuth tokens in logs
  - Platform credentials managed via environment variables
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.paths import job_dir
from app.publishing.metadata_generator import PublishingPlanBuilder
from app.publishing.schemas import Platform, PublishingMetadata, Visibility
from app.publishing.stage import PublishingStage

log = get_logger(__name__)
router = APIRouter(prefix="/publishing", tags=["publishing"])


# ============================================================================
# Safe-id validation
# ============================================================================


def _validate_id(job_id: str) -> str:
    if not re.match(r"^[A-Za-z0-9_-]+$", job_id):
        raise ValueError("Invalid job_id format")
    return job_id


def _to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


# ============================================================================
# Request / Response models
# ============================================================================


class PublishingPreflightRequest(BaseModel):
    job_id: str = Field(max_length=64)
    topic: str = Field(max_length=200)
    title: str = Field(max_length=150)
    description: str = Field(max_length=5000)
    tags: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(
        default_factory=lambda: ["youtube", "tiktok", "facebook"]
    )
    visibility: str = Field(default="public")
    thumbnail_override: str | None = Field(default=None, max_length=512)


class PublishingIssue(BaseModel):
    severity: str  # error | warning
    field: str
    message: str


class PublishingPreflightResponse(BaseModel):
    job_id: str
    status: str  # ok | errors | warnings
    errors: list[PublishingIssue] = Field(default_factory=list)
    warnings: list[PublishingIssue] = Field(default_factory=list)
    plan_id: str | None
    platforms_prepared: list[str]
    video_available: bool
    short_available: bool
    thumbnail_available: bool
    created_at: str


class PublishingFinalizeRequest(BaseModel):
    job_id: str = Field(max_length=64)
    topic: str = Field(max_length=200)
    title: str = Field(max_length=150)
    description: str = Field(max_length=5000)
    tags: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(
        default_factory=lambda: ["youtube", "tiktok", "facebook"]
    )
    visibility: str = Field(default="public")
    auto_publish: bool = Field(
        default=False,
        description="If True, also call platform APIs (requires credentials)"
    )


class PublishingFinalizeResponse(BaseModel):
    job_id: str
    status: str
    plan_id: str | None
    message: str
    platforms: list[str]
    created_at: str


class PlatformResultItem(BaseModel):
    platform: str
    status: str
    url: str | None = None
    error: str | None = None


class PublishingResultResponse(BaseModel):
    job_id: str
    plan_id: str | None
    status: str  # draft | pending | published | failed | partial
    platforms: list[PlatformResultItem]
    all_succeeded: bool
    any_failed: bool
    created_at: str | None


# ============================================================================
# POST /publishing/preflight
# ============================================================================


@router.post("/preflight", response_model=PublishingPreflightResponse)
async def publishing_preflight(req: PublishingPreflightRequest) -> PublishingPreflightResponse:
    """Validate publishing plan before submission."""
    try:
        job_id = _validate_id(req.job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    issues: list[PublishingIssue] = []
    warnings: list[PublishingIssue] = []

    # Validate platforms
    valid_platforms = {"youtube", "tiktok", "facebook"}
    requested = set(req.platforms)
    invalid = requested - valid_platforms
    if invalid:
        issues.append(PublishingIssue(
            severity="error",
            field="platforms",
            message=f"Unknown platforms: {invalid}",
        ))
    requested = requested & valid_platforms

    # Validate title lengths per platform
    for platform in requested:
        if platform == "tiktok" and len(req.title) > 150:
            issues.append(PublishingIssue(
                severity="error",
                field="title",
                message=f"TikTok title too long ({len(req.title)} > 150)",
            ))
        elif platform == "youtube" and len(req.title) > 100:
            issues.append(PublishingIssue(
                severity="warning",
                field="title",
                message=f"YouTube title > 100 chars; will be truncated",
            ))

    # Validate description
    if len(req.description) > 5000:
        warnings.append(PublishingIssue(
            severity="warning",
            field="description",
            message=f"YouTube description > 5000 chars; will be truncated",
        ))

    # Check available content
    jd = job_dir(job_id)
    video_available = (jd / "final.mp4").exists()
    short_available = (jd / "shorts").exists()
    thumbnail_available = (jd / "thumbnails").exists()

    if not video_available:
        warnings.append(PublishingIssue(
            severity="warning",
            field="video",
            message="final.mp4 not found; full video may not be publishable",
        ))

    # Validate visibility
    valid_visibilities = {"public", "unlisted", "private"}
    if req.visibility not in valid_visibilities:
        issues.append(PublishingIssue(
            severity="error",
            field="visibility",
            message=f"Invalid visibility: {req.visibility}",
        ))

    errors = [i for i in issues if i.severity == "error"]
    all_warnings = warnings + [i for i in issues if i.severity == "warning"]

    return PublishingPreflightResponse(
        job_id=job_id,
        status="ok" if not errors else "errors",
        errors=errors,
        warnings=all_warnings,
        plan_id=f"publish_{job_id}" if not errors else None,
        platforms_prepared=list(requested),
        video_available=video_available,
        short_available=short_available,
        thumbnail_available=thumbnail_available,
        created_at=_to_iso(datetime.now(timezone.utc)) or "",
    )


# ============================================================================
# POST /publishing/finalize
# ============================================================================


@router.post("/finalize", response_model=PublishingFinalizeResponse)
async def publishing_finalize(req: PublishingFinalizeRequest) -> PublishingFinalizeResponse:
    """Generate publishing plan (and optionally publish to platforms)."""
    try:
        job_id = _validate_id(req.job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    # Validate platforms
    valid_platforms = {"youtube", "tiktok", "facebook"}
    requested = set(req.platforms)
    invalid = requested - valid_platforms
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown platforms: {invalid}",
        )
    requested = requested & valid_platforms

    # Validate visibility
    valid_visibilities = {"public", "unlisted", "private"}
    if req.visibility not in valid_visibilities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid visibility: {req.visibility}",
        )

    # Build plan using PublishingStage logic
    stage = PublishingStage()
    result = stage.run(type("Ctx", (), {"job_id": job_id})())

    # Map to response
    status = "draft"
    if req.auto_publish:
        # Check credentials
        if not _has_any_credentials():
            log.warning("[publishing] auto_publish=True but no credentials found")
            status = "draft"
        else:
            status = "pending"

    return PublishingFinalizeResponse(
        job_id=job_id,
        status=status,
        plan_id=result.get("plan_path", f"publish_{job_id}"),
        message=_finalize_message(status, req.auto_publish),
        platforms=list(requested),
        created_at=_to_iso(datetime.now(timezone.utc)) or "",
    )


# ============================================================================
# GET /publishing/{job_id}/plan
# ============================================================================


@router.get("/{job_id}/plan")
async def get_publishing_plan(job_id: str) -> dict:
    """Return the publishing plan JSON for a job."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    plan_path = jd / "publishing_plan.json"

    if not plan_path.exists():
        # Try stage path
        alt = jd / "stage_output" / "publishing_plan.json"
        if alt.exists():
            return json.loads(alt.read_text(encoding="utf-8"))
        raise HTTPException(
            status_code=404,
            detail=f"Publishing plan not found for job {job_id}",
        )

    import json
    return json.loads(plan_path.read_text(encoding="utf-8"))


# ============================================================================
# GET /publishing/{job_id}/result
# ============================================================================


@router.get("/{job_id}/result")
async def get_publishing_result(job_id: str) -> dict:
    """Return the publishing result for a job."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    result_path = jd / "publishing_result.json"

    if not result_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Publishing result not found for job {job_id}. "
                   "Run publishing/finalize first.",
        )

    import json
    return json.loads(result_path.read_text(encoding="utf-8"))


# ============================================================================
# Helpers
# ============================================================================


def _has_any_credentials() -> bool:
    """Check if any platform credentials are available."""
    import os
    return any([
        os.getenv("YOUTUBE_API_KEY"),
        os.getenv("YOUTUBE_CLIENT_ID"),
        os.getenv("TIKTOK_CLIENT_KEY"),
        os.getenv("TIKTOK_ACCESS_TOKEN"),
        os.getenv("FACEBOOK_ACCESS_TOKEN"),
    ])


def _finalize_message(status: str, auto_publish: bool) -> str:
    if status == "pending":
        return "Publishing plan created. Platforms queued for publishing."
    elif auto_publish and status == "draft":
        return "Publishing plan created (draft). Auto-publish skipped: no credentials configured."
    else:
        return "Publishing plan created. Call platform APIs to publish."


__all__ = ["router"]

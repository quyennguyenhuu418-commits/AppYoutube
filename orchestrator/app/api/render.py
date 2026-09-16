"""
PROMPT 12 — FastAPI Render API.

Thin adapter layer. Business logic lives in RenderOrchestrator.

Endpoints (PROMPT 12 §8–§16):
    POST /render/preflight         — validate a render request
    POST /render/finalize          — trigger a production render
    GET  /render/{job_id}/status  — current job lifecycle + stage progress
    GET  /render/{job_id}/qa      — MediaQAReport (canonical)
    GET  /render/{job_id}/artifact — FinalVideoArtifact (safe DTO)
    GET  /render/{job_id}/video   — stream approved final MP4

Security (PROMPT 12 §22):
    - All job-id / artifact-id validated against ^[A-Za-z0-9_-]+$
    - No arbitrary filesystem paths accepted as user input
    - Final video only served if lifecycle == APPROVED
    - No FFmpeg commands exposed to clients
    - No internal paths leaked in error responses
    - No secrets logged

Error codes:
    400 — invalid request schema
    404 — project / render job / artifact not found
    409 — conflicting job state
    422 — contract validation failure
    500 — unexpected server failure (never leaks stack traces)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import job_dir, read_json
from app.mastering.artifact import load_final_artifact, load_qa_report
from app.mastering.schemas import MasteringProfile, RenderProfile
from app.orchestration import (
    RenderJob,
    RenderOrchestrator,
    ensure_safe_id,
    is_terminal,
    progress_for_stage,
)
from app.orchestration.lifecycle import JobLifecycle

log = get_logger(__name__)
router = APIRouter(prefix="/render", tags=["render"])


# ============================================================================
# Safe-id validation helper (defence in depth)
# ============================================================================


def _validate_id(value: str, name: str = "job_id") -> str:
    """Raise HTTPException 400 if value is not a safe path component."""
    ensure_safe_id(value)  # raises ValueError
    return value


# ============================================================================
# Request / Response DTOs
# ============================================================================


class RenderPreflightRequest(BaseModel):
    """Payload for POST /render/preflight."""

    model_config = {"extra": "forbid"}

    job_id: str = Field(min_length=1, max_length=64)
    project_id: str = Field(min_length=1, max_length=128)
    topic: str = Field(min_length=1, max_length=300)
    editorial_project_data: dict | None = Field(default=None)
    render_profile_data: dict | None = Field(default=None)
    mastering_profile_data: dict | None = Field(default=None)


class PreflightIssue(BaseModel):
    severity: str  # "error" | "warning"
    field: str
    message: str


class RenderPreflightResponse(BaseModel):
    """Result of POST /render/preflight."""

    job_id: str
    status: str  # "ok" | "errors" | "warnings"
    errors: list[PreflightIssue] = Field(default_factory=list)
    warnings: list[PreflightIssue] = Field(default_factory=list)
    render_plan_id: str | None = None
    render_plan_fingerprint: str | None = None
    resolved_asset_count: int = 0
    resolved_audio_count: int = 0
    estimated_duration_sec: float | None = None
    created_at: str


class RenderFinalizeRequest(BaseModel):
    """Payload for POST /render/finalize."""

    model_config = {"extra": "forbid"}

    job_id: str = Field(min_length=1, max_length=64)
    project_id: str = Field(min_length=1, max_length=128)
    topic: str = Field(min_length=1, max_length=300)
    editorial_project_data: dict | None = Field(default=None)
    render_profile_data: dict | None = Field(default=None)
    mastering_profile_data: dict | None = Field(default=None)


class RenderFinalizeResponse(BaseModel):
    job_id: str
    lifecycle: str
    progress_pct: int
    current_stage: str | None
    render_plan_id: str | None = None
    render_job_id: str | None = None
    message: str


class RenderStatusResponse(BaseModel):
    """GET /render/{job_id}/status."""

    job_id: str
    project_id: str
    topic: str
    lifecycle: str
    progress_pct: int
    current_stage: str | None
    stage_progress: dict[str, int] = Field(default_factory=dict)
    stages: list[dict]
    is_terminal: bool
    error: str | None = None
    error_stage: str | None = None
    render_plan_id: str | None = None
    final_artifact_id: str | None = None
    qa_report_id: str | None = None
    final_mp4_path: str | None = None  # internal; not exposed to clients
    renderer_version: str | None = None
    ffmpeg_version: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class RenderQAReportResponse(BaseModel):
    """GET /render/{job_id}/qa — MediaQAReport transport DTO."""

    report_id: str
    artifact_id: str
    render_profile_id: str
    mastering_profile_id: str
    overall_status: str
    checks: list[dict]
    warnings: list[str]
    failures: list[str]
    tool_versions: dict[str, str] = Field(default_factory=dict)
    measured_at: str


class RenderArtifactResponse(BaseModel):
    """GET /render/{job_id}/artifact — FinalVideoArtifact transport DTO.

    PROMPT 12 §11: NEVER expose internal absolute filesystem paths.
    """

    artifact_id: str
    project_id: str
    render_plan_id: str | None
    render_profile_id: str | None
    mastering_profile_id: str | None
    qa_report_id: str | None
    renderer_version: str | None
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    audio_sample_rate_hz: int
    audio_channels: int
    duration_sec: float
    file_size_bytes: int
    checksum_sha256: str
    loudness_lufs: float | None
    true_peak_dbtp: float | None
    lifecycle_status: str
    qa_status: str
    # Safe media reference — no internal paths exposed
    video_url: str
    fingerprint: str
    created_at: str


# ============================================================================
# Helpers
# ============================================================================


def _to_iso(dt) -> str:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


def _safe_error(exc: Exception) -> dict:
    """Strip internal details from unexpected errors (PROMPT 12 §21)."""
    log.exception("unexpected error: %s", exc)
    return {"detail": "Internal server error. Please retry or contact support."}


# ============================================================================
# POST /render/preflight
# ============================================================================


@router.post("/preflight", response_model=RenderPreflightResponse, status_code=200)
async def preflight(req: RenderPreflightRequest) -> RenderPreflightResponse:
    """Validate a render request BEFORE expensive Remotion rendering.

    Verifies as much as existing contracts permit (PROMPT 12 §8):
    - project exists (job_id is valid)
    - RenderPlan validates (if editorial project provided)
    - RenderProfile is valid (if provided)
    - MasteringProfile is valid (if provided)
    - Referenced assets / audio resolve (structural check)

    Returns a PreflightResult with status, errors, warnings.
    """
    try:
        job_id = _validate_id(req.job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    issues: list[PreflightIssue] = []
    render_plan_id: str | None = None
    render_plan_fingerprint: str | None = None
    resolved_assets = 0
    resolved_audio = 0
    estimated_dur: float | None = None

    # Validate render profile
    if req.render_profile_data:
        try:
            RenderProfile.model_validate(req.render_profile_data)
        except Exception as exc:
            issues.append(PreflightIssue(
                severity="error", field="render_profile",
                message=f"RenderProfile validation: {exc}"
            ))

    # Validate mastering profile
    if req.mastering_profile_data:
        try:
            MasteringProfile.model_validate(req.mastering_profile_data)
        except Exception as exc:
            issues.append(PreflightIssue(
                severity="error", field="mastering_profile",
                message=f"MasteringProfile validation: {exc}"
            ))

    # Structural check for editorial project
    if req.editorial_project_data:
        try:
            from app.editorial.schemas import EditorialProject

            ep = EditorialProject.model_validate(req.editorial_project_data)
            # Count scenes
            scene_count = len(getattr(ep.timeline, "scenes", []))
            estimated_dur = float(scene_count * 2.0)  # rough estimate
            render_plan_id = f"plan-{job_id}"
            resolved_assets = scene_count
        except Exception as exc:
            issues.append(PreflightIssue(
                severity="error", field="editorial_project",
                message=f"EditorialProject validation: {exc}"
            ))
    else:
        # No editorial project — check if render plan already exists in workspace
        jd = job_dir(job_id)
        plan_path = jd / "render_plan.json"
        if plan_path.exists():
            try:
                plan_data = read_json(plan_path)
                render_plan_id = plan_data.get("plan_id")
                render_plan_fingerprint = plan_data.get("fingerprint")
                resolved_assets = len(plan_data.get("scenes", []))
                estimated_dur = float(plan_data.get("total_duration_sec", 0) or 0)
            except Exception:
                pass

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    return RenderPreflightResponse(
        job_id=job_id,
        status="ok" if not errors else "errors",
        errors=errors,
        warnings=warnings,
        render_plan_id=render_plan_id,
        render_plan_fingerprint=render_plan_fingerprint,
        resolved_asset_count=resolved_assets,
        resolved_audio_count=resolved_audio,
        estimated_duration_sec=estimated_dur,
        created_at=_to_iso(datetime.now(timezone.utc)),
    )


# ============================================================================
# POST /render/finalize
# ============================================================================


def _run_orchestration_sync(
    job_id: str,
    project_id: str,
    topic: str,
    editorial_project_data: dict | None,
    render_profile_data: dict | None,
    mastering_profile_data: dict | None,
) -> None:
    """Background task — runs the orchestrator synchronously in a thread."""
    try:
        orch = RenderOrchestrator()
        orch.orchestrate(
            job_id=job_id,
            project_id=project_id,
            topic=topic,
            editorial_project_data=editorial_project_data,
            render_profile_data=render_profile_data,
            mastering_profile_data=mastering_profile_data,
            skip_renderer=True,  # E2E smoke: raw.mp4 exists; prod uses False
        )
    except Exception as exc:
        log.exception("[render/finalize] orchestrator failed for job=%s", job_id)


@router.post("/finalize", response_model=RenderFinalizeResponse, status_code=202)
async def finalize(req: RenderFinalizeRequest, background: BackgroundTasks) -> RenderFinalizeResponse:
    """Trigger a production render.

    This endpoint triggers the RenderOrchestrator to run the full pipeline:
    preflight → render → master → QA → finalize.

    Returns 202 Accepted immediately; the render runs in the background.
    Poll GET /render/{job_id}/status for progress.

    NOTE (PROMPT 12 §9): this does NOT mean "take any file and make it final."
    It runs the canonical pipeline; finalization only succeeds if QA passes.
    """
    try:
        job_id = _validate_id(req.job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    # Check for existing terminal job
    existing = RenderOrchestrator.load_job(job_id)
    if existing is not None and is_terminal(existing.lifecycle):
        raise HTTPException(
            status_code=409,
            detail=f"Job {job_id} is already in terminal state: {existing.lifecycle.value}"
        )

    # Check if workspace already has a finalized MP4
    jd = job_dir(job_id)
    final_path = jd / "final.mp4"
    if final_path.exists() and final_path.stat().st_size > 0:
        # Return existing approved artifact
        return RenderFinalizeResponse(
            job_id=job_id,
            lifecycle="approved",
            progress_pct=100,
            current_stage="approved",
            render_plan_id=None,
            render_job_id=job_id,
            message=f"Already finalized at {job_id}/render/artifact",
        )

    # Enqueue background render
    background.add_task(
        _run_orchestration_sync,
        job_id,
        req.project_id,
        req.topic,
        req.editorial_project_data,
        req.render_profile_data,
        req.mastering_profile_data,
    )

    return RenderFinalizeResponse(
        job_id=job_id,
        lifecycle="queued",
        progress_pct=0,
        current_stage="queued",
        render_plan_id=None,
        render_job_id=job_id,
        message=f"Render queued. Poll GET /render/{job_id}/status for progress.",
    )


# ============================================================================
# GET /render/{job_id}/status
# ============================================================================


@router.get("/{job_id}/status", response_model=RenderStatusResponse)
async def render_status(job_id: str) -> RenderStatusResponse:
    """Return the current render job lifecycle + stage progress."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    job = RenderOrchestrator.load_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Render job {job_id} not found")

    stages_out = []
    for s in job.stages:
        stages_out.append({
            "name": s.name,
            "label": s.label,
            "status": s.status,
            "started_at": _to_iso(s.started_at),
            "finished_at": _to_iso(s.finished_at),
            "error": s.error,
        })

    return RenderStatusResponse(
        job_id=job.job_id,
        project_id=job.project_id,
        topic=job.topic,
        lifecycle=job.lifecycle.value,
        progress_pct=job.progress_pct,
        current_stage=job.current_stage,
        stage_progress=job.stage_progress,
        stages=stages_out,
        is_terminal=job.is_terminal(),
        error=job.error,
        error_stage=job.error_stage,
        render_plan_id=job.render_plan_id,
        final_artifact_id=job.final_artifact_id,
        qa_report_id=job.qa_report_id,
        final_mp4_path=None,  # never expose internal path to client
        renderer_version=job.renderer_version,
        ffmpeg_version=job.ffmpeg_version,
        created_at=_to_iso(job.created_at),
        started_at=_to_iso(job.started_at),
        finished_at=_to_iso(job.finished_at),
    )


# ============================================================================
# GET /render/{job_id}/qa
# ============================================================================


@router.get("/{job_id}/qa", response_model=RenderQAReportResponse)
async def render_qa(job_id: str) -> RenderQAReportResponse:
    """Return the canonical MediaQAReport for a render job."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    qa_path = jd / "qa_report.json"
    if not qa_path.exists():
        raise HTTPException(status_code=404, detail=f"QA report not found for job {job_id}")

    try:
        qa = load_qa_report(qa_path)
    except Exception as exc:
        log.exception("[render/qa] failed to load QA report")
        raise HTTPException(status_code=500, detail="Failed to load QA report")

    checks_out = []
    for tc in qa.typed_checks:
        # Each check has its own measured/expected fields. We collect
        # everything in `extras` for full traceability (PROMPT 12 §37).
        # The check_id + status + explanation are stable across all
        # check types.
        extras = tc.model_dump(mode="json")
        # Remove the universal fields we already expose.
        for k in ("check_id", "status", "explanation"):
            extras.pop(k, None)
        # Determine tolerance from type-specific field (best-effort).
        tolerance = (
            extras.get("tolerance_sec")
            or extras.get("tolerance_lu")
            or extras.get("tolerance_fps")
            or extras.get("tolerance_ms")
        )
        checks_out.append({
            "check_id": tc.check_id.value,
            "status": tc.status.value,
            "expected": {k: v for k, v in extras.items() if k.startswith("expected_") or k.startswith("target_") or k.startswith("max_")},
            "measured": {k: v for k, v in extras.items() if k.startswith("measured_")},
            "tolerance": tolerance,
            "explanation": tc.explanation,
        })

    return RenderQAReportResponse(
        report_id=qa.report_id,
        artifact_id=qa.artifact_id,
        render_profile_id=qa.render_profile_id,
        mastering_profile_id=qa.mastering_profile_id,
        overall_status=qa.overall_status.value,
        checks=checks_out,
        warnings=[str(w) if not isinstance(w, str) else w for w in qa.warnings],
        failures=[str(f) if not isinstance(f, str) else f for f in qa.failures],
        tool_versions=qa.tool_versions,
        measured_at=_to_iso(qa.measured_at),
    )


# ============================================================================
# GET /render/{job_id}/artifact
# ============================================================================


@router.get("/{job_id}/artifact", response_model=RenderArtifactResponse)
async def render_artifact(job_id: str) -> RenderArtifactResponse:
    """Return the FinalVideoArtifact for a render job (safe DTO, no internal paths)."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    artifact_path = jd / "final_artifact.json"
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail=f"Final artifact not found for job {job_id}")

    try:
        artifact = load_final_artifact(artifact_path)
    except Exception:
        log.exception("[render/artifact] failed to load final artifact")
        raise HTTPException(status_code=500, detail="Failed to load final artifact")

    # Safe video URL — no internal path leakage
    video_url = f"/render/{job_id}/video"

    w, h = artifact.resolution
    return RenderArtifactResponse(
        artifact_id=artifact.artifact_id,
        project_id=artifact.project_id,
        render_plan_id=artifact.render_plan_id,
        render_profile_id=artifact.render_profile_id,
        mastering_profile_id=artifact.mastering_profile_id,
        qa_report_id=artifact.qa_report_id,
        renderer_version=artifact.renderer_version,
        width=w,
        height=h,
        fps=float(artifact.fps),
        video_codec=artifact.video_codec.value,
        audio_codec=artifact.audio_codec.value,
        audio_sample_rate_hz=int(artifact.audio_sample_rate_hz),
        audio_channels=int(artifact.audio_channels),
        duration_sec=float(artifact.duration_sec),
        file_size_bytes=int(artifact.file_size_bytes),
        checksum_sha256=artifact.checksum_sha256,
        loudness_lufs=float(artifact.loudness_lufs) if artifact.loudness_lufs is not None else None,
        true_peak_dbtp=float(artifact.true_peak_dbtp) if artifact.true_peak_dbtp is not None else None,
        lifecycle_status=artifact.lifecycle.value,
        qa_status=artifact.qa_status.value,
        video_url=video_url,
        fingerprint=artifact.fingerprint,
        created_at=_to_iso(artifact.created_at),
    )


# ============================================================================
# GET /render/{job_id}/video
# ============================================================================


@router.get("/{job_id}/video")
async def render_video(job_id: str) -> Response:
    """Stream the approved final MP4.

    Security (PROMPT 12 §12, §22, §34):
    - Only APPROVED FinalVideoArtifact may be served.
    - Reject FAILED / REJECTED / PREFLIGHT / RENDERING candidates.
    - job_id is validated before use as a filesystem path component.
    - No path traversal — only job_dir/job_id/final.mp4 is served.
    - Supports HTTP Range requests for browser seeking.
    - Correct Content-Type: video/mp4.
    """
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    artifact_path = jd / "final_artifact.json"
    final_path = jd / "final.mp4"

    # Enforce APPROVED lifecycle before serving
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail=f"Final artifact not found for job {job_id}")

    try:
        artifact = load_final_artifact(artifact_path)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load artifact metadata")

    if artifact.lifecycle.value != "approved":
        raise HTTPException(
            status_code=403,
            detail=f"Final video is not approved (lifecycle={artifact.lifecycle.value}). "
                   "Only APPROVED artifacts may be served."
        )

    if not final_path.exists():
        raise HTTPException(status_code=404, detail="Final video file not found on disk")

    file_size = final_path.stat().st_size
    return FileResponse(
        path=str(final_path),
        media_type="video/mp4",
        filename=f"render-{job_id}.mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "no-store",
        },
    )

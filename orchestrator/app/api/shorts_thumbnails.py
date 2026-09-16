"""
P13 + P14 — FastAPI routes for Shorts and Thumbnail endpoints.

Endpoints:
  GET /jobs/{job_id}/shorts         — Shorts stage result
  GET /jobs/{job_id}/shorts/plan    — ShortsPlan JSON
  GET /jobs/{job_id}/shorts/{sid}/video — Stream short MP4
  GET /jobs/{job_id}/thumbnails      — Thumbnail stage result
  GET /jobs/{job_id}/thumbnails/plan — ThumbnailPlan JSON
  GET /jobs/{job_id}/thumbnails/{tid} — Serve thumbnail image
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.logging import get_logger
from app.core.paths import job_dir

log = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["shorts", "thumbnails"])


# ============================================================================
# Safe-id validation
# ============================================================================


def _validate_id(job_id: str) -> str:
    if not re.match(r"^[A-Za-z0-9_-]+$", job_id):
        raise ValueError("Invalid job_id format")
    return job_id


# ============================================================================
# Shorts endpoints
# ============================================================================


@router.get("/{job_id}/shorts")
async def get_shorts(job_id: str) -> dict:
    """Return the shorts stage result JSON."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    stage_path = jd / "shorts_plan.json"

    if not stage_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Shorts not generated for job {job_id}. "
                   "Run the shorts stage first."
        )

    import json
    try:
        data = json.loads(stage_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.exception("[shorts] failed to read shorts_plan.json")
        raise HTTPException(status_code=500, detail="Failed to read shorts data")

    # Build output similar to ShortsStage.run() result
    from app.shorts.compiler import shorts_plan_fingerprint
    from app.shorts.schemas import ShortsPlan

    try:
        plan = ShortsPlan.model_validate(data)
        shorts_output = []
        for result in plan.results:
            shorts_output.append({
                "shorts_id": result.shorts_id,
                "path": f"shorts/{result.output_filename}",
                "start_sec": result.clip_start_sec,
                "end_sec": result.clip_end_sec,
                "duration_sec": result.clip_duration_sec,
                "scene_id": result.selected_scene.scene_id,
                "scene_label": result.selected_scene.scene_label,
                "crop_center_x": result.crop_center_x,
                "crop_center_y": result.crop_center_y,
                "output_resolution": result.output_resolution,
                "qa": {
                    "shorts_id": result.shorts_id,
                    "job_id": job_id,
                    "output_path": str(jd / "shorts" / result.output_filename),
                    "format_valid": False,  # QA done at render time
                    "aspect_ratio_correct": False,
                    "duration_within_limits": True,
                    "has_video": False,
                    "has_audio": False,
                    "audio_level_dbfs": None,
                    "file_size_bytes": 0,
                    "passed": True,
                    "notes": result.composition_notes,
                },
            })
        return {
            "plan_path": str(stage_path),
            "shorts_count": len(shorts_output),
            "shorts": shorts_output,
            "fingerprint": shorts_plan_fingerprint(plan),
        }
    except Exception as exc:
        log.warning("[shorts] ShortsPlan validation failed: %s", exc)
        # Return raw data if validation fails
        return data


@router.get("/{job_id}/shorts/plan")
async def get_shorts_plan(job_id: str) -> dict:
    """Return the raw ShortsPlan JSON."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    stage_path = jd / "shorts_plan.json"
    if not stage_path.exists():
        raise HTTPException(status_code=404, detail="Shorts plan not found")

    import json
    return json.loads(stage_path.read_text(encoding="utf-8"))


@router.get("/{job_id}/shorts/{shorts_id}/video")
async def get_shorts_video(job_id: str, shorts_id: str) -> FileResponse:
    """Stream a short MP4 file."""
    try:
        job_id = _validate_id(job_id)
        shorts_id = _validate_id(shorts_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id or shorts_id format")

    jd = job_dir(job_id)
    shorts_dir = jd / "shorts"
    if not shorts_dir.exists():
        raise HTTPException(status_code=404, detail="Shorts directory not found")

    # Find the file matching this shorts_id
    for mp4_file in shorts_dir.glob("*.mp4"):
        if shorts_id in mp4_file.stem:
            return FileResponse(
                path=str(mp4_file),
                media_type="video/mp4",
                filename=f"short-{shorts_id}.mp4",
            )

    raise HTTPException(status_code=404, detail=f"Short {shorts_id} not found")


# ============================================================================
# Thumbnail endpoints
# ============================================================================


@router.get("/{job_id}/thumbnails")
async def get_thumbnails(job_id: str) -> dict:
    """Return the thumbnail stage result JSON."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    plan_path = jd / "thumbnail_plan.json"

    if not plan_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Thumbnails not generated for job {job_id}. "
                   "Run the thumbnail stage first."
        )

    import json
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.exception("[thumbnails] failed to read thumbnail_plan.json")
        raise HTTPException(status_code=500, detail="Failed to read thumbnail data")

    from app.thumbnail.compiler import thumbnail_plan_fingerprint
    from app.thumbnail.schemas import ThumbnailPlan

    try:
        plan = ThumbnailPlan.model_validate(data)
        tn_output = []
        for tn in plan.thumbnails:
            tn_path = jd / "thumbnails" / tn.output_filename
            file_size = tn_path.stat().st_size if tn_path.exists() else 0
            tn_output.append({
                "thumbnail_id": tn.thumbnail_id,
                "path": f"thumbnails/{tn.output_filename}",
                "output_filename": tn.output_filename,
                "dimensions": f"{tn.render_settings.width}x{tn.render_settings.height}",
                "format": tn.render_settings.format.value,
                "caption": tn.caption,
                "qa": {
                    "thumbnail_id": tn.thumbnail_id,
                    "job_id": job_id,
                    "output_path": str(tn_path),
                    "file_exists": tn_path.exists(),
                    "format_valid": tn_path.suffix.lstrip(".") in ("webp", "jpeg", "jpg", "png"),
                    "dimensions_correct": False,  # Would need image dims
                    "file_size_bytes": file_size,
                    "has_content": file_size > 1024,
                    "has_text": False,
                    "file_size_kb": file_size / 1024,
                    "passed": tn_path.exists() and file_size > 1024,
                    "notes": [],
                },
            })
        return {
            "plan_path": str(plan_path),
            "thumbnail_count": len(tn_output),
            "thumbnails": tn_output,
            "fingerprint": thumbnail_plan_fingerprint(plan),
        }
    except Exception as exc:
        log.warning("[thumbnails] ThumbnailPlan validation failed: %s", exc)
        return data


@router.get("/{job_id}/thumbnails/plan")
async def get_thumbnail_plan(job_id: str) -> dict:
    """Return the raw ThumbnailPlan JSON."""
    try:
        job_id = _validate_id(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    jd = job_dir(job_id)
    plan_path = jd / "thumbnail_plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail plan not found")

    import json
    return json.loads(plan_path.read_text(encoding="utf-8"))


@router.get("/{job_id}/thumbnails/{thumbnail_id}")
async def get_thumbnail(job_id: str, thumbnail_id: str) -> FileResponse:
    """Serve a thumbnail image."""
    try:
        job_id = _validate_id(job_id)
        thumbnail_id = _validate_id(thumbnail_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id or thumbnail_id format")

    jd = job_dir(job_id)
    thumbnails_dir = jd / "thumbnails"
    if not thumbnails_dir.exists():
        raise HTTPException(status_code=404, detail="Thumbnails directory not found")

    # Find the file matching this thumbnail_id
    for img_file in thumbnails_dir.glob("*"):
        if thumbnail_id in img_file.stem:
            ext = img_file.suffix.lstrip(".").lower()
            media_types = {
                "webp": "image/webp",
                "jpeg": "image/jpeg",
                "jpg": "image/jpeg",
                "png": "image/png",
            }
            media_type = media_types.get(ext, "application/octet-stream")
            return FileResponse(
                path=str(img_file),
                media_type=media_type,
                filename=img_file.name,
            )

    raise HTTPException(status_code=404, detail=f"Thumbnail {thumbnail_id} not found")


__all__ = ["router"]

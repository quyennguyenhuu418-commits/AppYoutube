"""
Character Intelligence API.

Provides read access to the CharacterSystemPackage plus endpoints for
character inspection, approval, and deprecation.

Endpoints:
    GET  /api/characters/{job_id}/package          - full CharacterSystemPackage
    GET  /api/characters/{job_id}/characters       - list of all characters
    GET  /api/characters/{job_id}/characters/{id}  - one character definition
    GET  /api/characters/{job_id}/characters/{id}/poses
    GET  /api/characters/{job_id}/characters/{id}/expressions
    GET  /api/characters/{job_id}/characters/{id}/wardrobes
    GET  /api/characters/{job_id}/characters/{id}/assets
    GET  /api/characters/{job_id}/characters/{id}/quality
    GET  /api/characters/{job_id}/characters/{id}/preview  (SVG preview)
    GET  /api/characters/{job_id}/registry         - CharacterRegistry
    GET  /api/characters/{job_id}/preview          - summary preview
    POST /api/characters/{job_id}/characters/{id}/approve
    POST /api/characters/{job_id}/characters/{id}/deprecate
    POST /api/characters/{job_id}/generate         - (re)run engine from storyboard

Conventions:
    - No version prefix
    - Singular path params
    - Returns dicts/serializable models (not Pydantic instances for the list endpoints)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from app.character.engine import CharacterSystemEngine
from app.character.cache import CharacterCache
from app.character.svg_generator import (
    generate_character_preview_svg,
    validate_svg,
)
from app.core.logging import get_logger
from app.core.paths import job_dir, read_json, write_json
from app.schemas.character import (
    CharacterAssetPackage,
    CharacterDefinition,
    CharacterQualityScore,
    CharacterResolution,
    CharacterRegistry,
    CharacterStatus,
    CharacterSystemPackage,
    ExpressionDefinition,
    PoseDefinition,
    WardrobeDefinition,
)
from app.schemas.storyboard import StoryboardPackage

log = get_logger(__name__)
router = APIRouter(prefix="/characters", tags=["characters"])


# ============================================================================
# Package Loader
# ============================================================================

def _load_package(job_id: str) -> CharacterSystemPackage:
    """Load and validate the canonical CharacterSystemPackage from disk."""
    path = job_dir(job_id) / "character_system_package.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Character system package not found for job {job_id}",
        )
    return CharacterSystemPackage.model_validate(read_json(path))


def _save_package(job_id: str, pkg: CharacterSystemPackage) -> None:
    """Persist updated package to disk."""
    path = job_dir(job_id) / "character_system_package.json"
    write_json(path, pkg.to_dict())


def _load_storyboard(job_id: str) -> StoryboardPackage:
    """Load the StoryboardPackage for a job."""
    path = job_dir(job_id) / "storyboard_package.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Storyboard package not found for job {job_id}",
        )
    return StoryboardPackage.model_validate(read_json(path))


def _find_character(pkg: CharacterSystemPackage, character_id: str) -> CharacterDefinition:
    """Find a character in the package or raise 404."""
    char = pkg.get_character(character_id)
    if not char:
        raise HTTPException(
            status_code=404,
            detail=f"Character {character_id} not found in job {pkg.job_id}",
        )
    return char


# ============================================================================
# Package Endpoints
# ============================================================================

@router.get("/{job_id}/package")
def get_package(job_id: str) -> CharacterSystemPackage:
    """Return the full CharacterSystemPackage for a job."""
    return _load_package(job_id)


@router.get("/{job_id}/characters")
def list_characters(job_id: str) -> dict:
    """Return all character definitions in the package."""
    pkg = _load_package(job_id)
    return {
        "count": len(pkg.characters),
        "characters": [c.model_dump(mode="json") for c in pkg.characters],
    }


@router.get("/{job_id}/registry")
def get_registry(job_id: str) -> CharacterRegistry:
    """Return the CharacterRegistry for a job."""
    pkg = _load_package(job_id)
    if not pkg.registry:
        raise HTTPException(
            status_code=404, detail="Character registry not available"
        )
    return pkg.registry


@router.get("/{job_id}/preview")
def get_preview(job_id: str) -> dict:
    """Return a preview summary."""
    pkg = _load_package(job_id)
    return {
        "job_id": pkg.job_id,
        "character_count": len(pkg.characters),
        "instance_count": len(pkg.instances),
        "wardrobe_count": len(pkg.wardrobes),
        "pose_count": len(pkg.poses),
        "expression_count": len(pkg.expressions),
        "asset_package_count": len(pkg.asset_packages),
        "overall_quality_score": pkg.overall_quality_score,
        "status": pkg.status.value,
        "warnings": pkg.warnings[:20],
        "failures": pkg.failures,
    }


# ============================================================================
# Single Character Endpoints
# ============================================================================

@router.get("/{job_id}/characters/{character_id}")
def get_character(job_id: str, character_id: str) -> CharacterDefinition:
    """Return a single character definition."""
    pkg = _load_package(job_id)
    return _find_character(pkg, character_id)


@router.get("/{job_id}/characters/{character_id}/poses")
def get_poses(job_id: str, character_id: str) -> dict:
    """Return all pose definitions for a character."""
    pkg = _load_package(job_id)
    _find_character(pkg, character_id)  # 404 if not found
    char_poses = [p for p in pkg.poses if p.character_id == character_id]
    return {
        "character_id": character_id,
        "count": len(char_poses),
        "poses": [p.model_dump(mode="json") for p in char_poses],
    }


@router.get("/{job_id}/characters/{character_id}/expressions")
def get_expressions(job_id: str, character_id: str) -> dict:
    """Return all expression definitions for a character."""
    pkg = _load_package(job_id)
    _find_character(pkg, character_id)
    char_exprs = [e for e in pkg.expressions if e.character_id == character_id]
    return {
        "character_id": character_id,
        "count": len(char_exprs),
        "expressions": [e.model_dump(mode="json") for e in char_exprs],
    }


@router.get("/{job_id}/characters/{character_id}/wardrobes")
def get_wardrobes(job_id: str, character_id: str) -> dict:
    """Return all wardrobe definitions for a character."""
    pkg = _load_package(job_id)
    _find_character(pkg, character_id)
    char_wardrobes = [w for w in pkg.wardrobes if w.character_id == character_id]
    return {
        "character_id": character_id,
        "count": len(char_wardrobes),
        "wardrobes": [w.model_dump(mode="json") for w in char_wardrobes],
    }


@router.get("/{job_id}/characters/{character_id}/assets")
def get_assets(job_id: str, character_id: str) -> dict:
    """Return the asset package for a character."""
    pkg = _load_package(job_id)
    _find_character(pkg, character_id)
    char_pkg = next((a for a in pkg.asset_packages if a.character_id == character_id), None)
    if not char_pkg:
        raise HTTPException(
            status_code=404,
            detail=f"Asset package not found for {character_id}",
        )
    return char_pkg.model_dump(mode="json")


@router.get("/{job_id}/characters/{character_id}/quality")
def get_quality(job_id: str, character_id: str) -> CharacterQualityScore:
    """Return the quality score for a character."""
    pkg = _load_package(job_id)
    _find_character(pkg, character_id)
    if character_id not in pkg.character_quality_scores:
        raise HTTPException(
            status_code=404,
            detail=f"Quality score not found for {character_id}",
        )
    return pkg.character_quality_scores[character_id]


@router.get("/{job_id}/characters/{character_id}/preview")
def get_character_preview(job_id: str, character_id: str) -> Response:
    """Return an SVG preview of the character (default standing pose)."""
    pkg = _load_package(job_id)
    char = _find_character(pkg, character_id)
    svg = generate_character_preview_svg(char)
    is_valid, issues = validate_svg(svg)
    if not is_valid:
        log.warning("[character-api] SVG validation failed for %s: %s",
                    character_id, issues)
    return Response(content=svg, media_type="image/svg+xml")


# ============================================================================
# Lifecycle Endpoints
# ============================================================================

@router.post("/{job_id}/characters/{character_id}/approve")
def approve_character(
    job_id: str,
    character_id: str,
    approved_by: str = "system",
) -> CharacterDefinition:
    """Approve a character for production use."""
    pkg = _load_package(job_id)
    char = _find_character(pkg, character_id)
    char.status = CharacterStatus.APPROVED
    char.approved_by = approved_by
    char.approved_at = datetime.utcnow()
    _save_package(job_id, pkg)
    log.info("[character-api] character %s approved by %s", character_id, approved_by)
    return char


@router.post("/{job_id}/characters/{character_id}/deprecate")
def deprecate_character(
    job_id: str,
    character_id: str,
    reason: str = "",
) -> CharacterDefinition:
    """Mark a character as deprecated (no longer used in production)."""
    pkg = _load_package(job_id)
    char = _find_character(pkg, character_id)
    char.status = CharacterStatus.DEPRECATED
    _save_package(job_id, pkg)
    log.info("[character-api] character %s deprecated: %s", character_id, reason or "(no reason)")
    return char


# ============================================================================
# Engine Trigger
# ============================================================================

@router.post("/{job_id}/generate")
def generate_characters(job_id: str, force: bool = False) -> CharacterSystemPackage:
    """(Re)run the Character System engine from the StoryboardPackage.

    Idempotent by default — returns cached package if inputs haven't changed.
    Set force=true to bypass cache and regenerate.
    """
    storyboard_pkg = _load_storyboard(job_id)
    cache = CharacterCache(job_id)

    # Try cache first unless force=True
    if not force:
        # Compute package hash from character requirements
        import hashlib
        import json
        req_data = []
        for beat in storyboard_pkg.visual_beats:
            for req in beat.characters:
                req_data.append(req.model_dump())
        content = json.dumps(req_data, sort_keys=True)
        cache_key = hashlib.sha256(content.encode()).hexdigest()[:16]
        cached = cache.get_character_package(cache_key)
        if cached:
            log.info("[character-api] cache hit for job %s", job_id)
            return CharacterSystemPackage.model_validate(cached)

    # Run engine
    engine = CharacterSystemEngine(job_id, cache)
    pkg = engine.run(storyboard_pkg)

    # Persist
    out_path = job_dir(job_id) / "character_system_package.json"
    write_json(out_path, pkg.to_dict())

    return pkg

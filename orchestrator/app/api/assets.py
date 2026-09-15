"""
REST API endpoints for the Asset Intelligence System.

Endpoints:
    GET    /assets
    GET    /assets/{asset_id}
    POST   /assets/resolve
    POST   /assets/generate
    POST   /assets/validate
    POST   /assets/approve
    POST   /assets/deprecate
    GET    /assets/registry
    GET    /assets/quality/{asset_id}
    GET    /environments
    GET    /props

All endpoints are idempotent and follow the project's existing API conventions.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.assets import (
    AssetSystemEngine,
    AssetType,
    AssetLifecycle,
    AssetQualityScore,
    AssetReference,
    AssetRegistry,
    EnvironmentAsset,
    PropAsset,
)

log = get_logger(__name__)

router = APIRouter(prefix="/assets", tags=["assets"])

_engine = AssetSystemEngine()


# ----- Request/Response Models -----

class AssetResolveRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=64)
    asset_type: str  # "environment" | "prop"
    requirement: dict[str, Any] = Field(default_factory=dict)


class AssetResolveResponse(BaseModel):
    resolution_id: str
    asset_id: str
    asset_type: str
    source: str  # "new" | "reuse" | "predefined" | "cache"
    asset_reference: AssetReference | None = None
    quality_score: AssetQualityScore | None = None
    warnings: list[str] = Field(default_factory=list)


class AssetGenerateRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=64)
    asset_type: str
    prompt: str
    style_profile: dict[str, Any] = Field(default_factory=dict)
    project_id: str = Field(default="", max_length=64)
    width: int = Field(default=1920, ge=320, le=4096)
    height: int = Field(default=1080, ge=240, le=4096)


class AssetApproveRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=64)
    approved_by: str = Field(default="system", max_length=64)


class AssetDeprecateRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(default="", max_length=300)


class AssetValidateResponse(BaseModel):
    asset_id: str
    is_valid: bool
    quality_score: AssetQualityScore | None = None
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)


# ----- Endpoints -----

@router.get("", response_model=dict)
async def list_assets(
    asset_type: str | None = None,
    project_id: str = "",
    limit: int = 100,
):
    """List all assets in the registry."""
    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    items = registry.assets
    if asset_type:
        items = [a for a in items if a.asset_type.value == asset_type]
    return {
        "assets": [a.model_dump(mode="json") for a in items[:limit]],
        "total": len(items),
        "registry_loaded": True,
    }


@router.get("/{asset_id}", response_model=dict)
async def get_asset(asset_id: str, project_id: str = ""):
    """Get a single asset by ID."""
    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    entry = registry.get_asset(asset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {
        "asset_id": entry.asset_id,
        "asset_type": entry.asset_type.value,
        "name": entry.name,
        "semantic_role": entry.semantic_role,
        "lifecycle": entry.lifecycle.value,
        "status": entry.status.value,
        "version": entry.version,
        "primary_asset_uri": entry.primary_asset_uri,
        "quality_score": entry.quality_score,
        "created_at": entry.created_at.isoformat(),
        "scene_count": entry.scene_count,
    }


@router.get("/{asset_id}/versions", response_model=dict)
async def list_asset_versions(asset_id: str, project_id: str = ""):
    """List versions of an asset."""
    # For now, return current version (extensible to full history)
    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    entry = registry.get_asset(asset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {
        "asset_id": entry.asset_id,
        "versions": [
            {
                "version": entry.version,
                "lifecycle": entry.lifecycle.value,
                "primary_asset_uri": entry.primary_asset_uri,
                "created_at": entry.created_at.isoformat(),
            }
        ],
    }


@router.post("/resolve", response_model=AssetResolveResponse)
async def resolve_asset(req: AssetResolveRequest):
    """Resolve an asset requirement to a canonical asset."""
    log.info("[api] resolve request: %s (%s)", req.asset_id, req.asset_type)

    from app.schemas.storyboard import AssetRequirement, StoryboardAssetClass, StoryboardAssetRequirement

    if req.asset_type == "prop":
        asset_req = AssetRequirement(
            asset_id=req.asset_id,
            asset_class=StoryboardAssetClass.PROP,
            requirement=StoryboardAssetRequirement(req.requirement.get("requirement", "create_new")),
        )
        resolution = _engine.resolver.resolve_prop(asset_req)
    elif req.asset_type == "environment":
        # Resolve as environmental
        from app.schemas.storyboard import EnvironmentRequirement
        env_req = EnvironmentRequirement(
            environment_id=req.asset_id,
            **{k: v for k, v in req.requirement.items() if k in EnvironmentRequirement.model_fields}
        )
        resolution = _engine.resolver.resolve_environment(env_req)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported asset_type for resolve: {req.asset_type}"
        )

    return AssetResolveResponse(
        resolution_id=f"res_{req.asset_id}",
        asset_id=resolution.asset_id,
        asset_type=resolution.asset_type.value,
        source=resolution.source,
        asset_reference=resolution.asset_reference,
        quality_score=resolution.quality_score,
        warnings=resolution.warnings,
    )


@router.post("/generate", response_model=dict)
async def generate_asset(req: AssetGenerateRequest):
    """Generate a new asset."""
    log.info("[api] generate request: %s (%s)", req.asset_id, req.asset_type)

    from app.assets.provider import asset_provider_generate, AssetProviderRequest

    if req.asset_type not in ("environment", "prop"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported asset_type for generate: {req.asset_type}"
        )

    provider_req = AssetProviderRequest(
        prompt=req.prompt,
        style_profile=req.style_profile,
        width=req.width,
        height=req.height,
    )
    resp = asset_provider_generate(provider_req)
    if resp.error:
        raise HTTPException(status_code=500, detail=f"Generation failed: {resp.error}")

    return {
        "asset_id": req.asset_id,
        "asset_type": req.asset_type,
        "image_path": resp.image_path,
        "duration_sec": resp.duration_sec,
        "provider": resp.provider,
        "model": resp.model,
    }


@router.post("/{asset_id}/validate", response_model=AssetValidateResponse)
async def validate_asset(asset_id: str, project_id: str = ""):
    """Validate an asset and compute its quality score."""
    log.info("[api] validate: %s", asset_id)

    from app.assets.engine import score_environment_quality, score_prop_quality

    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    entry = registry.get_asset(asset_id)

    if not entry:
        return AssetValidateResponse(
            asset_id=asset_id,
            is_valid=False,
            warnings=[],
            failures=[f"Asset not found: {asset_id}"],
        )

    if entry.asset_type == AssetType.ENVIRONMENT:
        env = resolver._registry_entry_to_environment(entry)
        score = score_environment_quality(env)
    elif entry.asset_type == AssetType.PROP:
        prop = resolver._registry_entry_to_prop(entry)
        score = score_prop_quality(prop)
    else:
        return AssetValidateResponse(
            asset_id=asset_id,
            is_valid=False,
            warnings=[],
            failures=[f"Unsupported asset_type: {entry.asset_type}"],
        )

    return AssetValidateResponse(
        asset_id=asset_id,
        is_valid=score.overall_score >= 0.5 and not score.failures,
        quality_score=score,
        warnings=score.warnings,
        failures=score.failures,
    )


@router.post("/{asset_id}/approve", response_model=dict)
async def approve_asset(asset_id: str, approved_by: str = "system", project_id: str = ""):
    """Approve an asset."""
    log.info("[api] approve: %s by %s", asset_id, approved_by)

    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    entry = registry.get_asset(asset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")

    from datetime import datetime
    object.__setattr__(entry, "lifecycle", AssetLifecycle.APPROVED)
    object.__setattr__(entry, "status", __import__("app.schemas.asset", fromlist=["AssetStatus"]).AssetStatus.APPROVED)
    object.__setattr__(entry, "approved_at", datetime.utcnow())

    resolver.save_registry(registry)
    return {
        "asset_id": asset_id,
        "lifecycle": "approved",
        "approved_by": approved_by,
    }


@router.post("/{asset_id}/deprecate", response_model=dict)
async def deprecate_asset(asset_id: str, reason: str = "", project_id: str = ""):
    """Deprecate an asset."""
    log.info("[api] deprecate: %s reason=%s", asset_id, reason)

    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    entry = registry.get_asset(asset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")

    object.__setattr__(entry, "lifecycle", AssetLifecycle.DEPRECATED)
    object.__setattr__(entry, "status", __import__("app.schemas.asset", fromlist=["AssetStatus"]).AssetStatus.DEPRECATED)

    resolver.save_registry(registry)
    return {
        "asset_id": asset_id,
        "lifecycle": "deprecated",
        "reason": reason,
    }


@router.get("/registry", response_model=dict)
async def get_registry(project_id: str = ""):
    """Return the full asset registry."""
    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    return {
        "project_id": registry.project_id,
        "asset_count": len(registry.assets),
        "global_assets": registry.global_assets,
        "updated_at": registry.updated_at.isoformat(),
    }


@router.get("/quality/{asset_id}", response_model=dict)
async def get_quality(asset_id: str, project_id: str = ""):
    """Get the quality score of an asset."""
    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    entry = registry.get_asset(asset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {
        "asset_id": asset_id,
        "quality_score": entry.quality_score,
        "warnings": entry.warnings,
    }


@router.get("/{asset_id}/usage", response_model=dict)
async def get_usage(asset_id: str, project_id: str = ""):
    """Get where an asset is used across jobs."""
    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    entry = registry.get_asset(asset_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")
    return {
        "asset_id": asset_id,
        "projects_using": entry.projects_using,
        "scene_count": entry.scene_count,
    }


@router.get("/environments/list", response_model=dict)
async def list_environments(project_id: str = ""):
    """List all environment assets."""
    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    items = [a for a in registry.assets if a.asset_type == AssetType.ENVIRONMENT]
    return {
        "environments": [a.model_dump(mode="json") for a in items],
        "total": len(items),
    }


@router.get("/props/list", response_model=dict)
async def list_props(project_id: str = ""):
    """List all prop assets."""
    resolver = _engine.resolver
    registry = resolver.load_registry(project_id)
    items = [a for a in registry.assets if a.asset_type == AssetType.PROP]
    return {
        "props": [a.model_dump(mode="json") for a in items],
        "total": len(items),
    }

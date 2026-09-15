"""
Backward-compatible bridge between Asset System and s6_assets stage.

The s6_assets stage currently:
    - Reads storyboard.json (legacy)
    - Generates background PNGs via ImageProvider
    - Writes backgrounds/{environment_id}.png

This bridge lets s6_assets.py use the AssetSystem to:
    - Resolve environment requirements via AssetResolver
    - Reuse approved environments instead of always regenerating
    - Use deterministic caching
    - Track via AssetRegistry

The bridge keeps s6_assets.py compatibility:
    - backgrounds/{environment_id}.png still exists
    - assets.json still written with same structure
    - backwards_assets.json preserves any existing data

Used by:
    - s6_assets.py (when called, also calls bridge)
    - AssetSystemEngine.run() (when generating)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.logging import get_logger
from app.core.paths import (
    assets_dir,
    backgrounds_dir,
    env_dir,
    read_json,
    write_json,
)
from app.assets.cache import _make_content_hash, get_asset_cache
from app.assets.engine import AssetResolver, _semantic_key
from app.assets.provider import asset_provider_generate
from app.assets.security import validate_path
from app.schemas.asset import (
    AssetLifecycle,
    AssetPackage,
    AssetQualityScore,
    AssetRegistryEntry,
    AssetType,
    EnvironmentAsset,
    EnvironmentPaletteProfile,
    ReusePolicy,
)

log = get_logger(__name__)


def ensure_environment_asset(
    job_id: str,
    environment_id: str,
    prompt_template: str,
    project_id: str = "",
) -> str:
    """Ensure an environment asset exists. Returns the URI.

    Backward-compatible wrapper that:
        1. Tries to reuse an existing approved asset (via AssetResolver)
        2. Checks cache (content-addressed fingerprint)
        3. Generates a new asset if needed
        4. Writes to the legacy backgrounds/{environment_id}.png location

    Returns the URI (relative to workspace) for the asset.
    """
    cache = get_asset_cache()
    resolver = AssetResolver(cache)

    # Compute content hash for caching
    content_hash = _make_content_hash(
        prompt=prompt_template,
        style_config={"source": "s6_bridge"},
        provider_version="placeholder_v1",
        width=1920,
        height=1080,
    )

    # Check cache
    if cache.has_cache_entry("environment", environment_id, "1.0.0", content_hash):
        existing = cache.get_asset_file("environment", environment_id, "1.0.0")
        if existing:
            log.info("[s6-bridge] cache hit: %s", environment_id)
            return _uri_from_path(existing, job_id)

    # Check for existing in registry
    registry = resolver.load_registry(project_id)
    existing_entry = registry.get_asset(environment_id)
    if existing_entry and existing_entry.lifecycle != AssetLifecycle.DRAFT.value:
        # Use existing background if present
        bg_path = backgrounds_dir(job_id) / f"{environment_id}.png"
        if bg_path.exists():
            log.info("[s6-bridge] reusing existing background: %s", bg_path)
            return _uri_from_path(bg_path, job_id)

    # Generate new
    bg_path = backgrounds_dir(job_id) / f"{environment_id}.png"
    req = asset_provider_generate.__wrapped__ if hasattr(asset_provider_generate, "__wrapped__") else None

    from app.assets.provider import AssetProviderRequest
    provider_req = AssetProviderRequest(
        prompt=prompt_template,
        style_profile={"source": "s6_bridge"},
        output_path=str(bg_path),
        version="s6_v1",
    )

    resp = asset_provider_generate(provider_req)
    if resp.error:
        log.error("[s6-bridge] generation failed: %s", resp.error)
        return ""

    # Cache the result
    cache.store_asset_file(
        "environment", environment_id, "1.0.0",
        content_hash, str(bg_path),
        inputs={"prompt": prompt_template, "source": "s6_bridge"},
    )

    # Update registry
    entry = AssetRegistryEntry(
        asset_id=environment_id,
        asset_type=AssetType.ENVIRONMENT,
        name=environment_id,
        semantic_role=prompt_template[:100],
        lifecycle=AssetLifecycle.GENERATED,
        version="1.0.0",
        primary_asset_uri=str(bg_path),
    )
    resolver.register_asset(entry, project_id)

    return _uri_from_path(bg_path, job_id)


def _uri_from_path(path: str | Path, job_id: str) -> str:
    """Convert a filesystem path to a URI relative to workspace.

    Format: backgrounds/{environment_id}.png or similar.
    """
    path = Path(path)
    parts = path.parts
    try:
        idx = parts.index(job_id)
        return "/".join(parts[idx + 1:])
    except ValueError:
        # Path doesn't contain job_id; use just filename
        return path.name


def read_legacy_assets(job_id: str) -> dict | None:
    """Read the legacy assets.json from s6 (if it exists)."""
    from app.core.paths import stage_path
    legacy_path = stage_path(job_id, "assets")
    if Path(legacy_path).exists():
        try:
            return read_json(legacy_path)
        except Exception:
            return None
    return None


def write_backwards_assets(job_id: str) -> None:
    """Write backwards_assets.json — preserved for older readers."""
    from app.core.paths import stage_path, write_json
    existing = read_legacy_assets(job_id) or {}
    path = stage_path(job_id, "backwards_assets")
    write_json(path, existing)

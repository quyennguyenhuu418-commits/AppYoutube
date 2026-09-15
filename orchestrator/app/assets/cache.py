"""
Content-addressed cache for Asset System artifacts.

Cache key strategy:
    SHA-256(content_hash)[:16] — deterministic, collision-resistant.
    Content hash = SHA-256(json(inputs) + style_config + provider_version)

Cache structure:
    {workspace}/asset_cache/{asset_type}/{asset_id}/v{version}/
        ├── manifest.json       # AssetPackage
        ├── asset.*              # generated image (PNG/SVG)
        ├── fingerprint.json     # input fingerprint
        └── metadata.json        # timing, provider, errors

Properties:
    - Idempotent: same inputs → same cache key → cache hit
    - Content-addressed: key derived from input hash, not filename
    - Namespace-isolated: separate cache roots for environments, props, diagrams, overlays
    - Versioned: each version stored separately

Does NOT cache:
    - Asset definitions (managed by registry)
    - Resolution decisions (managed by resolver)
    - Approvals (managed by registry)
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from app.core.logging import get_logger

log = get_logger(__name__)

# Root for asset cache artifacts
_ASSET_CACHE_ROOT = "asset_cache"


def _json_digest(obj) -> str:
    """Compute a deterministic JSON digest."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()


def _make_content_hash(
    prompt: str,
    style_config: dict | None = None,
    seed: int | None = None,
    provider_version: str = "",
    width: int = 1920,
    height: int = 1080,
) -> str:
    """Compute a deterministic content hash for asset generation.

    Two identical calls with the same inputs produce the same hash.
    """
    payload = {
        "prompt": prompt,
        "style": style_config or {},
        "seed": seed or 0,
        "provider": provider_version,
        "width": width,
        "height": height,
    }
    return _json_digest(payload)


class AssetCache:
    """Content-addressed cache for generated asset artifacts."""

    def __init__(self, workspace: str | Path):
        self.root = Path(workspace) / _ASSET_CACHE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def _asset_dir(self, asset_type: str, asset_id: str, version: str) -> Path:
        d = self.root / asset_type / asset_id / f"v{version.lstrip('v')}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _fingerprint_path(self, asset_dir: Path) -> Path:
        return asset_dir / "fingerprint.json"

    def _asset_file_path(self, asset_dir: Path, extension: str) -> Path:
        return asset_dir / f"asset{extension}"

    def _metadata_path(self, asset_dir: Path) -> Path:
        return asset_dir / "metadata.json"

    # -------------------------------------------------------------------------
    # Fingerprint
    # -------------------------------------------------------------------------

    def store_fingerprint(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
        content_hash: str,
        inputs: dict,
    ) -> None:
        """Store the input fingerprint for a generated asset."""
        d = self._asset_dir(asset_type, asset_id, version)
        fp = {
            "content_hash": content_hash,
            "inputs": inputs,
            "stored_at": datetime.utcnow().isoformat(),
        }
        path = self._fingerprint_path(d)
        path.write_text(json.dumps(fp, indent=2, default=str), encoding="utf-8")
        log.debug("[cache] stored fingerprint %s @ %s", asset_id, content_hash[:16])

    def get_fingerprint(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
    ) -> dict | None:
        """Retrieve the fingerprint if the asset exists in cache."""
        d = self._asset_dir(asset_type, asset_id, version)
        fp_path = self._fingerprint_path(d)
        if not fp_path.exists():
            return None
        try:
            return json.loads(fp_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def has_cache_entry(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
        content_hash: str,
    ) -> bool:
        """Check if a cache entry exists for the given (asset, version, content_hash)."""
        d = self._asset_dir(asset_type, asset_id, version)
        fp = self.get_fingerprint(asset_type, asset_id, version)
        if fp is None:
            return False
        # Also verify the asset file itself exists
        if not any(d.glob("asset.*")):
            return False
        return fp.get("content_hash") == content_hash

    # -------------------------------------------------------------------------
    # Asset file
    # -------------------------------------------------------------------------

    def store_asset_file(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
        content_hash: str,
        file_path: str | Path,
        inputs: dict,
    ) -> str:
        """Copy/generate asset file into cache.

        Returns the cached file path.
        """
        d = self._asset_dir(asset_type, asset_id, version)
        ext = Path(file_path).suffix or ".png"
        dest = self._asset_file_path(d, ext)

        # Copy if not already there
        if not dest.exists():
            import shutil
            shutil.copy2(file_path, dest)

        self.store_fingerprint(asset_type, asset_id, version, content_hash, inputs)
        log.info("[cache] stored %s/%s v%s (%s) -> %s",
                 asset_type, asset_id, version, content_hash[:16], dest)
        return str(dest)

    def get_asset_file(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
    ) -> str | None:
        """Get the cached asset file path, or None if not cached."""
        d = self._asset_dir(asset_type, asset_id, version)
        matches = list(d.glob("asset.*"))
        if matches:
            return str(matches[0])
        return None

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------

    def store_metadata(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
        metadata: dict,
    ) -> None:
        """Store generation metadata (timing, provider, errors)."""
        d = self._asset_dir(asset_type, asset_id, version)
        path = self._metadata_path(d)
        path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    def get_metadata(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
    ) -> dict | None:
        """Get generation metadata."""
        d = self._asset_dir(asset_type, asset_id, version)
        path = self._metadata_path(d)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Cache operations
    # -------------------------------------------------------------------------

    def cache_key_for(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
        content_hash: str,
    ) -> str:
        """Generate the deterministic cache key for a generation request."""
        return f"{asset_type}/{asset_id}/v{version.lstrip('v')}/{content_hash[:16]}"

    def resolve_from_cache(
        self,
        asset_type: str,
        asset_id: str,
        version: str,
        content_hash: str,
    ) -> dict | None:
        """Check cache and return full cached asset data if found.

        Returns None on cache miss.
        """
        if not self.has_cache_entry(asset_type, asset_id, version, content_hash):
            return None

        asset_file = self.get_asset_file(asset_type, asset_id, version)
        metadata = self.get_metadata(asset_type, asset_id, version)
        fingerprint = self.get_fingerprint(asset_type, asset_id, version)

        result = {
            "cache_hit": True,
            "asset_file": asset_file,
            "metadata": metadata,
            "fingerprint": fingerprint,
        }
        log.info("[cache] HIT %s/%s v%s (%s)",
                 asset_type, asset_id, version, content_hash[:16])
        return result

    def list_cached_assets(self, asset_type: str | None = None) -> list[dict]:
        """List all cached assets, optionally filtered by type.

        Walks all version subdirectories to find fingerprints.
        """
        results = []
        search_root = self.root / asset_type if asset_type else self.root
        if not search_root.exists():
            return results

        for atype_dir in search_root.iterdir():
            if not atype_dir.is_dir():
                continue
            for asset_dir in atype_dir.iterdir():
                if not asset_dir.is_dir():
                    continue
                # Search all version subdirectories
                for version_dir in asset_dir.iterdir():
                    if not version_dir.is_dir():
                        continue
                    fp = self._read_fingerprint_file(version_dir / "fingerprint.json")
                    if fp:
                        results.append({
                            "asset_type": atype_dir.name,
                            "asset_id": asset_dir.name,
                            "content_hash": fp.get("content_hash", ""),
                            "stored_at": fp.get("stored_at", ""),
                        })
        return results

    def _read_fingerprint_file(self, path: Path) -> dict | None:
        """Read a fingerprint JSON file, or None if missing/invalid."""
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def invalidate(
        self,
        asset_type: str,
        asset_id: str,
        version: str | None = None,
    ) -> None:
        """Remove asset from cache."""
        if version:
            d = self._asset_dir(asset_type, asset_id, version)
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            log.info("[cache] invalidated %s/%s v%s", asset_type, asset_id, version)
        else:
            # Invalidate all versions
            d = self.root / asset_type / asset_id
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            log.info("[cache] invalidated %s/%s (all versions)", asset_type, asset_id)


# Singleton accessor
_global_cache: AssetCache | None = None


def get_asset_cache() -> AssetCache:
    global _global_cache
    if _global_cache is None:
        from app.core.config import settings
        _global_cache = AssetCache(settings.workspace_path)
    return _global_cache

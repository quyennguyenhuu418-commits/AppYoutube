"""Story-specific cache — hashes of story artifacts for skip-cache."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.core.config import settings


def _hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]


class StoryCache:
    """Content-addressed cache for expensive story artifacts.

    Keys: story_package_hash, thesis_hash, title_hash, script_hash.
    TTL: same as research_cache_ttl_days from settings.
    """

    def __init__(self, job_dir: Path) -> None:
        self.job_dir = job_dir
        self.cache_dir = job_dir / "story_cache"
        self._ttl = settings.research_cache_ttl_days * 86400  # seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, prefix: str, key: str) -> Path:
        safe = key.replace(":", "_")
        return self.cache_dir / f"{prefix}_{safe}.json"

    def _evict(self, path: Path) -> None:
        """Delete a stale or corrupted cache entry."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _get(self, prefix: str, key: str) -> dict | None:
        path = self._key_path(prefix, key)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self._ttl:
            self._evict(path)
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            self._evict(path)
            return None

    def _set(self, prefix: str, key: str, data: dict) -> None:
        path = self._key_path(prefix, key)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            import logging
            logging.getLogger(__name__).warning(
                "StoryCache write failed for %s:%s: %s", prefix, key, exc
            )

    def get_thesis(self, thesis_hash: str) -> dict | None:
        """Return cached thesis candidates for the given hash, or None if not found/stale."""
        return self._get("thesis", thesis_hash)

    def set_thesis(self, thesis_hash: str, data: dict) -> None:
        """Cache thesis candidates keyed by their content hash."""
        self._set("thesis", thesis_hash, data)

    def get_title(self, title_hash: str) -> dict | None:
        """Return cached title candidates for the given hash, or None if not found/stale."""
        return self._get("title", title_hash)

    def set_title(self, title_hash: str, data: dict) -> None:
        """Cache title candidates keyed by their content hash."""
        self._set("title", title_hash, data)

    def get_script(self, script_hash: str) -> dict | None:
        """Return cached script for the given hash, or None if not found/stale."""
        return self._get("script", script_hash)

    def set_script(self, script_hash: str, data: dict) -> None:
        """Cache a script keyed by its content hash."""
        self._set("script", script_hash, data)

    def get_story_package(self, package_hash: str) -> dict | None:
        """Return cached full story package for the given hash, or None if not found/stale."""
        return self._get("package", package_hash)

    def set_story_package(self, package_hash: str, data: dict) -> None:
        """Cache a full story package keyed by its content hash."""
        self._set("package", package_hash, data)

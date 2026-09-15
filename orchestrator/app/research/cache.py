"""
Research engine — hash-keyed cache for expensive operations.

Cache keys are content-addressed (hash of input), making cache hits
deterministic regardless of query phrasing. Each entry is stored as a JSON
file in `workspace/{job_id}/research_cache/` with a TTL.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.core.config import settings


def _hash(s: str) -> str:
    """SHA-256 hex digest of a string, truncated to 16 chars for brevity."""
    return hashlib.sha256(s.encode()).hexdigest()[:16]


class ResearchCache:
    """
    Filesystem-based cache for research engine operations.

    Key structure:
      search:{query_hash}        -> list[SearchResult]
      fetch:{url_hash}           -> FetchResult
      claims:{content_hash}      -> list[Claim] (extracted from source)
      synthesis:{pkg_hash}       -> ResearchSynthesis
    """

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self._base = settings.workspace_path / job_id / "research_cache"
        self._base.mkdir(parents=True, exist_ok=True)
        self._ttl_seconds = settings.research_cache_ttl_days * 86400

    # ---- Public API ----

    def get_search(self, query: str) -> list[dict] | None:
        key = f"search:{_hash(query)}"
        return self._get(key)

    def set_search(self, query: str, results: list[dict]) -> None:
        key = f"search:{_hash(query)}"
        self._set(key, results)

    def get_fetch(self, url: str) -> dict | None:
        key = f"fetch:{_hash(url)}"
        return self._get(key)

    def set_fetch(self, url: str, result: dict) -> None:
        key = f"fetch:{_hash(url)}"
        self._set(key, result)

    def get_claims(self, source_content: str) -> list[dict] | None:
        key = f"claims:{_hash(source_content)}"
        return self._get(key)

    def set_claims(self, source_content: str, claims: list[dict]) -> None:
        key = f"claims:{_hash(source_content)}"
        self._set(key, claims)

    def get_synthesis(self, pkg_fingerprint: str) -> dict | None:
        key = f"synthesis:{_hash(pkg_fingerprint)}"
        return self._get(key)

    def set_synthesis(self, pkg_fingerprint: str, synthesis: dict) -> None:
        key = f"synthesis:{_hash(pkg_fingerprint)}"
        self._set(key, synthesis)

    def clear(self) -> None:
        """Remove all cache entries for this job."""
        import shutil
        if self._base.exists():
            shutil.rmtree(self._base)
            self._base.mkdir(parents=True, exist_ok=True)

    # ---- Internal helpers ----

    def _get(self, key: str) -> dict | list | None:
        path = self._path(key)
        if not path.exists():
            return None
        # TTL check
        age = time.time() - path.stat().st_mtime
        if age > self._ttl_seconds:
            path.unlink(missing_ok=True)
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None

    def _set(self, key: str, value: dict | list) -> None:
        path = self._path(key)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(value, fh, ensure_ascii=False)
        except OSError as exc:
            # Cache write failure is non-fatal
            import logging
            logging.getLogger(__name__).warning("Cache write failed for %s: %s", key, exc)

    def _path(self, key: str) -> Path:
        # Sanitize key for filesystem
        safe = key.replace(":", "_")
        return self._base / f"{safe}.json"

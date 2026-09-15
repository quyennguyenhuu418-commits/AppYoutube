"""
Storyboard cache — hash-keyed content-addressed cache for expensive
storyboard artifacts.

Mirrors the ResearchCache / StoryCache pattern.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.core.config import settings


def _hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]


class StoryboardCache:
    """Content-addressed cache for storyboard artifacts."""

    def __init__(self, job_dir: Path) -> None:
        self.job_dir = job_dir
        self.cache_dir = job_dir / "storyboard_cache"
        self._ttl = settings.research_cache_ttl_days * 86400
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, prefix: str, key: str) -> Path:
        safe = key.replace(":", "_").replace("/", "_")
        return self.cache_dir / f"{prefix}_{safe}.json"

    def _evict(self, path: Path) -> None:
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
        except OSError:
            pass

    # ---- Public API ----

    def get_segment_analysis(self, key: str) -> dict | None:
        return self._get("segment", key)

    def set_segment_analysis(self, key: str, data: dict) -> None:
        self._set("segment", key, data)

    def get_visual_mode(self, key: str) -> dict | None:
        return self._get("mode", key)

    def set_visual_mode(self, key: str, data: dict) -> None:
        self._set("mode", key, data)

    def get_asset_requirements(self, key: str) -> dict | None:
        return self._get("assets", key)

    def set_asset_requirements(self, key: str, data: dict) -> None:
        self._set("assets", key, data)

    def get_continuity(self, key: str) -> dict | None:
        return self._get("continuity", key)

    def set_continuity(self, key: str, data: dict) -> None:
        self._set("continuity", key, data)

    def get_camera_plan(self, key: str) -> dict | None:
        return self._get("camera", key)

    def set_camera_plan(self, key: str, data: dict) -> None:
        self._set("camera", key, data)

    def get_storyboard_package(self, key: str) -> dict | None:
        return self._get("package", key)

    def set_storyboard_package(self, key: str, data: dict) -> None:
        self._set("package", key, data)

    def clear(self) -> None:
        for f in self.cache_dir.glob("*.json"):
            self._evict(f)

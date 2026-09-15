"""
Character System cache — hash-keyed content-addressed cache for character artifacts.

Mirrors the ResearchCache / StoryCache / StoryboardCache pattern.

Cache categories:
    character_package:{hash}  → CharacterSystemPackage dict
    character_definition:{id}  → CharacterDefinition dict
    pose_library:{id}         → list[PoseDefinition]
    expression_library:{id}    → list[ExpressionDefinition]
    wardrobe:{id}             → WardrobeDefinition dict
    quality_score:{id}        → CharacterQualityScore dict
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.core.config import settings


def _hash(data: str) -> str:
    """SHA-256 hex digest, truncated to 16 chars."""
    return hashlib.sha256(data.encode()).hexdigest()[:16]


class CharacterCache:
    """Content-addressed cache for Character System artifacts."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self._base = settings.workspace_path / job_id / "character_cache"
        self._base.mkdir(parents=True, exist_ok=True)
        self._ttl = settings.research_cache_ttl_days * 86400

    # ---- Internal ----

    def _path(self, key: str) -> Path:
        safe = key.replace(":", "_").replace("/", "_")
        return self._base / f"{safe}.json"

    def _evict(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _get(self, key: str) -> dict | list | None:
        path = self._path(key)
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

    def _set(self, key: str, data: dict | list) -> None:
        path = self._path(key)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def clear(self) -> None:
        """Remove all cache entries for this job."""
        import shutil
        if self._base.exists():
            shutil.rmtree(self._base)
            self._base.mkdir(parents=True, exist_ok=True)

    # ---- Character Package ----

    def get_character_package(self, key: str) -> dict | None:
        return self._get(f"character_package:{key}")

    def set_character_package(self, key: str, data: dict) -> None:
        self._set(f"character_package:{key}", data)

    # ---- Individual Character Definition ----

    def get_character_definition(self, character_id: str) -> dict | None:
        return self._get(f"character_definition:{character_id}")

    def set_character_definition(self, character_id: str, data: dict) -> None:
        self._set(f"character_definition:{character_id}", data)

    # ---- Poses ----

    def get_poses(self, character_id: str) -> list[dict] | None:
        return self._get(f"pose_library:{character_id}")

    def set_poses(self, character_id: str, data: list[dict]) -> None:
        self._set(f"pose_library:{character_id}", data)

    # ---- Expressions ----

    def get_expressions(self, character_id: str) -> list[dict] | None:
        return self._get(f"expression_library:{character_id}")

    def set_expressions(self, character_id: str, data: list[dict]) -> None:
        self._set(f"expression_library:{character_id}", data)

    # ---- Wardrobe ----

    def get_wardrobe(self, wardrobe_id: str) -> dict | None:
        return self._get(f"wardrobe:{wardrobe_id}")

    def set_wardrobe(self, wardrobe_id: str, data: dict) -> None:
        self._set(f"wardrobe:{wardrobe_id}", data)

    # ---- Quality Score ----

    def get_quality_score(self, character_id: str) -> dict | None:
        return self._get(f"quality_score:{character_id}")

    def set_quality_score(self, character_id: str, data: dict) -> None:
        self._set(f"quality_score:{character_id}", data)

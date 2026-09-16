"""
Filesystem path helpers for job artifacts.

All job artifacts live under `workspace/<job_id>/`. Centralizing the
layout here means the API, pipeline, and renderer all agree on where
files go.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings


def job_dir(job_id: str) -> Path:
    """Return the workspace directory for a job, creating it if missing."""
    p = settings.workspace_path / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def stage_path(job_id: str, name: str, suffix: str = "json") -> Path:
    """Path for a stage's primary output file (e.g. `research.json`)."""
    return job_dir(job_id) / f"{name}.{suffix}"


def backgrounds_dir(job_id: str) -> Path:
    p = job_dir(job_id) / "backgrounds"
    p.mkdir(exist_ok=True)
    return p


def assets_dir(job_id: str | Path = "") -> Path:
    """Canonical assets directory (job-level or root-level).

    Job-level: assets/{job_id}/
    Root-level: assets/
    """
    if isinstance(job_id, str) and job_id:
        p = job_dir(job_id) / "assets"
    elif isinstance(job_id, Path):
        p = job_dir(job_id.name) / "assets" if job_id.name else job_id / "assets"
    else:
        p = settings.workspace_path / "assets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def asset_cache_dir(job_id: str) -> Path:
    p = job_dir(job_id) / "asset_cache"
    p.mkdir(exist_ok=True)
    return p


def env_dir(job_id: str, env_id: str, version: str = "1.0.0") -> Path:
    p = assets_dir(job_id) / "environments" / env_id / f"v{version.lstrip('v')}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def prop_dir(job_id: str, prop_id: str, version: str = "1.0.0") -> Path:
    p = assets_dir(job_id) / "props" / prop_id / f"v{version.lstrip('v')}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def shorts_dir(job_id: str) -> Path:
    p = job_dir(job_id) / "shorts"
    p.mkdir(exist_ok=True)
    return p


def thumbnails_dir(job_id: str) -> Path:
    p = job_dir(job_id) / "thumbnails"
    p.mkdir(exist_ok=True)
    return p


# ---- JSON I/O helpers (atomic writes to avoid half-written files) ----

def write_json(path: Path, data: Any) -> None:
    """Atomically write JSON. Writes to a temp file then renames."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    def _default(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=_default), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0

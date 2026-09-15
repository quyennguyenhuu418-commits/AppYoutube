"""
Stage-level caching.

Every stage produces a primary output file (e.g. `research.json`). If the
file already exists and is non-empty, the stage is skipped on subsequent
runs. This makes development fast: tweak a downstream stage without
re-paying for LLM calls.

Cache modes (from `settings.cache_mode`):
  - 'always': skip if output exists (default, fast iteration)
  - 'missing-only': same as 'always' for now (placeholder for a future
    "re-run if inputs changed" strategy)
  - 'never': always re-run
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings


def should_skip(output_path: Path) -> bool:
    """Return True if the stage should be skipped because its output already exists."""
    if settings.cache_mode == "never":
        return False
    return output_path.exists() and output_path.stat().st_size > 0

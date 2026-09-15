"""Integration test: run the full pipeline against the mock provider.

This is the golden test. If this passes, you can demo the system end-to-end
without any API keys.
"""
from __future__ import annotations

import os

# Force mock mode BEFORE importing settings.
os.environ["OPENAI_API_KEY"] = ""
os.environ["ELEVENLABS_API_KEY"] = ""

import pytest  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.paths import job_dir  # noqa: E402
from app.db import store  # noqa: E402
from app.pipeline.runner import STAGES  # noqa: E402
from app.pipeline.stages.base import StageContext  # noqa: E402
from app.schemas.job import JobCreateRequest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_workspace(tmp_path, monkeypatch) -> None:
    """Redirect the workspace into a temp dir so tests don't pollute the repo."""
    # workspace_path is a computed property derived from workspace_dir.
    monkeypatch.setattr(settings, "workspace_dir", tmp_path)
    monkeypatch.setattr(settings, "cache_mode", "always")


def test_full_pipeline_with_mock_providers() -> None:
    """Run all stages except render (which needs Node) and verify outputs."""
    req = JobCreateRequest(topic="How Did Ancient Humans Survive Deadly Winters?")
    detail = store.create_job(req)

    # Run only the first 9 stages (skip render + shorts to avoid Node/ffmpeg dep).
    ctx = StageContext(job_id=detail.id, topic=detail.topic, state={})
    for stage in STAGES[:9]:
        out = stage.run(ctx)
        ctx.state[stage.name] = out

    # Verify each expected file exists.
    jd = job_dir(detail.id)
    expected = {
        "research.json": jd / "research.json",
        "thesis.json": jd / "thesis.json",
        "titles.json": jd / "titles.json",
        "script.json": jd / "script.json",
        "storyboard.json": jd / "storyboard.json",
        "assets.json": jd / "assets.json",
        "narration.words.json": jd / "narration.words.json",
        "scene_definition.json": jd / "scene_definition.json",
    }
    for name, p in expected.items():
        assert p.exists(), f"missing {name}"
        assert p.stat().st_size > 0, f"empty {name}"

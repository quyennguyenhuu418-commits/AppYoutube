"""
PROMPT 12 — RenderJob canonical contract.

Extends the existing `JobDetail` model with a render-job lifecycle. The
existing model already carries `stages: list[StageInfo]` for the 11
upstream pipeline stages; RenderJob adds the per-render-job state
machine plus request fingerprinting.

Contract additions (PROMPT 12 §3, §4, §35):

    RenderJob                       — full per-job orchestrator view
    RenderJobStageInfo              — one orchestrator stage record
    RenderRequestFingerprint        — composite of upstream fingerprints
    compute_request_fingerprint()   — deterministic composite
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.orchestration.lifecycle import JobLifecycle, progress_for_stage

# ============================================================================
# Constraints
# ============================================================================

# Strict alphanumeric+dash+underscore job-id shape (matches what the
# existing job store emits and what the orchestrator accepts as a path
# segment). Rejects path-traversal characters such as '.' '/' '\'.
SafeId = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$"),
]


def _safe_id(value: str) -> str:
    """Library-side enforcement for SafeId (defence in depth)."""
    import re

    if not value or len(value) > 64:
        raise ValueError(f"invalid id length: {len(value)}")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid id characters: {value!r}")
    return value


# ============================================================================
# Stage info
# ============================================================================


class RenderJobStageInfo(BaseModel):
    """One orchestrator-stage record."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["preparing", "preflight", "rendering", "mastering", "qa", "finalizing"]
    label: str
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    note: str | None = None


# ============================================================================
# RenderJob
# ============================================================================


class RenderRequestFingerprint(BaseModel):
    """Composite fingerprint for a render request (PROMPT 12 §35).

    Combines fingerprints already produced by the upstream layers:
      - RenderPlan.fingerprint
      - RenderProfile.fingerprint
      - MasteringProfile.fingerprint
      - renderer_version
      - ffmpeg_version
      - upstream artifact fingerprints (list)
    """

    model_config = ConfigDict(extra="forbid")

    render_plan_fingerprint: str = Field(min_length=4, max_length=128)
    render_profile_fingerprint: str = Field(min_length=4, max_length=128)
    mastering_profile_fingerprint: str = Field(min_length=4, max_length=128)
    renderer_version: str = Field(min_length=1, max_length=64)
    ffmpeg_version: str = Field(min_length=1, max_length=64)
    upstream_fingerprints: list[str] = Field(default_factory=list)

    @property
    def composite(self) -> str:
        """Deterministic composite fingerprint.

        Uses the same canonical-JSON algorithm as P11 (sorted keys,
        no whitespace) to avoid inventing a parallel scheme.
        """
        payload = {
            "render_plan_fingerprint": self.render_plan_fingerprint,
            "render_profile_fingerprint": self.render_profile_fingerprint,
            "mastering_profile_fingerprint": self.mastering_profile_fingerprint,
            "renderer_version": self.renderer_version,
            "ffmpeg_version": self.ffmpeg_version,
            "upstream_fingerprints": sorted(self.upstream_fingerprints),
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "rj_" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]


def compute_request_fingerprint(
    *,
    render_plan_fingerprint: str,
    render_profile_fingerprint: str,
    mastering_profile_fingerprint: str,
    renderer_version: str,
    ffmpeg_version: str,
    upstream_fingerprints: list[str] | None = None,
) -> RenderRequestFingerprint:
    return RenderRequestFingerprint(
        render_plan_fingerprint=render_plan_fingerprint,
        render_profile_fingerprint=render_profile_fingerprint,
        mastering_profile_fingerprint=mastering_profile_fingerprint,
        renderer_version=renderer_version,
        ffmpeg_version=ffmpeg_version,
        upstream_fingerprints=list(upstream_fingerprints or []),
    )


class RenderJob(BaseModel):
    """Canonical render-job view (PROMPT 12 §4).

    Persisted at `<job_dir>/render_job.json` by the orchestrator.
    The existing `JobDetail` model already carries the upstream
    pipeline `stages[]`; this view layers the render-job lifecycle
    on top.
    """

    model_config = ConfigDict(extra="forbid")

    job_id: SafeId
    project_id: str = Field(min_length=1, max_length=128)
    topic: str = Field(min_length=1, max_length=300)

    lifecycle: JobLifecycle = JobLifecycle.QUEUED
    progress_pct: int = 0
    stage_progress: dict[str, int] = Field(default_factory=dict)
    stages: list[RenderJobStageInfo] = Field(default_factory=list)
    current_stage: str | None = None

    # Identity / provenance
    request_fingerprint: RenderRequestFingerprint | None = None
    renderer_version: str | None = None
    ffmpeg_version: str | None = None

    # Results
    render_plan_id: str | None = None
    render_plan_fingerprint: str | None = None
    raw_artifact_id: str | None = None
    final_artifact_id: str | None = None
    qa_report_id: str | None = None

    # Artifact paths (resolved via canonical metadata, never user input)
    workspace_dir: str | None = None
    final_mp4_path: str | None = None

    # Errors
    error: str | None = None
    error_stage: str | None = None

    # Timestamps
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None

    def is_terminal(self) -> bool:
        from app.orchestration.lifecycle import is_terminal as _it

        return _it(self.lifecycle)

    def progress_for(self, stage: JobLifecycle | str | None) -> int:
        """Stage-weighted progress."""
        if stage is None:
            return self.progress_pct
        if isinstance(stage, str):
            try:
                stage = JobLifecycle(stage)
            except ValueError:
                return self.progress_pct
        return progress_for_stage(stage)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict (model_dump + mode=json)."""
        d = self.model_dump(mode="json")
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RenderJob":
        return cls.model_validate(data)

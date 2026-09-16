"""
PROMPT 12 — Render Orchestration layer.

This package connects the existing deterministic media pipeline (P11
MasteringPipeline + P10 EditorialCompiler + P9 caption engine, etc.) to
the existing FastAPI + Next.js application surface.

Architecture (PROMPT 12 §2):

    Web UI
      ↓
    FastAPI Render API (/render/*)
      ↓
    RenderOrchestrator                    ← orchestration layer
      ↓
    ├─ Preflight validation (P11 preflight_validate)
    ├─ EditorialCompiler.compile()        (P10)
    ├─ MasteringPipeline                  (P11 — single canonical media path)
    └─ Atomic finalization (P11 finalize)

P12 must ORCHESTRATE the existing pipeline; it must NOT reimplement it.

Public API:
    RenderOrchestrator          — top-level orchestrator
    RenderJob                   — canonical render-job contract
    JobLifecycle                — explicit state machine enum
    can_transition()            — transition validation
    Build an orchestrator via RenderOrchestrator.from_settings().
"""
from __future__ import annotations

from .lifecycle import (
    JobLifecycle,
    STAGE_PROGRESS_WEIGHTS,
    STAGE_TO_PROGRESS,
    can_transition,
    is_terminal,
    progress_for_stage,
)
from .render_job import (
    RenderJob,
    RenderJobStageInfo,
    RenderRequestFingerprint,
    compute_request_fingerprint,
)
from .orchestrator import (
    OrchestrationResult,
    RenderOrchestrator,
    ensure_safe_id,
)

__all__ = [
    "JobLifecycle",
    "STAGE_PROGRESS_WEIGHTS",
    "STAGE_TO_PROGRESS",
    "can_transition",
    "is_terminal",
    "progress_for_stage",
    "RenderJob",
    "RenderJobStageInfo",
    "RenderRequestFingerprint",
    "compute_request_fingerprint",
    "OrchestrationResult",
    "RenderOrchestrator",
    "ensure_safe_id",
]

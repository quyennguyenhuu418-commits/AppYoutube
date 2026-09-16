"""
PROMPT 12 — Job Lifecycle state machine.

Canonical render-job lifecycle (PROMPT 12 §4, §5):

    QUEUED
      → PREPARING
    PREPARING
      → PREFLIGHT
      → FAILED
    PREFLIGHT
      → RENDERING
      → FAILED
    RENDERING
      → MASTERING
      → FAILED
    MASTERING
      → QA
      → FAILED
    QA
      → FINALIZING
      → FAILED
    FINALIZING
      → APPROVED
      → FAILED
    [any non-terminal]
      → CANCELLED

Terminal states: APPROVED, FAILED, CANCELLED.

Stage-weighted progress (PROMPT 12 §6). These values are
explicitly labelled as "stage progress" rather than physical render
progress, and they never claim precise frame percentages.

    PREPARING     5%
    PREFLIGHT    10%
    RENDERING    55%
    MASTERING    75%
    QA           90%
    FINALIZING   98%
    APPROVED    100%
"""
from __future__ import annotations

from enum import Enum


class JobLifecycle(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    PREFLIGHT = "preflight"
    RENDERING = "rendering"
    MASTERING = "mastering"
    QA = "qa"
    FINALIZING = "finalizing"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES: frozenset[JobLifecycle] = frozenset(
    {
        JobLifecycle.APPROVED,
        JobLifecycle.FAILED,
        JobLifecycle.CANCELLED,
    }
)


# Explicit transition map. Any transition not listed is invalid.
_ALLOWED: dict[JobLifecycle, frozenset[JobLifecycle]] = {
    JobLifecycle.QUEUED: frozenset({JobLifecycle.PREPARING, JobLifecycle.CANCELLED, JobLifecycle.FAILED}),
    JobLifecycle.PREPARING: frozenset({JobLifecycle.PREFLIGHT, JobLifecycle.CANCELLED, JobLifecycle.FAILED}),
    JobLifecycle.PREFLIGHT: frozenset({JobLifecycle.RENDERING, JobLifecycle.CANCELLED, JobLifecycle.FAILED}),
    JobLifecycle.RENDERING: frozenset({JobLifecycle.MASTERING, JobLifecycle.CANCELLED, JobLifecycle.FAILED}),
    JobLifecycle.MASTERING: frozenset({JobLifecycle.QA, JobLifecycle.CANCELLED, JobLifecycle.FAILED}),
    JobLifecycle.QA: frozenset({JobLifecycle.FINALIZING, JobLifecycle.CANCELLED, JobLifecycle.FAILED}),
    JobLifecycle.FINALIZING: frozenset({JobLifecycle.APPROVED, JobLifecycle.CANCELLED, JobLifecycle.FAILED}),
    JobLifecycle.APPROVED: frozenset(),
    JobLifecycle.FAILED: frozenset(),
    JobLifecycle.CANCELLED: frozenset(),
}


def can_transition(current: JobLifecycle, target: JobLifecycle) -> bool:
    """Return True iff the explicit lifecycle transition is allowed."""
    return target in _ALLOWED.get(current, frozenset())


def is_terminal(state: JobLifecycle) -> bool:
    return state in TERMINAL_STATES


# Stage-weighted progress (PROMPT 12 §6)
# Exposed as a function so the orchestrator can produce stable,
# reproducible values for any lifecycle state.
STAGE_PROGRESS_WEIGHTS: dict[JobLifecycle, int] = {
    JobLifecycle.QUEUED: 0,
    JobLifecycle.PREPARING: 5,
    JobLifecycle.PREFLIGHT: 10,
    JobLifecycle.RENDERING: 55,
    JobLifecycle.MASTERING: 75,
    JobLifecycle.QA: 90,
    JobLifecycle.FINALIZING: 98,
    JobLifecycle.APPROVED: 100,
    JobLifecycle.FAILED: 100,
    JobLifecycle.CANCELLED: 100,
}

# Stages that count toward progress (i.e. not terminal AND not QUEUED).
STAGE_TO_PROGRESS: dict[JobLifecycle, int] = {
    JobLifecycle.PREPARING: 5,
    JobLifecycle.PREFLIGHT: 10,
    JobLifecycle.RENDERING: 55,
    JobLifecycle.MASTERING: 75,
    JobLifecycle.QA: 90,
    JobLifecycle.FINALIZING: 98,
}


def progress_for_stage(stage: JobLifecycle) -> int:
    """Return the stage-weighted progress percentage for a given state.

    These values are explicit stage progress (NOT physical frame
    progress). They are documented as such in PROMPT 12 §6.
    """
    return int(STAGE_PROGRESS_WEIGHTS.get(stage, 0))

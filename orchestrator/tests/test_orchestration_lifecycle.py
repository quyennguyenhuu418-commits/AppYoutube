"""
PROMPT 12 — Orchestration lifecycle + state machine tests.

Covers:
  * JobLifecycle enum members
  * can_transition matrix
  * is_terminal classification
  * Stage-weighted progress values
  * RenderJob + RenderRequestFingerprint serialisation
  * compute_request_fingerprint determinism
  * Invalid transition rejection
"""
from __future__ import annotations

import pytest
from app.orchestration.lifecycle import (
    JobLifecycle,
    STAGE_PROGRESS_WEIGHTS,
    can_transition,
    is_terminal,
    progress_for_stage,
)
from app.orchestration.render_job import (
    RenderJob,
    RenderRequestFingerprint,
    compute_request_fingerprint,
)
from datetime import datetime, timezone


# ============================================================================
# JobLifecycle enum
# ============================================================================


def test_lifecycle_has_ten_members():
    assert len(JobLifecycle) == 10
    assert JobLifecycle.QUEUED.value == "queued"
    assert JobLifecycle.PREPARING.value == "preparing"
    assert JobLifecycle.PREFLIGHT.value == "preflight"
    assert JobLifecycle.RENDERING.value == "rendering"
    assert JobLifecycle.MASTERING.value == "mastering"
    assert JobLifecycle.QA.value == "qa"
    assert JobLifecycle.FINALIZING.value == "finalizing"
    assert JobLifecycle.APPROVED.value == "approved"
    assert JobLifecycle.FAILED.value == "failed"
    assert JobLifecycle.CANCELLED.value == "cancelled"


def test_terminal_states():
    for state in (JobLifecycle.APPROVED, JobLifecycle.FAILED, JobLifecycle.CANCELLED):
        assert is_terminal(state), f"{state.value} should be terminal"
    for state in (
        JobLifecycle.QUEUED, JobLifecycle.PREPARING, JobLifecycle.PREFLIGHT,
        JobLifecycle.RENDERING, JobLifecycle.MASTERING, JobLifecycle.QA,
        JobLifecycle.FINALIZING,
    ):
        assert not is_terminal(state), f"{state.value} should not be terminal"


# ============================================================================
# can_transition
# ============================================================================


def test_forward_progression_valid():
    chain = [
        JobLifecycle.QUEUED, JobLifecycle.PREPARING, JobLifecycle.PREFLIGHT,
        JobLifecycle.RENDERING, JobLifecycle.MASTERING, JobLifecycle.QA,
        JobLifecycle.FINALIZING, JobLifecycle.APPROVED,
    ]
    for i in range(len(chain) - 1):
        assert can_transition(chain[i], chain[i + 1]), \
            f"{chain[i].value} → {chain[i+1].value} should be valid"


def test_skipping_states_rejected():
    # Cannot skip PREPARING → RENDERING
    assert not can_transition(JobLifecycle.QUEUED, JobLifecycle.RENDERING)
    # Cannot skip PREFLIGHT → MASTERING
    assert not can_transition(JobLifecycle.PREFLIGHT, JobLifecycle.MASTERING)
    # Cannot skip QA → APPROVED (must go via FINALIZING)
    assert not can_transition(JobLifecycle.QA, JobLifecycle.APPROVED)


def test_backward_transitions_rejected():
    assert not can_transition(JobLifecycle.RENDERING, JobLifecycle.PREFLIGHT)
    assert not can_transition(JobLifecycle.QA, JobLifecycle.MASTERING)


def test_terminal_cannot_transition():
    for terminal in (JobLifecycle.APPROVED, JobLifecycle.FAILED, JobLifecycle.CANCELLED):
        for target in JobLifecycle:
            assert not can_transition(terminal, target), \
                f"terminal {terminal.value} → {target.value} must be rejected"


def test_cancellable_from_any_non_terminal():
    non_terminals = [
        JobLifecycle.QUEUED, JobLifecycle.PREPARING, JobLifecycle.PREFLIGHT,
        JobLifecycle.RENDERING, JobLifecycle.MASTERING, JobLifecycle.QA,
        JobLifecycle.FINALIZING,
    ]
    for state in non_terminals:
        assert can_transition(state, JobLifecycle.CANCELLED), \
            f"cancellation must be allowed from {state.value}"


def test_failed_from_any_non_terminal():
    non_terminals = [
        JobLifecycle.QUEUED, JobLifecycle.PREPARING, JobLifecycle.PREFLIGHT,
        JobLifecycle.RENDERING, JobLifecycle.MASTERING, JobLifecycle.QA,
        JobLifecycle.FINALIZING,
    ]
    for state in non_terminals:
        assert can_transition(state, JobLifecycle.FAILED), \
            f"failure must be reachable from {state.value}"


# ============================================================================
# Stage-weighted progress
# ============================================================================


def test_stage_progress_values_documented():
    assert STAGE_PROGRESS_WEIGHTS[JobLifecycle.QUEUED] == 0
    assert STAGE_PROGRESS_WEIGHTS[JobLifecycle.PREPARING] == 5
    assert STAGE_PROGRESS_WEIGHTS[JobLifecycle.PREFLIGHT] == 10
    assert STAGE_PROGRESS_WEIGHTS[JobLifecycle.RENDERING] == 55
    assert STAGE_PROGRESS_WEIGHTS[JobLifecycle.MASTERING] == 75
    assert STAGE_PROGRESS_WEIGHTS[JobLifecycle.QA] == 90
    assert STAGE_PROGRESS_WEIGHTS[JobLifecycle.FINALIZING] == 98
    assert STAGE_PROGRESS_WEIGHTS[JobLifecycle.APPROVED] == 100


def test_progress_for_stage_function():
    assert progress_for_stage(JobLifecycle.QUEUED) == 0
    assert progress_for_stage(JobLifecycle.PREPARING) == 5
    assert progress_for_stage(JobLifecycle.RENDERING) == 55
    assert progress_for_stage(JobLifecycle.APPROVED) == 100


# ============================================================================
# RenderJob
# ============================================================================


def test_render_job_minimum_required():
    job = RenderJob(
        job_id="job_abc",
        project_id="proj_x",
        topic="Test",
        created_at=datetime.now(timezone.utc),
    )
    assert job.job_id == "job_abc"
    assert job.lifecycle == JobLifecycle.QUEUED
    assert job.progress_pct == 0
    assert job.is_terminal() is False


def test_render_job_safe_id_rejects_path_traversal():
    with pytest.raises(Exception):
        RenderJob(
            job_id="../../etc/passwd",
            project_id="p",
            topic="t",
            created_at=datetime.now(timezone.utc),
        )


def test_render_job_safe_id_rejects_empty():
    with pytest.raises(Exception):
        RenderJob(
            job_id="",
            project_id="p",
            topic="t",
            created_at=datetime.now(timezone.utc),
        )


def test_render_job_safe_id_rejects_special_chars():
    for bad in ["a/b", "a\\b", "a.b", "a b", "a;b", "a&b", "a*b"]:
        with pytest.raises(Exception):
            RenderJob(
                job_id=bad,
                project_id="p",
                topic="t",
                created_at=datetime.now(timezone.utc),
            )


# ============================================================================
# RenderRequestFingerprint
# ============================================================================


def test_request_fingerprint_deterministic():
    fp1 = compute_request_fingerprint(
        render_plan_fingerprint="rp_fp_1234",
        render_profile_fingerprint="rndr_fp_5678",
        mastering_profile_fingerprint="mstr_fp_9012",
        renderer_version="remotion-1.0",
        ffmpeg_version="ffmpeg-9.0",
        upstream_fingerprints=["audio_fp_1", "audio_fp_2"],
    )
    fp2 = compute_request_fingerprint(
        render_plan_fingerprint="rp_fp_1234",
        render_profile_fingerprint="rndr_fp_5678",
        mastering_profile_fingerprint="mstr_fp_9012",
        renderer_version="remotion-1.0",
        ffmpeg_version="ffmpeg-9.0",
        upstream_fingerprints=["audio_fp_2", "audio_fp_1"],  # order swapped
    )
    assert fp1.composite == fp2.composite  # sorted internally


def test_request_fingerprint_changes_with_input():
    base = compute_request_fingerprint(
        render_plan_fingerprint="rp_fp_1234",
        render_profile_fingerprint="rndr_fp_5678",
        mastering_profile_fingerprint="mstr_fp_9012",
        renderer_version="remotion-1.0",
        ffmpeg_version="ffmpeg-9.0",
    )
    changed = compute_request_fingerprint(
        render_plan_fingerprint="rp_fp_9999",  # different
        render_profile_fingerprint="rndr_fp_5678",
        mastering_profile_fingerprint="mstr_fp_9012",
        renderer_version="remotion-1.0",
        ffmpeg_version="ffmpeg-9.0",
    )
    assert base.composite != changed.composite


def test_request_fingerprint_has_rj_prefix():
    fp = compute_request_fingerprint(
        render_plan_fingerprint="aaaa",
        render_profile_fingerprint="bbbb",
        mastering_profile_fingerprint="cccc",
        renderer_version="d",
        ffmpeg_version="e",
    )
    assert fp.composite.startswith("rj_")
    assert len(fp.composite) > 10


def test_request_fingerprint_minimum_lengths():
    # Empty / short strings should fail validation
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        RenderRequestFingerprint(
            render_plan_fingerprint="x",  # too short (< min_length=1 actually)
            render_profile_fingerprint="b",
            mastering_profile_fingerprint="c",
            renderer_version="d",
            ffmpeg_version="e",
        )
    # Empty strings should fail
    with pytest.raises(pydantic.ValidationError):
        RenderRequestFingerprint(
            render_plan_fingerprint="",
            render_profile_fingerprint="b",
            mastering_profile_fingerprint="c",
            renderer_version="d",
            ffmpeg_version="e",
        )


# ============================================================================
# RenderJob lifecycle interaction
# ============================================================================


def test_render_job_is_terminal():
    job = RenderJob(
        job_id="job_t",
        project_id="p",
        topic="t",
        lifecycle=JobLifecycle.APPROVED,
        created_at=datetime.now(timezone.utc),
    )
    assert job.is_terminal()
    job.lifecycle = JobLifecycle.FAILED
    assert job.is_terminal()
    job.lifecycle = JobLifecycle.RENDERING
    assert not job.is_terminal()


def test_render_job_progress_for_helper():
    job = RenderJob(
        job_id="job_p",
        project_id="p",
        topic="t",
        created_at=datetime.now(timezone.utc),
    )
    assert job.progress_for(JobLifecycle.MASTERING) == 75
    assert job.progress_for("mastering") == 75
    assert job.progress_for(None) == 0  # uses current

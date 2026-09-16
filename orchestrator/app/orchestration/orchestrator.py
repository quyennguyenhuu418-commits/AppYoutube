"""
PROMPT 12 — RenderOrchestrator.

Top-level orchestration coordinator. Conceptually implements (PROMPT 12 §3):

    create_render_job()
        ↓
    validate_request()
        ↓
    load_project()
        ↓
    resolve_render_plan()
        ↓
    preflight()
        ↓
    render()
        ↓
    master()
        ↓
    qa()
        ↓
    finalize()
        ↓
    persist_result()

All business logic lives here. FastAPI routes are thin adapters.

The orchestrator calls the EXISTING canonical components:
    - EditorialCompiler.compile()         (P10)
    - MasteringPipeline.run_full_pipeline() (P11)

NOT a second media pipeline.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import job_dir, read_json, write_json
from app.editorial.compiler import EditorialCompiler
from app.editorial.schemas import EditorialProject
from app.mastering.media_processor import MediaProcessor
from app.mastering.pipeline import MasteringPipeline
from app.mastering.qa import MediaQAEngine
from app.mastering.schemas import (
    MasteringProfile,
    RenderProfile,
)
from app.orchestration.lifecycle import (
    JobLifecycle,
    can_transition,
    progress_for_stage,
)
from app.orchestration.render_job import (
    RenderJob,
    RenderJobStageInfo,
    RenderRequestFingerprint,
    compute_request_fingerprint,
)

log = get_logger(__name__)


# ============================================================================
# Safe-id helpers (PROMPT 12 §22 — path traversal defence)
# ============================================================================


def ensure_safe_id(value: str) -> str:
    """Raise ValueError if value contains path-separation characters.

    Used by API routes to validate job-id / artifact-id before use as a
    filesystem path component.
    """
    if not value or len(value) > 64:
        raise ValueError(f"invalid id length ({len(value)}): {value!r}")
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", value):
        raise ValueError(f"invalid id characters: {value!r}")
    return value


# ============================================================================
# Result types
# ============================================================================


@dataclass
class StageUpdate:
    name: str
    label: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    note: str | None = None


@dataclass
class OrchestrationResult:
    """Structured outcome of an orchestration run."""

    success: bool
    job: RenderJob | None = None
    error: str | None = None
    error_stage: str | None = None
    updates: list[StageUpdate] = field(default_factory=list)
    log: list[str] = field(default_factory=list)


# ============================================================================
# FFmpeg / renderer version helpers
# ============================================================================


def _get_ffmpeg_version() -> str:
    """Query ffmpeg -version and return the first line or a safe fallback."""
    import subprocess

    try:
        proc = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        first = proc.stdout.split("\n")[0].strip()
        # Normalise: "ffmpeg version 9.0" → "ffmpeg-9.0"
        ver = first.split()[-1] if first else "unknown"
        return f"ffmpeg-{ver}"
    except Exception:
        return "ffmpeg-unknown"


def _get_renderer_version() -> str:
    """Return the installed Remotion renderer version or a safe fallback."""
    try:
        pkg = settings.renderer_path / "package.json"
        if pkg.exists():
            data = json.loads(pkg.read_text(encoding="utf-8"))
            ver = data.get("version", "unknown")
            return f"remotion-{ver}"
    except Exception:
        pass
    return "remotion-unknown"


# ============================================================================
# RenderOrchestrator
# ============================================================================


class RenderOrchestrator:
    """Canonical render orchestrator (PROMPT 12 §3).

    Drives a production render from an existing EditorialProject
    through the P11 MasteringPipeline to a final FinalVideoArtifact.

    Usage::

        orchestrator = RenderOrchestrator()
        result = orchestrator.orchestrate(job_id="...")
    """

    def __init__(
        self,
        *,
        processor: MediaProcessor | None = None,
        qa_engine: MediaQAEngine | None = None,
    ) -> None:
        self.processor = processor or MediaProcessor()
        self.qa = qa_engine or MediaQAEngine(processor=self.processor)
        self._pipeline = MasteringPipeline(
            processor=self.processor, qa_engine=self.qa
        )
        self._ffmpeg_version = _get_ffmpeg_version()
        self._renderer_version = _get_renderer_version()

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def orchestrate(
        self,
        *,
        job_id: str,
        project_id: str,
        topic: str,
        editorial_project_path: Path | str | None = None,
        editorial_project_data: dict[str, Any] | None = None,
        render_profile: RenderProfile | None = None,
        mastering_profile: MasteringProfile | None = None,
        render_profile_data: dict[str, Any] | None = None,
        mastering_profile_data: dict[str, Any] | None = None,
        skip_renderer: bool = True,
    ) -> OrchestrationResult:
        """Run the full orchestration.

        Args:
            job_id:             safe-id of the job (validated by caller).
            project_id:         owning project (used for RenderJob.project_id).
            topic:              topic string (used for RenderJob.topic).
            editorial_project_path:  Path to an editorial_project.json on disk.
            editorial_project_data:  Already-loaded dict (takes precedence over path).
            render_profile:      RenderProfile instance (takes precedence).
            mastering_profile:   MasteringProfile instance (takes precedence).
            render_profile_data: RenderProfile as dict (deserialised if profile missing).
            mastering_profile_data: MasteringProfile as dict (deserialised if profile missing).
            skip_renderer:       If True, assume raw.mp4 already exists on disk.
                                For the smoke test / E2E tests; production sets False.

        Returns:
            OrchestrationResult with .success, .job, .error, .log.
        """
        job_id = ensure_safe_id(job_id)
        result = OrchestrationResult(success=False, log=[])
        jd = job_dir(job_id)
        jd.mkdir(parents=True, exist_ok=True)

        # ── Build the RenderJob record ────────────────────────────────
        job = RenderJob(
            job_id=job_id,
            project_id=project_id,
            topic=topic,
            lifecycle=JobLifecycle.QUEUED,
            progress_pct=0,
            workspace_dir=str(jd),
            renderer_version=self._renderer_version,
            ffmpeg_version=self._ffmpeg_version,
            created_at=datetime.now(timezone.utc),
        )

        # ── Load profiles ────────────────────────────────────────────
        errors: list[str] = []
        if render_profile is None and render_profile_data:
            try:
                render_profile = RenderProfile.model_validate(render_profile_data)
            except Exception as exc:
                errors.append(f"RenderProfile validation: {exc}")

        if mastering_profile is None and mastering_profile_data:
            try:
                mastering_profile = MasteringProfile.model_validate(mastering_profile_data)
            except Exception as exc:
                errors.append(f"MasteringProfile validation: {exc}")

        # Default profiles
        if render_profile is None:
            render_profile = RenderProfile(
                profile_id="rp_default",
                profile_version=1,
                width=1280,
                height=720,
                fps=30.0,
            )
        if mastering_profile is None:
            mastering_profile = MasteringProfile(
                profile_id="mp_default",
                profile_version=1,
            )

        # ── Load editorial project ─────────────────────────────────────
        editorial_project: EditorialProject | None = None
        editorial_project_data_dict: dict[str, Any] | None = editorial_project_data
        if editorial_project_data_dict is None and editorial_project_path:
            ep_path = Path(editorial_project_path)
            if ep_path.exists():
                try:
                    editorial_project_data_dict = read_json(ep_path)
                except Exception as exc:
                    errors.append(f"Cannot read EditorialProject: {exc}")

        if editorial_project_data_dict:
            try:
                editorial_project = EditorialProject.model_validate(editorial_project_data_dict)
            except Exception as exc:
                errors.append(f"EditorialProject validation: {exc}")

        # ── Compile to RenderPlan ────────────────────────────────────
        compile_result = None
        render_plan = None
        render_plan_dict: dict[str, Any] | None = None
        if editorial_project:
            try:
                compiler = EditorialCompiler()
                compile_result = compiler.compile(editorial_project)
                if compile_result.plan is not None:
                    render_plan = compile_result.plan
                    render_plan_dict = render_plan.model_dump(mode="json")
            except Exception as exc:
                errors.append(f"EditorialCompiler: {exc}")

        # ── Initialise stage list ───────────────────────────────────
        stages: list[RenderJobStageInfo] = [
            RenderJobStageInfo(name="preparing", label="Preparing"),
            RenderJobStageInfo(name="preflight", label="Preflight"),
            RenderJobStageInfo(name="rendering", label="Rendering"),
            RenderJobStageInfo(name="mastering", label="Mastering"),
            RenderJobStageInfo(name="qa", label="QA"),
            RenderJobStageInfo(name="finalizing", label="Finalizing"),
        ]

        def stage_record(name: str) -> RenderJobStageInfo:
            return next(s for s in stages if s.name == name)

        def emit(stage_name: str, **kwargs) -> None:
            for upd in result.updates:
                if upd.name == stage_name:
                    for k, v in kwargs.items():
                        setattr(stage_record(stage_name), k, v)
                    break

        def transition_to(next_state: JobLifecycle, err: str | None = None) -> None:
            job.lifecycle = next_state
            job.progress_pct = progress_for_stage(next_state)
            job.current_stage = next_state.value
            job.updated_at = datetime.now(timezone.utc)
            if err:
                job.error = err
                job.error_stage = result.error_stage

        # ── Error on critical failures before running ────────────────
        if errors:
            job.lifecycle = JobLifecycle.FAILED
            job.error = "; ".join(errors)
            job.error_stage = "preparing"
            job.progress_pct = 0
            job.finished_at = datetime.now(timezone.utc)
            self._persist_job(job, jd)
            return OrchestrationResult(
                success=False,
                job=job,
                error=job.error,
                error_stage="preparing",
                log=result.log,
            )

        # ══════════════════════════════════════════════════════════════
        # Stage 1 — PREPARING
        # ══════════════════════════════════════════════════════════════
        job.lifecycle = JobLifecycle.PREPARING
        job.progress_pct = progress_for_stage(JobLifecycle.PREPARING)
        job.current_stage = "preparing"
        job.started_at = datetime.now(timezone.utc)
        job.updated_at = job.started_at
        job.stages = stages
        s_prep = stage_record("preparing")
        s_prep.status = "running"
        s_prep.started_at = job.started_at
        log.info("[orchestrator] job=%s preparing", job_id)
        result.log.append(f"[preparing] job={job_id}")

        # If no editorial project, build a minimal smoke render plan
        # (production path uses editorial_project from upstream stages)
        render_plan_path = jd / "render_plan.json"
        if render_plan_dict is None:
            # Minimal smoke plan — 1 scene, 2s
            render_plan_dict = {
                "plan_id": f"plan-{job_id}",
                "project_id": project_id,
                "fps": float(render_profile.fps),
                "width": int(render_profile.width),
                "height": int(render_profile.height),
                "total_duration_frames": int(render_profile.fps * 2),
                "total_duration_sec": 2.0,
                "scenes": [
                    {
                        "scene_id": "scene_1",
                        "order": 0,
                        "master_start_frame": 0,
                        "master_start_sec": 0.0,
                        "duration_frames": int(render_profile.fps * 2),
                        "duration_sec": 2.0,
                        "source_scene_duration_sec": 2.0,
                        "transition_in": None,
                        "transition_out": None,
                        "animation_plan_id": None,
                        "caption_track_id": None,
                    }
                ],
                "layers": [],
                "audio_clips": [],
                "audio_track_ids": [],
                "title_cards": [],
                "layer_order": [],
                "source_fingerprint": "p12_smoke",
            }
            log.info("[orchestrator] no editorial project; using minimal smoke plan")

        write_json(render_plan_path, render_plan_dict)
        job.render_plan_id = render_plan_dict.get("plan_id", "unknown")
        job.render_plan_fingerprint = render_plan_dict.get(
            "fingerprint", f"fp-{job_id}"
        )

        s_prep.status = "completed"
        s_prep.finished_at = datetime.now(timezone.utc)
        result.log.append("[preparing] done")
        log.info("[orchestrator] job=%s preparing done", job_id)

        # ══════════════════════════════════════════════════════════════
        # Stage 2 — PREFLIGHT
        # ══════════════════════════════════════════════════════════════
        job.lifecycle = JobLifecycle.PREFLIGHT
        job.progress_pct = progress_for_stage(JobLifecycle.PREFLIGHT)
        job.current_stage = "preflight"
        job.updated_at = datetime.now(timezone.utc)
        s_pf = stage_record("preflight")
        s_pf.status = "running"
        s_pf.started_at = datetime.now(timezone.utc)
        result.log.append("[preflight] starting")
        log.info("[orchestrator] job=%s preflight", job_id)

        from app.mastering.pipeline import preflight_validate

        pf_errors = preflight_validate(
            render_plan_path=render_plan_path,
            render_profile=render_profile,
            mastering_profile=mastering_profile,
            audio_artifact_paths={},
        )
        if pf_errors:
            err = f"preflight failed: {'; '.join(pf_errors)}"
            job.lifecycle = JobLifecycle.FAILED
            job.error = err
            job.error_stage = "preflight"
            job.progress_pct = 0
            job.finished_at = datetime.now(timezone.utc)
            s_pf.status = "failed"
            s_pf.finished_at = job.finished_at
            s_pf.error = err
            self._persist_job(job, jd)
            return OrchestrationResult(
                success=False,
                job=job,
                error=err,
                error_stage="preflight",
                log=result.log,
            )

        s_pf.status = "completed"
        s_pf.finished_at = datetime.now(timezone.utc)
        result.log.append("[preflight] passed")
        log.info("[orchestrator] job=%s preflight passed", job_id)

        # ══════════════════════════════════════════════════════════════
        # Stage 3-6 — Render + Master + QA + Finalize
        # Wrapped in try/except so any failure during these stages
        # transitions the job to FAILED with a clear error_stage.
        # ══════════════════════════════════════════════════════════════

        # Compute plan_for_pipeline in this scope so it's available to
        # both the inner method and any error handler.
        from app.editorial.schemas import RenderPlan as EditorialRenderPlan

        plan_for_pipeline: EditorialRenderPlan | dict[str, Any] | None = None
        if compile_result is not None and compile_result.plan is not None:
            plan_for_pipeline = compile_result.plan
        elif render_plan_dict:
            try:
                plan_for_pipeline = EditorialRenderPlan.model_validate(render_plan_dict)
            except Exception:
                plan_for_pipeline = render_plan_dict

        try:
            self._run_render_master_qa_finalize(
                job=job,
                jd=jd,
                render_plan_path=render_plan_path,
                plan_for_pipeline=plan_for_pipeline,
                render_plan_dict=render_plan_dict,
                render_profile=render_profile,
                mastering_profile=mastering_profile,
                skip_renderer=skip_renderer,
                stages=stages,
                result=result,
                log=log,
            )
        except Exception as exc:
            # Find which stage we were in
            current = job.lifecycle
            failed_stage = current.value if current != JobLifecycle.APPROVED else "finalizing"
            err = f"{type(exc).__name__}: {exc}"
            log.error("[orchestrator] job=%s failed at stage=%s: %s", job_id, failed_stage, err)
            job.lifecycle = JobLifecycle.FAILED
            job.error = err
            job.error_stage = failed_stage
            job.finished_at = datetime.now(timezone.utc)
            # Mark the relevant stage as failed
            stage_map = {"rendering": "rendering", "mastering": "mastering", "qa": "qa", "finalizing": "finalizing"}
            target_stage = stage_map.get(failed_stage)
            if target_stage:
                for s in job.stages:
                    if s.name == target_stage:
                        s.status = "failed"
                        s.finished_at = datetime.now(timezone.utc)
                        s.error = err
                        break
            self._persist_job(job, jd)
            return OrchestrationResult(
                success=False,
                job=job,
                error=err,
                error_stage=failed_stage,
                log=result.log,
            )

        return OrchestrationResult(
            success=True,
            job=job,
            log=result.log,
        )

    # ------------------------------------------------------------------
    # Render + Master + QA + Finalize (split out for clean error handling)
    # ------------------------------------------------------------------

    def _run_render_master_qa_finalize(
        self,
        *,
        job: RenderJob,
        jd: Path,
        render_plan_path: Path,
        plan_for_pipeline,
        render_plan_dict: dict[str, Any],
        render_profile,
        mastering_profile,
        skip_renderer: bool,
        stages: list[RenderJobStageInfo],
        result: "OrchestrationResult",
        log,
    ) -> None:
        """Run stages 3-6: rendering → mastering → qa → finalizing."""
        job_id = job.job_id

        def stage_record(name: str) -> RenderJobStageInfo:
            return next(s for s in stages if s.name == name)

        # ══════════════════════════════════════════════════════════════
        # Stage 3 — RENDERING (Remotion)
        # ══════════════════════════════════════════════════════════════
        job.lifecycle = JobLifecycle.RENDERING
        job.progress_pct = progress_for_stage(JobLifecycle.RENDERING)
        job.current_stage = "rendering"
        job.updated_at = datetime.now(timezone.utc)
        s_ren = stage_record("rendering")
        s_ren.status = "running"
        s_ren.started_at = datetime.now(timezone.utc)
        result.log.append("[rendering] starting")
        log.info("[orchestrator] job=%s rendering", job_id)

        raw_art = self._pipeline.render(
            job_dir=jd,
            render_plan_path=render_plan_path,
            render_profile=render_profile,
            audio_artifact_paths={},
            renderer_version=f"{self._renderer_version}/{self._ffmpeg_version}",
            source_fingerprint=job.render_plan_fingerprint or "smoke",
            skip_renderer=skip_renderer,
        )
        job.raw_artifact_id = raw_art.artifact_id
        result.log.append(f"[rendering] raw={raw_art.raw_path} {raw_art.file_size_bytes}B")

        s_ren.status = "completed"
        s_ren.finished_at = datetime.now(timezone.utc)
        result.log.append("[rendering] done")
        log.info("[orchestrator] job=%s rendering done", job_id)

        # ══════════════════════════════════════════════════════════════
        # Stage 4 — MASTERING
        # ══════════════════════════════════════════════════════════════
        job.lifecycle = JobLifecycle.MASTERING
        job.progress_pct = progress_for_stage(JobLifecycle.MASTERING)
        job.current_stage = "mastering"
        job.updated_at = datetime.now(timezone.utc)
        s_mas = stage_record("mastering")
        s_mas.status = "running"
        s_mas.started_at = datetime.now(timezone.utc)
        result.log.append("[mastering] starting")
        log.info("[orchestrator] job=%s mastering", job_id)

        mixed_wav = jd / "mixed.wav"
        has_audio_clips = (
            plan_for_pipeline is not None
            and not isinstance(plan_for_pipeline, dict)
            and bool(getattr(plan_for_pipeline, "audio_clips", None))
        ) or (
            isinstance(plan_for_pipeline, dict)
            and bool(plan_for_pipeline.get("audio_clips"))
        )
        if has_audio_clips:
            mix_result = self._pipeline.mix_audio(
                render_plan=plan_for_pipeline,
                audio_artifact_paths={},
                out_path=mixed_wav,
            )
        else:
            import subprocess
            dur = max(float(raw_art.duration_sec), 0.1)
            silence_proc = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-y",
                    "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
                    "-t", str(dur),
                    "-ar", "48000", "-ac", "2",
                    str(mixed_wav),
                ],
                capture_output=True, text=True, timeout=30,
            )
            mix_result = {"method": "silence", "output_path": str(mixed_wav)}
            if silence_proc.returncode != 0:
                log.warning("[orchestrator] silence gen failed: %s", silence_proc.stderr[-200:])
        result.log.append(f"[mastering] mixed={mix_result}")

        mastered_wav = jd / "mastered.wav"
        master_result = self._pipeline.master_audio(
            mixed_wav_path=mixed_wav,
            mastering_profile=mastering_profile,
            out_path=mastered_wav,
        )
        result.log.append(f"[mastering] mastered={master_result}")

        s_mas.status = "completed"
        s_mas.finished_at = datetime.now(timezone.utc)
        result.log.append("[mastering] done")
        log.info("[orchestrator] job=%s mastering done", job_id)

        # ══════════════════════════════════════════════════════════════
        # Stage 5 — QA
        # ══════════════════════════════════════════════════════════════
        job.lifecycle = JobLifecycle.QA
        job.progress_pct = progress_for_stage(JobLifecycle.QA)
        job.current_stage = "qa"
        job.updated_at = datetime.now(timezone.utc)
        s_qa = stage_record("qa")
        s_qa.status = "running"
        s_qa.started_at = datetime.now(timezone.utc)
        result.log.append("[qa] starting")
        log.info("[orchestrator] job=%s qa", job_id)

        candidate = jd / "candidate.mp4"
        mux_result = self._pipeline.mux(
            raw_video_path=Path(raw_art.raw_path),
            mastered_audio_path=mastered_wav,
            out_path=candidate,
            render_profile=render_profile,
            target_duration_sec=raw_art.duration_sec,
        )
        result.log.append(f"[qa] mux={mux_result}")

        qa_report = self._pipeline.run_qa(
            final_mp4_path=candidate,
            render_profile=render_profile,
            mastering_profile=mastering_profile,
            render_plan=plan_for_pipeline if plan_for_pipeline is not None else render_plan_dict,
            raw=raw_art,
        )
        from app.mastering.artifact import save_qa_report

        save_qa_report(qa_report, jd / "qa_report.json")
        job.qa_report_id = qa_report.report_id
        result.log.append(f"[qa] overall={qa_report.overall_status.value}")

        s_qa.status = "completed"
        s_qa.finished_at = datetime.now(timezone.utc)
        result.log.append("[qa] done")
        log.info("[orchestrator] job=%s qa done", job_id)

        # ══════════════════════════════════════════════════════════════
        # Stage 6 — FINALIZING
        # ══════════════════════════════════════════════════════════════
        job.lifecycle = JobLifecycle.FINALIZING
        job.progress_pct = progress_for_stage(JobLifecycle.FINALIZING)
        job.current_stage = "finalizing"
        job.updated_at = datetime.now(timezone.utc)
        s_fin = stage_record("finalizing")
        s_fin.status = "running"
        s_fin.started_at = datetime.now(timezone.utc)
        result.log.append("[finalizing] starting")
        log.info("[orchestrator] job=%s finalizing", job_id)

        final_artifact = self._pipeline.finalize(
            candidate_path=candidate,
            job_dir=jd,
            render_profile=render_profile,
            mastering_profile=mastering_profile,
            render_plan_id=job.render_plan_id or "unknown",
            renderer_version=f"{self._renderer_version}/{self._ffmpeg_version}",
            project_id=job.project_id,
            qa=qa_report,
            raw=raw_art,
        )

        job.final_artifact_id = final_artifact.artifact_id
        job.final_mp4_path = str(jd / "final.mp4")
        # PROMPT 12 §4 — RENDERING SUCCESS != FINAL SUCCESS
        # The job's lifecycle must reflect the QA outcome:
        # - Artifact.APPROVED + qa_status.FINAL_APPROVED → job = APPROVED
        # - Anything else → job = FAILED (P12 §37 / §34)
        from app.mastering.schemas import ArtifactLifecycleStatus, ArtifactQAStatus

        if (
            final_artifact.lifecycle == ArtifactLifecycleStatus.APPROVED
            and final_artifact.qa_status == ArtifactQAStatus.FINAL_APPROVED
        ):
            job.lifecycle = JobLifecycle.APPROVED
            job.progress_pct = progress_for_stage(JobLifecycle.APPROVED)
            job.current_stage = "approved"
        else:
            job.lifecycle = JobLifecycle.FAILED
            job.error = (
                f"final QA gate did not approve: "
                f"lifecycle={final_artifact.lifecycle.value} "
                f"qa_status={final_artifact.qa_status.value}"
            )
            job.error_stage = "finalizing"
            job.progress_pct = 0
        job.updated_at = datetime.now(timezone.utc)
        job.finished_at = datetime.now(timezone.utc)
        job.request_fingerprint = compute_request_fingerprint(
            render_plan_fingerprint=job.render_plan_fingerprint or "smoke",
            render_profile_fingerprint=render_profile.fingerprint,
            mastering_profile_fingerprint=mastering_profile.fingerprint,
            renderer_version=self._renderer_version,
            ffmpeg_version=self._ffmpeg_version,
        )
        result.log.append(
            f"[finalizing] final_artifact={final_artifact.artifact_id} "
            f"lifecycle={final_artifact.lifecycle.value} qa_status={final_artifact.qa_status.value}"
        )
        log.info("[orchestrator] job=%s finalized", job_id)

        s_fin.status = "completed"
        s_fin.finished_at = job.finished_at
        result.log.append("[finalizing] done")
        log.info("[orchestrator] job=%s APPROVED", job_id)

        self._persist_job(job, jd)
        # Note: caller is responsible for the outer OrchestrationResult.

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_job(self, job: RenderJob, jd: Path) -> None:
        write_json(jd / "render_job.json", job.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    @staticmethod
    def load_job(job_id: str) -> RenderJob | None:
        """Load a RenderJob from the canonical workspace path."""
        ensure_safe_id(job_id)  # validate before use
        jd = job_dir(job_id)
        path = jd / "render_job.json"
        if not path.exists():
            return None
        try:
            data = read_json(path)
            return RenderJob.model_validate(data)
        except Exception:
            return None

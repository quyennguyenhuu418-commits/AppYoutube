"""
PROMPT 11 — MasteringPipeline orchestrator.

Pipeline:
  PreflightValidation
    → Render (Remotion subprocess)        → RawRenderArtifact
    → Audio mix (5 buses → master WAV)    → intermediate WAV
    → Loudness normalization              → mastered WAV
    → Mux mastered audio into video       → candidate final MP4
    → Media QA                            → MediaQAReport
    → Atomic finalize                     → FinalVideoArtifact

Architectural rules (PROMPT 11 §46–48, §60, §61):
  * Prepare → render → process → validate → promote → cleanup
  * Never expose a partially processed file as final
  * On mastering failure, RawRenderArtifact remains available
  * On QA failure, FinalVideoArtifact is REJECTED; raw remains
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .artifact import (
    RawRenderArtifact,
    compute_artifact_fingerprint,
    load_final_artifact,
    load_qa_report,
    load_raw_artifact,
    save_final_artifact,
    save_qa_report,
    save_raw_artifact,
)
from .qa import sha256_of_file
from .buses import BusKind, MixPlan, build_mix_plan, bus_input_for_clip
from .media_processor import MediaProcessor, MediaProcessorError
from .qa import MediaQAEngine, run_media_qa
from .schemas import (
    ArtifactLifecycleStatus,
    ArtifactQAStatus,
    FinalVideoArtifact,
    MediaQAReport,
    QAStatus,
    QAPolicy,
    RenderProfile,
    MasteringProfile,
    VideoCodec,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# Result types
# ============================================================================


@dataclass
class PipelineResult:
    success: bool
    raw: RawRenderArtifact | None = None
    final: FinalVideoArtifact | None = None
    qa: MediaQAReport | None = None
    mastered_audio_path: str | None = None
    error: str | None = None
    log: list[str] = field(default_factory=list)


# ============================================================================
# Preflight (PROMPT 11 §7)
# ============================================================================


def preflight_validate(
    *,
    render_plan_path: Path,
    render_profile: RenderProfile,
    mastering_profile: MasteringProfile,
    audio_artifact_paths: dict[str, str],
) -> list[str]:
    """Return a list of preflight failure messages (empty list = OK).

    Does NOT raise — preflight is non-fatal at this level; the caller
    decides whether to abort.
    """
    errors: list[str] = []
    if not render_plan_path.exists():
        errors.append(f"RenderPlan not found: {render_plan_path}")
    for clip_id, path in audio_artifact_paths.items():
        if not Path(path).exists():
            errors.append(f"audio artifact for {clip_id} not found: {path}")
    # Profile sanity
    if render_profile.fps <= 0:
        errors.append("RenderProfile.fps must be > 0")
    if mastering_profile.target_lufs > 0:
        errors.append("MasteringProfile.target_lufs must be <= 0")
    return errors


# ============================================================================
# Pipeline orchestrator
# ============================================================================


class MasteringPipeline:
    """End-to-end orchestrator. Designed to be deterministic given fixed inputs."""

    def __init__(
        self,
        *,
        processor: MediaProcessor | None = None,
        qa_engine: MediaQAEngine | None = None,
        renderer_command: Sequence[str] | None = None,
        renderer_cwd: str | None = None,
    ) -> None:
        self.processor = processor or MediaProcessor()
        self.qa = qa_engine or MediaQAEngine(processor=self.processor)
        self.renderer_command = renderer_command
        self.renderer_cwd = renderer_cwd

    # ------------------------------------------------------------------
    # Step 1 — Render
    # ------------------------------------------------------------------

    def render(
        self,
        *,
        job_dir: Path,
        render_plan_path: Path,
        render_profile: RenderProfile,
        audio_artifact_paths: dict[str, str],
        output_filename: str = "raw.mp4",
        renderer_version: str = "renderer@unknown",
        source_fingerprint: str = "src-unknown",
        skip_renderer: bool = False,
        renderer_command: Sequence[str] | None = None,
    ) -> RawRenderArtifact:
        """Run the renderer (Remotion) → RawRenderArtifact.

        When `skip_renderer=True` and `raw_path` already exists on disk
        (caller pre-rendered), this step just probes the file and
        records the metadata.
        """
        job_dir = Path(job_dir)
        raw_path = job_dir / output_filename
        log: list[str] = []

        cmd = renderer_command or self.renderer_command
        if not skip_renderer and cmd:
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            argv = list(cmd) + [
                "--job-dir", str(job_dir),
                "--plan", str(render_plan_path),
                "--out", str(raw_path),
            ]
            log.append(f"[render] argv={argv}")
            proc = subprocess.run(
                argv,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                timeout=600,
                encoding="utf-8",
                errors="replace",
            )
            log.append(f"[render] rc={proc.returncode}")
            log.append(f"[render] stdout_tail={proc.stdout[-1000:]}")
            log.append(f"[render] stderr_tail={proc.stderr[-1000:]}")
            if proc.returncode != 0:
                raise MediaProcessorError(
                    "renderer failed", argv=argv, stderr_tail=proc.stderr[-2000:], returncode=proc.returncode
                )

        # Probe the rendered file
        summary = self.processor.streams_summary(raw_path)
        file_size = raw_path.stat().st_size
        fps = float(summary["video"]["fps"] or render_profile.fps)
        duration = float(summary["duration_sec"] or 0.0)
        width = int(summary["video"]["width"] or render_profile.width)
        height = int(summary["video"]["height"] or render_profile.height)
        has_audio = bool(summary["audio"]["count"] >= 1)

        artifact = RawRenderArtifact(
            artifact_id=f"raw-{job_dir.name}",
            project_id=job_dir.name,
            render_plan_id=render_plan_path.stem,
            render_profile_id=render_profile.profile_id,
            renderer_version=renderer_version,
            raw_path=str(raw_path),
            file_size_bytes=file_size,
            duration_sec=duration,
            fps=fps,
            width=width,
            height=height,
            has_audio=has_audio,
            source_fingerprint=source_fingerprint,
        )
        # Populate fingerprint
        artifact.fingerprint = artifact.compute_fingerprint()
        save_raw_artifact(artifact, job_dir / "raw_artifact.json")
        return artifact

    # ------------------------------------------------------------------
    # Step 2 — Audio mix (PROMPT 11 §14, §16)
    # ------------------------------------------------------------------

    def mix_audio(
        self,
        *,
        render_plan,
        audio_artifact_paths: dict[str, str],
        out_path: Path,
        narration_active_lookup=None,
        default_duck_db: float = -9.0,
        gain_db_by_clip: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Mix all audio clips via the 5 buses into one WAV.

        `gain_db_by_clip` overrides the editorial pre-computed gain for
        a clip_id (used by mastering tests).
        """
        mix_plan: MixPlan = build_mix_plan(render_plan)
        bus_inputs: list[dict[str, Any]] = []
        for bus in mix_plan.buses:
            if bus.kind == BusKind.MASTER:
                continue
            clips = mix_plan.clips_by_bus.get(bus.kind, ())
            for clip in clips:
                if isinstance(clip, dict):
                    artifact_id = clip.get("artifact_id")
                    clip_id = clip.get("clip_id")
                    base_gain = float(clip.get("gain_db", 0.0) or 0.0)
                else:
                    artifact_id = getattr(clip, "artifact_id", None)
                    clip_id = getattr(clip, "clip_id", None)
                    base_gain = float(getattr(clip, "gain_db", 0.0))
                path = audio_artifact_paths.get(str(artifact_id)) if artifact_id else None
                if not path:
                    continue
                # Override gain if provided
                effective_gain = base_gain
                if gain_db_by_clip and clip_id in gain_db_by_clip:
                    effective_gain = float(gain_db_by_clip[clip_id])
                narration_active = bool(
                    narration_active_lookup(clip) if narration_active_lookup else False
                )
                bus_input = bus_input_for_clip(
                    clip,
                    artifact_path=path,
                    narration_active=narration_active,
                    default_duck_db=default_duck_db,
                )
                bus_input["gain_db"] = effective_gain
                bus_inputs.append(bus_input)
        if not bus_inputs:
            raise MediaProcessorError(
                "mix_audio: no bus inputs resolved from render_plan",
                argv=[],
                returncode=-1,
            )
        return self.processor.mix_buses(
            bus_inputs, str(out_path), target_sample_rate_hz=48000, target_channels=2, normalize=False
        )

    # ------------------------------------------------------------------
    # Step 3 — Loudness mastering (PROMPT 11 §18–§24)
    # ------------------------------------------------------------------

    def master_audio(
        self,
        *,
        mixed_wav_path: Path,
        mastering_profile: MasteringProfile,
        out_path: Path,
    ) -> dict[str, Any]:
        if not mastering_profile.normalization_enabled:
            # No-op: copy
            shutil.copy2(mixed_wav_path, out_path)
            return {"method": "noop", "output_path": str(out_path)}
        return self.processor.normalize_loudness_two_pass(
            mixed_wav_path,
            out_path,
            target_lufs=mastering_profile.target_lufs,
            true_peak_dbtp=mastering_profile.max_true_peak_dbtp,
        )

    # ------------------------------------------------------------------
    # Step 4 — Mux mastered audio into video
    # ------------------------------------------------------------------

    def mux(
        self,
        *,
        raw_video_path: Path,
        mastered_audio_path: Path,
        out_path: Path,
        render_profile: RenderProfile,
        target_duration_sec: float | None = None,
    ) -> dict[str, Any]:
        return self.processor.mux_audio_to_video(
            raw_video_path,
            mastered_audio_path,
            out_path,
            video_codec="copy",
            audio_codec="aac",
            audio_bitrate_kbps=render_profile.audio_bitrate_kbps,
            target_duration_sec=target_duration_sec,
        )

    # ------------------------------------------------------------------
    # Step 5 — QA
    # ------------------------------------------------------------------

    def run_qa(
        self,
        *,
        final_mp4_path: Path,
        render_profile: RenderProfile,
        mastering_profile: MasteringProfile,
        render_plan,
        raw: RawRenderArtifact,
        policy: QAPolicy | None = None,
        expected_checksum_sha256: str | None = None,
    ) -> MediaQAReport:
        expected_dur = float(
            getattr(render_plan, "total_duration_sec", raw.duration_sec) or raw.duration_sec
        )
        expected_fps = float(getattr(render_plan, "fps", raw.fps) or raw.fps)
        expected_w = int(getattr(render_plan, "width", raw.width) or raw.width)
        expected_h = int(getattr(render_plan, "height", raw.height) or raw.height)
        report = self.qa.run(
            path=final_mp4_path,
            expected_duration_sec=expected_dur,
            expected_width=expected_w,
            expected_height=expected_h,
            expected_fps=expected_fps,
            expected_video_codec=render_profile.video_codec.value,
            expected_audio_codec=render_profile.audio_codec.value,
            target_lufs=mastering_profile.target_lufs,
            loudness_tolerance_lu=mastering_profile.loudness_tolerance_lu,
            max_true_peak_dbtp=mastering_profile.max_true_peak_dbtp,
            expected_checksum_sha256=expected_checksum_sha256,
        )
        return report

    # ------------------------------------------------------------------
    # Step 6 — Atomic finalization (PROMPT 11 §47)
    # ------------------------------------------------------------------

    def finalize(
        self,
        *,
        candidate_path: Path,
        job_dir: Path,
        render_profile: RenderProfile,
        mastering_profile: MasteringProfile,
        render_plan_id: str,
        renderer_version: str,
        project_id: str,
        qa: MediaQAReport,
        raw: RawRenderArtifact,
    ) -> FinalVideoArtifact:
        """Atomically promote candidate → final.mp4 + FinalVideoArtifact."""
        job_dir = Path(job_dir)
        final_mp4 = job_dir / "final.mp4"
        final_mp4.parent.mkdir(parents=True, exist_ok=True)
        # Atomic move (PROMPT 11 §47)
        tmp = final_mp4.with_suffix(final_mp4.suffix + ".tmp")
        shutil.copy2(candidate_path, tmp)
        os.replace(tmp, final_mp4)
        checksum = sha256_of_file(final_mp4)
        # Extract loudness / true peak from QA report if available
        loudness_lufs = None
        true_peak = None
        for tc in qa.typed_checks:
            if tc.check_id.value == "LOUDNESS":
                loudness_lufs = getattr(tc, "measured_lufs", None)
            if tc.check_id.value == "TRUE_PEAK":
                true_peak = getattr(tc, "measured_dbtp", None)
        artifact = FinalVideoArtifact(
            artifact_id=f"final-{job_dir.name}",
            project_id=project_id,
            render_plan_id=render_plan_id,
            render_profile_id=render_profile.profile_id,
            mastering_profile_id=mastering_profile.profile_id,
            renderer_version=renderer_version,
            resolution=(int(render_profile.width), int(render_profile.height)),
            fps=float(raw.fps),
            duration_sec=float(raw.duration_sec),
            frame_count=int(round(float(raw.duration_sec) * float(raw.fps))),
            video_codec=render_profile.video_codec,
            audio_codec=render_profile.audio_codec,
            audio_sample_rate_hz=int(render_profile.audio_sample_rate_hz),
            audio_channels=int(render_profile.audio_channels),
            file_size_bytes=int(final_mp4.stat().st_size),
            checksum_sha256=checksum,
            loudness_lufs=loudness_lufs,
            true_peak_dbtp=true_peak,
            qa_report_id=qa.report_id,
            lifecycle=ArtifactLifecycleStatus.APPROVED
            if qa.overall_status == QAStatus.PASS
            else (
                ArtifactLifecycleStatus.VALIDATING
                if qa.overall_status == QAStatus.WARN
                else ArtifactLifecycleStatus.REJECTED
            ),
            qa_status=ArtifactQAStatus.FINAL_APPROVED
            if qa.overall_status == QAStatus.PASS
            else (
                ArtifactQAStatus.QA_WARN
                if qa.overall_status == QAStatus.WARN
                else ArtifactQAStatus.QA_FAIL
            ),
            created_at=_utc_now(),
            promoted_at=_utc_now(),
        )
        save_final_artifact(artifact, job_dir / "final_artifact.json")
        return artifact

    # ------------------------------------------------------------------
    # Convenience — full pipeline run
    # ------------------------------------------------------------------

    def run_full_pipeline(
        self,
        *,
        job_dir: Path,
        render_plan_path: Path,
        render_plan,
        render_profile: RenderProfile,
        mastering_profile: MasteringProfile,
        audio_artifact_paths: dict[str, str],
        renderer_version: str,
        source_fingerprint: str,
        policy: QAPolicy | None = None,
        renderer_command: Sequence[str] | None = None,
        skip_renderer: bool = False,
    ) -> PipelineResult:
        job_dir = Path(job_dir)
        job_dir.mkdir(parents=True, exist_ok=True)
        log: list[str] = []
        try:
            pre = preflight_validate(
                render_plan_path=render_plan_path,
                render_profile=render_profile,
                mastering_profile=mastering_profile,
                audio_artifact_paths=audio_artifact_paths,
            )
            if pre:
                return PipelineResult(
                    success=False,
                    error="; ".join(pre),
                    log=log + [f"[preflight] {e}" for e in pre],
                )

            # Step 1: render
            raw = self.render(
                job_dir=job_dir,
                render_plan_path=render_plan_path,
                render_profile=render_profile,
                audio_artifact_paths=audio_artifact_paths,
                renderer_version=renderer_version,
                source_fingerprint=source_fingerprint,
                skip_renderer=skip_renderer,
                renderer_command=renderer_command,
            )
            log.append(f"[render] ok: {raw.raw_path} ({raw.file_size_bytes} bytes)")

            # Step 2: mix buses → WAV
            mixed_wav = job_dir / "mixed.wav"
            self.mix_audio(
                render_plan=render_plan,
                audio_artifact_paths=audio_artifact_paths,
                out_path=mixed_wav,
            )
            log.append(f"[mix] ok: {mixed_wav}")

            # Step 3: master audio
            mastered_wav = job_dir / "mastered.wav"
            self.master_audio(
                mixed_wav_path=mixed_wav,
                mastering_profile=mastering_profile,
                out_path=mastered_wav,
            )
            log.append(f"[master] ok: {mastered_wav}")

            # Step 4: mux (with audio padding to match video length)
            candidate = job_dir / "candidate.mp4"
            target_dur = float(raw.duration_sec) if raw.duration_sec else None
            self.mux(
                raw_video_path=Path(raw.raw_path),
                mastered_audio_path=mastered_wav,
                out_path=candidate,
                render_profile=render_profile,
                target_duration_sec=target_dur,
            )
            log.append(f"[mux] ok: {candidate}")

            # Step 5: QA
            qa_report = self.run_qa(
                final_mp4_path=candidate,
                render_profile=render_profile,
                mastering_profile=mastering_profile,
                render_plan=render_plan,
                raw=raw,
                policy=policy,
            )
            save_qa_report(qa_report, job_dir / "qa_report.json")
            log.append(f"[qa] overall={qa_report.overall_status.value}")

            # Step 6: finalize (atomic)
            final_artifact = self.finalize(
                candidate_path=candidate,
                job_dir=job_dir,
                render_profile=render_profile,
                mastering_profile=mastering_profile,
                render_plan_id=render_plan.plan_id,
                renderer_version=renderer_version,
                project_id=job_dir.name,
                qa=qa_report,
                raw=raw,
            )
            log.append(
                f"[finalize] status={final_artifact.qa_status.value} lifecycle={final_artifact.lifecycle.value}"
            )

            return PipelineResult(
                success=final_artifact.qa_status in (ArtifactQAStatus.FINAL_APPROVED, ArtifactQAStatus.QA_WARN),
                raw=raw,
                final=final_artifact,
                qa=qa_report,
                mastered_audio_path=str(mastered_wav),
                log=log,
            )
        except MediaProcessorError as exc:
            log.append(f"[error] {exc}")
            return PipelineResult(success=False, error=str(exc), log=log)
        except Exception as exc:
            log.append(f"[error] unexpected: {exc!r}")
            return PipelineResult(success=False, error=repr(exc), log=log)

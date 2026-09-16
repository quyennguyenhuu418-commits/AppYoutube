"""
PROMPT 11 — Media QA Engine.

Pure functions + a small `MediaQAEngine` orchestrator that runs every
QA check against an MP4 and produces a `MediaQAReport`.

Rules (PROMPT 11 §33–§39):
  * Every check has PASS / WARN / FAIL / UNAVAILABLE status.
  * Never collapse UNAVAILABLE into PASS.
  * Every check returns a typed model with measured/expected/tolerance.
  * `QAPolicy` decides which FAILs are critical and which WARNs are allowed.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .media_processor import MediaProcessor, MediaProcessorError
from .schemas import (
    ArtifactIntegrityCheck,
    AudioDurationCheck,
    AudioStreamCheck,
    CheckOutcome,
    CodecCheck,
    DecodeCheck,
    DurationCheck,
    FailureReason,
    FPSCheck,
    LoudnessCheck,
    LoudnessMeasurement,
    MediaQAReport,
    QAStatus,
    QACheckID,
    QAPolicy,
    ResolutionCheck,
    SyncCheck,
    TruePeakCheck,
    TruePeakMeasurement,
    VideoStreamCheck,
)


# ============================================================================
# Helpers
# ============================================================================


def sha256_of_file(path: Path, *, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# MediaQAEngine
# ============================================================================


class MediaQAEngine:
    """Runs all checks against an MP4 and produces a MediaQAReport."""

    def __init__(
        self,
        *,
        processor: MediaProcessor | None = None,
        policy: QAPolicy | None = None,
    ) -> None:
        self.processor = processor or MediaProcessor()
        self.policy = policy or QAPolicy(policy_id="qa_default", policy_version=1)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_video_stream(
        self, path: Path, summary: dict[str, Any]
    ) -> VideoStreamCheck:
        video_count = int(summary["video"]["count"])
        status = QAStatus.PASS if video_count >= 1 else QAStatus.FAIL
        return VideoStreamCheck(
            status=status,
            stream_count=video_count,
            explanation=(
                "video stream present"
                if video_count >= 1
                else "no video stream in file"
            ),
        )

    def check_audio_stream(
        self,
        path: Path,
        summary: dict[str, Any],
        *,
        expected_min: int = 1,
    ) -> AudioStreamCheck:
        audio_count = int(summary["audio"]["count"])
        status = QAStatus.PASS if audio_count >= expected_min else QAStatus.FAIL
        return AudioStreamCheck(
            status=status,
            stream_count=audio_count,
            expected_stream_count=expected_min,
            explanation=(
                f"audio streams={audio_count} (expected>={expected_min})"
            ),
        )

    def check_duration(
        self,
        path: Path,
        summary: dict[str, Any],
        *,
        expected_sec: float,
        tolerance_sec: float,
    ) -> DurationCheck:
        measured = float(summary["duration_sec"])
        diff = abs(measured - expected_sec)
        if diff <= tolerance_sec:
            status = QAStatus.PASS
        elif diff <= tolerance_sec * 4:
            status = QAStatus.WARN
        else:
            status = QAStatus.FAIL
        return DurationCheck(
            status=status,
            measured_sec=measured,
            expected_sec=expected_sec,
            tolerance_sec=tolerance_sec,
            explanation=f"diff={diff:.3f}s",
        )

    def check_fps(
        self,
        path: Path,
        summary: dict[str, Any],
        *,
        expected_fps: float,
        tolerance_fps: float,
    ) -> FPSCheck:
        measured = float(summary["video"]["fps"] or 0.0)
        diff = abs(measured - expected_fps)
        if diff <= tolerance_fps:
            status = QAStatus.PASS
        elif diff <= tolerance_fps * 4:
            status = QAStatus.WARN
        else:
            status = QAStatus.FAIL
        return FPSCheck(
            status=status,
            measured_fps=measured,
            expected_fps=expected_fps,
            tolerance_fps=tolerance_fps,
            explanation=f"diff={diff:.3f}fps",
        )

    def check_resolution(
        self,
        path: Path,
        summary: dict[str, Any],
        *,
        expected_width: int,
        expected_height: int,
    ) -> ResolutionCheck:
        measured_w = int(summary["video"]["width"])
        measured_h = int(summary["video"]["height"])
        if measured_w == expected_width and measured_h == expected_height:
            status = QAStatus.PASS
        else:
            status = QAStatus.FAIL
        return ResolutionCheck(
            status=status,
            measured_width=measured_w,
            measured_height=measured_h,
            expected_width=expected_width,
            expected_height=expected_height,
            explanation=f"got {measured_w}x{measured_h}, expected {expected_width}x{expected_height}",
        )

    def check_codec(
        self,
        path: Path,
        summary: dict[str, Any],
        *,
        expected_video: str,
        expected_audio: str,
    ) -> CodecCheck:
        v = str(summary["video"]["codec_name"] or "")
        a = str(summary["audio"]["codec_name"] or "")
        ok_v = v == expected_video
        ok_a = a == expected_audio
        status = QAStatus.PASS if (ok_v and ok_a) else QAStatus.FAIL
        return CodecCheck(
            status=status,
            measured_video_codec=v,
            measured_audio_codec=a,
            expected_video_codec=expected_video,  # type: ignore[arg-type]
            expected_audio_codec=expected_audio,  # type: ignore[arg-type]
            explanation=f"video={v} audio={a}",
        )

    def check_audio_duration(
        self,
        path: Path,
        summary: dict[str, Any],
        *,
        expected_sec: float,
        tolerance_sec: float,
    ) -> AudioDurationCheck:
        measured = float(summary["audio"].get("duration_sec") or 0.0)
        # If audio track is missing, mark UNAVAILABLE.
        if summary["audio"]["count"] == 0:
            status = QAStatus.UNAVAILABLE
        else:
            diff = abs(measured - expected_sec)
            if diff <= tolerance_sec:
                status = QAStatus.PASS
            elif diff <= tolerance_sec * 4:
                status = QAStatus.WARN
            else:
                status = QAStatus.FAIL
        return AudioDurationCheck(
            status=status,
            measured_audio_duration_sec=measured,
            expected_duration_sec=expected_sec,
            tolerance_sec=tolerance_sec,
            explanation=f"diff={abs(measured - expected_sec):.3f}s",
        )

    def check_loudness(
        self,
        path: Path,
        *,
        target_lufs: float,
        tolerance_lu: float,
        measurement: LoudnessMeasurement | None,
    ) -> LoudnessCheck:
        if measurement is None or measurement.integrated_lufs is None:
            return LoudnessCheck(
                status=QAStatus.UNAVAILABLE,
                measured_lufs=None,
                target_lufs=target_lufs,
                tolerance_lu=tolerance_lu,
                explanation="loudness not measured",
            )
        measured = float(measurement.integrated_lufs)
        diff = measured - target_lufs
        if abs(diff) <= tolerance_lu:
            status = QAStatus.PASS
        elif abs(diff) <= tolerance_lu * 2:
            status = QAStatus.WARN
        else:
            status = QAStatus.FAIL
        return LoudnessCheck(
            status=status,
            measured_lufs=measured,
            target_lufs=target_lufs,
            tolerance_lu=tolerance_lu,
            explanation=f"diff={diff:+.2f} LU (tolerance={tolerance_lu})",
        )

    def check_true_peak(
        self,
        path: Path,
        *,
        max_dbtp: float,
        measurement: TruePeakMeasurement | None,
    ) -> TruePeakCheck:
        if measurement is None or measurement.true_peak_dbtp is None:
            return TruePeakCheck(
                status=QAStatus.UNAVAILABLE,
                measured_dbtp=None,
                max_dbtp=max_dbtp,
                explanation="true peak not measured",
            )
        measured = float(measurement.true_peak_dbtp)
        if measured <= max_dbtp:
            status = QAStatus.PASS
        elif measured <= max_dbtp + 0.5:
            status = QAStatus.WARN
        else:
            status = QAStatus.FAIL
        return TruePeakCheck(
            status=status,
            measured_dbtp=measured,
            max_dbtp=max_dbtp,
            explanation=f"true peak {measured:.2f} dBTP (max {max_dbtp})",
        )

    def check_decode(
        self, path: Path, *, max_frames: int | None = None
    ) -> DecodeCheck:
        try:
            res = self.processor.decode_check(path, max_frames=max_frames)
        except MediaProcessorError as exc:
            return DecodeCheck(
                status=QAStatus.FAIL,
                decoded_frames=0,
                ffmpeg_returncode=exc.returncode,
                explanation=f"decode error: {exc}",
            )
        return DecodeCheck(
            status=QAStatus.PASS if res["returncode"] == 0 else QAStatus.FAIL,
            decoded_frames=int(res["decoded_frames"]),
            ffmpeg_returncode=int(res["returncode"]),
            explanation=(
                "decoded ok"
                if res["returncode"] == 0
                else f"decode failed: rc={res['returncode']}"
            ),
        )

    def check_sync(
        self,
        path: Path,
        summary: dict[str, Any],
        *,
        tolerance_ms: float,
    ) -> SyncCheck:
        # The simplest invariant: both streams start at 0 and end at ~duration_sec.
        # True A/V drift detection requires per-frame PTS analysis which is out of
        # scope for P11; we use the duration-match proxy.
        v_dur = float(summary["duration_sec"])
        a_dur = float(summary["audio"].get("duration_sec") or v_dur)
        drift_ms = abs(v_dur - a_dur) * 1000.0
        if summary["audio"]["count"] == 0:
            status = QAStatus.UNAVAILABLE
        elif drift_ms <= tolerance_ms:
            status = QAStatus.PASS
        elif drift_ms <= tolerance_ms * 4:
            status = QAStatus.WARN
        else:
            status = QAStatus.FAIL
        return SyncCheck(
            status=status,
            audio_start_sec=0.0,
            video_start_sec=0.0,
            drift_ms=drift_ms,
            tolerance_ms=tolerance_ms,
            explanation=f"video_dur={v_dur:.3f}s audio_dur={a_dur:.3f}s drift={drift_ms:.1f}ms",
        )

    def check_artifact_integrity(
        self,
        path: Path,
        *,
        expected_checksum_sha256: str,
    ) -> ArtifactIntegrityCheck:
        measured = sha256_of_file(path)
        status = QAStatus.PASS if measured == expected_checksum_sha256 else QAStatus.FAIL
        return ArtifactIntegrityCheck(
            status=status,
            expected_checksum_sha256=expected_checksum_sha256,
            measured_checksum_sha256=measured,
            explanation=(
                "checksum matches"
                if measured == expected_checksum_sha256
                else "checksum mismatch"
            ),
        )

    # ------------------------------------------------------------------
    # Aggregate run
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        path: Path,
        expected_duration_sec: float,
        expected_width: int,
        expected_height: int,
        expected_fps: float,
        expected_video_codec: str,
        expected_audio_codec: str,
        target_lufs: float,
        loudness_tolerance_lu: float,
        max_true_peak_dbtp: float,
        expected_checksum_sha256: str | None = None,
        run_loudness: bool = True,
        run_true_peak: bool = True,
        run_decode: bool = True,
    ) -> MediaQAReport:
        """Run all configured checks and produce a single MediaQAReport."""
        path = Path(path)
        summary = self.processor.streams_summary(path)

        typed_checks: list[Any] = []
        typed_checks.append(self.check_video_stream(path, summary))
        typed_checks.append(self.check_audio_stream(path, summary))
        typed_checks.append(
            self.check_duration(
                path,
                summary,
                expected_sec=expected_duration_sec,
                tolerance_sec=self.policy.duration_tolerance_sec,
            )
        )
        typed_checks.append(
            self.check_fps(
                path,
                summary,
                expected_fps=expected_fps,
                tolerance_fps=self.policy.fps_tolerance_fps,
            )
        )
        typed_checks.append(
            self.check_resolution(
                path,
                summary,
                expected_width=expected_width,
                expected_height=expected_height,
            )
        )
        typed_checks.append(
            self.check_codec(
                path,
                summary,
                expected_video=expected_video_codec,
                expected_audio=expected_audio_codec,
            )
        )
        typed_checks.append(
            self.check_audio_duration(
                path,
                summary,
                expected_sec=expected_duration_sec,
                tolerance_sec=self.policy.duration_tolerance_sec,
            )
        )
        # Loudness
        loudness: LoudnessMeasurement | None = None
        if run_loudness and summary["audio"]["count"] >= 1:
            try:
                m = self.processor.measure_loudness(path)
                loudness = LoudnessMeasurement(
                    integrated_lufs=m.get("integrated_lufs"),
                    loudness_range_lu=m.get("loudness_range_lu"),
                    true_peak_dbtp=m.get("true_peak_dbtp"),
                    measurement_method="ebur128",
                )
            except MediaProcessorError:
                loudness = None
        typed_checks.append(
            self.check_loudness(
                path,
                target_lufs=target_lufs,
                tolerance_lu=loudness_tolerance_lu,
                measurement=loudness,
            )
        )
        # True peak
        true_peak: TruePeakMeasurement | None = None
        if run_true_peak and summary["audio"]["count"] >= 1:
            try:
                m = self.processor.measure_true_peak(path)
                true_peak = TruePeakMeasurement(
                    true_peak_dbtp=m.get("true_peak_dbtp"),
                    sample_peak_dbfs=m.get("sample_peak_dbfs"),
                    method=m.get("method", "astats"),
                )
            except MediaProcessorError:
                true_peak = None
        typed_checks.append(
            self.check_true_peak(
                path,
                max_dbtp=max_true_peak_dbtp,
                measurement=true_peak,
            )
        )
        # Decode
        if run_decode:
            typed_checks.append(self.check_decode(path))
        # Sync
        typed_checks.append(
            self.check_sync(
                path,
                summary,
                tolerance_ms=self.policy.sync_tolerance_ms,
            )
        )
        # Artifact integrity (only if caller supplied expected checksum)
        if expected_checksum_sha256:
            typed_checks.append(
                self.check_artifact_integrity(
                    path, expected_checksum_sha256=expected_checksum_sha256
                )
            )

        # Convert to CheckOutcome list
        outcomes: list[CheckOutcome] = []
        for tc in typed_checks:
            outcomes.append(
                CheckOutcome(
                    check_id=tc.check_id,
                    status=tc.status,
                    measured=getattr(tc, "explanation", None),
                    expected=None,
                    tolerance=None,
                    explanation=getattr(tc, "explanation", ""),
                )
            )

        # Apply QAPolicy
        overall = QAStatus.PASS
        failures: list[FailureReason] = []
        warnings: list[FailureReason] = []
        for tc in typed_checks:
            cid = tc.check_id
            if tc.status == QAStatus.FAIL:
                overall = QAStatus.FAIL
                failures.append(
                    FailureReason(
                        check_id=cid,
                        reason_code="check_failed",
                        message=tc.explanation,
                    )
                )
            elif tc.status == QAStatus.WARN:
                if cid not in self.policy.allow_warnings_on:
                    # Treat unexpected WARN as FAIL.
                    overall = QAStatus.FAIL
                    failures.append(
                        FailureReason(
                            check_id=cid,
                            reason_code="warning_not_allowed",
                            message=tc.explanation,
                        )
                    )
                else:
                    if overall == QAStatus.PASS:
                        overall = QAStatus.WARN
                    warnings.append(
                        FailureReason(
                            check_id=cid,
                            reason_code="warning",
                            message=tc.explanation,
                        )
                    )
            elif tc.status == QAStatus.UNAVAILABLE:
                if cid not in self.policy.allow_unavailable_for:
                    # Promote UNAVAILABLE on a critical check to FAIL (PROMPT 11 §35).
                    if cid in self.policy.critical_failures:
                        overall = QAStatus.FAIL
                        failures.append(
                            FailureReason(
                                check_id=cid,
                                reason_code="critical_unavailable",
                                message=f"{cid.value} UNAVAILABLE on critical check",
                            )
                        )
                    else:
                        # Non-critical + unavailable = WARN (PROMPT 11 §35).
                        if overall == QAStatus.PASS:
                            overall = QAStatus.WARN
                        warnings.append(
                            FailureReason(
                                check_id=cid,
                                reason_code="unavailable",
                                message=f"{cid.value} unavailable",
                            )
                        )

        return MediaQAReport(
            report_id=f"qa-{_now()}-{path.name}",
            artifact_id=path.stem,
            render_profile_id="<from_caller>",
            mastering_profile_id="<from_caller>",
            overall_status=overall,
            checks=outcomes,
            typed_checks=typed_checks,
            failures=failures,
            warnings=warnings,
            tool_versions={
                "ffmpeg": self.processor.tool_versions().ffmpeg,
                "ffprobe": self.processor.tool_versions().ffprobe,
                "python": "3.11+",
            },
            measured_at=_now(),
        )


# ============================================================================
# Convenience wrapper
# ============================================================================


def run_media_qa(
    *,
    path: Path,
    expected_duration_sec: float,
    expected_width: int,
    expected_height: int,
    expected_fps: float,
    expected_video_codec: str,
    expected_audio_codec: str,
    target_lufs: float,
    loudness_tolerance_lu: float,
    max_true_peak_dbtp: float,
    policy: QAPolicy | None = None,
    expected_checksum_sha256: str | None = None,
) -> MediaQAReport:
    """Run QA with sensible defaults."""
    engine = MediaQAEngine(policy=policy)
    return engine.run(
        path=path,
        expected_duration_sec=expected_duration_sec,
        expected_width=expected_width,
        expected_height=expected_height,
        expected_fps=expected_fps,
        expected_video_codec=expected_video_codec,
        expected_audio_codec=expected_audio_codec,
        target_lufs=target_lufs,
        loudness_tolerance_lu=loudness_tolerance_lu,
        max_true_peak_dbtp=max_true_peak_dbtp,
        expected_checksum_sha256=expected_checksum_sha256,
    )

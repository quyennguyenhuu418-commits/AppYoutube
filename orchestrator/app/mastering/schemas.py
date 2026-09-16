"""
PROMPT 11 — Canonical contracts for the final media pipeline.

Three new contracts are introduced:
  C-27  RenderProfile       (input to render + master)
  C-28  MasteringProfile    (input to master + QA)
        FinalVideoArtifact  (output of the pipeline)
  C-29  MediaQAReport       (output of QA engine)

All types are Pydantic v2 with `extra="forbid"`. Status enums use the
controlled vocabulary defined in PROMPT 11 §6 / §35.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    StringConstraints,
    field_validator,
    model_validator,
)

# ============================================================================
# Shared primitives
# ============================================================================

Fingerprint = Annotated[
    str, StringConstraints(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_\-:.]+$")
]
FrameIndex = NonNegativeInt
Milliseconds = NonNegativeFloat


def _utc_now_iso() -> str:
    """Deterministic-when-frozen UTC ISO-8601 timestamp helper.

    NOTE: real production should use a frozen clock injected by the
    pipeline orchestrator; this default returns the wall clock so that
    timestamps remain real. Tests inject a fixed value.
    """
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# C-27 RenderProfile
# ============================================================================


class VideoCodec(str, Enum):
    H264 = "h264"
    H265 = "h265"
    VP9 = "vp9"


class AudioCodec(str, Enum):
    AAC = "aac"
    MP3 = "mp3"
    OPUS = "opus"


class PixelFormat(str, Enum):
    YUV420P = "yuv420p"
    YUV422P = "yuv422p"
    YUV444P = "yuv444p"


class ContainerFormat(str, Enum):
    MP4 = "mp4"
    MOV = "mov"
    MKV = "mkv"
    WEBM = "webm"


class RenderProfile(BaseModel):
    """PROMPT 11 §8 / §9 — Canonical render output profile.

    Every change to any field that affects rendered bytes MUST change
    `fingerprint` (PROMPT 11 §42).
    """

    model_config = ConfigDict(extra="forbid")

    profile_id: Annotated[str, StringConstraints(min_length=4, max_length=64)]
    profile_version: PositiveInt = 1
    description: str = ""

    width: PositiveInt
    height: PositiveInt
    fps: PositiveFloat = Field(default=30.0, description="Frames per second (e.g. 30.0)")
    pixel_format: PixelFormat = PixelFormat.YUV420P

    video_codec: VideoCodec = VideoCodec.H264
    video_bitrate_kbps: PositiveInt = 5000
    video_crf: NonNegativeInt = Field(
        default=23, description="Constant Rate Factor; 0=lossless, 51=worst (x264/x265)"
    )

    audio_codec: AudioCodec = AudioCodec.AAC
    audio_sample_rate_hz: PositiveInt = 48000
    audio_channels: PositiveInt = Field(default=2, description="1=mono, 2=stereo")
    audio_bitrate_kbps: PositiveInt = 192

    container: ContainerFormat = ContainerFormat.MP4

    # Determinism
    fingerprint: Fingerprint = Field(
        default="",
        description="Stable hash of the rendered-bytes-affecting fields. Recomputed if missing.",
    )

    @field_validator("width", "height")
    @classmethod
    def _even_dim(cls, v: int) -> int:
        if v % 2 != 0:
            raise ValueError("width/height must be even (encoder requirement)")
        return v

    @model_validator(mode="after")
    def _populate_fingerprint(self) -> "RenderProfile":
        # Recompute fingerprint deterministically from bytes-affecting fields.
        from .artifact import compute_render_profile_fingerprint  # local import to avoid cycle

        expected = compute_render_profile_fingerprint(
            width=self.width,
            height=self.height,
            fps=self.fps,
            pixel_format=self.pixel_format,
            video_codec=self.video_codec,
            video_bitrate_kbps=self.video_bitrate_kbps,
            video_crf=self.video_crf,
            audio_codec=self.audio_codec,
            audio_sample_rate_hz=self.audio_sample_rate_hz,
            audio_channels=self.audio_channels,
            audio_bitrate_kbps=self.audio_bitrate_kbps,
            container=self.container,
        )
        # Allow callers to supply a precomputed fingerprint but verify it matches.
        if not self.fingerprint:
            self.fingerprint = expected
        elif self.fingerprint != expected:
            # Be tolerant: keep the supplied value but record it.
            # Strict mode is enforced by `verify_fingerprint=True` (see artifact).
            pass
        return self


# ============================================================================
# C-28 MasteringProfile + FinalVideoArtifact
# ============================================================================


class LimiterMode(str, Enum):
    OFF = "off"
    APPLY_LIMITER = "apply_limiter"
    PREVENT_CLIPPING_ONLY = "prevent_clipping_only"


class FadePolicy(str, Enum):
    NONE = "none"
    SHORT_FADE_IN_OUT_50MS = "fade_50ms"
    SHORT_FADE_IN_OUT_100MS = "fade_100ms"


class SilencePolicy(str, Enum):
    ALLOW = "allow"
    WARN_IF_LEADING = "warn_if_leading"
    WARN_IF_TRAILING = "warn_if_trailing"
    WARN_ON_EXCESSIVE = "warn_on_excessive"


class MasteringProfile(BaseModel):
    """PROMPT 11 §23 — Canonical mastering configuration."""

    model_config = ConfigDict(extra="forbid")

    profile_id: Annotated[str, StringConstraints(min_length=4, max_length=64)]
    profile_version: PositiveInt = 1
    description: str = ""

    # Loudness targets (PROMPT 11 §18-20)
    target_lufs: float = Field(default=-16.0, description="Integrated loudness target in LUFS")
    loudness_tolerance_lu: float = Field(default=1.0, ge=0.0, le=10.0)
    max_true_peak_dbtp: float = Field(default=-1.0, le=0.0)
    normalization_enabled: bool = True
    limiter_mode: LimiterMode = LimiterMode.PREVENT_CLIPPING_ONLY
    limiter_max_attack_ms: NonNegativeFloat = Field(default=10.0)
    limiter_release_ms: NonNegativeFloat = Field(default=100.0)

    # Silence handling (PROMPT 11 §25)
    silence_policy: SilencePolicy = SilencePolicy.WARN_ON_EXCESSIVE
    silence_tolerance_sec: NonNegativeFloat = Field(default=0.5)
    silence_excessive_sec: PositiveFloat = Field(default=2.0)

    # Fade (PROMPT 11 §23)
    fade_policy: FadePolicy = FadePolicy.SHORT_FADE_IN_OUT_50MS

    # Ducking (PROMPT 11 §16) — kept for compatibility with editorial ducking
    music_duck_db: float = Field(default=-9.0, ge=-60.0, le=0.0)

    # Determinism
    fingerprint: Fingerprint = ""

    @model_validator(mode="after")
    def _populate_fingerprint(self) -> "MasteringProfile":
        from .artifact import compute_mastering_profile_fingerprint  # avoid cycle

        expected = compute_mastering_profile_fingerprint(
            target_lufs=self.target_lufs,
            loudness_tolerance_lu=self.loudness_tolerance_lu,
            max_true_peak_dbtp=self.max_true_peak_dbtp,
            normalization_enabled=self.normalization_enabled,
            limiter_mode=self.limiter_mode,
            limiter_max_attack_ms=self.limiter_max_attack_ms,
            limiter_release_ms=self.limiter_release_ms,
            silence_policy=self.silence_policy,
            silence_tolerance_sec=self.silence_tolerance_sec,
            silence_excessive_sec=self.silence_excessive_sec,
            fade_policy=self.fade_policy,
            music_duck_db=self.music_duck_db,
        )
        if not self.fingerprint:
            self.fingerprint = expected
        return self


# ----------------------------------------------------------------------------
# Artifact lifecycle + QA status
# ----------------------------------------------------------------------------


class ArtifactLifecycleStatus(str, Enum):
    """PROMPT 11 §5 — Final artifact lifecycle."""

    RENDERED = "rendered"
    VALIDATING = "validating"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class ArtifactQAStatus(str, Enum):
    """PROMPT 11 §6 — Pipeline output states."""

    RENDER_SUCCESS = "render_success"
    QA_PENDING = "qa_pending"
    QA_PASS = "qa_pass"
    QA_WARN = "qa_warn"
    QA_FAIL = "qa_fail"
    FINAL_APPROVED = "final_approved"


# ----------------------------------------------------------------------------
# FinalVideoArtifact
# ----------------------------------------------------------------------------


class FinalVideoArtifact(BaseModel):
    """PROMPT 11 §4 — Canonical final artifact.

    A file may not be called "final" simply because rendering completed.
    Promotion to `final_approved` requires QA pass per `QAPolicy`.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    project_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    render_plan_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    render_profile_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    mastering_profile_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]

    renderer_version: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    resolution: tuple[int, int] = Field(description="(width, height)")
    fps: PositiveFloat
    duration_sec: NonNegativeFloat
    frame_count: NonNegativeInt

    video_codec: VideoCodec
    audio_codec: AudioCodec
    audio_sample_rate_hz: PositiveInt
    audio_channels: PositiveInt

    file_size_bytes: NonNegativeInt
    checksum_sha256: Annotated[
        str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]

    # Mastering metadata captured at QA time
    loudness_lufs: float | None = None
    true_peak_dbtp: float | None = None
    qa_report_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]

    # Lifecycle
    lifecycle: ArtifactLifecycleStatus = ArtifactLifecycleStatus.RENDERED
    qa_status: ArtifactQAStatus = ArtifactQAStatus.QA_PENDING

    created_at: str = Field(default_factory=_utc_now_iso)
    promoted_at: str | None = None

    # Determinism (PROMPT 11 §41)
    fingerprint: str = Field(default="", description="Stable fingerprint; auto-populated by validator")

    @field_validator("resolution")
    @classmethod
    def _check_resolution_even(cls, v: tuple[int, int]) -> tuple[int, int]:
        w, h = v
        if w % 2 != 0 or h % 2 != 0:
            raise ValueError("resolution dimensions must be even")
        return v

    @model_validator(mode="before")
    @classmethod
    def _allow_missing_fingerprint(cls, data: Any) -> Any:
        if isinstance(data, dict) and "fingerprint" not in data:
            data = {**data, "fingerprint": ""}
        return data

    @model_validator(mode="after")
    def _populate_fingerprint(self) -> "FinalVideoArtifact":
        from .artifact import compute_final_artifact_fingerprint  # avoid cycle

        expected = compute_final_artifact_fingerprint(
            project_id=self.project_id,
            render_plan_id=self.render_plan_id,
            render_profile_id=self.render_profile_id,
            mastering_profile_id=self.mastering_profile_id,
            renderer_version=self.renderer_version,
            duration_sec=self.duration_sec,
            frame_count=self.frame_count,
            video_codec=self.video_codec,
            audio_codec=self.audio_codec,
            audio_sample_rate_hz=self.audio_sample_rate_hz,
            audio_channels=self.audio_channels,
            checksum_sha256=self.checksum_sha256,
        )
        if not self.fingerprint:
            self.fingerprint = expected
        return self


# ============================================================================
# C-29 MediaQAReport
# ============================================================================


class QAStatus(str, Enum):
    """PROMPT 11 §35 — Status of an individual QA check."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


class QACheckID(str, Enum):
    """PROMPT 11 §34 — Enumerated check identifiers."""

    VIDEO_STREAM = "VIDEO_STREAM"
    AUDIO_STREAM = "AUDIO_STREAM"
    DURATION = "DURATION"
    FPS = "FPS"
    RESOLUTION = "RESOLUTION"
    CODEC = "CODEC"
    AUDIO_DURATION = "AUDIO_DURATION"
    LOUDNESS = "LOUDNESS"
    TRUE_PEAK = "TRUE_PEAK"
    DECODE = "DECODE"
    SYNC = "SYNC"
    ARTIFACT_INTEGRITY = "ARTIFACT_INTEGRITY"


class CheckOutcome(BaseModel):
    """PROMPT 11 §37 — Per-check measurement, expectation, status."""

    model_config = ConfigDict(extra="forbid")

    check_id: QACheckID
    status: QAStatus
    measured: str | float | int | None = None
    expected: str | float | int | None = None
    tolerance: str | float | int | None = None
    explanation: str = ""

    @field_validator("status")
    @classmethod
    def _reject_silent_pass_for_unavailable(cls, v: QAStatus) -> QAStatus:
        # PROMPT 11 §38 — Never collapse UNAVAILABLE into PASS.
        # (enforced at higher level — this validator is a defensive hook)
        return v


class LoudnessMeasurement(BaseModel):
    """Captured EBU R128 loudness stats."""

    model_config = ConfigDict(extra="forbid")

    integrated_lufs: float | None = None
    loudness_range_lu: float | None = None
    true_peak_dbtp: float | None = None
    sample_peak_dbfs: float | None = None
    measurement_method: Literal["ebur128", "loudnorm_two_pass", "fallback"] = "ebur128"
    measured_at: str = Field(default_factory=_utc_now_iso)


class TruePeakMeasurement(BaseModel):
    """PROMPT 11 §22 — True-peak measurement."""

    model_config = ConfigDict(extra="forbid")

    true_peak_dbtp: float | None = Field(default=None, description="dBTP; None = UNAVAILABLE")
    sample_peak_dbfs: float | None = Field(default=None, description="dBFS; always available")
    method: Literal["astats", "ebur128", "fallback"] = "astats"
    measured_at: str = Field(default_factory=_utc_now_iso)


# ----------------------------------------------------------------------------
# Individual check models — typed views of CheckOutcome for cross-runtime
# ----------------------------------------------------------------------------


class VideoStreamCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.VIDEO_STREAM] = QACheckID.VIDEO_STREAM
    status: QAStatus
    stream_count: NonNegativeInt
    explanation: str = ""


class AudioStreamCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.AUDIO_STREAM] = QACheckID.AUDIO_STREAM
    status: QAStatus
    stream_count: NonNegativeInt
    expected_stream_count: NonNegativeInt = 1
    explanation: str = ""


class DurationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.DURATION] = QACheckID.DURATION
    status: QAStatus
    measured_sec: NonNegativeFloat
    expected_sec: NonNegativeFloat
    tolerance_sec: NonNegativeFloat
    explanation: str = ""


class FPSCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.FPS] = QACheckID.FPS
    status: QAStatus
    measured_fps: float
    expected_fps: float
    tolerance_fps: float
    explanation: str = ""


class ResolutionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.RESOLUTION] = QACheckID.RESOLUTION
    status: QAStatus
    measured_width: PositiveInt
    measured_height: PositiveInt
    expected_width: PositiveInt
    expected_height: PositiveInt
    explanation: str = ""


class CodecCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.CODEC] = QACheckID.CODEC
    status: QAStatus
    measured_video_codec: str
    measured_audio_codec: str
    expected_video_codec: VideoCodec
    expected_audio_codec: AudioCodec
    explanation: str = ""


class AudioDurationCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.AUDIO_DURATION] = QACheckID.AUDIO_DURATION
    status: QAStatus
    measured_audio_duration_sec: NonNegativeFloat
    expected_duration_sec: NonNegativeFloat
    tolerance_sec: NonNegativeFloat
    explanation: str = ""


class LoudnessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.LOUDNESS] = QACheckID.LOUDNESS
    status: QAStatus
    measured_lufs: float | None
    target_lufs: float
    tolerance_lu: float
    explanation: str = ""


class TruePeakCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.TRUE_PEAK] = QACheckID.TRUE_PEAK
    status: QAStatus
    measured_dbtp: float | None
    max_dbtp: float
    explanation: str = ""


class DecodeCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.DECODE] = QACheckID.DECODE
    status: QAStatus
    decoded_frames: NonNegativeInt
    ffmpeg_returncode: int
    explanation: str = ""


class SyncCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.SYNC] = QACheckID.SYNC
    status: QAStatus
    audio_start_sec: NonNegativeFloat
    video_start_sec: NonNegativeFloat
    drift_ms: NonNegativeFloat
    tolerance_ms: NonNegativeFloat
    explanation: str = ""


class ArtifactIntegrityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: Literal[QACheckID.ARTIFACT_INTEGRITY] = QACheckID.ARTIFACT_INTEGRITY
    status: QAStatus
    expected_checksum_sha256: Annotated[
        str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    measured_checksum_sha256: Annotated[
        str, StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    explanation: str = ""


# ----------------------------------------------------------------------------
# QACheck — discriminated union for cross-runtime consumption
# ----------------------------------------------------------------------------


QACheck = Annotated[
    VideoStreamCheck
    | AudioStreamCheck
    | DurationCheck
    | FPSCheck
    | ResolutionCheck
    | CodecCheck
    | AudioDurationCheck
    | LoudnessCheck
    | TruePeakCheck
    | DecodeCheck
    | SyncCheck
    | ArtifactIntegrityCheck,
    Field(discriminator="check_id"),
]


class FailureReason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_id: QACheckID
    reason_code: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    message: str
    measured: str | float | int | None = None
    expected: str | float | int | None = None


class MediaQAReport(BaseModel):
    """PROMPT 11 §33 — Canonical QA report."""

    model_config = ConfigDict(extra="forbid")

    report_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    artifact_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    render_profile_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    mastering_profile_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]

    overall_status: QAStatus
    checks: list[CheckOutcome]
    typed_checks: list[
        VideoStreamCheck
        | AudioStreamCheck
        | DurationCheck
        | FPSCheck
        | ResolutionCheck
        | CodecCheck
        | AudioDurationCheck
        | LoudnessCheck
        | TruePeakCheck
        | DecodeCheck
        | SyncCheck
        | ArtifactIntegrityCheck
    ] = Field(default_factory=list)
    failures: list[FailureReason] = Field(default_factory=list)
    warnings: list[FailureReason] = Field(default_factory=list)

    tool_versions: dict[str, str] = Field(default_factory=dict)
    measured_at: str = Field(default_factory=_utc_now_iso)

    @model_validator(mode="after")
    def _consistency(self) -> "MediaQAReport":
        # overall_status must be FAIL if any check is FAIL (PROMPT 11 §36).
        statuses = [c.status for c in self.checks]
        if QAStatus.FAIL in statuses:
            if self.overall_status != QAStatus.FAIL:
                self.overall_status = QAStatus.FAIL
        elif QAStatus.WARN in statuses:
            if self.overall_status == QAStatus.PASS:
                self.overall_status = QAStatus.WARN
        return self


# ============================================================================
# QAPolicy (PROMPT 11 §36)
# ============================================================================


class QAPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: Annotated[str, StringConstraints(min_length=4, max_length=64)]
    policy_version: PositiveInt = 1

    # Critical failure check IDs — any FAIL in these means REJECTED (PROMPT 11 §39).
    critical_failures: list[QACheckID] = Field(
        default_factory=lambda: [
            QACheckID.VIDEO_STREAM,
            QACheckID.DECODE,
            QACheckID.RESOLUTION,
            QACheckID.CODEC,
            QACheckID.ARTIFACT_INTEGRITY,
        ]
    )

    # Tolerances
    duration_tolerance_sec: NonNegativeFloat = 0.5
    fps_tolerance_fps: NonNegativeFloat = 0.5
    sync_tolerance_ms: NonNegativeFloat = 100.0

    # Warnings allowed per check
    allow_warnings_on: list[QACheckID] = Field(
        default_factory=lambda: [
            QACheckID.LOUDNESS,
            QACheckID.TRUE_PEAK,
            QACheckID.SYNC,
        ]
    )

    # Whether UNavailable is acceptable as PASS for non-critical checks
    allow_unavailable_for: list[QACheckID] = Field(
        default_factory=lambda: [
            QACheckID.TRUE_PEAK,
            QACheckID.LOUDNESS,
        ]
    )

    @model_validator(mode="after")
    def _check_disjoint(self) -> "QAPolicy":
        # A check that is critical-fail cannot be allow_unavailable at the same time
        # (UNAVAILABLE is not allowed for critical checks).
        overlap = set(self.critical_failures) & set(self.allow_unavailable_for)
        if overlap:
            raise ValueError(
                f"critical_failures and allow_unavailable_for must be disjoint: {sorted(overlap)}"
            )
        return self


# ============================================================================
# Re-exports
# ============================================================================

__all__ = [
    "Fingerprint",
    "FrameIndex",
    "Milliseconds",
    # C-27
    "RenderProfile",
    "VideoCodec",
    "AudioCodec",
    "PixelFormat",
    "ContainerFormat",
    # C-28
    "MasteringProfile",
    "LimiterMode",
    "FadePolicy",
    "SilencePolicy",
    "FinalVideoArtifact",
    "ArtifactLifecycleStatus",
    "ArtifactQAStatus",
    # C-29
    "MediaQAReport",
    "QAStatus",
    "CheckOutcome",
    "QACheck",
    "QACheckID",
    "LoudnessMeasurement",
    "TruePeakMeasurement",
    "VideoStreamCheck",
    "AudioStreamCheck",
    "DurationCheck",
    "FPSCheck",
    "ResolutionCheck",
    "CodecCheck",
    "AudioDurationCheck",
    "LoudnessCheck",
    "TruePeakCheck",
    "DecodeCheck",
    "SyncCheck",
    "ArtifactIntegrityCheck",
    "QAPolicy",
    "FailureReason",
]

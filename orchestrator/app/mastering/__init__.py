"""
PROMPT 11 — Final Mastering, Media Pipeline & Video QA Engine.

PUBLIC API:

This package owns the deterministic final-media pipeline:

  RenderPlan
    → PreflightValidation
    → Render (Remotion)
    → RawRenderArtifact
    → AudioMix (FFmpeg amix with explicit buses)
    → Audio Mastering (loudnorm + true-peak limiter)
    → Media QA (checks against RenderProfile + MasteringProfile)
    → FinalVideoArtifact (atomic promotion)

Architectural rules (PROMPT 11 §3, §44, §60):
  * Editorial does NOT own final mastering; this package consumes
    RenderPlan and produces FinalVideoArtifact.
  * FFmpeg / FFprobe invocations live ONLY inside MediaProcessor.
    Application code must not shell out to ffmpeg directly.
  * No LLM calls anywhere in this pipeline.
  * QA failures do NOT silently auto-pass — UNVERIFIED is reported
    as `UNAVAILABLE`, not `PASS`.
  * No file may be promoted to `final` until all required QA checks
    have status PASS or WARN (per policy).

Modules:
  - schemas        C-27 RenderProfile, C-28 MasteringProfile + FinalVideoArtifact,
                   C-29 MediaQAReport + checks
  - media_processor  isolated FFmpeg / FFprobe wrapper (safe argv, no shell)
  - ffmpeg       low-level ffmpeg/ffprobe helpers (probe, loudness, peak)
  - buses        explicit mix-bus architecture (narration / dialogue /
                 music / sfx / ambience / master)
  - qa           MediaQAEngine + QAPolicy + check implementations
  - pipeline     MasteringPipeline orchestrator (preflight → render →
                 master → qa → promote)
  - artifact     RawRenderArtifact + FinalVideoArtifact persistence

Renderer-side mirror lives under `renderer/src/mastering/`.
"""

from .schemas import (
    # C-27
    RenderProfile,
    VideoCodec,
    AudioCodec,
    PixelFormat,
    ContainerFormat,
    # C-28
    MasteringProfile,
    LimiterMode,
    FadePolicy,
    SilencePolicy,
    FinalVideoArtifact,
    ArtifactLifecycleStatus,
    ArtifactQAStatus,
    # C-29
    MediaQAReport,
    QAStatus,
    CheckOutcome,
    QACheck,
    QACheckID,
    LoudnessMeasurement,
    TruePeakMeasurement,
    VideoStreamCheck,
    AudioStreamCheck,
    DurationCheck,
    FPSCheck,
    ResolutionCheck,
    CodecCheck,
    AudioDurationCheck,
    LoudnessCheck,
    TruePeakCheck,
    DecodeCheck,
    SyncCheck,
    ArtifactIntegrityCheck,
    # shared
    Fingerprint,
    FrameIndex,
    Milliseconds,
    # policies
    QAPolicy,
    FailureReason,
)
from .artifact import (
    RawRenderArtifact,
    load_render_profile,
    save_render_profile,
    load_mastering_profile,
    save_mastering_profile,
    compute_artifact_fingerprint,
)
from .qa import MediaQAEngine, run_media_qa
from .pipeline import MasteringPipeline, PipelineResult
from .media_processor import MediaProcessor, MediaProcessorError

__all__ = [
    "RenderProfile",
    "VideoCodec",
    "AudioCodec",
    "PixelFormat",
    "ContainerFormat",
    "MasteringProfile",
    "LimiterMode",
    "FadePolicy",
    "SilencePolicy",
    "FinalVideoArtifact",
    "ArtifactLifecycleStatus",
    "ArtifactQAStatus",
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
    "Fingerprint",
    "FrameIndex",
    "Milliseconds",
    "QAPolicy",
    "FailureReason",
    "RawRenderArtifact",
    "load_render_profile",
    "save_render_profile",
    "load_mastering_profile",
    "save_mastering_profile",
    "compute_artifact_fingerprint",
    "MediaQAEngine",
    "run_media_qa",
    "MasteringPipeline",
    "PipelineResult",
    "MediaProcessor",
    "MediaProcessorError",
]

"""
PROMPT 11 — Artifact module: RawRenderArtifact + fingerprint helpers.

Provides:
  - compute_render_profile_fingerprint   — stable hash of RenderProfile bytes-affecting fields
  - compute_mastering_profile_fingerprint — stable hash of MasteringProfile bytes-affecting fields
  - compute_final_artifact_fingerprint   — stable hash of FinalVideoArtifact identity fields
  - compute_artifact_fingerprint         — wrapper used by MediaProcessor
  - RawRenderArtifact                    — canonical record of the rendered (pre-master) MP4
  - load/save helpers for profiles and raw artifacts

All fingerprints are SHA-256 over canonical JSON (sorted keys, no
whitespace, UTF-8). No file content is included; content identity is
captured by `checksum_sha256` separately on FinalVideoArtifact.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    StringConstraints,
)
from typing_extensions import Annotated

from .schemas import (
    AudioCodec,
    ContainerFormat,
    Fingerprint,
    LimiterMode,
    FadePolicy,
    PixelFormat,
    SilencePolicy,
    VideoCodec,
)

# ============================================================================
# Fingerprint helpers
# ============================================================================


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    """Stable JSON bytes for fingerprinting.

    Keys are sorted, separators are tight, UTF-8.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _hash(payload: bytes, prefix: str) -> str:
    """SHA-256 hex digest prefixed with the namespace."""
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def compute_render_profile_fingerprint(
    *,
    width: int,
    height: int,
    fps: float,
    pixel_format: PixelFormat,
    video_codec: VideoCodec,
    video_bitrate_kbps: int,
    video_crf: int,
    audio_codec: AudioCodec,
    audio_sample_rate_hz: int,
    audio_channels: int,
    audio_bitrate_kbps: int,
    container: ContainerFormat,
) -> Fingerprint:
    payload = {
        "width": int(width),
        "height": int(height),
        "fps": float(fps),
        "pixel_format": str(pixel_format.value if hasattr(pixel_format, "value") else pixel_format),
        "video_codec": str(video_codec.value if hasattr(video_codec, "value") else video_codec),
        "video_bitrate_kbps": int(video_bitrate_kbps),
        "video_crf": int(video_crf),
        "audio_codec": str(audio_codec.value if hasattr(audio_codec, "value") else audio_codec),
        "audio_sample_rate_hz": int(audio_sample_rate_hz),
        "audio_channels": int(audio_channels),
        "audio_bitrate_kbps": int(audio_bitrate_kbps),
        "container": str(container.value if hasattr(container, "value") else container),
    }
    return _hash(_canonical_payload(payload), "rp")


def compute_mastering_profile_fingerprint(
    *,
    target_lufs: float,
    loudness_tolerance_lu: float,
    max_true_peak_dbtp: float,
    normalization_enabled: bool,
    limiter_mode: LimiterMode,
    limiter_max_attack_ms: float,
    limiter_release_ms: float,
    silence_policy: SilencePolicy,
    silence_tolerance_sec: float,
    silence_excessive_sec: float,
    fade_policy: FadePolicy,
    music_duck_db: float,
) -> Fingerprint:
    payload = {
        "target_lufs": float(target_lufs),
        "loudness_tolerance_lu": float(loudness_tolerance_lu),
        "max_true_peak_dbtp": float(max_true_peak_dbtp),
        "normalization_enabled": bool(normalization_enabled),
        "limiter_mode": str(limiter_mode.value if hasattr(limiter_mode, "value") else limiter_mode),
        "limiter_max_attack_ms": float(limiter_max_attack_ms),
        "limiter_release_ms": float(limiter_release_ms),
        "silence_policy": str(
            silence_policy.value if hasattr(silence_policy, "value") else silence_policy
        ),
        "silence_tolerance_sec": float(silence_tolerance_sec),
        "silence_excessive_sec": float(silence_excessive_sec),
        "fade_policy": str(fade_policy.value if hasattr(fade_policy, "value") else fade_policy),
        "music_duck_db": float(music_duck_db),
    }
    return _hash(_canonical_payload(payload), "mp")


def compute_final_artifact_fingerprint(
    *,
    project_id: str,
    render_plan_id: str,
    render_profile_id: str,
    mastering_profile_id: str,
    renderer_version: str,
    duration_sec: float,
    frame_count: int,
    video_codec: VideoCodec,
    audio_codec: AudioCodec,
    audio_sample_rate_hz: int,
    audio_channels: int,
    checksum_sha256: str,
) -> Fingerprint:
    payload = {
        "project_id": str(project_id),
        "render_plan_id": str(render_plan_id),
        "render_profile_id": str(render_profile_id),
        "mastering_profile_id": str(mastering_profile_id),
        "renderer_version": str(renderer_version),
        "duration_sec": round(float(duration_sec), 6),
        "frame_count": int(frame_count),
        "video_codec": str(video_codec.value if hasattr(video_codec, "value") else video_codec),
        "audio_codec": str(audio_codec.value if hasattr(audio_codec, "value") else audio_codec),
        "audio_sample_rate_hz": int(audio_sample_rate_hz),
        "audio_channels": int(audio_channels),
        "checksum_sha256": str(checksum_sha256),
    }
    return _hash(_canonical_payload(payload), "fa")


def compute_artifact_fingerprint(*parts: str) -> Fingerprint:
    """Generic fingerprint used by `RawRenderArtifact`."""
    return _hash(_canonical_payload({"parts": list(parts)}), "rr")


# ============================================================================
# RawRenderArtifact — the un-mastered, just-rendered MP4 record
# ============================================================================


class RawRenderArtifact(BaseModel):
    """PROMPT 11 §10 — Record of the rendered (pre-master) MP4.

    The file itself remains at `raw_path` until mastering is complete;
    only the metadata is captured here for traceability.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    project_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    render_plan_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    render_profile_id: Annotated[str, StringConstraints(min_length=4, max_length=128)]
    renderer_version: Annotated[str, StringConstraints(min_length=1, max_length=64)]

    raw_path: str = Field(description="Absolute or relative path to the raw MP4")
    file_size_bytes: NonNegativeInt
    duration_sec: float
    fps: float
    width: int
    height: int
    has_audio: bool

    source_fingerprint: Annotated[
        str,
        StringConstraints(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_\-:.]+$"),
    ] = Field(
        description="Fingerprint of the inputs (RenderPlan + AudioArtifacts + AnimationPlan versions)"
    )

    created_at: str = Field(default_factory=lambda: _utc_now_iso_now())

    fingerprint: str = Field(default="", description="Auto-populated fingerprint")

    def compute_fingerprint(self) -> Fingerprint:
        payload = {
            "artifact_id": self.artifact_id,
            "render_plan_id": self.render_plan_id,
            "render_profile_id": self.render_profile_id,
            "renderer_version": self.renderer_version,
            "raw_path": self.raw_path,
            "file_size_bytes": self.file_size_bytes,
            "duration_sec": round(self.duration_sec, 6),
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "has_audio": self.has_audio,
            "source_fingerprint": self.source_fingerprint,
        }
        return _hash(_canonical_payload(payload), "rr")

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        # Auto-populate fingerprint if missing
        if not self.fingerprint:
            self.fingerprint = self.compute_fingerprint()


def _utc_now_iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# Profile load/save helpers
# ============================================================================


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """Atomic JSON write — write to .tmp, then os.replace (PROMPT 11 §47)."""
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def save_render_profile(profile, path: Path) -> Path:
    _atomic_write(path, profile.model_dump(mode="json"))
    return path


def load_render_profile(path: Path):
    from .schemas import RenderProfile  # local to avoid cycles

    return RenderProfile.model_validate_json(path.read_text(encoding="utf-8"))


def save_mastering_profile(profile, path: Path) -> Path:
    _atomic_write(path, profile.model_dump(mode="json"))
    return path


def load_mastering_profile(path: Path):
    from .schemas import MasteringProfile  # local to avoid cycles

    return MasteringProfile.model_validate_json(path.read_text(encoding="utf-8"))


def save_raw_artifact(artifact: RawRenderArtifact, path: Path) -> Path:
    _atomic_write(path, artifact.model_dump(mode="json"))
    return path


def load_raw_artifact(path: Path) -> RawRenderArtifact:
    return RawRenderArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def save_final_artifact(artifact, path: Path) -> Path:
    _atomic_write(path, artifact.model_dump(mode="json"))
    return path


def load_final_artifact(path: Path):
    from .schemas import FinalVideoArtifact  # local to avoid cycles

    return FinalVideoArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def save_qa_report(report, path: Path) -> Path:
    _atomic_write(path, report.model_dump(mode="json"))
    return path


def load_qa_report(path: Path):
    from .schemas import MediaQAReport  # local to avoid cycles

    return MediaQAReport.model_validate_json(path.read_text(encoding="utf-8"))

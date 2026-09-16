"""Deterministic audio validation (PROMPT 8 §22).

Validates a synthesized AudioArtifact against the canonical requirements:
- file exists
- format matches declared `format`
- sample rate / channels / bit depth match declared metadata
- duration is within `±0.5s` of declared `duration_sec` (or matches)
- WAV is decodeable end-to-end

Uses Python stdlib `wave` for WAV; for MP3 we verify the file exists and
is non-empty (full probe requires pydub/ffprobe which may not be present).

No silent failures. Every rejected artifact is recorded with a reason.
"""
from __future__ import annotations

import wave
from dataclasses import dataclass, field
from pathlib import Path

from app.voice.schemas import (
    AudioArtifact,
    AudioArtifactStatus,
    TimestampSource,
)


@dataclass
class AudioValidationResult:
    """Result of validating an AudioArtifact."""
    valid: bool
    artifact_id: str
    issues: list[str] = field(default_factory=list)
    actual_duration_sec: float = 0.0
    actual_sample_rate: int = 0
    actual_channels: int = 0
    actual_bits: int = 0
    actual_byte_size: int = 0


class AudioValidationError(Exception):
    """Raised when audio validation fails."""


# Tolerance for declared-vs-actual duration (seconds).
_DURATION_TOLERANCE_SEC = 0.5


def validate_audio_file(
    audio_path: str | Path,
    declared_format: str = "wav",
    declared_sample_rate: int = 22050,
    declared_channels: int = 1,
    declared_bits: int = 16,
    declared_duration_sec: float = 0.0,
    artifact_id: str = "",
) -> AudioValidationResult:
    """Validate a single audio file against declared metadata."""
    issues: list[str] = []
    actual_duration = 0.0
    actual_sr = 0
    actual_ch = 0
    actual_bits = 0
    actual_size = 0

    p = Path(audio_path)
    if not p.exists():
        return AudioValidationResult(
            valid=False,
            artifact_id=artifact_id,
            issues=["audio file does not exist"],
        )

    actual_size = p.stat().st_size
    if actual_size == 0:
        issues.append("audio file is empty (0 bytes)")

    fmt = declared_format.lower()
    if fmt == "wav":
        try:
            with wave.open(str(p), "rb") as wf:
                actual_ch = wf.getnchannels()
                actual_bits = wf.getsampwidth() * 8
                actual_sr = wf.getframerate()
                n_frames = wf.getnframes()
                actual_duration = n_frames / max(actual_sr, 1)
                # Read every frame to verify decodeability (no corruption).
                _ = wf.readframes(n_frames)
        except wave.Error as exc:
            issues.append(f"WAV decode error: {exc}")
        except EOFError:
            issues.append("WAV file truncated (unexpected EOF)")
        except Exception as exc:  # noqa: BLE001 — defensive
            issues.append(f"WAV parse failure: {type(exc).__name__}: {exc}")

        if not issues:
            if actual_ch != declared_channels:
                issues.append(
                    f"channel mismatch: declared={declared_channels}, actual={actual_ch}"
                )
            if actual_bits != declared_bits:
                issues.append(
                    f"bits-per-sample mismatch: declared={declared_bits}, actual={actual_bits}"
                )
            # Sample rate is allowed to differ (resampling downstream),
            # but we log a warning.
            if actual_sr != declared_sample_rate:
                issues.append(
                    f"sample-rate mismatch: declared={declared_sample_rate}, actual={actual_sr}"
                )
    elif fmt == "mp3":
        # Without pydub/ffprobe we can only check non-empty size.
        if actual_size < 64:
            issues.append("mp3 file too small to be valid (< 64 bytes)")
        # Duration check skipped (requires ffprobe).
    else:
        issues.append(f"unsupported declared format: {fmt!r}")

    # Duration check (apply only if we could probe a real duration).
    if fmt == "wav" and not issues and actual_duration > 0:
        if abs(actual_duration - declared_duration_sec) > _DURATION_TOLERANCE_SEC:
            issues.append(
                f"duration mismatch: declared={declared_duration_sec:.3f}s, "
                f"actual={actual_duration:.3f}s (tolerance ±{_DURATION_TOLERANCE_SEC}s)"
            )

    return AudioValidationResult(
        valid=len(issues) == 0,
        artifact_id=artifact_id,
        issues=issues,
        actual_duration_sec=actual_duration,
        actual_sample_rate=actual_sr,
        actual_channels=actual_ch,
        actual_bits=actual_bits,
        actual_byte_size=actual_size,
    )


def apply_validation_to_artifact(
    artifact: AudioArtifact,
) -> AudioArtifact:
    """Validate artifact and update its `status` field."""
    result = validate_audio_file(
        audio_path=artifact.absolute_path or artifact.uri,
        declared_format=artifact.format,
        declared_sample_rate=artifact.sample_rate,
        declared_channels=artifact.channels,
        declared_bits=artifact.bits_per_sample,
        declared_duration_sec=artifact.duration_sec,
        artifact_id=artifact.artifact_id,
    )
    if result.valid:
        # VALIDATED: file is good. The `NORMALIZED` state is for future use
        # (loudness / format normalization).
        artifact.status = AudioArtifactStatus.VALIDATED
    else:
        artifact.status = AudioArtifactStatus.REJECTED
        for issue in result.issues:
            artifact.metadata.setdefault("validation_issues", []).append(issue)
    artifact.metadata.setdefault(
        "validation_actual_duration_sec", result.actual_duration_sec,
    )
    artifact.metadata.setdefault(
        "validation_actual_sample_rate", result.actual_sample_rate,
    )
    artifact.metadata.setdefault(
        "validation_actual_channels", result.actual_channels,
    )
    artifact.metadata.setdefault(
        "validation_actual_byte_size", result.actual_byte_size,
    )
    return artifact


def parse_timestamps_from_response(
    word_timestamps: list[dict],
    duration_sec: float,
    declared_format: str,
) -> tuple[list, TimestampSource]:
    """Translate provider word_timestamps dicts into canonical WordTiming.

    Returns `(words, source)`. Source is PROVIDER_NATIVE / UNIFORM_ALIGNMENT /
    UNAVAILABLE based on input quality. Never fabricates timestamps.
    """
    from app.voice.schemas import WordTiming, TimestampSource
    if not word_timestamps:
        return [], TimestampSource.UNAVAILABLE

    # Detect "uniform alignment" by checking that inter-word intervals are equal.
    starts = [float(w.get("start_sec", 0.0)) for w in word_timestamps]
    ends = [float(w.get("end_sec", 0.0)) for w in word_timestamps]
    if len(starts) >= 2:
        intervals = [ends[i] - starts[i] for i in range(len(starts))]
        spread = max(intervals) - min(intervals)
        if spread < 1e-3:
            source = TimestampSource.UNIFORM_ALIGNMENT
        else:
            source = TimestampSource.PROVIDER_NATIVE
    else:
        source = TimestampSource.PROVIDER_NATIVE

    out = []
    for i, raw in enumerate(word_timestamps):
        word = str(raw.get("word", "")).strip()
        if not word:
            continue
        start_sec = float(raw.get("start_sec", 0.0))
        end_sec = float(raw.get("end_sec", start_sec + 0.1))
        confidence = raw.get("confidence", None)
        try:
            confidence_f = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence_f = None
        out.append(WordTiming(
            word=word,
            start_sec=max(0.0, start_sec),
            end_sec=max(start_sec + 1e-6, end_sec),
            confidence=confidence_f,
        ))
    return out, source


__all__ = [
    "AudioValidationResult",
    "AudioValidationError",
    "validate_audio_file",
    "apply_validation_to_artifact",
    "parse_timestamps_from_response",
]

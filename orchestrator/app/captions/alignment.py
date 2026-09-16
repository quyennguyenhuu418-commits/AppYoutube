"""Forced-alignment provider boundary (PROMPT 9 §34).

This module does NOT implement a real forced-alignment model. It only
exposes the interface so a future provider (Whisper alignment, MFA,
wav2vec, provider-native alignment) can be slotted in without touching
downstream code.

Concrete providers:

- ``UniformAlignmentProvider`` — deterministic fallback used when no
  real alignment engine is available. Honors
  ``TimestampSource.UNIFORM_ALIGNMENT`` honestly (PROMPT 9 §36).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.voice.schemas import (
    AudioArtifact,
    NarrationUnit,
    SpeechTiming,
    TimestampSource,
    WordTiming,
)


@dataclass(frozen=True)
class AlignmentRequest:
    """Inputs for an alignment provider."""
    audio: AudioArtifact
    narration: NarrationUnit
    expected_duration_sec: float | None = None


@dataclass(frozen=True)
class AlignmentResult:
    """Output of an alignment provider."""
    timing: SpeechTiming


@runtime_checkable
class AlignmentProvider(Protocol):
    """Provider boundary for forced alignment (PROMPT 9 §34)."""

    provider_id: str

    def align(self, request: AlignmentRequest) -> AlignmentResult: ...


class UniformAlignmentProvider:
    """Deterministic uniform-pacing fallback (PROMPT 9 §36).

    Honest about its quality: ``timestamp_source = UNIFORM_ALIGNMENT``,
    low confidence.
    """

    provider_id = "uniform_v1"

    def align(self, request: AlignmentRequest) -> AlignmentResult:
        text = request.narration.text
        tokens = [t for t in re.split(r"\s+", text.strip()) if t]
        if not tokens:
            words: list[WordTiming] = []
        else:
            # Use audio duration; fall back to narration.expected_duration_sec.
            duration = (
                request.expected_duration_sec
                if request.expected_duration_sec
                else request.audio.duration_sec
            )
            duration = max(duration, 0.001)
            weights = [max(1, len(t)) for t in tokens]
            total = sum(weights)
            words = []
            cursor = 0.0
            for tok, w in zip(tokens, weights):
                dur = (w / total) * duration
                start = cursor
                end = min(duration, cursor + dur)
                words.append(
                    WordTiming(
                        word=tok,
                        start_sec=round(start, 6),
                        end_sec=round(end, 6),
                        confidence=None,
                    )
                )
                cursor = end

        timing = SpeechTiming(
            timing_id=f"timing_{request.audio.artifact_id}",
            artifact_id=request.audio.artifact_id,
            narration_id=request.narration.narration_id,
            language=request.narration.language,
            timestamp_source=TimestampSource.UNIFORM_ALIGNMENT,
            words=words,
            segments=[],
            duration_sec=request.audio.duration_sec,
            provider=request.audio.provider,
        )
        return AlignmentResult(timing=timing)


__all__ = [
    "AlignmentProvider",
    "AlignmentRequest",
    "AlignmentResult",
    "UniformAlignmentProvider",
]

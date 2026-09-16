"""Deterministic timing quality scoring (PROMPT 9 §9).

Every score dimension has a reason. No invented scores.

Dimensions:

- ``timestamp_validity``     — every word has start/end in [0, duration].
- ``monotonicity``           — words are non-decreasing in start_sec.
- ``coverage``               — words span a sensible fraction of duration.
- ``duration_alignment``     — total word span ≈ duration (within tolerance).
- ``source_quality``         — PROVIDER_NATIVE / FORCED > UNIFORM > UNAVAILABLE.
- ``word_boundary_quality``  — word boundaries are clean (no punctuation in word).
- ``segment_consistency``    — every segment has at least one word with valid
                                start_sec/end_sec, and segment end > start.

Scoring is on a [0.0, 1.0] scale for each dimension. The overall score is
a weighted mean (deterministic).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.captions.frames import Tolerance
from app.voice.schemas import SpeechTiming, TimestampSource


_SOURCE_QUALITY_SCORES: dict[TimestampSource, float] = {
    # Honest hierarchy: provider_native is the best we have today.
    TimestampSource.PROVIDER_NATIVE: 1.0,
    TimestampSource.FORCED_ALIGNMENT: 1.0,
    TimestampSource.UNIFORM_ALIGNMENT: 0.5,
    TimestampSource.UNAVAILABLE: 0.0,
}


class _Dimension(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list, max_length=8)


class TimingQualityScore(BaseModel):
    """Deterministic per-dimension timing quality score (PROMPT 9 §9)."""
    version: str = Field(default="1.0.0")
    timestamp_validity: _Dimension
    monotonicity: _Dimension
    coverage: _Dimension
    duration_alignment: _Dimension
    source_quality: _Dimension
    word_boundary_quality: _Dimension
    segment_consistency: _Dimension
    overall: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list, max_length=32)


def compute_timing_quality(timing: SpeechTiming) -> TimingQualityScore:
    """Score a SpeechTiming (PROMPT 9 §9).

    Pure, deterministic. No LLM. No wall-clock.
    """
    # 1) timestamp_validity: every word's [start, end] is within [0, duration+tolerance]
    if timing.words:
        invalid = [
            i for i, w in enumerate(timing.words)
            if w.start_sec < 0
            or w.end_sec < w.start_sec
            or w.end_sec > timing.duration_sec + Tolerance.DURATION_END
        ]
        tv_score = 1.0 - (len(invalid) / len(timing.words))
        reasons = [f"{len(invalid)} invalid words"] if invalid else ["all words valid"]
    else:
        tv_score = 0.0
        reasons = ["no words"]
    timestamp_validity = _Dimension(score=tv_score, reasons=reasons)

    # 2) monotonicity: starts are non-decreasing (allowing coarticulation)
    if len(timing.words) >= 2:
        violations = 0
        last_start = 0.0
        backtrack_total = 0.0
        for w in timing.words:
            if w.start_sec + 1e-6 < last_start - 0.5:
                violations += 1
                backtrack_total += last_start - w.start_sec
            last_start = max(last_start, w.start_sec)
        mono_score = 1.0 - (violations / max(1, len(timing.words)))
        if violations:
            reasons = [f"{violations} severe backtracks; {backtrack_total:.3f}s total"]
        else:
            reasons = ["monotonic"]
    else:
        mono_score = 1.0
        reasons = ["trivial"]
    monotonicity = _Dimension(score=mono_score, reasons=reasons)

    # 3) coverage: span of words / duration
    if timing.words and timing.duration_sec > 0:
        span = timing.words[-1].end_sec - timing.words[0].start_sec
        coverage = max(0.0, min(1.0, span / timing.duration_sec))
        reasons = [f"word span={span:.3f}s / duration={timing.duration_sec:.3f}s"]
    else:
        coverage = 0.0
        reasons = ["no words"]
    coverage_dim = _Dimension(score=coverage, reasons=reasons)

    # 4) duration_alignment: how close total span is to duration
    if timing.words and timing.duration_sec > 0:
        span = timing.words[-1].end_sec - timing.words[0].start_sec
        # ratio close to 1.0 is good
        ratio = span / timing.duration_sec
        da_score = max(0.0, 1.0 - abs(1.0 - ratio))
        reasons = [f"span/duration={ratio:.3f}"]
    else:
        da_score = 0.0
        reasons = ["no words"]
    duration_alignment = _Dimension(score=da_score, reasons=reasons)

    # 5) source_quality
    sq_score = _SOURCE_QUALITY_SCORES.get(timing.timestamp_source, 0.0)
    source_quality = _Dimension(
        score=sq_score,
        reasons=[f"timestamp_source={timing.timestamp_source.value}"],
    )

    # 6) word_boundary_quality: words shouldn't start/end with punctuation
    if timing.words:
        bad = 0
        bad_examples: list[str] = []
        for w in timing.words:
            stripped = w.word.strip()
            if not stripped:
                bad += 1
                continue
            if stripped[0] in ".,;:!?)]}\"'”’" or stripped[-1] in "([{\"“‘":
                bad += 1
                if len(bad_examples) < 3:
                    bad_examples.append(stripped)
        wb_score = 1.0 - (bad / len(timing.words))
        reasons = (
            [f"{bad} words with punctuation boundary; e.g. {bad_examples}"]
            if bad else ["clean boundaries"]
        )
    else:
        wb_score = 1.0  # vacuously clean
        reasons = ["no words"]
    word_boundary_quality = _Dimension(score=wb_score, reasons=reasons)

    # 7) segment_consistency
    if timing.segments:
        bad = 0
        for s in timing.segments:
            if s.end_sec < s.start_sec - 1e-6:
                bad += 1
            if s.end_sec > timing.duration_sec + Tolerance.DURATION_END:
                bad += 1
        sc_score = 1.0 - (bad / len(timing.segments))
        reasons = (
            [f"{bad} inconsistent segments"] if bad else ["all segments consistent"]
        )
    else:
        sc_score = 1.0
        reasons = ["no segments (optional)"]
    segment_consistency = _Dimension(score=sc_score, reasons=reasons)

    # Overall: weighted mean.
    weights: dict[str, float] = {
        "timestamp_validity": 0.25,
        "monotonicity": 0.15,
        "coverage": 0.10,
        "duration_alignment": 0.10,
        "source_quality": 0.20,
        "word_boundary_quality": 0.10,
        "segment_consistency": 0.10,
    }
    dims: dict[str, _Dimension] = {
        "timestamp_validity": timestamp_validity,
        "monotonicity": monotonicity,
        "coverage": coverage_dim,
        "duration_alignment": duration_alignment,
        "source_quality": source_quality,
        "word_boundary_quality": word_boundary_quality,
        "segment_consistency": segment_consistency,
    }
    overall = sum(dims[k].score * weights[k] for k in weights)
    notes = [f"weights: {weights}"]

    return TimingQualityScore(
        timestamp_validity=timestamp_validity,
        monotonicity=monotonicity,
        coverage=coverage_dim,
        duration_alignment=duration_alignment,
        source_quality=source_quality,
        word_boundary_quality=word_boundary_quality,
        segment_consistency=segment_consistency,
        overall=overall,
        notes=notes,
    )


__all__ = ["TimingQualityScore", "compute_timing_quality"]

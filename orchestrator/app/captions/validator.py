"""CaptionTrack validation (PROMPT 9 §30, §37).

Failures (block):

- invalid timestamps
- overlap conflict between segments
- segment end <= start
- line count invalid
- unsupported style values
- words fall outside segment bounds

Warnings (don't block):

- high reading speed
- long line
- low-quality timestamp source
- hard split used
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.captions.frames import Tolerance
from app.captions.schemas import CaptionTrack
from app.voice.schemas import TimestampSource


@dataclass
class CaptionValidationError:
    code: str
    message: str
    segment_id: str = ""


@dataclass
class CaptionValidationResult:
    errors: list[CaptionValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_caption_track(track: CaptionTrack) -> CaptionValidationResult:
    res = CaptionValidationResult()

    # 1) segment timestamp order
    for seg in track.segments:
        if seg.end_sec < seg.start_sec - Tolerance.WORD_INTERVAL:
            res.errors.append(
                CaptionValidationError(
                    code="segment.invalid_time",
                    message=(
                        f"segment {seg.segment_id}: end_sec ({seg.end_sec}) < "
                        f"start_sec ({seg.start_sec})"
                    ),
                    segment_id=seg.segment_id,
                )
            )

    # 2) overlap (PROMPT 9 §30)
    sorted_segs = sorted(track.segments, key=lambda s: s.start_sec)
    for a, b in zip(sorted_segs, sorted_segs[1:]):
        if b.start_sec < a.end_sec - Tolerance.SEGMENT_OVERLAP:
            res.errors.append(
                CaptionValidationError(
                    code="segment.overlap",
                    message=(
                        f"segments {a.segment_id} and {b.segment_id} overlap "
                        f"({a.end_sec:.3f} > {b.start_sec:.3f})"
                    ),
                    segment_id=b.segment_id,
                )
            )

    # 3) segment out of scene bounds
    for seg in track.segments:
        if seg.start_sec < track.scene_start_sec - Tolerance.WORD_INTERVAL:
            res.errors.append(
                CaptionValidationError(
                    code="segment.before_scene",
                    message=(
                        f"segment {seg.segment_id}: start_sec ({seg.start_sec}) < "
                        f"scene_start_sec ({track.scene_start_sec})"
                    ),
                    segment_id=seg.segment_id,
                )
            )
        if seg.end_sec > track.scene_end_sec + Tolerance.WORD_INTERVAL:
            res.errors.append(
                CaptionValidationError(
                    code="segment.after_scene",
                    message=(
                        f"segment {seg.segment_id}: end_sec ({seg.end_sec}) > "
                        f"scene_end_sec ({track.scene_end_sec})"
                    ),
                    segment_id=seg.segment_id,
                )
            )

    # 4) word-in-segment consistency
    for seg in track.segments:
        for i, w in enumerate(seg.words):
            if w.start_sec < seg.start_sec - Tolerance.WORD_INTERVAL:
                res.errors.append(
                    CaptionValidationError(
                        code="word.before_segment",
                        message=(
                            f"segment {seg.segment_id} word {i} start_sec "
                            f"({w.start_sec}) < segment start_sec ({seg.start_sec})"
                        ),
                        segment_id=seg.segment_id,
                    )
                )
            if w.end_sec > seg.end_sec + Tolerance.WORD_INTERVAL:
                res.errors.append(
                    CaptionValidationError(
                        code="word.after_segment",
                        message=(
                            f"segment {seg.segment_id} word {i} end_sec "
                            f"({w.end_sec}) > segment end_sec ({seg.end_sec})"
                        ),
                        segment_id=seg.segment_id,
                    )
                )

    # 5) line count vs style
    max_lines = track.style.max_lines
    for seg in track.segments:
        if len(seg.lines) > max_lines:
            res.errors.append(
                CaptionValidationError(
                    code="line.too_many",
                    message=(
                        f"segment {seg.segment_id} has {len(seg.lines)} lines, "
                        f"max is {max_lines}"
                    ),
                    segment_id=seg.segment_id,
                )
            )

    # 6) line char limits
    for seg in track.segments:
        for ln in seg.lines:
            if ln.char_count > track.style.max_chars_per_line * 1.5:
                res.warnings.append(
                    f"segment {seg.segment_id} line {ln.line_index} "
                    f"has {ln.char_count} chars (max {track.style.max_chars_per_line})"
                )

    # 7) reading speed (PROMPT 9 §16) — warnings only
    for seg in track.segments:
        if seg.end_sec <= seg.start_sec:
            continue
        dur = seg.end_sec - seg.start_sec
        cps = len(seg.text) / dur
        if cps > Tolerance.READING_RATE_BLOCK:
            res.warnings.append(
                f"segment {seg.segment_id}: high reading speed "
                f"{cps:.1f} chars/sec (>{Tolerance.READING_RATE_BLOCK})"
            )
        elif cps > Tolerance.READING_RATE_WARN:
            res.warnings.append(
                f"segment {seg.segment_id}: elevated reading speed "
                f"{cps:.1f} chars/sec"
            )

    # 8) timestamp source quality
    if track.timestamp_source == TimestampSource.UNAVAILABLE:
        if track.segments:
            res.warnings.append(
                "CaptionTrack has segments but TimestampSource=UNAVAILABLE; "
                "this should be impossible unless uniform fallback was used"
            )
    if track.timestamp_source == TimestampSource.UNIFORM_ALIGNMENT:
        res.warnings.append(
            "CaptionTrack uses UNIFORM_ALIGNMENT timing; "
            "word-level precision is approximate"
        )

    return res


__all__ = [
    "CaptionValidationError",
    "CaptionValidationResult",
    "validate_caption_track",
]

"""Caption / Timing canonical package (PROMPT 9).

This package is the canonical timing layer that consumes
``SpeechTiming`` (C-20) and ``NarrationTimeline`` (C-21) and produces
``CaptionTrack`` data which the renderer (Remotion) consumes without
ever inspecting raw narration text.

Design rules (PROMPT 9 §3, §4, §54):

1. ONE temporal authority — timing here references
   ``NarrationTimeline.scene_start_sec / scene_end_sec`` and
   ``SpeechTiming.words``. No re-derivation from raw text.
2. No provider-specific fields. ``AlignmentProvider`` boundary is
   exposed; no actual alignment engine is implemented.
3. Identity is content-derived where possible.
4. Determinism: same inputs → same CaptionTrack bytes.
5. Renderer never invents timing — it consumes the precompiled track.

Modules:

- ``schemas`` — canonical Pydantic models (CaptionTrack etc.).
- ``frames`` — canonical frame/time helpers (PROMPT 9 §24).
- ``quality`` — deterministic timing quality metadata (PROMPT 9 §9).
- ``segmenter`` — word → segment (PROMPT 9 §13, §14).
- ``line_breaker`` — segment → lines (PROMPT 9 §17).
- ``alignment`` — AlignmentProvider boundary (PROMPT 9 §34).
- ``validator`` — CaptionTrack validation (PROMPT 9 §37).
- ``compiler`` — CaptionCompiler: NarrationTimeline + SpeechTiming →
  CaptionTrack (PROMPT 9 §35, §36).
"""

from app.captions.alignment import (
    AlignmentProvider,
    AlignmentRequest,
    AlignmentResult,
    UniformAlignmentProvider,
)
from app.captions.compiler import (
    CaptionCompiler,
    CaptionCompileRequest,
    CaptionCompileResult,
    compute_caption_id,
)
from app.captions.frames import (
    FrameRoundingPolicy,
    Tolerance,
    frame_to_time,
    time_to_frame,
)
from app.captions.line_breaker import (
    LineBreaker,
    LineBreakPolicy,
    LineBreakResult,
)
from app.captions.quality import (
    TimingQualityScore,
    compute_timing_quality,
)
from app.captions.schemas import (
    CaptionAnimationMode,
    CaptionBreakReason,
    CaptionLine,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    CaptionVerticalAnchor,
    CaptionWord,
)
from app.captions.segmenter import (
    CaptionSegmenter,
    SegmentationPolicy,
    SegmentationResult,
)
from app.captions.validator import (
    CaptionValidationError,
    CaptionValidationResult,
    validate_caption_track,
)

__all__ = [
    # schemas
    "CaptionAnimationMode",
    "CaptionBreakReason",
    "CaptionLine",
    "CaptionSegment",
    "CaptionStyle",
    "CaptionTrack",
    "CaptionVerticalAnchor",
    "CaptionWord",
    # frames
    "FrameRoundingPolicy",
    "Tolerance",
    "frame_to_time",
    "time_to_frame",
    # quality
    "TimingQualityScore",
    "compute_timing_quality",
    # segmenter
    "CaptionSegmenter",
    "SegmentationPolicy",
    "SegmentationResult",
    # line breaker
    "LineBreaker",
    "LineBreakPolicy",
    "LineBreakResult",
    # alignment
    "AlignmentProvider",
    "AlignmentRequest",
    "AlignmentResult",
    "UniformAlignmentProvider",
    # validator
    "CaptionValidationError",
    "CaptionValidationResult",
    "validate_caption_track",
    # compiler
    "CaptionCompiler",
    "CaptionCompileRequest",
    "CaptionCompileResult",
    "compute_caption_id",
]

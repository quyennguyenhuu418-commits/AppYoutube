"""Canonical Caption / Timing schemas (PROMPT 9 §5, §10, §11).

These models are the canonical timing layer consumed by the Remotion
renderer. They are designed to round-trip JSON with the
``renderer/src/captions/types.ts`` mirror without field loss.

Hierarchy::

    CaptionStyle      (data-driven visual config)
    CaptionWord       (word + timing + traceability)
    CaptionLine       (grouping of words for visual line)
    CaptionSegment    (one readable caption segment)
    CaptionTrack      (per-scene collection)

Cross-references (always by id, never by raw text):

- ``narration_id``  →  ``NarrationUnit.narration_id``  (C-18)
- ``artifact_id``   →  ``AudioArtifact.artifact_id``   (C-19)
- ``speech_timing_id``  →  ``SpeechTiming.timing_id``   (C-20)
- ``scene_id``      →  ``SceneDefinition.scenes[].id`` (C-01)

The renderer MUST consume only these objects; it MUST NOT inspect raw
narration text. (PROMPT 9 §25, §26, §51)
"""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.voice.schemas import TimestampSource

if TYPE_CHECKING:  # pragma: no cover
    from app.captions.quality import TimingQualityScore


# ============================================================================
# Enums
# ============================================================================

class CaptionVerticalAnchor(str, Enum):
    """Where the caption block is anchored vertically (PROMPT 9 §29).

    Aspect-ratio independent. The renderer adapter maps to actual
    coordinates for the current video resolution.
    """
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"
    LOWER_THIRD = "lower_third"


class CaptionAnimationMode(str, Enum):
    """Canonical animation modes (PROMPT 9 §20)."""
    NONE = "none"
    FADE = "fade"
    WORD_HIGHLIGHT = "word_highlight"
    SEGMENT_POP = "segment_pop"


class CaptionBreakReason(str, Enum):
    """Why a segment ended (debug/QA trace, PROMPT 9 §33)."""
    PUNCTUATION = "punctuation"      # . , ; : ! ? — etc.
    MAX_CHARS = "max_chars"          # max_chars_per_line exceeded
    MAX_WORDS = "max_words"          # max_words_per_segment exceeded
    MAX_DURATION = "max_duration"    # max_segment_duration_sec exceeded
    MIN_DURATION = "min_duration"    # segment forced to min length
    PHRASE_BOUNDARY = "phrase"       # weak phrase break
    SPEAKER_CHANGE = "speaker_change"
    NARration_END = "narration_end"
    HARD_SPLIT = "hard_split"        # last resort


# ============================================================================
# CaptionStyle (PROMPT 9 §11)
# ============================================================================

class CaptionStyle(BaseModel):
    """Data-driven visual style (PROMPT 9 §11, §27, §28).

    Resolution-independent. The renderer applies ``safe_area_pct``
    relative to actual video dimensions.
    """
    version: str = Field(default="1.0.0")
    style_id: str = Field(default="documentary_default", min_length=1, max_length=64)
    name: str = Field(default="documentary_default", max_length=64)

    # Typography
    font_family: str = Field(default="Inter, sans-serif", max_length=128)
    font_size_px: int = Field(default=48, ge=12, le=200,
                              description="Reference font size in 1920x1080 space.")
    font_weight: int = Field(default=600, ge=100, le=900)
    letter_spacing_px: float = Field(default=0.0, ge=-4.0, le=8.0)

    # Layout
    max_lines: int = Field(default=2, ge=1, le=4)
    max_chars_per_line: int = Field(default=42, ge=8, le=120)
    line_spacing_px: float = Field(default=6.0, ge=0.0, le=32.0)
    alignment: str = Field(default="center", max_length=16,
                            description="left | center | right")

    # Color
    text_color: str = Field(default="#FFFFFF", max_length=64,
                             description="#RGB or #RRGGBB or #RRGGBBAA, or rgba()/rgb()/hsl(), or named.")
    highlight_color: str = Field(default="#FFD166", max_length=64)
    background_color: str = Field(default="rgba(0,0,0,0.0)", max_length=64)
    shadow: bool = Field(default=True)

    # Safe area / anchor (PROMPT 9 §27, §28, §29)
    safe_area_pct: float = Field(default=0.08, ge=0.0, le=0.25,
                                  description="Horizontal safe area as fraction of width.")
    vertical_safe_area_pct: float = Field(default=0.08, ge=0.0, le=0.25)
    vertical_anchor: CaptionVerticalAnchor = CaptionVerticalAnchor.LOWER_THIRD
    bottom_margin_pct: float = Field(default=0.08, ge=0.0, le=0.4,
                                       description="Used when anchor == BOTTOM or LOWER_THIRD.")

    # Behavior
    animation_mode: CaptionAnimationMode = CaptionAnimationMode.WORD_HIGHLIGHT
    highlight_hold_pad_ms: int = Field(default=120, ge=0, le=400,
                                         description="How long (ms) after end_sec a word stays "
                                                     "highlighted (PROMPT 9 §18).")

    # Diagnostics
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_text_color(self) -> "CaptionStyle":
        # Permissive color check: #RGB, #RRGGBB, #RRGGBBAA, rgba(...), or named.
        v = self.text_color.strip()
        if not (
            v.startswith("#")
            or v.startswith("rgb")
            or v.startswith("hsl")
            or v in {"white", "black", "red", "green", "blue"}
        ):
            raise ValueError(
                f"text_color must be hex / rgb() / hsl() / named; got {v!r}"
            )
        return self


# ============================================================================
# CaptionWord (PROMPT 9 §32)
# ============================================================================

class CaptionWord(BaseModel):
    """One word in a caption segment (PROMPT 9 §10, §32).

    Timing is inherited from ``SpeechTiming`` (PROMPT 9 §7). Traceability
    IDs are present so debugging can walk text → audio → timestamp →
    caption → rendered frame.
    """
    word: str = Field(min_length=1, max_length=128)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    line_index: int = Field(default=0, ge=0, le=8,
                             description="0-based index into CaptionSegment.lines[].")
    position_in_line: int = Field(default=0, ge=0, le=64)

    # Traceability (PROMPT 9 §32)
    narration_id: str = Field(min_length=1, max_length=64)
    artifact_id: str = Field(min_length=1, max_length=64)
    speech_timing_id: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _validate_order(self) -> "CaptionWord":
        if self.end_sec < self.start_sec - 1e-6:
            raise ValueError(
                f"CaptionWord end_sec ({self.end_sec}) < start_sec ({self.start_sec})"
            )
        return self


# ============================================================================
# CaptionLine
# ============================================================================

class CaptionLine(BaseModel):
    """One visual line inside a segment (PROMPT 9 §17)."""
    line_index: int = Field(ge=0, le=8)
    text: str = Field(min_length=1, max_length=512)
    word_count: int = Field(ge=1, le=64)
    char_count: int = Field(ge=1, le=512)
    break_reason: CaptionBreakReason = CaptionBreakReason.PHRASE_BOUNDARY
    word_indices: list[int] = Field(default_factory=list, max_length=64,
                                     description="Indices into CaptionSegment.words[]. "
                                                 "Determines visual order.")


# ============================================================================
# CaptionSegment (PROMPT 9 §10)
# ============================================================================

_SEG_ID_RX = re.compile(r"^[a-z0-9_]+$")


class CaptionSegment(BaseModel):
    """One readable caption segment (PROMPT 9 §10)."""
    version: str = Field(default="1.0.0")
    segment_id: str = Field(min_length=1, max_length=64)
    caption_id: str = Field(default="", max_length=64,
                              description="The CaptionTrack.caption_id this segment belongs to. "
                                          "Backfilled by CaptionCompiler.")
    scene_id: str = Field(min_length=1, max_length=64)
    narration_id: str = Field(min_length=1, max_length=64)

    # Time (canonical seconds; PROMPT 9 §6, §21)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)

    # Content
    text: str = Field(min_length=1, max_length=2000)
    words: list[CaptionWord] = Field(default_factory=list, max_length=64)
    lines: list[CaptionLine] = Field(default_factory=list, max_length=8)

    # Traceability (PROMPT 9 §32)
    artifact_id: str = Field(min_length=1, max_length=64)
    speech_timing_id: str = Field(min_length=1, max_length=64)
    timestamp_source: TimestampSource = TimestampSource.UNAVAILABLE

    # Speaker (PROMPT 9 §31 — optional, never inferred)
    speaker_id: str = Field(default="narrator", max_length=64)
    speaker_name: str = Field(default="", max_length=64)
    speaker_role: str = Field(default="", max_length=32)

    # Style
    style_id: str = Field(default="documentary_default", max_length=64)

    # Emphasis (from NarrationUnit.emphasis_hints)
    emphasis_words: list[int] = Field(default_factory=list, max_length=64,
                                       description="Indices into CaptionSegment.words[].")

    # Diagnostics (PROMPT 9 §33)
    break_reason: CaptionBreakReason = CaptionBreakReason.PHRASE_BOUNDARY
    warnings: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _validate_segment(self) -> "CaptionSegment":
        if not _SEG_ID_RX.match(self.segment_id):
            raise ValueError(
                f"segment_id must match {_SEG_ID_RX.pattern}; got {self.segment_id!r}"
            )
        if self.end_sec < self.start_sec - 1e-6:
            raise ValueError(
                f"CaptionSegment end_sec ({self.end_sec}) < start_sec ({self.start_sec}) "
                f"for segment_id={self.segment_id!r}"
            )
        # Line consistency: every word must reference a valid line_index.
        if self.words and self.lines:
            valid_line_idx = {ln.line_index for ln in self.lines}
            for i, w in enumerate(self.words):
                if w.line_index not in valid_line_idx:
                    raise ValueError(
                        f"word {i} line_index={w.line_index} not in segment lines "
                        f"{sorted(valid_line_idx)}"
                    )
        # Char/word count consistency on lines.
        for ln in self.lines:
            if ln.word_count != len(ln.word_indices):
                raise ValueError(
                    f"line {ln.line_index} word_count={ln.word_count} disagrees with "
                    f"word_indices length {len(ln.word_indices)}"
                )
        return self


# ============================================================================
# CaptionTrack (PROMPT 9 §10)
# ============================================================================

class CaptionTrack(BaseModel):
    """Canonical per-scene caption track (PROMPT 9 §10).

    The renderer consumes a precompiled ``CaptionTrack``. No timing is
    derived in the renderer (PROMPT 9 §25, §26, §51).
    """
    version: str = Field(default="1.0.0")
    track_id: str = Field(min_length=1, max_length=64)
    caption_id: str = Field(min_length=1, max_length=64)
    project_id: str = Field(default="", max_length=64)
    job_id: str = Field(default="", max_length=64)
    narration_timeline_id: str = Field(min_length=1, max_length=64)
    scene_id: str = Field(min_length=1, max_length=64)
    language: str = Field(default="en", min_length=2, max_length=8)
    locale: str = Field(default="en-US", max_length=16)
    fps: int = Field(default=30, ge=12, le=60)

    # Style + segments
    style: CaptionStyle
    segments: list[CaptionSegment] = Field(default_factory=list, max_length=512)
    style_id: str = Field(default="documentary_default", min_length=1, max_length=64)

    # Source attribution (PROMPT 9 §8, §35, §36)
    timestamp_source: TimestampSource = TimestampSource.UNAVAILABLE
    alignment_provider_id: str = Field(default="", max_length=64,
                                         description="e.g. 'mock_uniform' or 'whisper_x' (future).")

    # Quality metadata (PROMPT 9 §9)
    quality: Optional["TimingQualityScore"] = None

    # Scene timing (PROMPT 9 §21)
    scene_start_sec: float = Field(ge=0.0)
    scene_end_sec: float = Field(ge=0.0)

    # Diagnostics
    warnings: list[str] = Field(default_factory=list, max_length=256)
    failures: list[str] = Field(default_factory=list, max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _validate_track(self) -> "CaptionTrack":
        if self.scene_end_sec < self.scene_start_sec - 1e-6:
            raise ValueError(
                f"CaptionTrack scene_end_sec ({self.scene_end_sec}) < "
                f"scene_start_sec ({self.scene_start_sec})"
            )
        # Segment IDs must be unique.
        seen: set[str] = set()
        for s in self.segments:
            if s.segment_id in seen:
                raise ValueError(f"Duplicate segment_id: {s.segment_id!r}")
            seen.add(s.segment_id)
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# Avoid circular import: TimingQualityScore is in app.captions.quality.
# Use model_rebuild() at import time of the quality module (see quality.py).
# noqa: E402
try:
    from app.captions.quality import TimingQualityScore  # type: ignore  # noqa: E402
    CaptionTrack.model_rebuild()
except ImportError:
    pass


__all__ = [
    "CaptionAnimationMode",
    "CaptionBreakReason",
    "CaptionVerticalAnchor",
    "CaptionStyle",
    "CaptionWord",
    "CaptionLine",
    "CaptionSegment",
    "CaptionTrack",
]

"""Canonical frame / time helpers (PROMPT 9 §24).

Single source of truth for ``time_sec ↔ frame`` conversions.

Rounding policy is explicit: ``round(time_sec * fps)`` (banker's round
via Python's built-in ``round``). All conversions in the codebase must
go through these helpers so that frame precision is consistent.
"""
from __future__ import annotations

from enum import Enum
from typing import Final


class FrameRoundingPolicy(str, Enum):
    """How ``time_sec * fps`` is rounded (PROMPT 9 §24).

    The canonical policy is ``ROUND_NEAREST``. ``FLOOR`` and ``CEIL``
    are exposed for explicit use by reconciliation code that needs them
    (e.g. ``FOLLOW_AUDIO`` deciding whether to extend the last frame).
    """
    ROUND_NEAREST = "round_nearest"
    FLOOR = "floor"
    CEIL = "ceil"


# Default policy. All modules that need frame conversion should accept
# an explicit policy; absent one, this default applies.
DEFAULT_FRAMING_POLICY: Final[FrameRoundingPolicy] = FrameRoundingPolicy.ROUND_NEAREST


class Tolerance(float, Enum):
    """Canonical timing tolerances (PROMPT 9 §23)."""
    WORD_INTERVAL = 1e-6       # word interval validity
    SEGMENT_OVERLAP = 1e-6     # segment overlap check
    DURATION_END = 0.5         # allowed word/segment overshoot (sec)
    READING_RATE_WARN = 25.0   # characters/sec warning threshold
    READING_RATE_BLOCK = 40.0  # characters/sec blocking threshold (warning, not fail)
    SCENE_PADDING = 0.05       # default reconciliation padding (sec)


def time_to_frame(
    time_sec: float,
    fps: int,
    policy: FrameRoundingPolicy = DEFAULT_FRAMING_POLICY,
) -> int:
    """Convert seconds to frame index using ``policy`` (PROMPT 9 §24)."""
    if fps <= 0:
        raise ValueError(f"fps must be positive; got {fps}")
    raw = time_sec * fps
    if policy == FrameRoundingPolicy.ROUND_NEAREST:
        # Python's round() is banker's round; we use it directly.
        return int(round(raw))
    if policy == FrameRoundingPolicy.FLOOR:
        return int(raw // 1)
    if policy == FrameRoundingPolicy.CEIL:
        # Ceiling for non-negative.
        return -int(-raw // 1)
    raise ValueError(f"Unknown FrameRoundingPolicy: {policy!r}")


def frame_to_time(
    frame: int,
    fps: int,
) -> float:
    """Convert frame index to seconds (PROMPT 9 §24)."""
    if fps <= 0:
        raise ValueError(f"fps must be positive; got {fps}")
    return frame / fps


__all__ = [
    "DEFAULT_FRAMING_POLICY",
    "FrameRoundingPolicy",
    "Tolerance",
    "frame_to_time",
    "time_to_frame",
]

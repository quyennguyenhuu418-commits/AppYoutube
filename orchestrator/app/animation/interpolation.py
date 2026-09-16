"""Interpolation utilities — canonical interpolation modes.

PROMPT 7 §8: Provide a controlled interpolation system. NO arbitrary JS
functions inside serialized animation contracts.

Supported modes:
    linear, ease_in, ease_out, ease_in_out, hold

The math here is the canonical reference implementation. The TypeScript
runtime MUST produce identical numbers (see `renderer/src/animation/interpolation.ts`).
"""
from __future__ import annotations

import math

from app.animation.schemas import Interpolation


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b at parameter t in [0, 1]."""
    return a + (b - a) * t


def ease_in_cubic(t: float) -> float:
    """Cubic ease-in: starts slow, accelerates."""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out: starts fast, decelerates."""
    v = 1.0 - t
    return 1.0 - v * v * v


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out: slow start, slow end."""
    if t < 0.5:
        return 4.0 * t * t * t
    v = 1.0 - t
    return 1.0 - 4.0 * v * v * v


def interpolate_value(
    a: float,
    b: float,
    t: float,
    mode: Interpolation = Interpolation.LINEAR,
) -> float:
    """Interpolate between a and b at parameter t in [0, 1].

    For HOLD mode, returns a for all t < 1.0 and b for t >= 1.0.
    For LINEAR, uses straight linear interpolation.
    For ease_in/out/in_out, applies the corresponding cubic easing to t
    before linear interpolation.
    """
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0

    if mode == Interpolation.HOLD:
        return a if t < 1.0 else b
    if mode == Interpolation.LINEAR:
        return lerp(a, b, t)
    if mode == Interpolation.EASE_IN:
        return lerp(a, b, ease_in_cubic(t))
    if mode == Interpolation.EASE_OUT:
        return lerp(a, b, ease_out_cubic(t))
    if mode == Interpolation.EASE_IN_OUT:
        return lerp(a, b, ease_in_out_cubic(t))

    # Fallback (should be unreachable — enum is enforced).
    return lerp(a, b, t)


def interpolate_keyframes(
    keyframes: list,
    time_sec: float,
    track_duration: float = 0.0,
) -> float:
    """Find the value at `time_sec` across an ordered list of Keyframes.

    If `track_duration` > 0 and the keyframes' last time_sec differs,
    the keyframes are scaled to span [0, track_duration].

    If there are fewer than 2 keyframes, returns:
        - the single keyframe's value, or
        - 0.0 if there are none.
    """
    if not keyframes:
        return 0.0
    if len(keyframes) == 1:
        return float(keyframes[0].value)

    # Determine effective duration.
    first_t = float(keyframes[0].time_sec)
    last_t = float(keyframes[-1].time_sec)
    if track_duration > 0.0 and last_t > first_t:
        # Scale time_sec into the keyframes' range.
        span = last_t - first_t
        if span > 0.0:
            t_norm = (time_sec / track_duration) * span + first_t
        else:
            t_norm = time_sec
    else:
        t_norm = time_sec

    if t_norm <= float(keyframes[0].time_sec):
        return float(keyframes[0].value)
    if t_norm >= float(keyframes[-1].time_sec):
        return float(keyframes[-1].value)

    # Find the surrounding pair.
    for i in range(len(keyframes) - 1):
        t_a = float(keyframes[i].time_sec)
        t_b = float(keyframes[i + 1].time_sec)
        if t_a <= t_norm <= t_b:
            if t_b == t_a:
                return float(keyframes[i].value)
            local_t = (t_norm - t_a) / (t_b - t_a)
            return interpolate_value(
                float(keyframes[i].value),
                float(keyframes[i + 1].value),
                local_t,
                keyframes[i].interpolation,
            )

    # Should be unreachable given the bounds check above.
    return float(keyframes[-1].value)

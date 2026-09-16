"""
PROMPT 7 — Animation Interpolation tests.

Verifies the canonical interpolation modes produce expected values.
"""
from __future__ import annotations

from app.animation.interpolation import (
    ease_in_cubic,
    ease_in_out_cubic,
    ease_out_cubic,
    interpolate_keyframes,
    interpolate_value,
    lerp,
)
from app.animation.schemas import Interpolation, Keyframe


# ---- lerp ----

def test_lerp_zero_returns_a():
    assert lerp(0.0, 100.0, 0.0) == 0.0


def test_lerp_one_returns_b():
    assert lerp(0.0, 100.0, 1.0) == 100.0


def test_lerp_half_returns_midpoint():
    assert lerp(10.0, 20.0, 0.5) == 15.0


# ---- easings ----

def test_ease_in_zero():
    assert ease_in_cubic(0.0) == 0.0


def test_ease_in_one():
    assert ease_in_cubic(1.0) == 1.0


def test_ease_out_zero():
    assert ease_out_cubic(0.0) == 0.0


def test_ease_out_one():
    assert ease_out_cubic(1.0) == 1.0


def test_ease_in_out_zero():
    assert ease_in_out_cubic(0.0) == 0.0


def test_ease_in_out_one():
    assert ease_in_out_cubic(1.0) == 1.0


def test_ease_in_out_half():
    assert abs(ease_in_out_cubic(0.5) - 0.5) < 1e-9


# ---- interpolate_value ----

def test_interpolate_value_linear():
    assert interpolate_value(0.0, 100.0, 0.5, Interpolation.LINEAR) == 50.0


def test_interpolate_value_ease_in_slower_than_linear():
    linear = interpolate_value(0.0, 100.0, 0.5, Interpolation.LINEAR)
    ease_in = interpolate_value(0.0, 100.0, 0.5, Interpolation.EASE_IN)
    assert ease_in < linear


def test_interpolate_value_ease_out_faster_than_linear():
    linear = interpolate_value(0.0, 100.0, 0.5, Interpolation.LINEAR)
    ease_out = interpolate_value(0.0, 100.0, 0.5, Interpolation.EASE_OUT)
    assert ease_out > linear


def test_interpolate_value_hold():
    assert interpolate_value(0.0, 100.0, 0.0, Interpolation.HOLD) == 0.0
    assert interpolate_value(0.0, 100.0, 0.5, Interpolation.HOLD) == 0.0
    assert interpolate_value(0.0, 100.0, 0.999, Interpolation.HOLD) == 0.0
    assert interpolate_value(0.0, 100.0, 1.0, Interpolation.HOLD) == 100.0


def test_interpolate_value_clamps():
    assert interpolate_value(0.0, 100.0, -0.5, Interpolation.LINEAR) == 0.0
    assert interpolate_value(0.0, 100.0, 1.5, Interpolation.LINEAR) == 100.0


# ---- interpolate_keyframes ----

def test_interpolate_keyframes_empty():
    assert interpolate_keyframes([], 5.0) == 0.0


def test_interpolate_keyframes_single():
    kfs = [Keyframe(time_sec=0.0, value=42.0)]
    assert interpolate_keyframes(kfs, 5.0) == 42.0


def test_interpolate_keyframes_before_first():
    kfs = [
        Keyframe(time_sec=1.0, value=10.0),
        Keyframe(time_sec=2.0, value=20.0),
    ]
    assert interpolate_keyframes(kfs, 0.0) == 10.0


def test_interpolate_keyframes_after_last():
    kfs = [
        Keyframe(time_sec=1.0, value=10.0),
        Keyframe(time_sec=2.0, value=20.0),
    ]
    assert interpolate_keyframes(kfs, 5.0) == 20.0


def test_interpolate_keyframes_linear():
    kfs = [
        Keyframe(time_sec=0.0, value=0.0, interpolation=Interpolation.LINEAR),
        Keyframe(time_sec=1.0, value=100.0, interpolation=Interpolation.LINEAR),
    ]
    assert interpolate_keyframes(kfs, 0.5) == 50.0


def test_interpolate_keyframes_scales_to_duration():
    kfs = [
        Keyframe(time_sec=0.0, value=0.0, interpolation=Interpolation.LINEAR),
        Keyframe(time_sec=1.0, value=100.0, interpolation=Interpolation.LINEAR),
    ]
    # At t=5s in a 10s track, we're at the midpoint of the keyframes.
    result = interpolate_keyframes(kfs, 5.0, track_duration=10.0)
    assert abs(result - 50.0) < 1e-6

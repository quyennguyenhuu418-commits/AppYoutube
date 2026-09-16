/**
 * Interpolation tests — verify canonical modes produce expected values.
 *
 * PROMPT 7 §35 + §36: Renderer tests must cover interpolation.
 */
import { describe, expect, it } from "vitest";

import {
  easeInCubic,
  easeInOutCubic,
  easeOutCubic,
  interpolateKeyframes,
  interpolateValue,
  lerp,
} from "./interpolation";

describe("lerp", () => {
  it("lerp(0, 1, 0) = 0", () => {
    expect(lerp(0, 1, 0)).toBe(0);
  });
  it("lerp(0, 1, 1) = 1", () => {
    expect(lerp(0, 1, 1)).toBe(1);
  });
  it("lerp(10, 20, 0.5) = 15", () => {
    expect(lerp(10, 20, 0.5)).toBe(15);
  });
});

describe("easing curves", () => {
  it("easeInCubic(0) = 0, easeInCubic(1) = 1", () => {
    expect(easeInCubic(0)).toBe(0);
    expect(easeInCubic(1)).toBe(1);
  });
  it("easeOutCubic(0) = 0, easeOutCubic(1) = 1", () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
  });
  it("easeInOutCubic(0) = 0, easeInOutCubic(1) = 1", () => {
    expect(easeInOutCubic(0)).toBe(0);
    expect(easeInOutCubic(1)).toBe(1);
  });
  it("easeInOutCubic(0.5) = 0.5", () => {
    expect(easeInOutCubic(0.5)).toBeCloseTo(0.5, 6);
  });
});

describe("interpolateValue", () => {
  it("linear interpolation at t=0.5 returns midpoint", () => {
    expect(interpolateValue(0, 100, 0.5, "linear")).toBe(50);
  });

  it("ease_in is slower than linear at t=0.5", () => {
    const linear = interpolateValue(0, 100, 0.5, "linear");
    const easeIn = interpolateValue(0, 100, 0.5, "ease_in");
    expect(easeIn).toBeLessThan(linear);
  });

  it("ease_out is faster than linear at t=0.5", () => {
    const linear = interpolateValue(0, 100, 0.5, "linear");
    const easeOut = interpolateValue(0, 100, 0.5, "ease_out");
    expect(easeOut).toBeGreaterThan(linear);
  });

  it("hold returns a for t<1 and b for t>=1", () => {
    expect(interpolateValue(0, 100, 0, "hold")).toBe(0);
    expect(interpolateValue(0, 100, 0.5, "hold")).toBe(0);
    expect(interpolateValue(0, 100, 0.999, "hold")).toBe(0);
    expect(interpolateValue(0, 100, 1, "hold")).toBe(100);
  });

  it("clamps t to [0, 1]", () => {
    expect(interpolateValue(0, 100, -0.5, "linear")).toBe(0);
    expect(interpolateValue(0, 100, 1.5, "linear")).toBe(100);
  });
});

describe("interpolateKeyframes", () => {
  it("returns first value before first keyframe", () => {
    const result = interpolateKeyframes(
      [
        { time_sec: 1, value: 10, interpolation: "linear" },
        { time_sec: 2, value: 20, interpolation: "linear" },
      ],
      0,
      0,
    );
    expect(result).toBe(10);
  });

  it("returns last value after last keyframe", () => {
    const result = interpolateKeyframes(
      [
        { time_sec: 1, value: 10, interpolation: "linear" },
        { time_sec: 2, value: 20, interpolation: "linear" },
      ],
      5,
      0,
    );
    expect(result).toBe(20);
  });

  it("interpolates linearly between two keyframes", () => {
    const result = interpolateKeyframes(
      [
        { time_sec: 0, value: 0, interpolation: "linear" },
        { time_sec: 1, value: 100, interpolation: "linear" },
      ],
      0.5,
      0,
    );
    expect(result).toBe(50);
  });

  it("returns single keyframe value when only one exists", () => {
    const result = interpolateKeyframes(
      [{ time_sec: 0, value: 42, interpolation: "linear" }],
      5,
      0,
    );
    expect(result).toBe(42);
  });

  it("returns 0 when keyframes is empty", () => {
    const result = interpolateKeyframes([], 5, 0);
    expect(result).toBe(0);
  });

  it("scales keyframes to trackDuration", () => {
    const result = interpolateKeyframes(
      [
        { time_sec: 0, value: 0, interpolation: "linear" },
        { time_sec: 1, value: 100, interpolation: "linear" },
      ],
      5, // 5 seconds into a 10-second track → halfway
      10,
    );
    expect(result).toBeCloseTo(50, 6);
  });
});

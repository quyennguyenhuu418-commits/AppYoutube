/**
 * Caption package: frame/time conversion tests (PROMPT 9 §24, §40).
 */

import { describe, expect, it } from "vitest";

import {
  DEFAULT_FRAMING_POLICY,
  FrameRoundingPolicy,
  Tolerance,
  frameToTime,
  timeToFrame,
} from "./frames";

describe("captions/frames — time_to_frame / frame_to_time", () => {
  it("round-trip is stable at frame boundaries", () => {
    const fps = 30;
    for (const frame of [0, 1, 15, 30, 45, 60, 90, 120]) {
      const t = frameToTime(frame, fps);
      expect(timeToFrame(t, fps)).toBe(frame);
    }
  });

  it("zero maps to frame 0", () => {
    expect(timeToFrame(0, 30)).toBe(0);
    expect(timeToFrame(0, 60)).toBe(0);
  });

  it("duration end maps to last frame (30fps)", () => {
    expect(timeToFrame(4.05, 30)).toBe(122);
    expect(timeToFrame(4.0, 30)).toBe(120);
  });

  it("fractional frame uses round-nearest (JS Math.round: 0.5 → up)", () => {
    // JavaScript's Math.round rounds .5 up (always), unlike Python's
    // banker's round. Tests reflect the JS semantics.
    expect(timeToFrame(0.5 / 30, 30)).toBe(1);    // 0.5 → 1
    expect(timeToFrame(1.5 / 30, 30)).toBe(2);    // 1.5 → 2
    expect(timeToFrame(2.5 / 30, 30)).toBe(3);    // 2.5 → 3 (JS rounds up)
  });

  it("policy=FLOOR is consistent", () => {
    expect(timeToFrame(0.99, 30, FrameRoundingPolicy.FLOOR)).toBe(29);
    expect(timeToFrame(1.0, 30, FrameRoundingPolicy.FLOOR)).toBe(30);
  });

  it("policy=CEIL is consistent", () => {
    expect(timeToFrame(0.01, 30, FrameRoundingPolicy.CEIL)).toBe(1);
    expect(timeToFrame(1.0, 30, FrameRoundingPolicy.CEIL)).toBe(30);
  });

  it("rejects non-positive fps", () => {
    expect(() => timeToFrame(1, 0)).toThrow();
    expect(() => timeToFrame(1, -30)).toThrow();
    expect(() => frameToTime(0, 0)).toThrow();
  });

  it("DEFAULT_FRAMING_POLICY is round_nearest", () => {
    expect(DEFAULT_FRAMING_POLICY).toBe(FrameRoundingPolicy.ROUND_NEAREST);
  });

  it("Tolerance.DURATION_END is 0.5 (PROMPT 9 §23)", () => {
    expect(Tolerance.DURATION_END).toBe(0.5);
    expect(Tolerance.READING_RATE_WARN).toBe(25.0);
    expect(Tolerance.READING_RATE_BLOCK).toBe(40.0);
    expect(Tolerance.SCENE_PADDING).toBe(0.05);
  });
});

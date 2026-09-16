/**
 * Canonical frame / time helpers — TypeScript mirror of
 * `orchestrator/app/captions/frames.py` (PROMPT 9 §24).
 *
 * One source of truth for `time_sec ↔ frame` conversions. Render
 * components MUST use these helpers so frame precision stays
 * deterministic across the codebase.
 */

export const FrameRoundingPolicy = {
  ROUND_NEAREST: "round_nearest",
  FLOOR: "floor",
  CEIL: "ceil",
} as const;

export type FrameRoundingPolicy =
  (typeof FrameRoundingPolicy)[keyof typeof FrameRoundingPolicy];

export const DEFAULT_FRAMING_POLICY: FrameRoundingPolicy = "round_nearest";

export const Tolerance = {
  WORD_INTERVAL: 1e-6,
  SEGMENT_OVERLAP: 1e-6,
  DURATION_END: 0.5,
  READING_RATE_WARN: 25.0,
  READING_RATE_BLOCK: 40.0,
  SCENE_PADDING: 0.05,
} as const;

export function timeToFrame(
  timeSec: number,
  fps: number,
  policy: FrameRoundingPolicy = DEFAULT_FRAMING_POLICY,
): number {
  if (fps <= 0) throw new Error(`fps must be positive; got ${fps}`);
  const raw = timeSec * fps;
  switch (policy) {
    case "round_nearest":
      return Math.round(raw);
    case "floor":
      return Math.floor(raw);
    case "ceil":
      return Math.ceil(raw - 1e-9);
    default:
      throw new Error(`Unknown FrameRoundingPolicy: ${policy}`);
  }
}

export function frameToTime(frame: number, fps: number): number {
  if (fps <= 0) throw new Error(`fps must be positive; got ${fps}`);
  return frame / fps;
}

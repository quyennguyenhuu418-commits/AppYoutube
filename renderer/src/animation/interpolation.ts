/**
 * Interpolation utilities — canonical interpolation modes.
 *
 * PROMPT 7 §8: NO arbitrary JS functions inside serialized animation
 * contracts. Supported modes: linear, ease_in, ease_out, ease_in_out, hold.
 *
 * This math MUST match `orchestrator/app/animation/interpolation.py`
 * (the Python reference implementation).
 */

export type InterpolationMode =
  | "linear"
  | "ease_in"
  | "ease_out"
  | "ease_in_out"
  | "hold";

export interface Keyframe {
  time_sec: number;
  value: number;
  interpolation: InterpolationMode;
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function easeInCubic(t: number): number {
  return t * t * t;
}

export function easeOutCubic(t: number): number {
  const v = 1.0 - t;
  return 1.0 - v * v * v;
}

export function easeInOutCubic(t: number): number {
  if (t < 0.5) return 4.0 * t * t * t;
  const v = 1.0 - t;
  return 1.0 - 4.0 * v * v * v;
}

/**
 * Interpolate between a and b at parameter t in [0, 1].
 * HOLD: returns a for all t < 1, b for t >= 1.
 */
export function interpolateValue(
  a: number,
  b: number,
  t: number,
  mode: InterpolationMode = "linear",
): number {
  let clamped = t < 0 ? 0 : t > 1 ? 1 : t;
  if (mode === "hold") {
    return clamped < 1.0 ? a : b;
  }
  if (mode === "linear") return lerp(a, b, clamped);
  if (mode === "ease_in") return lerp(a, b, easeInCubic(clamped));
  if (mode === "ease_out") return lerp(a, b, easeOutCubic(clamped));
  if (mode === "ease_in_out") return lerp(a, b, easeInOutCubic(clamped));
  return lerp(a, b, clamped);
}

/**
 * Resolve a keyframe list to a value at a given time_sec.
 *
 * If `trackDuration` is provided and > 0, keyframes are scaled so the
 * last keyframe time is mapped to `trackDuration`.
 */
export function interpolateKeyframes(
  keyframes: Keyframe[],
  timeSec: number,
  trackDuration: number = 0,
): number {
  if (keyframes.length === 0) return 0.0;
  if (keyframes.length === 1) return keyframes[0]!.value;

  const firstT = keyframes[0]!.time_sec;
  const lastT = keyframes[keyframes.length - 1]!.time_sec;

  let tNorm: number;
  if (trackDuration > 0 && lastT > firstT) {
    const span = lastT - firstT;
    tNorm = (timeSec / trackDuration) * span + firstT;
  } else {
    tNorm = timeSec;
  }

  if (tNorm <= firstT) return keyframes[0]!.value;
  if (tNorm >= lastT) return keyframes[keyframes.length - 1]!.value;

  for (let i = 0; i < keyframes.length - 1; i++) {
    const tA = keyframes[i]!.time_sec;
    const tB = keyframes[i + 1]!.time_sec;
    if (tA <= tNorm && tNorm <= tB) {
      if (tB === tA) return keyframes[i]!.value;
      const localT = (tNorm - tA) / (tB - tA);
      return interpolateValue(
        keyframes[i]!.value,
        keyframes[i + 1]!.value,
        localT,
        keyframes[i]!.interpolation,
      );
    }
  }
  return keyframes[keyframes.length - 1]!.value;
}

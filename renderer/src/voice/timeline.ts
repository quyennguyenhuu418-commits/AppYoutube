/**
 * NarrationTimeline → scene timing conversion helpers.
 *
 * PROMPT 8 §27–§29: integrates narration timing with SceneDefinition
 * and AnimationPlan. The renderer is fs-free; this module receives
 * already-validated canonical data and computes per-scene offsets
 * deterministically.
 *
 * Determinism guarantee: same input → same output.
 */

import type { NarrationTimeline } from "./types";

/**
 * For each scene_id, compute the canonical narration start offset
 * (seconds) derived from the NarrationTimeline.
 *
 * Returns a map: scene_id → start_sec. If no entry covers a scene,
 * the start_sec is 0.0.
 */
export function computeSceneNarrationOffsets(
  timeline: NarrationTimeline,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const entry of timeline.entries) {
    if (!entry.scene_id) continue;
    if (!(entry.scene_id in out)) {
      out[entry.scene_id] = entry.scene_start_sec;
    }
  }
  return out;
}

/**
 * Compute total narration duration (sum of audio durations) from
 * a NarrationTimeline. Returns 0 for empty timelines.
 */
export function totalNarrationDuration(timeline: NarrationTimeline): number {
  if (timeline.entries.length === 0) return 0.0;
  let total = 0.0;
  for (const entry of timeline.entries) {
    total += entry.audio_end_sec - entry.audio_start_sec;
  }
  return Math.round(total * 1000) / 1000;
}

/**
 * Find the narration entry whose audio is active at a given time.
 * Returns null if no entry covers the time.
 */
export function findEntryAtTime(
  timeline: NarrationTimeline,
  timeSec: number,
) {
  for (const entry of timeline.entries) {
    if (timeSec >= entry.audio_start_sec && timeSec < entry.audio_end_sec) {
      return entry;
    }
  }
  return null;
}

/**
 * Convert a wall-clock time to a word timing lookup. Returns the word
 * active at the given time across the full narration timeline.
 *
 * Note: this requires the SpeechTiming objects to be looked up
 * separately; here we only operate on the timeline entries.
 */
export function isWithinNarration(
  timeline: NarrationTimeline,
  timeSec: number,
): boolean {
  return findEntryAtTime(timeline, timeSec) !== null;
}

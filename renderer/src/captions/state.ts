/**
 * Pure deterministic caption frame-state derivation (PROMPT 9 §19, §26).
 *
 * Given a precompiled `CaptionTrack` and an absolute time `t_sec`,
 * returns the caption state at that moment WITHOUT inspecting raw
 * narration text or invoking any LLM/clock.
 *
 * The function is:
 *  - pure (same inputs → same output),
 *  - seekable (can be called at any frame, no previous-frame state),
 *  - frame-stable (no allocations that change across calls except the
 *    return value).
 */

import type {
  CaptionLine,
  CaptionSegment,
  CaptionTrack,
} from "./types";
import { Tolerance } from "./frames";

export interface ActiveWord {
  segment_id: string;
  word_index: number;
  word: string;
  start_sec: number;
  end_sec: number;
  line_index: number;
  position_in_line: number;
}

export interface CaptionFrameState {
  /** True if any segment is active at this time. */
  active: boolean;
  /** The currently-active segment, or null. */
  segment: CaptionSegment | null;
  /** The currently-active word within the segment, or null. */
  word: ActiveWord | null;
  /** Indices of words already fully spoken within the active segment. */
  previous_word_indices: number[];
  /** Indices of words not yet spoken within the active segment. */
  future_word_indices: number[];
  /** Per-line: indices of already-spoken words in that line. */
  previous_words_by_line: Record<number, number[]>;
  /** Per-line: indices of not-yet-spoken words in that line. */
  future_words_by_line: Record<number, number[]>;
  /** Segment progress in [0, 1]. */
  segment_progress: number;
  /** The lines currently rendered (full array). */
  lines: CaptionLine[];
}

const EMPTY: CaptionFrameState = {
  active: false,
  segment: null,
  word: null,
  previous_word_indices: [],
  future_word_indices: [],
  previous_words_by_line: {},
  future_words_by_line: {},
  segment_progress: 0,
  lines: [],
};

/**
 * Find the active segment intersecting [t_sec, t_sec].
 */
function findActiveSegment(
  track: CaptionTrack,
  tSec: number,
): CaptionSegment | null {
  // Segments are time-ordered by construction but not guaranteed sorted
  // after deserialization; sort defensively. Use a stable linear scan
  // since segment counts are small (max 512 in schema).
  for (const seg of track.segments) {
    if (tSec + Tolerance.SEGMENT_OVERLAP >= seg.start_sec
        && tSec - Tolerance.SEGMENT_OVERLAP <= seg.end_sec) {
      return seg;
    }
  }
  return null;
}

/**
 * Find the active word within a segment.
 *
 * Semantics: a word is "active" if t is in [start_sec, end_sec +
 * holdPadSec]. When two consecutive words overlap due to the hold
 * pad, the LATER word wins (so highlights do not get stuck on a word
 * that has clearly been superseded).
 */
function findActiveWord(
  segment: CaptionSegment,
  tSec: number,
  holdPadSec: number,
): ActiveWord | null {
  for (let i = 0; i < segment.words.length; i++) {
    const w = segment.words[i];
    const startOk = tSec + 1e-6 >= w.start_sec;
    const endOk = tSec - 1e-6 <= w.end_sec + holdPadSec;
    if (!startOk || !endOk) continue;
    // Prefer the latest word whose start_sec <= tSec (i.e. is "current").
    // Walk forward from i to find any later word that has started.
    let chosen: number = i;
    for (let j = i + 1; j < segment.words.length; j++) {
      const wj = segment.words[j];
      if (tSec + 1e-6 >= wj.start_sec) {
        chosen = j;
      } else {
        break;
      }
    }
    const w2 = segment.words[chosen];
    return {
      segment_id: segment.segment_id,
      word_index: chosen,
      word: w2.word,
      start_sec: w2.start_sec,
      end_sec: w2.end_sec,
      line_index: w2.line_index,
      position_in_line: w2.position_in_line,
    };
  }
  return null;
}

/**
 * Derive the per-line previous/future indices for a segment.
 *
 * Convention: the active word is segregated from both previous and
 * future — it is the word currently being spoken. Previous words are
 * strictly less-indexed; future words are strictly greater-indexed.
 */
function partitionByLine(
  segment: CaptionSegment,
  activeWordIndex: number | null,
): { previousByLine: Record<number, number[]>; futureByLine: Record<number, number[]> } {
  const previousByLine: Record<number, number[]> = {};
  const futureByLine: Record<number, number[]> = {};
  for (let i = 0; i < segment.words.length; i++) {
    if (i === activeWordIndex) continue;
    const w = segment.words[i];
    const isPast = activeWordIndex !== null && i < activeWordIndex;
    const bucket = isPast ? previousByLine : futureByLine;
    if (!bucket[w.line_index]) bucket[w.line_index] = [];
    bucket[w.line_index].push(i);
  }
  return { previousByLine, futureByLine };
}

/**
 * Compute the caption frame state at absolute time `t_sec`.
 */
export function computeCaptionFrameState(
  track: CaptionTrack,
  tSec: number,
): CaptionFrameState {
  const segment = findActiveSegment(track, tSec);
  if (!segment) return EMPTY;
  const holdPadSec = (track.style?.highlight_hold_pad_ms ?? 120) / 1000;
  const word = findActiveWord(segment, tSec, holdPadSec);
  const wordIdx = word?.word_index ?? null;
  const { previousByLine, futureByLine } = partitionByLine(segment, wordIdx);
  const dur = Math.max(1e-6, segment.end_sec - segment.start_sec);
  const progress = Math.min(1, Math.max(0, (tSec - segment.start_sec) / dur));

  const previous: number[] = [];
  const future: number[] = [];
  for (const ln of segment.lines) {
    for (const wi of ln.word_indices) {
      if (wordIdx !== null && wi < wordIdx) previous.push(wi);
      else if (wordIdx === null || wi > wordIdx) future.push(wi);
    }
  }

  return {
    active: true,
    segment,
    word,
    previous_word_indices: previous,
    future_word_indices: future,
    previous_words_by_line: previousByLine,
    future_words_by_line: futureByLine,
    segment_progress: progress,
    lines: segment.lines,
  };
}

/**
 * Convert a CaptionTrack's word timings into the legacy `WordTimestamp`
 * shape used by the existing `Caption.tsx` component. This is the
 * adapter boundary (PROMPT 9 §25): legacy renderer code consumes
 * `WordTimestamp[]`; canonical data comes from `CaptionTrack`.
 */
export interface LegacyWordTimestamp {
  word: string;
  start_sec: number;
  end_sec: number;
}

export function toLegacyWordTimestamps(
  track: CaptionTrack,
): LegacyWordTimestamp[] {
  const out: LegacyWordTimestamp[] = [];
  for (const seg of track.segments) {
    for (const w of seg.words) {
      out.push({
        word: w.word,
        start_sec: w.start_sec,
        end_sec: w.end_sec,
      });
    }
  }
  return out;
}

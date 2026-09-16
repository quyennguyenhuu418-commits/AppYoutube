/**
 * Caption package: caption frame-state derivation tests
 * (PROMPT 9 §18, §19, §40, §49).
 */

import { describe, expect, it } from "vitest";

import {
  computeCaptionFrameState,
  toLegacyWordTimestamps,
} from "./state";
import type {
  CaptionSegment,
  CaptionStyle,
  CaptionTrack,
} from "./types";

const STYLE: CaptionStyle = {
  version: "1.0.0",
  style_id: "documentary_default",
  name: "documentary_default",
  font_family: "Inter",
  font_size_px: 48,
  font_weight: 600,
  letter_spacing_px: 0,
  max_lines: 2,
  max_chars_per_line: 42,
  line_spacing_px: 6,
  alignment: "center",
  text_color: "#FFFFFF",
  highlight_color: "#FFD166",
  background_color: "rgba(0,0,0,0)",
  shadow: true,
  safe_area_pct: 0.08,
  vertical_safe_area_pct: 0.08,
  vertical_anchor: "lower_third",
  bottom_margin_pct: 0.08,
  animation_mode: "word_highlight",
  highlight_hold_pad_ms: 120,
  metadata: {},
};

function makeSegment(
  start: number,
  end: number,
  words: string[],
  startSecs: number[],
  endSecs: number[],
  lines: number[][],
): CaptionSegment {
  return {
    version: "1.0.0",
    segment_id: `seg_${start}`,
    caption_id: "cap_test",
    scene_id: "scene_1",
    narration_id: "n_0001",
    start_sec: start,
    end_sec: end,
    text: words.join(" "),
    words: words.map((w, i) => ({
      word: w,
      start_sec: startSecs[i],
      end_sec: endSecs[i],
      confidence: 1.0,
      line_index: lines.findIndex((arr) => arr.includes(i)),
      position_in_line: 0,
      narration_id: "n_0001",
      artifact_id: "0123456789abcdef_0123456789abcdef",
      speech_timing_id: "t1",
    })),
    lines: lines.map((arr, lineIdx) => ({
      line_index: lineIdx,
      text: arr.map((i) => words[i]).join(" "),
      word_count: arr.length,
      char_count: arr.map((i) => words[i]).join(" ").length,
      break_reason: "phrase",
      word_indices: arr,
    })),
    artifact_id: "0123456789abcdef_0123456789abcdef",
    speech_timing_id: "t1",
    timestamp_source: "provider_native",
    speaker_id: "narrator",
    speaker_name: "",
    speaker_role: "",
    style_id: "documentary_default",
    emphasis_words: [],
    break_reason: "phrase",
    warnings: [],
  };
}

const TRACK: CaptionTrack = {
  version: "1.0.0",
  track_id: "track_test",
  caption_id: "cap_test",
  project_id: "",
  job_id: "",
  narration_timeline_id: "tl1",
  scene_id: "scene_1",
  language: "en",
  locale: "en-US",
  fps: 30,
  style: STYLE,
  segments: [
    makeSegment(
      0.0, 1.5,
      ["Alice", "walks", "across", "the", "plains"],
      [0.0, 0.3, 0.6, 0.9, 1.2],
      [0.3, 0.6, 0.9, 1.2, 1.5],
      [[0, 1], [2, 3, 4]],
    ),
    makeSegment(
      1.5, 3.0,
      ["Birds", "sing", "softly", "above", "valley"],
      [1.5, 1.8, 2.1, 2.4, 2.7],
      [1.8, 2.1, 2.4, 2.7, 3.0],
      [[0, 1], [2, 3, 4]],
    ),
  ],
  style_id: "documentary_default",
  timestamp_source: "provider_native",
  alignment_provider_id: "",
  quality: null,
  scene_start_sec: 0.0,
  scene_end_sec: 3.0,
  warnings: [],
  failures: [],
  metadata: {},
  created_at: "2026-01-01T00:00:00",
};

describe("captions/state — computeCaptionFrameState", () => {
  it("frame 0 (t=0.0): first segment active, word 'Alice'", () => {
    const state = computeCaptionFrameState(TRACK, 0.0);
    expect(state.active).toBe(true);
    expect(state.segment?.segment_id).toBe("seg_0");
    expect(state.word?.word_index).toBe(0);
    expect(state.word?.word).toBe("Alice");
    expect(state.previous_word_indices).toEqual([]);
    expect(state.future_word_indices).toEqual([1, 2, 3, 4]);
    expect(state.lines.length).toBe(2);
  });

  it("frame 15 (t=0.5): word 'walks' active (hold-pad from word 1 [0.3,0.6])", () => {
    const state = computeCaptionFrameState(TRACK, 0.5);
    expect(state.active).toBe(true);
    expect(state.word?.word).toBe("walks");
    expect(state.word?.word_index).toBe(1);
    expect(state.previous_word_indices).toEqual([0]);
    expect(state.future_word_indices).toEqual([2, 3, 4]);
  });

  it("frame 30 (t=1.0): word 'the' active (past 'across')", () => {
    const state = computeCaptionFrameState(TRACK, 1.0);
    expect(state.word?.word).toBe("the");
    expect(state.word?.word_index).toBe(3);
    expect(state.future_word_indices).toEqual([4]);
  });

  it("frame 45 (t=1.5): halfway between segments", () => {
    const state = computeCaptionFrameState(TRACK, 1.5);
    expect(state.active).toBe(true);
    // Segment 1 ends at 1.5; segment 2 starts at 1.5. Both intersect.
    // The second segment is the "next" one in iteration order.
    expect(state.segment).not.toBeNull();
  });

  it("frame 60 (t=2.0): second segment active, word 'softly'", () => {
    const state = computeCaptionFrameState(TRACK, 2.0);
    expect(state.active).toBe(true);
    expect(state.segment?.segment_id).toBe("seg_1.5");
    // Words at 2.0: 'softly' is at [2.1, 2.4]; 'sing' is at [1.8, 2.1].
    // At t=2.0, 'sing' is still active.
    expect(state.word?.word).toBe("sing");
  });

  it("frame 90 (t=3.0): boundary — final word still highlighted (with hold pad)", () => {
    const state = computeCaptionFrameState(TRACK, 3.0);
    // At t = 3.0 (= scene_end_sec), segment 1 is still active because
    // its last word 'valley' ends exactly at 3.0. The highlight pad
    // (120ms) keeps the word highlighted for frames 91..94.
    expect(state.active).toBe(true);
    expect(state.segment?.segment_id).toBe("seg_1.5");
    expect(state.word?.word).toBe("valley");
  });

  it("beyond hold pad after scene end → inactive", () => {
    const state = computeCaptionFrameState(TRACK, 3.5);
    expect(state.active).toBe(false);
    expect(state.segment).toBeNull();
  });

  it("before scene_start_sec returns inactive", () => {
    const state = computeCaptionFrameState(TRACK, -0.5);
    expect(state.active).toBe(false);
  });

  it("seekability: calling at frame 0 then frame 60 yields correct, independent states", () => {
    const s0 = computeCaptionFrameState(TRACK, 0.0);
    const s60 = computeCaptionFrameState(TRACK, 2.0);
    // s0 has Alice, s60 has sing — no shared state.
    expect(s0.word?.word).toBe("Alice");
    expect(s60.word?.word).toBe("sing");
  });

  it("determinism: same inputs → identical output", () => {
    const a = computeCaptionFrameState(TRACK, 0.5);
    const b = computeCaptionFrameState(TRACK, 0.5);
    expect(a).toEqual(b);
  });

  it("per-line previous/future word indices are correct", () => {
    // At t=0.5 the active word is 'walks' (index 1, on line 0).
    const state = computeCaptionFrameState(TRACK, 0.5);
    expect(state.word?.word).toBe("walks");
    // Past on line 0: [0]; future on line 0: [] (active excluded).
    expect(state.previous_words_by_line[0]).toEqual([0]);
    expect(state.future_words_by_line[0] ?? []).toEqual([]);
    // Future on line 1: [2, 3, 4].
    expect(state.future_words_by_line[1]).toEqual([2, 3, 4]);
  });
});

describe("captions/state — toLegacyWordTimestamps", () => {
  it("returns flat list of word timings in scene order", () => {
    const out = toLegacyWordTimestamps(TRACK);
    expect(out).toHaveLength(10);
    expect(out[0]).toEqual({ word: "Alice", start_sec: 0.0, end_sec: 0.3 });
    expect(out[9]).toEqual({ word: "valley", start_sec: 2.7, end_sec: 3.0 });
  });
});

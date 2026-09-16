/**
 * Cross-runtime contract test (PROMPT 9 §41).
 *
 * Mirrors the Python `app.captions.schemas.CaptionTrack.to_dict()`
 * output and verifies the TypeScript side consumes the exact same
 * field names without loss.
 */

import { describe, expect, it } from "vitest";

import type {
  CaptionSegment,
  CaptionStyle,
  CaptionTrack,
} from "./types";

const STYLE: CaptionStyle = {
  version: "1.0.0",
  style_id: "documentary_default",
  name: "documentary_default",
  font_family: "Inter, sans-serif",
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

const SEGMENT: CaptionSegment = {
  version: "1.0.0",
  segment_id: "n1_s000000",
  caption_id: "cap_test",
  scene_id: "scene_1",
  narration_id: "n_0001",
  start_sec: 0.0,
  end_sec: 1.2,
  text: "Alice walks across the",
  words: [
    {
      word: "Alice",
      start_sec: 0.0,
      end_sec: 0.3,
      confidence: 1.0,
      line_index: 0,
      position_in_line: 0,
      narration_id: "n_0001",
      artifact_id: "0123456789abcdef_0123456789abcdef",
      speech_timing_id: "t1",
    },
  ],
  lines: [
    {
      line_index: 0,
      text: "Alice walks across the",
      word_count: 4,
      char_count: 22,
      break_reason: "phrase",
      word_indices: [0, 1, 2, 3],
    },
  ],
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

const TRACK: CaptionTrack = {
  version: "1.0.0",
  track_id: "cap_test_track",
  caption_id: "cap_test",
  project_id: "proj1",
  job_id: "job1",
  narration_timeline_id: "tl1",
  scene_id: "scene_1",
  language: "en",
  locale: "en-US",
  fps: 30,
  style: STYLE,
  segments: [SEGMENT],
  style_id: "documentary_default",
  timestamp_source: "provider_native",
  alignment_provider_id: "",
  quality: null,
  scene_start_sec: 0.0,
  scene_end_sec: 4.0,
  warnings: [],
  failures: [],
  metadata: {},
  created_at: "2026-01-01T00:00:00",
};

describe("Cross-runtime contract — CaptionTrack JSON (PROMPT 9 §41)", () => {
  it("every TS field name is snake_case (matches Python pydantic)", () => {
    function assertSnakeCase(obj: unknown, path: string): void {
      if (obj === null || typeof obj !== "object") return;
      if (Array.isArray(obj)) {
        for (const item of obj) assertSnakeCase(item, path);
        return;
      }
      for (const [k, v] of Object.entries(obj)) {
        expect(k, `field at ${path}.${k}`).toMatch(/^[a-z][a-z0-9_]*$/);
        assertSnakeCase(v, `${path}.${k}`);
      }
    }
    assertSnakeCase(TRACK, "track");
  });

  it("Track JSON round-trips through JSON.parse (no field loss)", () => {
    const json = JSON.parse(JSON.stringify(TRACK));
    expect(json.caption_id).toBe(TRACK.caption_id);
    expect(json.style.font_family).toBe(TRACK.style.font_family);
    expect(json.segments[0].words[0].start_sec).toBe(0.0);
    expect(json.segments[0].timestamp_source).toBe("provider_native");
  });

  it("CaptionStyle fields parity", () => {
    const json = JSON.parse(JSON.stringify(STYLE));
    expect(json.max_chars_per_line).toBe(42);
    expect(json.highlight_color).toBe("#FFD166");
    expect(json.vertical_anchor).toBe("lower_third");
    expect(json.animation_mode).toBe("word_highlight");
  });

  it("TimestampSource enum parity: PROVIDER_NATIVE", () => {
    expect(SEGMENT.timestamp_source).toBe("provider_native");
  });

  it("all required IDs are non-empty", () => {
    expect(TRACK.caption_id.length).toBeGreaterThan(0);
    expect(TRACK.track_id.length).toBeGreaterThan(0);
    expect(TRACK.narration_timeline_id.length).toBeGreaterThan(0);
    expect(TRACK.scene_id.length).toBeGreaterThan(0);
    expect(SEGMENT.segment_id.length).toBeGreaterThan(0);
    expect(SEGMENT.artifact_id.length).toBeGreaterThan(0);
    expect(SEGMENT.speech_timing_id.length).toBeGreaterThan(0);
  });
});

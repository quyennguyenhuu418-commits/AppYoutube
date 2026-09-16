/**
 * NarrationTimeline → scene timing conversion tests (PROMPT 8 §27, §28, §29).
 */
import { describe, expect, it } from "vitest";

import {
  computeSceneNarrationOffsets,
  findEntryAtTime,
  isWithinNarration,
  totalNarrationDuration,
} from "../voice/timeline";
import { isValidArtifactId } from "../voice/types";
import type { NarrationTimeline, NarrationTimelineEntry } from "../voice/types";

function makeEntry(
  scene_id: string,
  audio_start: number,
  audio_end: number,
  scene_start: number,
  scene_end: number,
): NarrationTimelineEntry {
  return {
    narration_id: `n_${scene_id}`,
    scene_id,
    artifact_id: "0123456789abcdef_0123456789abcdef",
    timing_id: "t1",
    voice_id: "v1",
    speaker_id: "narrator",
    audio_start_sec: audio_start,
    audio_end_sec: audio_end,
    scene_start_sec: scene_start,
    scene_end_sec: scene_end,
    pre_roll_sec: 0,
    post_roll_sec: 0,
    padding_sec: 0,
    resolution_strategy: "follow_audio",
    metadata: {},
  };
}

const TL: NarrationTimeline = {
  version: "1.0.0",
  timeline_id: "tl1",
  script_id: "s1",
  project_id: "",
  job_id: "",
  fps: 30,
  total_duration_sec: 6.0,
  entries: [
    makeEntry("scene_1", 0, 2.0, 0, 2.0),
    makeEntry("scene_2", 2.0, 4.0, 2.0, 4.0),
    makeEntry("scene_3", 4.0, 6.0, 4.0, 6.0),
  ],
  default_padding_sec: 0.05,
  default_pre_roll_sec: 0,
  default_post_roll_sec: 0,
  strategy: "follow_audio",
  warnings: [],
  failures: [],
  metadata: {},
  created_at: "2026-01-01T00:00:00",
};

describe("computeSceneNarrationOffsets", () => {
  it("returns one offset per scene_id", () => {
    const offsets = computeSceneNarrationOffsets(TL);
    expect(Object.keys(offsets).sort()).toEqual(["scene_1", "scene_2", "scene_3"]);
    expect(offsets.scene_1).toBe(0);
    expect(offsets.scene_2).toBe(2.0);
    expect(offsets.scene_3).toBe(4.0);
  });

  it("returns empty map for empty timeline", () => {
    const empty: NarrationTimeline = { ...TL, entries: [] };
    expect(computeSceneNarrationOffsets(empty)).toEqual({});
  });

  it("skips entries with empty scene_id", () => {
    const tl: NarrationTimeline = {
      ...TL,
      entries: [makeEntry("", 0, 1, 0, 1), makeEntry("scene_x", 1, 2, 1, 2)],
    };
    const offsets = computeSceneNarrationOffsets(tl);
    expect(Object.keys(offsets)).toEqual(["scene_x"]);
  });
});

describe("totalNarrationDuration", () => {
  it("sums audio durations across entries", () => {
    expect(totalNarrationDuration(TL)).toBe(6.0);
  });

  it("returns 0 for empty timeline", () => {
    const empty: NarrationTimeline = { ...TL, entries: [] };
    expect(totalNarrationDuration(empty)).toBe(0);
  });

  it("rounds to 3 decimal places", () => {
    const tl: NarrationTimeline = {
      ...TL,
      entries: [
        makeEntry("a", 0, 1.23456, 0, 1.23456),
        makeEntry("b", 1.23456, 3.34567, 1.23456, 3.34567),
      ],
    };
    expect(totalNarrationDuration(tl)).toBeCloseTo(3.346, 2);
  });
});

describe("findEntryAtTime", () => {
  it("returns the entry whose audio covers the given time", () => {
    const e = findEntryAtTime(TL, 3.0);
    expect(e?.scene_id).toBe("scene_2");
  });

  it("returns null outside any audio range", () => {
    expect(findEntryAtTime(TL, 10.0)).toBeNull();
  });

  it("returns null before all audio", () => {
    expect(findEntryAtTime(TL, -1.0)).toBeNull();
  });
});

describe("isWithinNarration", () => {
  it("returns true during audio", () => {
    expect(isWithinNarration(TL, 3.0)).toBe(true);
  });

  it("returns false outside audio", () => {
    expect(isWithinNarration(TL, 10.0)).toBe(false);
  });
});

describe("NarrationTimeline type guard", () => {
  it("isValidArtifactId accepts canonical id", () => {
    expect(isValidArtifactId("0123456789abcdef_0123456789abcdef")).toBe(true);
  });

  it("isValidArtifactId rejects malformed id", () => {
    expect(isValidArtifactId("bad")).toBe(false);
    expect(isValidArtifactId("0123456789abcdef-0123456789abcdef")).toBe(false);
    expect(isValidArtifactId("0123456789abcde_0123456789abcdef")).toBe(false);
  });
});

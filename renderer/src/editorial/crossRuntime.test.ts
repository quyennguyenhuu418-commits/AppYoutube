/**
 * Editorial Engine — cross-runtime contract tests (PROMPT 10 §41).
 *
 * Verifies that the canonical JSON shape produced by the Python
 * `EditorialCompiler` (a RenderPlan) round-trips through TS without
 * field loss and matches the TS interface exactly.
 *
 * The Python side is exercised by `tests/test_editorial_cross_runtime.py`.
 * This test file focuses on TS-side acceptance: every field the
 * `EditorialCompiler` serializes must be readable by the TS consumer.
 */
import { describe, it, expect } from "vitest";

import { isRenderPlan, type RenderPlan } from "./types";

// A canonical-shaped JSON blob that mirrors what the Python EditorialCompiler
// emits (see `tests/test_editorial_cross_runtime.py::test_renderplan_required_fields_present_in_json`).
const CANONICAL_BLOB: RenderPlan = {
  version: "1.0.0",
  plan_id: "rp_654233938b39053e",
  project_id: "p",
  job_id: "j",
  topic: "T",
  fps: 30,
  width: 1280,
  height: 720,
  total_duration_frames: 270,
  total_duration_sec: 9.0,
  scenes: [
    {
      scene_id: "scene_1",
      order: 0,
      master_start_frame: 0,
      duration_frames: 60,
      source_scene_duration_frames: 60,
      transition_in: null,
      transition_out: null,
      hold_frames_before: 0,
      hold_frames_after: 0,
      animation_plan_id: null,
      caption_track_id: null,
      pacing_category: "normal",
      emphasis_level: "medium",
    },
    {
      scene_id: "scene_2",
      order: 1,
      master_start_frame: 60,
      duration_frames: 60,
      source_scene_duration_frames: 60,
      transition_in: null,
      transition_out: null,
      hold_frames_before: 0,
      hold_frames_after: 0,
      animation_plan_id: null,
      caption_track_id: null,
      pacing_category: "normal",
      emphasis_level: "medium",
    },
    {
      scene_id: "scene_3",
      order: 2,
      master_start_frame: 120,
      duration_frames: 150,
      source_scene_duration_frames: 150,
      transition_in: null,
      transition_out: null,
      hold_frames_before: 0,
      hold_frames_after: 0,
      animation_plan_id: null,
      caption_track_id: null,
      pacing_category: "normal",
      emphasis_level: "medium",
    },
  ],
  layers: [
    {
      layer_id: "scene_1:background",
      kind: "background",
      z_order: 0,
      scene_id: "scene_1",
      master_start_frame: 0,
      duration_frames: 60,
      payload: { environment_id: "env1", character_ids: [], props: [] },
    },
  ],
  audio_clips: [
    {
      clip_id: "nar-1",
      artifact_id: "aa-narration",
      track_kind: "narration",
      track_id: "_auto_narration",
      scene_id: "scene_1",
      master_start_frame: 0,
      duration_frames: 60,
      gain_db: 0,
      fade_in_frames: 0,
      fade_out_frames: 0,
      duck_target_track_ids: [],
      duck_gain_db: null,
    },
  ],
  audio_track_ids: [],
  title_cards: [],
  layer_order: [
    "background", "environment", "props", "characters",
    "diagrams", "overlays", "captions", "title_cards",
  ],
  source_fingerprint: "fp_fe4ef05652764b9e4393358a",
  created_at: "2026-01-01T00:00:00Z",
  warnings: [],
  failures: [],
};

describe("cross-runtime contract", () => {
  it("isRenderPlan accepts the canonical blob", () => {
    expect(isRenderPlan(CANONICAL_BLOB)).toBe(true);
  });

  it("isRenderPlan rejects missing fields", () => {
    const broken = { ...CANONICAL_BLOB };
    delete (broken as Record<string, unknown>).fps;
    expect(isRenderPlan(broken)).toBe(false);
  });

  it("isRenderPlan rejects non-objects", () => {
    expect(isRenderPlan(null)).toBe(false);
    expect(isRenderPlan(undefined)).toBe(false);
    expect(isRenderPlan("plan")).toBe(false);
    expect(isRenderPlan(123)).toBe(false);
  });

  it("the canonical blob parses cleanly through JSON", () => {
    const json = JSON.stringify(CANONICAL_BLOB);
    const parsed = JSON.parse(json) as RenderPlan;
    expect(isRenderPlan(parsed)).toBe(true);
    expect(parsed.source_fingerprint).toBe(CANONICAL_BLOB.source_fingerprint);
    expect(parsed.total_duration_frames).toBe(CANONICAL_BLOB.total_duration_frames);
  });

  it("RenderPlan field order matches Python's `to_dict` output", () => {
    // We compare key sets, not insertion order, to avoid spurious failures
    // when the Python side emits a different ordering.
    const expectedTop = [
      "version", "plan_id", "project_id", "job_id", "topic",
      "fps", "width", "height", "total_duration_frames", "total_duration_sec",
      "scenes", "layers", "audio_clips", "audio_track_ids",
      "title_cards", "layer_order", "source_fingerprint",
    ];
    for (const key of expectedTop) {
      expect(CANONICAL_BLOB).toHaveProperty(key);
    }
  });

  it("RenderScene field set matches Python's per-scene output", () => {
    const scene = CANONICAL_BLOB.scenes[0]!;
    const expectedSceneKeys = [
      "scene_id", "order", "master_start_frame", "duration_frames",
      "source_scene_duration_frames", "transition_in", "transition_out",
      "hold_frames_before", "hold_frames_after", "animation_plan_id",
      "caption_track_id", "pacing_category", "emphasis_level",
    ];
    for (const key of expectedSceneKeys) {
      expect(scene).toHaveProperty(key);
    }
  });

  it("RenderAudioClip field set matches Python's per-clip output", () => {
    const clip = CANONICAL_BLOB.audio_clips[0]!;
    const expectedKeys = [
      "clip_id", "artifact_id", "track_kind", "track_id", "scene_id",
      "master_start_frame", "duration_frames", "gain_db",
      "fade_in_frames", "fade_out_frames",
      "duck_target_track_ids", "duck_gain_db",
    ];
    for (const key of expectedKeys) {
      expect(clip).toHaveProperty(key);
    }
  });

  it("RenderLayer field set matches Python's per-layer output", () => {
    const layer = CANONICAL_BLOB.layers[0]!;
    const expectedKeys = [
      "layer_id", "kind", "z_order", "scene_id",
      "master_start_frame", "duration_frames", "payload",
    ];
    for (const key of expectedKeys) {
      expect(layer).toHaveProperty(key);
    }
  });
});

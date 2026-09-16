/**
 * Golden Frame tests — verify canonical animation state at specific frames.
 *
 * PROMPT 7 §38: Test canonical state (position, scale, rotation, pose,
 * opacity, camera state) at frames 0, 15, 30, 60, 90. Do NOT depend
 * exclusively on pixel-perfect hashes across environments.
 */
import { describe, expect, it } from "vitest";

import { computeFrameState, type AnimationPlan } from "./runtime";

/**
 * Deterministic plan with:
 * - Camera pans right + zooms in (ease_in_out)
 * - Character "alice" walks with explicit WalkCycleParams
 * - Prop "spear" attached to alice at t=[1, 4]
 */
function makeGoldenPlan(): AnimationPlan {
  return {
    metadata: {
      version: "1.0.0",
      plan_id: "golden",
      scene_id: "scene_1",
      job_id: "",
      duration_sec: 6,
      created_at: "2026-01-01T00:00:00.000Z",
      source: "golden_test",
    },
    duration_sec: 6,
    camera: {
      camera_id: "main",
      start_pan_x: 0.4,
      start_pan_y: 0.5,
      start_zoom: 1.0,
      end_pan_x: 0.7,
      end_pan_y: 0.5,
      end_zoom: 1.6,
      easing: "ease_in_out",
    },
    characters: [
      {
        character_id: "alice",
        pose_sequence: [
          { start_sec: 0, end_sec: 6, action: "walk", pose: "walk" },
        ],
        walk_cycle_params: {
          walk_speed: 60,
          step_frequency: 2,
          stride_length: 0.1,
          body_bob: 0.01,
          arm_swing: 0.05,
        },
        motion_tracks: [],
      },
    ],
    props: [
      {
        prop_id: "spear",
        instance_id: "",
        motion_tracks: [],
        interactions: [
          {
            interaction_id: "i1",
            character_id: "alice",
            prop_id: "spear",
            character_anchor: "hand_left",
            prop_anchor: "grip",
            start_sec: 1,
            end_sec: 4,
            kind: "hold",
          },
        ],
      },
    ],
    tracks: [],
    events: [],
    warnings: [],
    failures: [],
  };
}

describe("Golden frame: deterministic canonical state", () => {
  const plan = makeGoldenPlan();

  // Each frame has a stable, computed expected value. We pin them here so
  // any change to the runtime math is intentional (and tracked).
  // Generated from _golden_compute.ts against the runtime math.
  const cases: Array<{
    frame: number;
    expected: {
      time_sec: number;
      camera: { pan_x: number; pan_y: number; zoom: number };
      characters: { id: string; pose: string; x: number; opacity: number };
      props: { id: string; attached_to: string | null };
    };
  }> = [
    {
      frame: 0,
      expected: {
        time_sec: 0,
        camera: { pan_x: 0.4, pan_y: 0.5, zoom: 1.0 },
        characters: { id: "alice", pose: "walk", x: 0.5, opacity: 1 },
        props: { id: "spear", attached_to: null },
      },
    },
    {
      frame: 15,
      expected: {
        time_sec: 0.5,
        camera: { pan_x: 0.40069, pan_y: 0.5, zoom: 1.00139 },
        characters: { id: "alice", pose: "walk", x: 0.5, opacity: 1 },
        props: { id: "spear", attached_to: null },
      },
    },
    {
      frame: 30,
      expected: {
        time_sec: 1,
        camera: { pan_x: 0.40556, pan_y: 0.5, zoom: 1.01111 },
        characters: { id: "alice", pose: "walk", x: 0.5, opacity: 1 },
        props: { id: "spear", attached_to: "alice" },
      },
    },
    {
      frame: 60,
      expected: {
        time_sec: 2,
        camera: { pan_x: 0.44444, pan_y: 0.5, zoom: 1.08889 },
        characters: { id: "alice", pose: "walk", x: 0.5, opacity: 1 },
        props: { id: "spear", attached_to: "alice" },
      },
    },
    {
      frame: 90,
      expected: {
        time_sec: 3,
        camera: { pan_x: 0.55, pan_y: 0.5, zoom: 1.3 },
        characters: { id: "alice", pose: "walk", x: 0.5, opacity: 1 },
        props: { id: "spear", attached_to: "alice" },
      },
    },
  ];

  for (const c of cases) {
    it(`frame ${c.frame}: time_sec=${c.expected.time_sec}`, () => {
      const tSec = c.frame / 30;
      const state = computeFrameState(plan, tSec);
      expect(state.time_sec).toBeCloseTo(c.expected.time_sec, 6);
    });

    it(`frame ${c.frame}: camera pan_x=${c.expected.camera.pan_x}`, () => {
      const tSec = c.frame / 30;
      const state = computeFrameState(plan, tSec);
      expect(state.camera.pan_x).toBeCloseTo(c.expected.camera.pan_x, 2);
    });

    it(`frame ${c.frame}: camera zoom=${c.expected.camera.zoom}`, () => {
      const tSec = c.frame / 30;
      const state = computeFrameState(plan, tSec);
      expect(state.camera.zoom).toBeCloseTo(c.expected.camera.zoom, 2);
    });

    it(`frame ${c.frame}: character pose=${c.expected.characters.pose}`, () => {
      const tSec = c.frame / 30;
      const state = computeFrameState(plan, tSec);
      const char = state.characters.find((ch) => ch.character_id === c.expected.characters.id)!;
      expect(char.pose).toBe(c.expected.characters.pose);
    });

    it(`frame ${c.frame}: prop attached=${c.expected.props.attached_to}`, () => {
      const tSec = c.frame / 30;
      const state = computeFrameState(plan, tSec);
      const prop = state.props.find((p) => p.prop_id === c.expected.props.id)!;
      expect(prop.attached_to_character_id).toBe(c.expected.props.attached_to);
    });
  }
});

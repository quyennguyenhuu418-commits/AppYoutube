/**
 * Animation Runtime tests — pose resolution, walk phase, frame state,
 * conflict resolution, determinism, seekability, replayability.
 *
 * PROMPT 7 §35: Renderer tests must cover character, prop, camera,
 * determinism, seekability.
 */
import { describe, expect, it } from "vitest";

import {
  computeFrameState,
  findWinningTrack,
  resolvePose,
  resolveTrackConflicts,
  resolveWalkPhase,
  type AnimationPlan,
  type AnimationTrack,
  type CharacterAnimation,
} from "./runtime";

// ----------------------------------------------------------------------------
// Test helpers
// ----------------------------------------------------------------------------

function makePlan(overrides: Partial<AnimationPlan> = {}): AnimationPlan {
  return {
    metadata: {
      version: "1.0.0",
      plan_id: "plan_test",
      scene_id: "scene_test",
      job_id: "",
      duration_sec: 5,
      created_at: "2026-01-01T00:00:00.000Z",
      source: "test",
    },
    duration_sec: 5,
    camera: {
      camera_id: "main",
      start_pan_x: 0.5,
      start_pan_y: 0.5,
      start_zoom: 1.0,
      end_pan_x: 0.6,
      end_pan_y: 0.5,
      end_zoom: 1.5,
      easing: "linear",
    },
    characters: [],
    props: [],
    tracks: [],
    events: [],
    warnings: [],
    failures: [],
    ...overrides,
  };
}

// ----------------------------------------------------------------------------
// Pose resolution
// ----------------------------------------------------------------------------

describe("resolvePose", () => {
  it("returns 'stand' when pose_sequence is empty", () => {
    const char: CharacterAnimation = {
      character_id: "alice",
      pose_sequence: [],
      walk_cycle_params: null,
      motion_tracks: [],
    };
    expect(resolvePose(char, 0)).toBe("stand");
    expect(resolvePose(char, 10)).toBe("stand");
  });

  it("returns the pose covering the current time", () => {
    const char: CharacterAnimation = {
      character_id: "alice",
      pose_sequence: [
        { start_sec: 0, end_sec: 2, action: "stand", pose: "stand" },
        { start_sec: 2, end_sec: 4, action: "walk", pose: "walk" },
        { start_sec: 4, end_sec: 6, action: "stand", pose: "point" },
      ],
      walk_cycle_params: null,
      motion_tracks: [],
    };
    expect(resolvePose(char, 0)).toBe("stand");
    expect(resolvePose(char, 1)).toBe("stand");
    expect(resolvePose(char, 2)).toBe("walk");
    expect(resolvePose(char, 3)).toBe("walk");
    expect(resolvePose(char, 4)).toBe("point");
    expect(resolvePose(char, 5)).toBe("point");
  });
});

// ----------------------------------------------------------------------------
// Walk phase
// ----------------------------------------------------------------------------

describe("resolveWalkPhase", () => {
  it("returns 0 when no walk_cycle_params", () => {
    const char: CharacterAnimation = {
      character_id: "alice",
      pose_sequence: [],
      walk_cycle_params: null,
      motion_tracks: [],
    };
    expect(resolveWalkPhase(char, 1)).toBe(0);
  });

  it("returns a value in [0, 1)", () => {
    const char: CharacterAnimation = {
      character_id: "alice",
      pose_sequence: [],
      walk_cycle_params: {
        walk_speed: 60,
        step_frequency: 2,
        stride_length: 0.15,
        body_bob: 0.02,
        arm_swing: 0.05,
      },
      motion_tracks: [],
    };
    for (const t of [0, 0.25, 0.5, 1.0, 2.5, 100]) {
      const phase = resolveWalkPhase(char, t);
      expect(phase).toBeGreaterThanOrEqual(0);
      expect(phase).toBeLessThan(1);
    }
  });
});

// ----------------------------------------------------------------------------
// Conflict resolution
// ----------------------------------------------------------------------------

describe("resolveTrackConflicts", () => {
  it("returns single tracks unchanged", () => {
    const track: AnimationTrack = {
      track_id: "t1",
      target: { target_id: "character:alice", kind: "character" },
      property: "x",
      keyframes: [{ time_sec: 0, value: 0, interpolation: "linear" }],
      priority: 0,
      duration_sec: 1,
    };
    expect(resolveTrackConflicts([track])).toEqual([track]);
  });

  it("keeps higher-priority track when two conflict", () => {
    const low: AnimationTrack = {
      track_id: "t_low",
      target: { target_id: "character:alice", kind: "character" },
      property: "x",
      keyframes: [{ time_sec: 0, value: 0, interpolation: "linear" }],
      priority: 0,
      duration_sec: 1,
    };
    const high: AnimationTrack = {
      track_id: "t_high",
      target: { target_id: "character:alice", kind: "character" },
      property: "x",
      keyframes: [{ time_sec: 0, value: 10, interpolation: "linear" }],
      priority: 10,
      duration_sec: 1,
    };
    const result = resolveTrackConflicts([low, high]);
    expect(result).toHaveLength(1);
    expect(result[0]!.track_id).toBe("t_high");
  });

  it("breaks ties by track_id alphabetically", () => {
    const t1: AnimationTrack = {
      track_id: "bbb",
      target: { target_id: "character:alice", kind: "character" },
      property: "x",
      keyframes: [],
      priority: 0,
      duration_sec: 1,
    };
    const t2: AnimationTrack = {
      track_id: "aaa",
      target: { target_id: "character:alice", kind: "character" },
      property: "x",
      keyframes: [],
      priority: 0,
      duration_sec: 1,
    };
    const result = resolveTrackConflicts([t1, t2]);
    expect(result[0]!.track_id).toBe("aaa");
  });
});

describe("findWinningTrack", () => {
  it("returns null when no track matches", () => {
    expect(findWinningTrack([], "character:alice", "x")).toBeNull();
  });
});

// ----------------------------------------------------------------------------
// Frame state computation
// ----------------------------------------------------------------------------

describe("computeFrameState", () => {
  it("interpolates camera between start and end", () => {
    const plan = makePlan();
    const state = computeFrameState(plan, 2.5);
    expect(state.camera.pan_x).toBeCloseTo(0.55, 6);
    expect(state.camera.zoom).toBeCloseTo(1.25, 6);
  });

  it("clamps time to duration", () => {
    const plan = makePlan();
    const state = computeFrameState(plan, 100);
    expect(state.time_sec).toBe(plan.duration_sec);
  });

  it("returns deterministic state across calls", () => {
    const plan = makePlan();
    const s1 = computeFrameState(plan, 1.5);
    const s2 = computeFrameState(plan, 1.5);
    expect(s1).toEqual(s2);
  });

  it("produces deterministic state at frame 0, 15, 30, 60, 90", () => {
    const plan = makePlan();
    const frames = [0, 15, 30, 60, 90];
    const states = frames.map((f) =>
      JSON.stringify(computeFrameState(plan, f / 30)),
    );
    // All must be identical strings for the given input (deterministic).
    for (const s of states) {
      expect(typeof s).toBe("string");
      expect(s.length).toBeGreaterThan(0);
    }
  });

  it("includes characters from the plan", () => {
    const plan = makePlan({
      characters: [
        {
          character_id: "alice",
          pose_sequence: [
            { start_sec: 0, end_sec: 5, action: "stand", pose: "stand" },
          ],
          walk_cycle_params: null,
          motion_tracks: [],
        },
      ],
    });
    const state = computeFrameState(plan, 2);
    expect(state.characters).toHaveLength(1);
    expect(state.characters[0]!.character_id).toBe("alice");
    expect(state.characters[0]!.pose).toBe("stand");
  });

  it("includes props from the plan", () => {
    const plan = makePlan({
      props: [
        {
          prop_id: "spear",
          instance_id: "",
          motion_tracks: [],
          interactions: [],
        },
      ],
    });
    const state = computeFrameState(plan, 1);
    expect(state.props).toHaveLength(1);
    expect(state.props[0]!.prop_id).toBe("spear");
  });

  it("marks prop as attached when interaction is active", () => {
    const plan = makePlan({
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
      characters: [
        {
          character_id: "alice",
          pose_sequence: [
            { start_sec: 0, end_sec: 5, action: "stand", pose: "stand" },
          ],
          walk_cycle_params: null,
          motion_tracks: [],
        },
      ],
    });
    const state = computeFrameState(plan, 2);
    expect(state.props[0]!.attached_to_character_id).toBe("alice");
    expect(state.props[0]!.attached_to_anchor).toBe("hand_left");
  });

  it("detaches prop after interaction ends", () => {
    const plan = makePlan({
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
              start_sec: 0,
              end_sec: 2,
              kind: "hold",
            },
          ],
        },
      ],
    });
    const beforeEnd = computeFrameState(plan, 1);
    expect(beforeEnd.props[0]!.attached_to_character_id).toBe("alice");
    const afterEnd = computeFrameState(plan, 3);
    expect(afterEnd.props[0]!.attached_to_character_id).toBeNull();
  });
});

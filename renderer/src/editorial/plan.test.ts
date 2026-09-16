/**
 * Editorial Engine — TS tests for RenderPlan consumption, scene offsets,
 * transitions, audio offsets, caption/animation offsets, layer ordering,
 * frame-state determinism.
 */
import { describe, it, expect } from "vitest";

import {
  placeScenes,
  validateTransitionPair,
  validateAllTransitions,
  collectNarrationWindows,
  isInAnyWindow,
  computeDucking,
  computeQualityScore,
  seekFrame,
  sceneLocalTime,
  masterTimeFrame,
  linearGain,
} from "./plan";
import {
  TransitionKind,
  AudioTrackKind,
  LayerKind,
  PacingCategory,
  EmphasisLevel,
  type EditorialProject,
  type EditorialScene,
  type EditorialTimeline,
  type RenderPlan,
  type RenderScene,
  type RenderLayer,
  type RenderAudioClip,
  type TransitionKindValue,
} from "./types";

// ============================================================================
// Fixtures
// ============================================================================

function makeScene(
  order: number,
  duration: number,
  transition_out_kind: TransitionKindValue | null = null,
  transition_out_dur = 0,
  transition_in_kind: TransitionKindValue | null = null,
  transition_in_dur = 0,
): EditorialScene {
  return {
    scene_id: `scene_${order + 1}`,
    order,
    source_scene_duration_sec: duration,
    transition_in:
      transition_in_kind !== null
        ? {
            transition_id: `in_${order}`,
            kind: transition_in_kind,
            duration_sec: transition_in_dur,
            easing: "ease_in_out",
          }
        : null,
    transition_out:
      transition_out_kind !== null
        ? {
            transition_id: `out_${order}`,
            kind: transition_out_kind,
            duration_sec: transition_out_dur,
            easing: "ease_in_out",
          }
        : null,
    holds: [],
    animation_plan_id: null,
    caption_track_id: null,
    pacing_category: PacingCategory.NORMAL,
    emphasis_level: EmphasisLevel.MEDIUM,
    audio_clips: [],
    layer_overrides: {},
  };
}

function makeTimeline(
  scenes: EditorialScene[],
  fps = 30,
): EditorialTimeline {
  return {
    timeline_id: "tl",
    fps,
    width: 1280,
    height: 720,
    scenes,
    audio_tracks: [],
    layer_order: [
      LayerKind.BACKGROUND,
      LayerKind.ENVIRONMENT,
      LayerKind.PROPS,
      LayerKind.CHARACTERS,
      LayerKind.DIAGRAMS,
      LayerKind.OVERLAYS,
      LayerKind.CAPTIONS,
      LayerKind.TITLE_CARDS,
    ],
    allow_micro_gaps: false,
    project_id: "p",
    job_id: "j",
  };
}

function makeRenderPlan(
  scenes: RenderScene[],
  layers: RenderLayer[] = [],
  audio_clips: RenderAudioClip[] = [],
  fps = 30,
  totalFrames = 60,
): RenderPlan {
  return {
    version: "1.0.0",
    plan_id: "rp_test",
    project_id: "p",
    job_id: "j",
    topic: "Test",
    fps,
    width: 1280,
    height: 720,
    total_duration_frames: totalFrames,
    total_duration_sec: totalFrames / fps,
    scenes,
    layers,
    audio_clips,
    audio_track_ids: [],
    title_cards: [],
    layer_order: [],
    source_fingerprint: "fp_test",
    created_at: "2026-01-01T00:00:00Z",
    warnings: [],
    failures: [],
  };
}

function makeRenderScene(
  order: number,
  start: number,
  duration: number,
): RenderScene {
  return {
    scene_id: `scene_${order + 1}`,
    order,
    master_start_frame: start,
    duration_frames: duration,
    source_scene_duration_frames: duration,
    transition_in: null,
    transition_out: null,
    hold_frames_before: 0,
    hold_frames_after: 0,
    animation_plan_id: null,
    caption_track_id: null,
    pacing_category: PacingCategory.NORMAL,
    emphasis_level: EmphasisLevel.MEDIUM,
  };
}

// ============================================================================
// placeScenes — scene offsets
// ============================================================================

describe("placeScenes", () => {
  it("places a single scene at master_start=0", () => {
    const tl = makeTimeline([makeScene(0, 5.0)]);
    const placements = placeScenes(tl);
    expect(placements).toHaveLength(1);
    expect(placements[0]!.master_start_sec).toBe(0);
    expect(placements[0]!.master_end_sec).toBe(5);
    expect(placements[0]!.master_start_frame).toBe(0);
    expect(placements[0]!.duration_frames).toBe(150);
  });

  it("places back-to-back scenes", () => {
    const tl = makeTimeline([makeScene(0, 3.0), makeScene(1, 2.0)]);
    const [a, b] = placeScenes(tl);
    expect(a!.master_end_sec).toBe(3.0);
    expect(b!.master_start_sec).toBe(3.0);
    expect(b!.master_end_sec).toBe(5.0);
  });

  it("overlaps by transition_out duration", () => {
    const tl = makeTimeline([
      makeScene(0, 3.0, TransitionKind.FADE, 0.5),
      makeScene(1, 2.0),
    ]);
    const [a, b] = placeScenes(tl);
    expect(b!.master_start_sec).toBeCloseTo(2.5);
  });

  it("throws on CUT transition_in with non-zero duration", () => {
    const tl = makeTimeline([
      makeScene(0, 3.0),
      makeScene(1, 2.0, null, 0, TransitionKind.CUT, 1.0),
    ]);
    expect(() => placeScenes(tl)).toThrow();
  });
});

// ============================================================================
// Transitions
// ============================================================================

describe("validateTransitionPair", () => {
  it("returns no errors for matching fade transitions", () => {
    const s0 = makeScene(0, 3.0, TransitionKind.FADE, 0.5);
    const s1 = makeScene(1, 2.0, null, 0, TransitionKind.FADE, 0.5);
    expect(validateTransitionPair(s0, s1)).toEqual([]);
  });

  it("detects kind mismatch", () => {
    const s0 = makeScene(0, 3.0, TransitionKind.FADE, 0.5);
    const s1 = makeScene(1, 2.0, null, 0, TransitionKind.CUT, 0);
    const errs = validateTransitionPair(s0, s1);
    expect(errs.some((e) => e.includes("kind mismatch"))).toBe(true);
  });

  it("detects duration mismatch", () => {
    const s0 = makeScene(0, 3.0, TransitionKind.FADE, 0.3);
    const s1 = makeScene(1, 2.0, null, 0, TransitionKind.FADE, 0.5);
    const errs = validateTransitionPair(s0, s1);
    expect(errs.some((e) => e.includes("duration mismatch"))).toBe(true);
  });

  it("detects transition exceeding scene duration", () => {
    const s0 = makeScene(0, 2.0, TransitionKind.FADE, 5.0);
    const s1 = makeScene(1, 3.0);
    const errs = validateTransitionPair(s0, s1);
    expect(errs.some((e) => e.includes("exceeds scene duration"))).toBe(true);
  });
});

describe("validateAllTransitions", () => {
  it("validates three back-to-back fades", () => {
    const scenes = [
      makeScene(0, 2.0, TransitionKind.FADE, 0.3),
      makeScene(1, 2.0, TransitionKind.FADE, 0.3),
      makeScene(2, 2.0, null, 0, TransitionKind.FADE, 0.3),
    ];
    expect(validateAllTransitions(scenes)).toEqual([]);
  });
});

// ============================================================================
// Audio mixing
// ============================================================================

describe("collectNarrationWindows", () => {
  it("filters narration clips and projects to master time", () => {
    const clips = [
      {
        clip_id: "c1",
        artifact_id: "aa1",
        track_kind: AudioTrackKind.NARRATION,
        priority: 0,
        scene_local_start_sec: 0,
        duration_sec: 2,
        gain_db: 0,
        fade_in_sec: 0,
        fade_out_sec: 0,
        loop: false,
      },
      {
        clip_id: "c2",
        artifact_id: "aa2",
        track_kind: AudioTrackKind.MUSIC,
        priority: 3,
        scene_local_start_sec: 0.5,
        duration_sec: 2,
        gain_db: 0,
        fade_in_sec: 0,
        fade_out_sec: 0,
        loop: false,
      },
    ];
    const starts = { c1: 5.0, c2: 6.0 };
    const sceneIds = { c1: "s1", c2: "s1" };
    const windows = collectNarrationWindows(clips, starts, sceneIds);
    expect(windows).toHaveLength(1);
    expect(windows[0]!.master_start_sec).toBe(5.0);
    expect(windows[0]!.master_end_sec).toBe(7.0);
  });
});

describe("isInAnyWindow", () => {
  const windows = [
    { scene_id: null, clip_id: "x", master_start_sec: 5.0, master_end_sec: 7.0 },
  ];
  it("returns true inside window", () => {
    expect(isInAnyWindow(5.5, windows)).toBe(true);
  });
  it("returns false at exclusive upper bound", () => {
    expect(isInAnyWindow(7.0, windows)).toBe(false);
  });
  it("returns false outside window", () => {
    expect(isInAnyWindow(4.9, windows)).toBe(false);
  });
});

describe("computeDucking", () => {
  it("ducks music when narration is active", () => {
    const windows = [
      { scene_id: null, clip_id: "x", master_start_sec: 2.0, master_end_sec: 6.0 },
    ];
    const r = computeDucking(-12, "music", 0, windows, 0, 10, undefined, -9);
    expect(r.effective_gain_db).toBeCloseTo(-21);
    expect(r.duck_gain_db).toBe(-9);
    expect(r.duck_target_track_ids).toContain("narration");
  });
  it("does not duck when no overlap", () => {
    const windows = [
      { scene_id: null, clip_id: "x", master_start_sec: 100.0, master_end_sec: 110.0 },
    ];
    const r = computeDucking(-12, "music", 0, windows, 0, 2, undefined, -9);
    expect(r.effective_gain_db).toBe(-12);
    expect(r.duck_target_track_ids).toEqual([]);
  });
  it("does not duck narration itself", () => {
    const r = computeDucking(0, "narration", 0, [], 0, 2, undefined, -9);
    expect(r.effective_gain_db).toBe(0);
    expect(r.duck_gain_db).toBe(null);
  });
});

// ============================================================================
// Quality score
// ============================================================================

describe("computeQualityScore", () => {
  it("returns overall within [0, 1]", () => {
    const plan = makeRenderPlan([makeRenderScene(0, 0, 30)]);
    const qs = computeQualityScore(plan, [], 1.0);
    expect(qs.overall).toBeGreaterThanOrEqual(0);
    expect(qs.overall).toBeLessThanOrEqual(1);
  });
  it("timeline_validity drops when failures present", () => {
    const plan = makeRenderPlan([makeRenderScene(0, 0, 30)]);
    const qs = computeQualityScore(plan, ["some failure"], 1.0);
    expect(qs.timeline_validity).toBeLessThan(1.0);
  });
});

// ============================================================================
// Frame seek
// ============================================================================

describe("seekFrame", () => {
  it("finds the active scene at frame N", () => {
    const plan = makeRenderPlan([
      makeRenderScene(0, 0, 30),
      makeRenderScene(1, 30, 30),
    ], [], [], 30, 60);
    expect(seekFrame(plan, 0).active_scene_id).toBe("scene_1");
    expect(seekFrame(plan, 15).active_scene_id).toBe("scene_1");
    expect(seekFrame(plan, 30).active_scene_id).toBe("scene_2");
    expect(seekFrame(plan, 59).active_scene_id).toBe("scene_2");
  });

  it("returns null active_scene_id outside any scene", () => {
    const plan = makeRenderPlan([
      makeRenderScene(0, 0, 30),
    ], [], [], 30, 30);
    expect(seekFrame(plan, 35).active_scene_id).toBeNull();
  });

  it("frame seek is deterministic", () => {
    const plan = makeRenderPlan([
      makeRenderScene(0, 0, 30),
      makeRenderScene(1, 30, 30),
    ], [], [], 30, 60);
    expect(seekFrame(plan, 15)).toEqual(seekFrame(plan, 15));
    expect(seekFrame(plan, 45)).toEqual(seekFrame(plan, 45));
  });

  it("finds active layers and audio_clips", () => {
    const layers = [
      {
        layer_id: "scene_1:background",
        kind: LayerKind.BACKGROUND,
        z_order: 0,
        scene_id: "scene_1",
        master_start_frame: 0,
        duration_frames: 30,
        payload: {},
      },
    ];
    const audio_clips = [
      {
        clip_id: "a1",
        artifact_id: "aa1",
        track_kind: AudioTrackKind.NARRATION,
        track_id: "trk-n",
        scene_id: "scene_1",
        master_start_frame: 0,
        duration_frames: 30,
        gain_db: 0,
        fade_in_frames: 0,
        fade_out_frames: 0,
        duck_target_track_ids: [],
        duck_gain_db: null,
      },
    ];
    const plan = makeRenderPlan([makeRenderScene(0, 0, 30)], layers, audio_clips, 30, 30);
    const snap = seekFrame(plan, 15);
    expect(snap.active_layer_ids).toEqual(["scene_1:background"]);
    expect(snap.active_audio_clip_ids).toEqual(["a1"]);
  });
});

describe("sceneLocalTime / masterTimeFrame", () => {
  it("round-trips a scene-local time", () => {
    const plan = makeRenderPlan([makeRenderScene(0, 0, 30)], [], [], 30, 30);
    const scene = plan.scenes[0]!;
    expect(sceneLocalTime(plan, scene, 15)).toBeCloseTo(0.5);
    expect(masterTimeFrame(plan, scene, 0.5)).toBe(15);
  });
  it("clamps negative values to 0", () => {
    const plan = makeRenderPlan([makeRenderScene(0, 0, 30)], [], [], 30, 30);
    const scene = plan.scenes[0]!;
    expect(sceneLocalTime(plan, scene, -10)).toBe(0);
  });
});

describe("linearGain", () => {
  it("0 dB → 1.0", () => {
    expect(linearGain(0)).toBeCloseTo(1);
  });
  it("-60 dB or less → 0", () => {
    expect(linearGain(-60)).toBe(0);
    expect(linearGain(-100)).toBe(0);
  });
  it("-12 dB ≈ 0.25", () => {
    expect(linearGain(-12)).toBeCloseTo(0.251, 3);
  });
});

// ============================================================================
// Cross-runtime shape parity
// ============================================================================

describe("RenderPlan shape parity", () => {
  it("every required field exists on the canonical shape", () => {
    const plan = makeRenderPlan([makeRenderScene(0, 0, 30)]);
    const expectedTopLevel = [
      "version", "plan_id", "project_id", "job_id", "topic",
      "fps", "width", "height", "total_duration_frames", "total_duration_sec",
      "scenes", "layers", "audio_clips", "audio_track_ids",
      "title_cards", "layer_order", "source_fingerprint",
    ];
    for (const key of expectedTopLevel) {
      expect(plan).toHaveProperty(key);
    }
  });
  it("RenderScene carries every renderer-needed field", () => {
    const s = makeRenderScene(0, 0, 30);
    const expected = [
      "scene_id", "order", "master_start_frame", "duration_frames",
      "source_scene_duration_frames", "transition_in", "transition_out",
      "hold_frames_before", "hold_frames_after", "animation_plan_id",
      "caption_track_id", "pacing_category", "emphasis_level",
    ];
    for (const key of expected) {
      expect(s).toHaveProperty(key);
    }
  });
  it("RenderAudioClip carries every renderer-needed field", () => {
    const c: RenderAudioClip = {
      clip_id: "a", artifact_id: "aa", track_kind: AudioTrackKind.NARRATION,
      track_id: "trk", scene_id: "s1", master_start_frame: 0,
      duration_frames: 30, gain_db: 0, fade_in_frames: 0, fade_out_frames: 0,
      duck_target_track_ids: [], duck_gain_db: null,
    };
    const expected = [
      "clip_id", "artifact_id", "track_kind", "track_id", "scene_id",
      "master_start_frame", "duration_frames", "gain_db",
      "fade_in_frames", "fade_out_frames",
      "duck_target_track_ids", "duck_gain_db",
    ];
    for (const key of expected) {
      expect(c).toHaveProperty(key);
    }
  });
});

// ============================================================================
// Layer ordering
// ============================================================================

describe("Layer ordering", () => {
  it("default z-order has BACKGROUND lowest, TITLE_CARDS highest", () => {
    const tl = makeTimeline([makeScene(0, 1.0)]);
    expect(tl.layer_order[0]).toBe(LayerKind.BACKGROUND);
    expect(tl.layer_order[tl.layer_order.length - 1]).toBe(LayerKind.TITLE_CARDS);
  });
});

// ============================================================================
// Determinism (PROMPT 10 §36)
// ============================================================================

describe("Determinism", () => {
  it("same plan yields same seek result", () => {
    const plan = makeRenderPlan([
      makeRenderScene(0, 0, 30),
      makeRenderScene(1, 30, 30),
    ], [], [], 30, 60);
    for (let f = 0; f < 60; f++) {
      expect(seekFrame(plan, f)).toEqual(seekFrame(plan, f));
    }
  });
});

// ============================================================================
// EditorialProject shape (minimal)
// ============================================================================

describe("EditorialProject shape", () => {
  it("requires the canonical fields", () => {
    const project: EditorialProject = {
      version: "1.0.0",
      project_id: "p",
      job_id: "j",
      topic: "T",
      story_package_id: null,
      storyboard_package_id: null,
      asset_package_id: null,
      narration_timeline_id: null,
      timeline: makeTimeline([makeScene(0, 2.0)]),
      mixing_policy: {
        base_gain_db: { narration: 0, dialogue: -1, music: -12, sfx: -3, ambience: -18 },
        narration_duck_gain_db: -9,
        target_peak_dbfs: -3,
        target_loudness_lufs: -16,
      },
      title_cards: [],
      target_total_duration_sec: 2.0,
      created_at: "2026-01-01T00:00:00Z",
    };
    expect(project.project_id).toBe("p");
    expect(project.timeline.scenes).toHaveLength(1);
  });
});

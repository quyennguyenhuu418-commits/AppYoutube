/**
 * Animation Runtime — types, target resolution, conflict resolution,
 * deterministic frame state computation.
 *
 * PROMPT 7 §28: Separate Animation Definition from Animation Runtime
 * from Rendering.
 *
 * This module is fs-free so it can be safely bundled by webpack.
 */

import {
  interpolateKeyframes,
  interpolateValue,
  type InterpolationMode,
  type Keyframe,
} from "./interpolation";

// ============================================================================
// Types — mirror of the Python AnimationPlan schema (orchestrator/app/animation/schemas.py)
// ============================================================================

export type Interpolation = InterpolationMode;

export type TargetKind = "character" | "prop" | "environment" | "camera" | "overlay";

export type TransformProperty = "x" | "y" | "scale" | "rotation_deg" | "opacity";
export type CameraProperty = "pan_x" | "pan_y" | "zoom";

export type ActionLabel =
  | "none"
  | "stand"
  | "walk"
  | "run"
  | "point"
  | "think"
  | "celebrate"
  | "hide"
  | "sit"
  | "enter"
  | "exit";

export interface AnimationTarget {
  target_id: string;
  kind: TargetKind;
  instance_id?: string;
}

export interface AnimationTrack {
  track_id: string;
  target: AnimationTarget;
  property: TransformProperty | CameraProperty;
  keyframes: Keyframe[];
  priority: number;
  duration_sec: number;
}

export interface PoseSegment {
  start_sec: number;
  end_sec: number;
  action: ActionLabel;
  pose: string;
}

export interface WalkCycleParams {
  walk_speed: number;
  step_frequency: number;
  stride_length: number;
  body_bob: number;
  arm_swing: number;
}

export interface CharacterAnimation {
  character_id: string;
  pose_sequence: PoseSegment[];
  walk_cycle_params?: WalkCycleParams | null;
  motion_tracks: AnimationTrack[];
}

export interface PropInteraction {
  interaction_id: string;
  character_id: string;
  prop_id: string;
  character_anchor: string;
  prop_anchor: string;
  start_sec: number;
  end_sec: number;
  kind: "attach" | "detach" | "hold" | "release";
}

export interface PropAnimation {
  prop_id: string;
  instance_id?: string;
  motion_tracks: AnimationTrack[];
  interactions: PropInteraction[];
}

export interface CameraAnimation {
  camera_id: string;
  start_pan_x: number;
  start_pan_y: number;
  start_zoom: number;
  end_pan_x: number;
  end_pan_y: number;
  end_zoom: number;
  easing: InterpolationMode;
  waypoints?: Array<[number, number, number]>;
}

export interface AnimationEvent {
  event_id: string;
  at_sec: number;
  kind: string;
  detail: Record<string, unknown>;
}

export interface AnimationPlanMetadata {
  version: string;
  plan_id: string;
  scene_id: string;
  job_id: string;
  duration_sec: number;
  created_at: string;
  source: string;
}

export interface AnimationPlan {
  metadata: AnimationPlanMetadata;
  duration_sec: number;
  camera: CameraAnimation;
  characters: CharacterAnimation[];
  props: PropAnimation[];
  tracks: AnimationTrack[];
  events: AnimationEvent[];
  warnings: string[];
  failures: string[];
}

// ============================================================================
// Frame state — the deterministic output of the runtime at frame N
// ============================================================================

export interface CharacterFrameState {
  character_id: string;
  x: number;
  y: number;
  scale: number;
  rotation_deg: number;
  opacity: number;
  pose: string;
  walk_phase: number;     // 0..1 — current step in walk cycle
}

export interface PropFrameState {
  prop_id: string;
  instance_id: string;
  x: number;
  y: number;
  scale: number;
  rotation_deg: number;
  opacity: number;
  attached_to_character_id: string | null;
  attached_to_anchor: string | null;
}

export interface CameraFrameState {
  pan_x: number;
  pan_y: number;
  zoom: number;
}

export interface AnimationFrameState {
  time_sec: number;
  duration_sec: number;
  characters: CharacterFrameState[];
  props: PropFrameState[];
  camera: CameraFrameState;
}

// ============================================================================
// Pose resolution — what pose is the character at this moment?
// ============================================================================

export function resolvePose(charAnim: CharacterAnimation, timeSec: number): string {
  // Find the latest pose segment covering timeSec.
  for (let i = charAnim.pose_sequence.length - 1; i >= 0; i--) {
    const seg = charAnim.pose_sequence[i]!;
    if (timeSec >= seg.start_sec && timeSec < seg.end_sec) {
      return seg.pose;
    }
  }
  // Fallback to last segment or "stand".
  if (charAnim.pose_sequence.length > 0) {
    const last = charAnim.pose_sequence[charAnim.pose_sequence.length - 1]!;
    return last.pose;
  }
  return "stand";
}

// ============================================================================
// Walk phase — deterministic phase based on time + step_frequency
// ============================================================================

export function resolveWalkPhase(
  charAnim: CharacterAnimation,
  timeSec: number,
): number {
  if (!charAnim.walk_cycle_params) return 0.0;
  const freq = charAnim.walk_cycle_params.step_frequency;
  if (freq <= 0) return 0.0;
  // Phase wraps every (1/freq) seconds. Always positive.
  const period = 1.0 / freq;
  const phase = (timeSec % period) / period;
  return phase < 0 ? phase + 1 : phase;
}

// ============================================================================
// Track resolution — for a given (target, property), find the winning track
// ============================================================================

export function findWinningTrack(
  tracks: AnimationTrack[],
  targetId: string,
  property: TransformProperty | CameraProperty,
): AnimationTrack | null {
  const candidates = tracks.filter(
    (t) => t.target.target_id === targetId && t.property === property,
  );
  if (candidates.length === 0) return null;
  if (candidates.length === 1) return candidates[0]!;
  // Highest priority, then lexicographic track_id (deterministic).
  candidates.sort((a, b) => {
    if (a.priority !== b.priority) return b.priority - a.priority;
    return a.track_id.localeCompare(b.track_id);
  });
  return candidates[0]!;
}

// ============================================================================
// Conflict resolution — deterministic
// ============================================================================

export function resolveTrackConflicts(
  tracks: AnimationTrack[],
): AnimationTrack[] {
  const groups = new Map<string, AnimationTrack[]>();
  for (const track of tracks) {
    const key = `${track.target.target_id}::${track.property}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(track);
  }
  const survivors: AnimationTrack[] = [];
  for (const group of groups.values()) {
    if (group.length === 1) {
      survivors.push(group[0]!);
      continue;
    }
    group.sort((a, b) => {
      if (a.priority !== b.priority) return b.priority - a.priority;
      return a.track_id.localeCompare(b.track_id);
    });
    survivors.push(group[0]!);
  }
  return survivors;
}

// ============================================================================
// Frame state computation — pure function of (plan, time_sec)
// ============================================================================

const DEFAULT_CHARACTER_STATE: Omit<CharacterFrameState, "character_id" | "pose" | "walk_phase"> = {
  x: 0.5,
  y: 0.5,
  scale: 1.0,
  rotation_deg: 0.0,
  opacity: 1.0,
};

const DEFAULT_PROP_STATE: Omit<PropFrameState, "prop_id" | "instance_id"> = {
  x: 0.5,
  y: 0.5,
  scale: 1.0,
  rotation_deg: 0.0,
  opacity: 1.0,
  attached_to_character_id: null,
  attached_to_anchor: null,
};

export function computeFrameState(plan: AnimationPlan, timeSec: number): AnimationFrameState {
  // Clamp time to [0, duration_sec].
  const t = Math.max(0, Math.min(timeSec, plan.duration_sec));

  // ---- Camera ----
  const camera: CameraFrameState = {
    pan_x: interpolateValue(
      plan.camera.start_pan_x,
      plan.camera.end_pan_x,
      t / Math.max(plan.duration_sec, 0.001),
      plan.camera.easing,
    ),
    pan_y: interpolateValue(
      plan.camera.start_pan_y,
      plan.camera.end_pan_y,
      t / Math.max(plan.duration_sec, 0.001),
      plan.camera.easing,
    ),
    zoom: interpolateValue(
      plan.camera.start_zoom,
      plan.camera.end_zoom,
      t / Math.max(plan.duration_sec, 0.001),
      plan.camera.easing,
    ),
  };

  // ---- Characters ----
  const characters: CharacterFrameState[] = plan.characters.map((charAnim) => {
    const tid = `character:${charAnim.character_id}`;
    const state: CharacterFrameState = {
      character_id: charAnim.character_id,
      ...DEFAULT_CHARACTER_STATE,
      pose: resolvePose(charAnim, t),
      walk_phase: resolveWalkPhase(charAnim, t),
    };

    const xTrack = findWinningTrack(charAnim.motion_tracks, tid, "x");
    if (xTrack) {
      const baseX = 0.5; // center
      state.x = baseX + interpolateKeyframes(xTrack.keyframes, t, xTrack.duration_sec || plan.duration_sec);
    }
    const yTrack = findWinningTrack(charAnim.motion_tracks, tid, "y");
    if (yTrack) {
      const baseY = 0.5;
      state.y = baseY + interpolateKeyframes(yTrack.keyframes, t, yTrack.duration_sec || plan.duration_sec);
    }
    const scaleTrack = findWinningTrack(charAnim.motion_tracks, tid, "scale");
    if (scaleTrack) {
      state.scale = interpolateKeyframes(scaleTrack.keyframes, t, scaleTrack.duration_sec || plan.duration_sec);
    }
    const rotTrack = findWinningTrack(charAnim.motion_tracks, tid, "rotation_deg");
    if (rotTrack) {
      state.rotation_deg = interpolateKeyframes(rotTrack.keyframes, t, rotTrack.duration_sec || plan.duration_sec);
    }
    const opTrack = findWinningTrack(charAnim.motion_tracks, tid, "opacity");
    if (opTrack) {
      state.opacity = interpolateKeyframes(opTrack.keyframes, t, opTrack.duration_sec || plan.duration_sec);
    }

    // Apply walk cycle: horizontal motion + bob.
    if (charAnim.walk_cycle_params) {
      const wp = charAnim.walk_cycle_params;
      const phase = state.walk_phase;
      // Horizontal displacement (oscillates around current x).
      // Stride / period = total range; half on each side.
      state.x += wp.stride_length * 0.5 * Math.sin(phase * 2 * Math.PI);
      // Body bob: vertical sinusoidal with frequency 2x (two bobs per step).
      state.y += wp.body_bob * Math.sin(phase * 4 * Math.PI);
      // If pose is "walk" and the pose_sequence doesn't already say so, keep current.
    }

    // Clamp.
    state.x = clamp01(state.x);
    state.y = clamp01(state.y);
    state.opacity = clamp(state.opacity, 0, 1);
    return state;
  });

  // ---- Props ----
  const props: PropFrameState[] = plan.props.map((propAnim) => {
    const instId = propAnim.instance_id || "";
    const tid = `prop:${propAnim.prop_id}`;
    const state: PropFrameState = {
      prop_id: propAnim.prop_id,
      instance_id: instId,
      ...DEFAULT_PROP_STATE,
    };

    const xTrack = findWinningTrack(propAnim.motion_tracks, tid, "x");
    if (xTrack) {
      state.x = 0.5 + interpolateKeyframes(xTrack.keyframes, t, xTrack.duration_sec || plan.duration_sec);
    }
    const yTrack = findWinningTrack(propAnim.motion_tracks, tid, "y");
    if (yTrack) {
      state.y = 0.5 + interpolateKeyframes(yTrack.keyframes, t, yTrack.duration_sec || plan.duration_sec);
    }
    const scaleTrack = findWinningTrack(propAnim.motion_tracks, tid, "scale");
    if (scaleTrack) {
      state.scale = interpolateKeyframes(scaleTrack.keyframes, t, scaleTrack.duration_sec || plan.duration_sec);
    }
    const rotTrack = findWinningTrack(propAnim.motion_tracks, tid, "rotation_deg");
    if (rotTrack) {
      state.rotation_deg = interpolateKeyframes(rotTrack.keyframes, t, rotTrack.duration_sec || plan.duration_sec);
    }
    const opTrack = findWinningTrack(propAnim.motion_tracks, tid, "opacity");
    if (opTrack) {
      state.opacity = interpolateKeyframes(opTrack.keyframes, t, opTrack.duration_sec || plan.duration_sec);
    }

    // Resolve active interaction at this time.
    const activeInteraction = propAnim.interactions.find(
      (i) => t >= i.start_sec && t < i.end_sec,
    );
    if (activeInteraction) {
      state.attached_to_character_id = activeInteraction.character_id;
      state.attached_to_anchor = activeInteraction.character_anchor;
    }

    // Clamp.
    state.x = clamp01(state.x);
    state.y = clamp01(state.y);
    state.opacity = clamp(state.opacity, 0, 1);
    return state;
  });

  return {
    time_sec: t,
    duration_sec: plan.duration_sec,
    characters,
    props,
    camera,
  };
}

function clamp01(v: number): number {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}
function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}

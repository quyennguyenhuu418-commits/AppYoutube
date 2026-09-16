/**
 * Editorial Engine — TypeScript mirror (PROMPT 10).
 *
 * These interfaces are byte-equivalent to the Python `RenderPlan` schema
 * (`orchestrator/app/editorial/schemas.py`). Cross-runtime parity is
 * verified by `renderer/src/editorial/crossRuntime.test.ts`.
 *
 * Architectural rule (PROMPT 10 §3, §33, §34):
 *   EditorialProject → EditorialCompiler → RenderPlan → Documentary.tsx
 *   The renderer is a deterministic function of (RenderPlan, frame).
 *   No business logic lives in JSX.
 */

// ============================================================================
// Enums
// ============================================================================

export const TransitionKind = {
  CUT: "cut",
  FADE: "fade",
  CROSSFADE: "crossfade",
  DISSOLVE: "dissolve",
  DIP_TO_BLACK: "dip_to_black",
  DIP_TO_WHITE: "dip_to_white",
} as const;
export type TransitionKindValue =
  (typeof TransitionKind)[keyof typeof TransitionKind];

export const AudioTrackKind = {
  NARRATION: "narration",
  DIALOGUE: "dialogue",
  MUSIC: "music",
  SFX: "sfx",
  AMBIENCE: "ambience",
} as const;
export type AudioTrackKindValue =
  (typeof AudioTrackKind)[keyof typeof AudioTrackKind];

export const AudioPriority = {
  NARRATION: 0,
  DIALOGUE: 1,
  SFX: 2,
  MUSIC: 3,
  AMBIENCE: 4,
} as const;

export const LayerKind = {
  BACKGROUND: "background",
  ENVIRONMENT: "environment",
  PROPS: "props",
  CHARACTERS: "characters",
  DIAGRAMS: "diagrams",
  OVERLAYS: "overlays",
  CAPTIONS: "captions",
  TITLE_CARDS: "title_cards",
} as const;
export type LayerKindValue = (typeof LayerKind)[keyof typeof LayerKind];

export const PacingCategory = {
  SLOW: "slow",
  NORMAL: "normal",
  FAST: "fast",
  IMPACT: "impact",
  REFLECTIVE: "reflective",
} as const;
export type PacingCategoryValue =
  (typeof PacingCategory)[keyof typeof PacingCategory];

export const EmphasisLevel = {
  LOW: "low",
  MEDIUM: "medium",
  HIGH: "high",
} as const;
export type EmphasisLevelValue =
  (typeof EmphasisLevel)[keyof typeof EmphasisLevel];

export const TitleCardKind = {
  INTRO: "intro",
  CHAPTER: "chapter",
  SECTION: "section",
  OUTRO: "outro",
} as const;
export type TitleCardKindValue =
  (typeof TitleCardKind)[keyof typeof TitleCardKind];

// ============================================================================
// Reference models (Python mirror)
// ============================================================================

export interface Transition {
  transition_id: string;
  kind: TransitionKindValue;
  duration_sec: number;
  easing: "linear" | "ease_in" | "ease_out" | "ease_in_out";
}

export interface EditorialHold {
  hold_id: string;
  target: "before" | "after";
  duration_sec: number;
  reason: string;
}

export interface AudioClipRef {
  clip_id: string;
  artifact_id: string;
  track_kind: AudioTrackKindValue;
  priority: number;
  scene_local_start_sec: number;
  duration_sec: number;
  gain_db: number;
  fade_in_sec: number;
  fade_out_sec: number;
  loop: boolean;
}

export interface AudioTrackLayer {
  track_id: string;
  kind: AudioTrackKindValue;
  clips: AudioClipRef[];
  duck_gain_db: number | null;
  duck_active_track_kinds: AudioTrackKindValue[];
}

export interface EditorialScene {
  scene_id: string;
  order: number;
  source_scene_duration_sec: number;
  transition_in: Transition | null;
  transition_out: Transition | null;
  holds: EditorialHold[];
  animation_plan_id: string | null;
  caption_track_id: string | null;
  pacing_category: PacingCategoryValue;
  emphasis_level: EmphasisLevelValue;
  audio_clips: AudioClipRef[];
  layer_overrides: Record<string, unknown>;
}

export interface EditorialTimeline {
  timeline_id: string;
  fps: number;
  width: number;
  height: number;
  scenes: EditorialScene[];
  audio_tracks: AudioTrackLayer[];
  layer_order: LayerKindValue[];
  allow_micro_gaps: boolean;
  project_id: string;
  job_id: string;
}

export interface AudioMixingPolicy {
  base_gain_db: Record<string, number>;
  narration_duck_gain_db: number;
  target_peak_dbfs: number;
  target_loudness_lufs: number | null;
}

export interface TitleCardSpec {
  card_id: string;
  kind: TitleCardKindValue;
  title: string;
  subtitle: string | null;
  master_start_sec: number;
  duration_sec: number;
  style_id: string;
}

export interface EditorialProject {
  version: string;
  project_id: string;
  job_id: string;
  topic: string;
  story_package_id: string | null;
  storyboard_package_id: string | null;
  asset_package_id: string | null;
  narration_timeline_id: string | null;
  timeline: EditorialTimeline;
  mixing_policy: AudioMixingPolicy;
  title_cards: TitleCardSpec[];
  target_total_duration_sec: number;
  created_at: string;
}

// ============================================================================
// RenderPlan (C-26)
// ============================================================================

export interface RenderLayer {
  layer_id: string;
  kind: LayerKindValue;
  z_order: number;
  scene_id: string;
  master_start_frame: number;
  duration_frames: number;
  payload: Record<string, unknown>;
}

export interface RenderAudioClip {
  clip_id: string;
  artifact_id: string;
  track_kind: AudioTrackKindValue;
  track_id: string;
  scene_id: string | null;
  master_start_frame: number;
  duration_frames: number;
  gain_db: number;
  fade_in_frames: number;
  fade_out_frames: number;
  duck_target_track_ids: string[];
  duck_gain_db: number | null;
}

export interface RenderScene {
  scene_id: string;
  order: number;
  master_start_frame: number;
  duration_frames: number;
  source_scene_duration_frames: number;
  transition_in: Transition | null;
  transition_out: Transition | null;
  hold_frames_before: number;
  hold_frames_after: number;
  animation_plan_id: string | null;
  caption_track_id: string | null;
  pacing_category: PacingCategoryValue;
  emphasis_level: EmphasisLevelValue;
}

export interface RenderPlan {
  version: string;
  plan_id: string;
  project_id: string;
  job_id: string;
  topic: string;
  fps: number;
  width: number;
  height: number;
  total_duration_frames: number;
  total_duration_sec: number;
  scenes: RenderScene[];
  layers: RenderLayer[];
  audio_clips: RenderAudioClip[];
  audio_track_ids: string[];
  title_cards: TitleCardSpec[];
  layer_order: LayerKindValue[];
  source_fingerprint: string;
  created_at: string;
  warnings: string[];
  failures: string[];
}

// ============================================================================
// Frame-seek helpers (PROMPT 10 §35, §47)
// ============================================================================

export interface FrameStateSnapshot {
  frame: number;
  time_sec: number;
  active_scene: RenderScene | null;
  active_layers: RenderLayer[];
  active_audio_clips: RenderAudioClip[];
  active_title_cards: TitleCardSpec[];
}

/**
 * Pure function: derive the frame's state from a RenderPlan.
 * No sequential playback state, no Date.now(), no setInterval.
 */
export function seekFrame(plan: RenderPlan, frame: number): FrameStateSnapshot {
  const time_sec = frame / plan.fps;
  const active_scene =
    plan.scenes.find(
      (s) =>
        s.master_start_frame <= frame &&
        frame < s.master_start_frame + s.duration_frames,
    ) ?? null;

  const active_layers = plan.layers.filter(
    (l) =>
      l.master_start_frame <= frame &&
      frame < l.master_start_frame + l.duration_frames,
  );
  const active_audio_clips = plan.audio_clips.filter(
    (c) =>
      c.master_start_frame <= frame &&
      frame < c.master_start_frame + c.duration_frames,
  );
  const active_title_cards = plan.title_cards.filter((tc) => {
    const start_frame = tc.master_start_sec * plan.fps;
    const end_frame = start_frame + tc.duration_sec * plan.fps;
    return start_frame <= frame && frame < end_frame;
  });
  return { frame, time_sec, active_scene, active_layers, active_audio_clips, active_title_cards };
}

/**
 * Compute a scene-local time from a master-time frame.
 * Pure function of (RenderPlan.scene, frame).
 */
export function sceneLocalTime(
  plan: RenderPlan,
  scene: RenderScene,
  frame: number,
): number {
  return Math.max(0, (frame - scene.master_start_frame) / plan.fps);
}

/**
 * Compute the master-time frame from a scene-local time.
 * Pure function of (RenderPlan.fps, scene.master_start_frame).
 */
export function masterTimeFrame(
  plan: RenderPlan,
  scene: RenderScene,
  sceneLocalSec: number,
): number {
  return scene.master_start_frame + Math.round(sceneLocalSec * plan.fps);
}

/**
 * Compute the effective linear gain (0..1) for an audio clip's `gain_db`.
 * -60 dB or lower → silent.
 */
export function linearGain(gain_db: number): number {
  if (gain_db <= -60) return 0;
  return Math.pow(10, gain_db / 20);
}

/**
 * Render-plan fingerprint comparison (PROMPT 10 §36).
 */
export function sameFingerprint(a: RenderPlan, b: RenderPlan): boolean {
  return a.source_fingerprint === b.source_fingerprint;
}

/**
 * Type guard — narrows an unknown JSON value to RenderPlan shape.
 * Light validation: only checks the top-level required fields.
 */
export function isRenderPlan(value: unknown): value is RenderPlan {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.plan_id === "string" &&
    typeof v.fps === "number" &&
    typeof v.width === "number" &&
    typeof v.height === "number" &&
    typeof v.total_duration_frames === "number" &&
    typeof v.source_fingerprint === "string" &&
    Array.isArray(v.scenes) &&
    Array.isArray(v.layers) &&
    Array.isArray(v.audio_clips)
  );
}

export const __all__ = [
  "TransitionKind",
  "AudioTrackKind",
  "LayerKind",
  "PacingCategory",
  "EmphasisLevel",
  "TitleCardKind",
];

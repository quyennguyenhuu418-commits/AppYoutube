/**
 * Editorial Engine — RenderPlan consumer + offset/transition/frame-seek
 * utilities (PROMPT 10 §35, §47).
 *
 * This module is pure (no fs, no React, no network). It is consumed by
 * the new DocumentaryRenderPlan.tsx composition which is a thin wrapper
 * around `<RenderPlanConsumer>`.
 */
import type {
  AudioClipRef,
  AudioTrackLayer,
  EditorialScene,
  EditorialTimeline,
  RenderAudioClip,
  RenderLayer,
  RenderPlan,
  RenderScene,
  Transition,
  TransitionKindValue,
} from "./types";
import { TransitionKind } from "./types";

// ============================================================================
// Editorial placement (TS mirror of Python offsets.place_scenes)
// ============================================================================

export interface ScenePlacement {
  scene_id: string;
  order: number;
  master_start_sec: number;
  master_end_sec: number;
  duration_sec: number;
  source_scene_duration_sec: number;
  hold_before_sec: number;
  hold_after_sec: number;
  transition_in_duration_sec: number;
  transition_out_duration_sec: number;
  master_start_frame: number;
  duration_frames: number;
}

/**
 * Place EditorialScenes on a master timeline. Pure function.
 *
 * Algorithm:
 *   master_start[n] = master_start[n-1] + source_dur[n-1] - transition_out_dur[n-1]
 *   master_end[n]   = master_start[n]   + source_dur[n] + holds
 *   transition_out_dur[last] = 0
 */
export function placeScenes(
  timeline: EditorialTimeline,
  initialOffsetSec = 0,
): ScenePlacement[] {
  const sorted = [...timeline.scenes].sort((a, b) => a.order - b.order);
  if (sorted.length === 0) return [];
  const placements: ScenePlacement[] = [];
  let masterStart = initialOffsetSec;
  let prevSourceDur = 0;
  let prevTransOut = 0;
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0) {
      masterStart = masterStart + prevSourceDur - prevTransOut;
    }
    const scene = sorted[i]!;
    const holdBefore = scene.holds
      .filter((h) => h.target === "before")
      .reduce((s, h) => s + h.duration_sec, 0);
    const holdAfter = scene.holds
      .filter((h) => h.target === "after")
      .reduce((s, h) => s + h.duration_sec, 0);
    const sourceDur = scene.source_scene_duration_sec;
    const durationSec = sourceDur + holdBefore + holdAfter;
    const tInDur = scene.transition_in?.duration_sec ?? 0;
    const tOutDur = scene.transition_out?.duration_sec ?? 0;
    if (
      scene.transition_in &&
      scene.transition_in.kind === TransitionKind.CUT &&
      tInDur !== 0
    ) {
      throw new Error(
        `CUT transition_in for scene ${scene.scene_id} must be 0-duration`,
      );
    }
    if (sourceDur <= 0) {
      placements.push({
        scene_id: scene.scene_id,
        order: scene.order,
        master_start_sec: masterStart,
        master_end_sec: masterStart,
        duration_sec: 0,
        source_scene_duration_sec: 0,
        hold_before_sec: 0,
        hold_after_sec: 0,
        transition_in_duration_sec: tInDur,
        transition_out_duration_sec: tOutDur,
        master_start_frame: Math.max(0, Math.round(masterStart * timeline.fps)),
        duration_frames: 0,
      });
      prevSourceDur = 0;
      prevTransOut = 0;
      continue;
    }
    placements.push({
      scene_id: scene.scene_id,
      order: scene.order,
      master_start_sec: masterStart,
      master_end_sec: masterStart + durationSec,
      duration_sec: durationSec,
      source_scene_duration_sec: sourceDur,
      hold_before_sec: holdBefore,
      hold_after_sec: holdAfter,
      transition_in_duration_sec: tInDur,
      transition_out_duration_sec: tOutDur,
      master_start_frame: Math.max(0, Math.round(masterStart * timeline.fps)),
      duration_frames: Math.max(1, Math.round(durationSec * timeline.fps)),
    });
    prevSourceDur = sourceDur;
    prevTransOut = tOutDur;
  }
  // Sanity: each scene's overlap budget matches its transition_out duration.
  for (let i = 1; i < placements.length; i++) {
    const a = placements[i - 1]!;
    const b = placements[i]!;
    const overlap = a.master_end_sec - b.master_start_sec;
    if (overlap > a.transition_out_duration_sec + 1e-6) {
      throw new Error(
        `Scenes ${a.scene_id} and ${b.scene_id} overlap in master time beyond transition budget: ` +
          `overlap=${overlap.toFixed(4)}s budget=${a.transition_out_duration_sec.toFixed(4)}s`,
      );
    }
  }
  return placements;
}

// ============================================================================
// Transition validation (TS mirror of Python transitions module)
// ============================================================================

export function validateTransitionPair(
  prev: EditorialScene,
  nxt: EditorialScene,
): string[] {
  const errs: string[] = [];
  const out = prev.transition_out;
  const inn = nxt.transition_in;
  if (!out && !inn) return errs;
  if (out && inn) {
    if (out.kind !== inn.kind) {
      errs.push(
        `transition kind mismatch between ${prev.scene_id}.transition_out ` +
          `(${out.kind}) and ${nxt.scene_id}.transition_in (${inn.kind})`,
      );
    }
    if (Math.abs(out.duration_sec - inn.duration_sec) > 1e-6) {
      errs.push(
        `transition duration mismatch: ${prev.scene_id}.transition_out ` +
          `(${out.duration_sec}s) != ${nxt.scene_id}.transition_in ` +
          `(${inn.duration_sec}s)`,
      );
    }
  }
  if (
    out &&
    out.kind !== TransitionKind.CUT &&
    out.duration_sec > prev.source_scene_duration_sec
  ) {
    errs.push(
      `transition_out of scene ${prev.scene_id} (${out.duration_sec}s) ` +
        `exceeds scene duration (${prev.source_scene_duration_sec}s)`,
    );
  }
  if (
    inn &&
    inn.kind !== TransitionKind.CUT &&
    inn.duration_sec > nxt.source_scene_duration_sec
  ) {
    errs.push(
      `transition_in of scene ${nxt.scene_id} (${inn.duration_sec}s) ` +
        `exceeds scene duration (${nxt.source_scene_duration_sec}s)`,
    );
  }
  return errs;
}

export function validateAllTransitions(scenes: EditorialScene[]): string[] {
  const sorted = [...scenes].sort((a, b) => a.order - b.order);
  const errs: string[] = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    errs.push(...validateTransitionPair(sorted[i]!, sorted[i + 1]!));
  }
  return errs;
}

// ============================================================================
// Audio mix + ducking (TS mirror of Python audio module)
// ============================================================================

export interface NarrationActiveWindow {
  scene_id: string | null;
  clip_id: string;
  master_start_sec: number;
  master_end_sec: number;
}

export function collectNarrationWindows(
  clips: AudioClipRef[],
  clipMasterStarts: Record<string, number>,
  sceneIdByClipId: Record<string, string | null>,
): NarrationActiveWindow[] {
  const out: NarrationActiveWindow[] = [];
  for (const c of clips) {
    if (c.track_kind === "narration" || c.track_kind === "dialogue") {
      const start = clipMasterStarts[c.clip_id];
      if (start === undefined) continue;
      out.push({
        scene_id: sceneIdByClipId[c.clip_id] ?? null,
        clip_id: c.clip_id,
        master_start_sec: start,
        master_end_sec: start + c.duration_sec,
      });
    }
  }
  out.sort((a, b) =>
    a.master_start_sec !== b.master_start_sec
      ? a.master_start_sec - b.master_start_sec
      : a.master_end_sec - b.master_end_sec,
  );
  return out;
}

export function isInAnyWindow(
  t: number,
  windows: NarrationActiveWindow[],
): boolean {
  for (const w of windows) {
    if (w.master_start_sec <= t && t < w.master_end_sec) return true;
  }
  return false;
}

export interface DuckingResult {
  effective_gain_db: number;
  duck_target_track_ids: string[];
  duck_gain_db: number | null;
}

export function computeDucking(
  baseGainDb: number,
  trackKind: string,
  clipGainDb: number,
  narrationWindows: NarrationActiveWindow[],
  clipMasterStartSec: number,
  clipDurationSec: number,
  track: AudioTrackLayer | undefined,
  policyDuckDb: number,
): DuckingResult {
  if (trackKind === "narration" || trackKind === "dialogue") {
    return {
      effective_gain_db: baseGainDb + clipGainDb,
      duck_target_track_ids: [],
      duck_gain_db: null,
    };
  }
  const mStart = clipMasterStartSec;
  const mEnd = mStart + clipDurationSec;
  const overlaps = narrationWindows.some(
    (w) => !(mEnd <= w.master_start_sec || mStart >= w.master_end_sec),
  );
  if (!overlaps) {
    return {
      effective_gain_db: baseGainDb + clipGainDb,
      duck_target_track_ids: [],
      duck_gain_db: null,
    };
  }
  const duckDb =
    track && track.duck_gain_db !== null && track.duck_gain_db !== undefined
      ? track.duck_gain_db
      : policyDuckDb;
  return {
    effective_gain_db: baseGainDb + clipGainDb + duckDb,
    duck_target_track_ids: track
      ? track.duck_active_track_kinds.map((k) => k as string)
      : ["narration", "dialogue"],
    duck_gain_db: duckDb,
  };
}

// ============================================================================
// Quality score (TS mirror of Python compiler._build_quality_score)
// ============================================================================

export interface EditorialQualityScore {
  timeline_validity: number;
  scene_continuity: number;
  transition_consistency: number;
  audio_continuity: number;
  caption_alignment: number;
  animation_alignment: number;
  asset_integrity: number;
  pacing_consistency: number;
  reasons: string[];
  overall: number;
}

export function computeQualityScore(
  plan: RenderPlan,
  failures: string[],
  targetTotalDurationSec: number,
): EditorialQualityScore {
  const reasons: string[] = [];
  const timeline_validity = failures.length === 0 ? 1.0 : Math.max(0, 1.0 - 0.05 * failures.length);
  const orders = plan.scenes.map((s) => s.order);
  const scene_continuity =
    orders.length === 0
      ? 0.5
      : JSON.stringify(orders) === JSON.stringify([...orders].sort((a, b) => a - b))
        ? 1.0
        : 0.7;
  const pairCount = Math.max(0, plan.scenes.length - 1);
  let matched = 0;
  for (let i = 0; i < pairCount; i++) {
    const a = plan.scenes[i]!;
    const b = plan.scenes[i + 1]!;
    const out = a.transition_out;
    const inn = b.transition_in;
    if (!out && !inn) matched++;
    else if (
      out &&
      inn &&
      out.kind === inn.kind &&
      Math.abs(out.duration_sec - inn.duration_sec) < 1e-6
    )
      matched++;
  }
  const transition_consistency = pairCount === 0 ? 1.0 : matched / pairCount;
  const audio_continuity = 1.0;
  const capWith = plan.scenes.filter((s) => !!s.caption_track_id).length;
  const capTotal = plan.scenes.length || 1;
  const caption_alignment = capWith / capTotal;
  const animWith = plan.scenes.filter((s) => !!s.animation_plan_id).length;
  const animation_alignment = animWith / capTotal;
  const refFailures = failures.filter(
    (f) => f.includes("not in known") || f.includes("not found"),
  );
  const asset_integrity =
    refFailures.length === 0 ? 1.0 : Math.max(0, 1.0 - 0.1 * refFailures.length);
  let pacing_consistency = 1.0;
  if (targetTotalDurationSec > 0 && plan.scenes.length > 0) {
    const actual = plan.total_duration_sec;
    const ratio = actual / targetTotalDurationSec;
    pacing_consistency = Math.max(0, 1.0 - Math.abs(ratio - 1.0));
  }
  const axes = [
    timeline_validity, scene_continuity, transition_consistency,
    audio_continuity, caption_alignment, animation_alignment,
    asset_integrity, pacing_consistency,
  ];
  const overall = axes.reduce((s, v) => s + v, 0) / axes.length;
  return {
    timeline_validity, scene_continuity, transition_consistency,
    audio_continuity, caption_alignment, animation_alignment,
    asset_integrity, pacing_consistency, reasons, overall,
  };
}

// ============================================================================
// Pure frame-seek (PROMPT 10 §35)
// ============================================================================

export interface FrameSeekResult {
  frame: number;
  time_sec: number;
  active_scene_id: string | null;
  active_layer_ids: string[];
  active_audio_clip_ids: string[];
  active_title_card_ids: string[];
}

export function seekFrame(plan: RenderPlan, frame: number): FrameSeekResult {
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
  return {
    frame,
    time_sec,
    active_scene_id: active_scene?.scene_id ?? null,
    active_layer_ids: active_layers.map((l) => l.layer_id),
    active_audio_clip_ids: active_audio_clips.map((c) => c.clip_id),
    active_title_card_ids: active_title_cards.map((tc) => tc.card_id),
  };
}

export function sceneLocalTime(
  plan: RenderPlan,
  scene: RenderScene,
  frame: number,
): number {
  return Math.max(0, (frame - scene.master_start_frame) / plan.fps);
}

export function masterTimeFrame(
  plan: RenderPlan,
  scene: RenderScene,
  sceneLocalSec: number,
): number {
  return scene.master_start_frame + Math.round(sceneLocalSec * plan.fps);
}

export function linearGain(gain_db: number): number {
  if (gain_db <= -60) return 0;
  return Math.pow(10, gain_db / 20);
}

/**
 * Validate a transition pair (returns the validation errors, empty on OK).
 */
export type { Transition, TransitionKindValue, EditorialScene };

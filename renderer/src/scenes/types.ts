/**
 * Hand-written TypeScript mirror of `orchestrator/app/schemas/scene_definition.py`.
 *
 * THIS FILE IS A CONTRACT. If you change it, change the Python schema too
 * (and vice versa). The renderer is intentionally deterministic: it can
 * only consume these exact shapes, never arbitrary JSX/SVG from the LLM.
 */

export type SceneKind = "narration" | "diagram" | "title" | "transition";
export type Pose =
  | "stand"
  | "walk"
  | "point"
  | "think"
  | "celebrate"
  | "hide"
  | "run"
  | "sit";
export type AnimName =
  | "none"
  | "fade_in"
  | "slide_left"
  | "slide_right"
  | "pop"
  | "zoom_in";
export type EasingName = "none" | "ease_in" | "ease_out" | "ease_in_out";

/** Vetted prop kinds. The renderer has a small SVG library for each. */
export type PropKind =
  | "human_silhouette"
  | "cave"
  | "fire"
  | "tree_pine"
  | "snowflake"
  | "arrow"
  | "timeline"
  | "chart_axes"
  | "animal_mammoth"
  | "sun"
  | "mountain"
  | "question_mark";

export interface Meta {
  title: string;
  description?: string;
  fps: number;
  width: number;
  height: number;
  target_duration_sec: number;
}

export interface Style {
  primary_color: string;
  accent_color: string;
  background_color: string;
  text_color: string;
  font_family: string;
}

export interface Character {
  id: string;
  name: string;
  color: string;
  default_pose: Pose;
  description?: string;
}

export interface Environment {
  id: string;
  name: string;
  /** Path relative to the renderer workspace, e.g. `backgrounds/ice_age_plains.png`. */
  background_asset: string;
  mood: "calm" | "tense" | "triumphant" | "mysterious" | "warm";
}

export interface Camera {
  pan_x: number; // 0..1
  pan_y: number; // 0..1
  zoom: number;  // 0.5..3
  easing: EasingName;
}

export interface Actor {
  character_id: string;
  x: number;
  y: number;
  scale: number;
  rotation_deg: number;
  pose: Pose;
  enter_anim: AnimName;
  exit_anim: AnimName;
}

export interface Prop {
  kind: PropKind;
  x: number;
  y: number;
  scale: number;
  rotation_deg: number;
  enter_anim: AnimName;
}

export interface OverlayText {
  text: string;
  x: number;
  y: number;
  font_size: number;
  enter_at_sec: number;
  exit_at_sec: number | null;
  color: string;
}

export interface WordTimestamp {
  word: string;
  start_sec: number;
  end_sec: number;
}

export interface SfxCue {
  name: string;
  at_sec: number;
  volume: number;
}

export interface MusicCue {
  name: string;
  gain_db: number;
  fade_in_sec: number;
  fade_out_sec: number;
}

export interface Scene {
  id: string;
  kind: SceneKind;
  start_sec: number;
  end_sec: number;
  environment_id: string;
  narration_text: string;
  narration_words: WordTimestamp[];
  camera: Camera;
  actors: Actor[];
  props: Prop[];
  overlay_text: OverlayText[];
  sfx: SfxCue[];
  music: MusicCue | null;
}

export interface SceneDefinition {
  meta: Meta;
  style: Style;
  characters: Character[];
  environments: Environment[];
  scenes: Scene[];
}

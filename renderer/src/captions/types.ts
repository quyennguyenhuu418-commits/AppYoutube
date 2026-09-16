/**
 * Caption / Timing canonical schemas — TypeScript mirror (PROMPT 9).
 *
 * Hand-mirrored from `orchestrator/app/captions/schemas.py`. Field names
 * are byte-equivalent to the Pydantic-serialized JSON. Cross-runtime
 * contract tests verify parity (see `caption.contract.test.ts`).
 *
 * Design rules:
 * 1. NO timing invention in the renderer (PROMPT 9 §25, §26).
 * 2. No LLM at runtime (PROMPT 9 §51).
 * 3. Pure deterministic frame-state derivation (PROMPT 9 §26, §49).
 */

export type TimestampSource =
  | "provider_native"
  | "forced_alignment"
  | "uniform_alignment"
  | "unavailable";

export type CaptionVerticalAnchor =
  | "top"
  | "center"
  | "bottom"
  | "lower_third";

export type CaptionAnimationMode =
  | "none"
  | "fade"
  | "word_highlight"
  | "segment_pop";

export type CaptionBreakReason =
  | "punctuation"
  | "max_chars"
  | "max_words"
  | "max_duration"
  | "min_duration"
  | "phrase"
  | "speaker_change"
  | "narration_end"
  | "hard_split";

export interface CaptionStyle {
  version: string;
  style_id: string;
  name: string;

  font_family: string;
  font_size_px: number;        // reference size for 1920x1080
  font_weight: number;
  letter_spacing_px: number;

  max_lines: number;
  max_chars_per_line: number;
  line_spacing_px: number;
  alignment: "left" | "center" | "right" | string;

  text_color: string;
  highlight_color: string;
  background_color: string;
  shadow: boolean;

  safe_area_pct: number;
  vertical_safe_area_pct: number;
  vertical_anchor: CaptionVerticalAnchor;
  bottom_margin_pct: number;

  animation_mode: CaptionAnimationMode;
  highlight_hold_pad_ms: number;

  metadata: Record<string, unknown>;
}

export interface CaptionWord {
  word: string;
  start_sec: number;
  end_sec: number;
  confidence: number | null;
  line_index: number;
  position_in_line: number;
  narration_id: string;
  artifact_id: string;
  speech_timing_id: string;
}

export interface CaptionLine {
  line_index: number;
  text: string;
  word_count: number;
  char_count: number;
  break_reason: CaptionBreakReason;
  /** Indices into CaptionSegment.words[] in visual order. */
  word_indices: number[];
}

export interface CaptionSegment {
  version: string;
  segment_id: string;
  caption_id: string;
  scene_id: string;
  narration_id: string;
  start_sec: number;
  end_sec: number;
  text: string;
  words: CaptionWord[];
  lines: CaptionLine[];
  artifact_id: string;
  speech_timing_id: string;
  timestamp_source: TimestampSource;
  speaker_id: string;
  speaker_name: string;
  speaker_role: string;
  style_id: string;
  emphasis_words: number[];
  break_reason: CaptionBreakReason;
  warnings: string[];
}

export interface TimingQualityDimension {
  score: number;
  reasons: string[];
}

export interface TimingQualityScore {
  version: string;
  timestamp_validity: TimingQualityDimension;
  monotonicity: TimingQualityDimension;
  coverage: TimingQualityDimension;
  duration_alignment: TimingQualityDimension;
  source_quality: TimingQualityDimension;
  word_boundary_quality: TimingQualityDimension;
  segment_consistency: TimingQualityDimension;
  overall: number;
  notes: string[];
}

export interface CaptionTrack {
  version: string;
  track_id: string;
  caption_id: string;
  project_id: string;
  job_id: string;
  narration_timeline_id: string;
  scene_id: string;
  language: string;
  locale: string;
  fps: number;
  style: CaptionStyle;
  segments: CaptionSegment[];
  style_id: string;
  timestamp_source: TimestampSource;
  alignment_provider_id: string;
  quality: TimingQualityScore | null;
  scene_start_sec: number;
  scene_end_sec: number;
  warnings: string[];
  failures: string[];
  metadata: Record<string, unknown>;
  created_at: string;
}

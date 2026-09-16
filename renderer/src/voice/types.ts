/**
 * Voice / TTS / Audio canonical schemas (C-17).
 *
 * PROMPT 8 — mirror of `orchestrator/app/voice/schemas.py`.
 *
 * These types are hand-mirrored and must stay byte-equivalent to the
 * Python canonical models. Cross-runtime contract tests verify the
 * Python-serialized JSON is consumable here without field loss.
 *
 * IMPORTANT: Do not add provider-specific fields. Provider logic lives
 *   in the Python orchestrator. The renderer consumes canonical data.
 */

export type VoiceLifecycleStatus =
  | "draft"
  | "validated"
  | "approved"
  | "active"
  | "deprecated"
  | "archived";

export type VoiceGender = "female" | "male" | "neutral" | "unspecified";

export type VoiceStyle =
  | "narrator"
  | "documentary"
  | "conversational"
  | "energetic"
  | "calm"
  | "dramatic"
  | "news"
  | "unspecified";

export type TtsProviderName =
  | "mock"
  | "gtts"
  | "elevenlabs"
  | "cosyvoice"
  | "f5_tts"
  | "vi_f5_tts"
  | "local_gpu";

export type TtsEnvironment = "mock" | "development" | "production";

export type AudioArtifactStatus =
  | "pending"
  | "generated"
  | "validated"
  | "normalized"
  | "rejected"
  | "superseded";

export type TimestampSource =
  | "provider_native"
  | "forced_alignment"
  | "uniform_alignment"
  | "unavailable";

export type DurationReconciliationStrategy =
  | "follow_audio"
  | "follow_scene"
  | "pad_to_scene"
  | "fail"
  | "auto";

export type SpeakerRole =
  | "narrator"
  | "historian"
  | "character_a"
  | "character_b"
  | "unspecified";

export interface VoiceSettings {
  speaking_rate: number;          // 0.5..2.0
  pitch: number;                  // 0.5..2.0
  stability: number;              // 0..1
  similarity: number;             // 0..1
  style_exaggeration: number;     // 0..1
  default_volume_db: number;      // -60..12
  pronunciation_profile: string;
}

export interface PronunciationHint {
  hint_id: string;
  word: string;
  replacement?: string | null;
  phonetic?: string | null;
  alias?: string | null;
  emphasis_intensity: number;     // 0..1
  break_ms?: number | null;
}

export interface EmphasisHint {
  hint_id: string;
  text: string;
  intensity: number;              // 0..1
  pacing_change: number;          // -0.5..0.5
}

export interface VoiceDefinition {
  version: string;
  voice_id: string;
  name: string;
  language: string;
  locale: string;
  gender: VoiceGender;
  provider: TtsProviderName;
  provider_voice_id: string;
  style: VoiceStyle;
  settings: VoiceSettings;
  supported_languages: string[];
  pronunciation_hints: PronunciationHint[];
  status: VoiceLifecycleStatus;
  version_label: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface VoiceInstance {
  instance_id: string;
  voice_id: string;
  speaker_role: string;
  speaker_id: string;
  project_id: string;
  scene_id: string;
  settings_override: VoiceSettings | null;
  volume_override_db: number | null;
  pronunciation_hints_override: PronunciationHint[];
  metadata: Record<string, unknown>;
}

export interface VoiceRegistryEntry {
  voice_id: string;
  version_label: string;
  status: VoiceLifecycleStatus;
  usage_count: number;
  last_used_at: string | null;
  approved_by: string;
  approved_at: string | null;
  deprecated_reason: string;
}

export interface VoiceRegistry {
  project_id: string;
  updated_at: string;
  voices: VoiceRegistryEntry[];
  warnings: string[];
  failures: string[];
}

export interface NarrationUnit {
  narration_id: string;
  scene_id: string;
  beat_id: string;
  speaker_id: string;
  speaker_role: SpeakerRole;
  voice_id: string | null;
  text: string;
  language: string;
  locale: string;
  pronunciation_hints: PronunciationHint[];
  emphasis_hints: EmphasisHint[];
  pacing_intent: number;
  expected_duration_sec: number | null;
  version: string;
  source_lineage: Record<string, unknown>;
}

export interface NarrationScript {
  version: string;
  script_id: string;
  project_id: string;
  job_id: string;
  language: string;
  locale: string;
  units: NarrationUnit[];
  default_voice_id: string | null;
  version_label: string;
  source_lineage: Record<string, unknown>;
  warnings: string[];
  failures: string[];
  created_at: string;
}

export interface AudioArtifact {
  version: string;
  artifact_id: string;            // "{texthash}_{voiceconfighash}"
  narration_id: string;
  voice_id: string;
  provider: TtsProviderName;
  provider_version: string;
  source_text_hash: string;       // 16 hex chars
  voice_config_hash: string;      // 16 hex chars
  format: string;                 // wav | mp3
  sample_rate: number;            // 8000..48000
  channels: number;               // 1..2
  bits_per_sample: number;        // 8..32
  duration_sec: number;
  uri: string;
  absolute_path: string;
  checksum_sha256: string;
  byte_size: number;
  created_at: string;
  status: AudioArtifactStatus;
  fingerprint: string;
  metadata: Record<string, unknown>;
}

export interface WordTiming {
  word: string;
  start_sec: number;
  end_sec: number;
  confidence: number | null;
}

export interface SegmentTiming {
  text: string;
  start_sec: number;
  end_sec: number;
}

export interface SpeechTiming {
  version: string;
  timing_id: string;
  artifact_id: string;
  narration_id: string;
  language: string;
  timestamp_source: TimestampSource;
  words: WordTiming[];
  segments: SegmentTiming[];
  duration_sec: number;
  provider: TtsProviderName;
  metadata: Record<string, unknown>;
}

export interface NarrationTimelineEntry {
  narration_id: string;
  scene_id: string;
  artifact_id: string;
  timing_id: string;
  voice_id: string;
  speaker_id: string;
  audio_start_sec: number;
  audio_end_sec: number;
  scene_start_sec: number;
  scene_end_sec: number;
  pre_roll_sec: number;
  post_roll_sec: number;
  padding_sec: number;
  resolution_strategy: DurationReconciliationStrategy;
  metadata: Record<string, unknown>;
}

export interface NarrationTimeline {
  version: string;
  timeline_id: string;
  script_id: string;
  project_id: string;
  job_id: string;
  fps: number;
  total_duration_sec: number;
  entries: NarrationTimelineEntry[];
  default_padding_sec: number;
  default_pre_roll_sec: number;
  default_post_roll_sec: number;
  strategy: DurationReconciliationStrategy;
  warnings: string[];
  failures: string[];
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ProviderCapability {
  provider: TtsProviderName;
  supported_languages: string[];
  supports_word_timestamps: boolean;
  supports_pronunciation_hints: boolean;
  supports_emphasis_hints: boolean;
  supports_ssml: boolean;
  supports_voice_cloning: boolean;
  supports_streaming: boolean;
  output_formats: string[];
  max_text_length: number;
  requires_api_key: boolean;
  deterministic: boolean;
}

export interface VoiceResolution {
  resolution_id: string;
  narration_id: string;
  resolved_voice_id: string;
  resolved_provider: TtsProviderName;
  strategy: string;
  settings_used: VoiceSettings;
  events: string[];
  fallback_used: boolean;
  mock_used: boolean;
  warnings: string[];
  metadata: Record<string, unknown>;
}

export interface ResolutionEvent {
  event_id: string;
  narration_id: string;
  requested_voice_id: string | null;
  resolved_voice_id: string;
  strategy: string;
  provider: TtsProviderName;
  environment: TtsEnvironment;
  timestamp: string;
  detail: Record<string, unknown>;
}

/**
 * Cross-runtime guard: an AudioArtifact.artifact_id must be exactly
 * `{16 hex chars}_{16 hex chars}`. This is the runtime check the
 * renderer uses to detect malformed artifacts.
 */
export function isValidArtifactId(id: string): boolean {
  return /^[0-9a-f]{16}_[0-9a-f]{16}$/.test(id);
}

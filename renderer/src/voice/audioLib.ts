/**
 * AudioLibrary — canonical artifact-ID resolution (PROMPT 8 §36).
 *
 * Per PROMPT 8:
 *   "AudioLibrary must resolve:
 *      artifact_id → approved artifact
 *    rather than:
 *      raw arbitrary filename → play
 *    Validate artifact metadata before playback."
 *
 * The renderer receives an array of `AudioArtifactSummary` objects
 * (subset of canonical fields). Each must be VALIDATED before the
 * audio library will resolve it. The library maps artifact_id →
 * approved local URI; consumers ask by artifact_id.
 */

import type { AudioArtifact, AudioArtifactStatus } from "./types";

/** Minimal artifact projection the renderer needs to map to local URIs. */
export interface AudioArtifactSummary {
  artifact_id: string;
  narration_id: string;
  voice_id: string;
  format: string;
  duration_sec: number;
  status: AudioArtifactStatus;
  /** Local filesystem path (or http(s) URL) of the resolved audio file. */
  uri: string;
}

/**
 * Canonical AudioLibrary — resolves artifact_id → URI.
 *
 * Validation:
 * - artifact_id must match the canonical "{16 hex}_{16 hex}" pattern.
 * - status must be VALIDATED (or NORMALIZED for advanced pipelines).
 * - format must be supported.
 * - duration_sec must be > 0.
 *
 * Unapproved / corrupt artifacts are NOT exposed via `resolve()`.
 */
export class CanonicalAudioLibrary {
  private readonly artifacts: Map<string, AudioArtifactSummary>;

  constructor(artifacts: AudioArtifactSummary[]) {
    this.artifacts = new Map();
    for (const a of artifacts) {
      if (!this._isAcceptable(a)) continue;
      this.artifacts.set(a.artifact_id, a);
    }
  }

  /** Lookup by canonical artifact_id. Returns null if missing/unapproved. */
  resolve(artifactId: string): string | null {
    const a = this.artifacts.get(artifactId);
    return a ? a.uri : null;
  }

  /** Lookup full artifact summary by canonical artifact_id. */
  getArtifact(artifactId: string): AudioArtifactSummary | null {
    return this.artifacts.get(artifactId) ?? null;
  }

  /** All approved artifact IDs. */
  approvedIds(): string[] {
    return Array.from(this.artifacts.keys());
  }

  /** Total approved count. */
  size(): number {
    return this.artifacts.size;
  }

  /**
   * Build an instance from the canonical AudioArtifact objects
   * (after the renderer has stripped down to summary fields).
   */
  static fromCanonical(artifacts: AudioArtifact[]): CanonicalAudioLibrary {
    const summaries: AudioArtifactSummary[] = artifacts.map((a) => ({
      artifact_id: a.artifact_id,
      narration_id: a.narration_id,
      voice_id: a.voice_id,
      format: a.format,
      duration_sec: a.duration_sec,
      status: a.status,
      uri: a.uri || a.absolute_path,
    }));
    return new CanonicalAudioLibrary(summaries);
  }

  /**
   * Permissive factory for summaries that don't match the canonical
   * 32-hex ID pattern. Used by PROMPT 11 §11 to play real voice
   * artifacts whose `artifact_id` is a counter-style ID (e.g. `n_0001`).
   * Strict validation still applies to: status, uri, duration, format.
   */
  static fromSummaries(summaries: AudioArtifactSummary[]): CanonicalAudioLibrary {
    const lib = Object.create(CanonicalAudioLibrary.prototype) as CanonicalAudioLibrary;
    (lib as unknown as { artifacts: Map<string, AudioArtifactSummary> }).artifacts = new Map();
    for (const a of summaries) {
      if (!lib._isAcceptablePermissive(a)) continue;
      (lib as unknown as { artifacts: Map<string, AudioArtifactSummary> }).artifacts.set(
        a.artifact_id,
        a,
      );
    }
    return lib;
  }

  private _isAcceptable(a: AudioArtifactSummary): boolean {
    if (!/^[0-9a-f]{16}_[0-9a-f]{16}$/.test(a.artifact_id)) return false;
    return this._isAcceptablePermissive(a);
  }

  /**
   * Strict checks that don't depend on the canonical ID pattern
   * (status, uri, duration, format). Used by `fromSummaries` for
   * PROMPT 11 real-voice audio playback.
   */
  private _isAcceptablePermissive(a: AudioArtifactSummary): boolean {
    if (a.status !== "validated" && a.status !== "normalized") return false;
    if (!a.uri || a.uri.length === 0) return false;
    if (a.duration_sec <= 0) return false;
    if (!["wav", "mp3"].includes(a.format.toLowerCase())) return false;
    return true;
  }
}

/**
 * Convenience factory for a null library (no audio).
 * The renderer can fall back to this when no approved artifacts exist.
 */
export function NULL_AUDIO_LIBRARY(): CanonicalAudioLibrary {
  return new CanonicalAudioLibrary([]);
}

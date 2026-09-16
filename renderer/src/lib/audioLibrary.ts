/**
 * Filesystem-based AudioLibrary — Node.js CLI side ONLY.
 *
 * This file uses node:fs/node:path and MUST NOT be imported by any
 * webpack-bundled composition. Only `render_cli.tsx` should import it.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import type { AudioArtifactSummary } from "../voice/audioLib";
import type { AudioArtifact } from "../voice/types";
import type { AudioLibrary } from "../components/AudioCue";

/**
 * Build a name-based AudioLibrary that resolves audio names against a
 * directory. Missing files return null (no silent substitution).
 */
export function buildAudioLibrary(audioDir: string | null): AudioLibrary {
  if (!audioDir || !fs.existsSync(audioDir)) {
    return {
      resolveSfx: () => null,
      resolveMusic: () => null,
    };
  }

  const cache: Record<string, string | null> = {};

  function resolveByExt(name: string): string | null {
    if (name in cache) return cache[name]!;
    for (const ext of [".mp3", ".wav", ".ogg", ".m4a"]) {
      const candidate = path.join(audioDir!, `${name}${ext}`);
      if (fs.existsSync(candidate)) {
        cache[name] = candidate;
        return candidate;
      }
    }
    cache[name] = null;
    return null;
  }

  return {
    resolveSfx: resolveByExt,
    resolveMusic: resolveByExt,
  };
}

/**
 * PROMPT 8 — canonical AudioArtifact resolution.
 *
 * Given a list of canonical AudioArtifacts, resolve each one's
 * `uri`/`absolute_path` against the job directory and return the
 * approved (validated/normalized) artifacts as AudioArtifactSummary
 * objects ready to pass to the renderer.
 *
 * Rejected / non-canonical artifacts are filtered out.
 */
export function buildCanonicalArtifactSummaries(
  artifacts: AudioArtifact[],
  jobDir: string,
): Array<{
  artifact_id: string;
  narration_id: string;
  voice_id: string;
  format: string;
  duration_sec: number;
  status: string;
  uri: string;
}> {
  const out: Array<{
    artifact_id: string;
    narration_id: string;
    voice_id: string;
    format: string;
    duration_sec: number;
    status: string;
    uri: string;
  }> = [];
  for (const a of artifacts) {
    if (a.status !== "validated" && a.status !== "normalized") continue;
    if (!/^[0-9a-f]{16}_[0-9a-f]{16}$/.test(a.artifact_id)) continue;
    // Resolve uri to an absolute file path.
    const abs = a.absolute_path || path.join(jobDir, a.uri);
    if (!fs.existsSync(abs)) continue;
    out.push({
      artifact_id: a.artifact_id,
      narration_id: a.narration_id,
      voice_id: a.voice_id,
      format: a.format,
      duration_sec: a.duration_sec,
      status: a.status,
      uri: abs,
    });
  }
  return out;
}

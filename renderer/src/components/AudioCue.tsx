/**
 * AudioCue — render scene-level SFX, music, AND canonical narration audio.
 *
 * PROMPT 7 §23 + §24: Wire Scene.sfx[] and Scene.music to Remotion audio.
 * PROMPT 8 §35–§36: Wire AudioArtifact (canonical) to AudioCue via the
 *   canonical `CanonicalAudioLibrary`. No silent substitution.
 *
 * Deterministic volume, timing, offsets. No silent substitution.
 *
 * This component is fs-free: it accepts the audio library as a prop
 * (the CLI side resolves paths from disk).
 */
import React from "react";
import { Audio, Sequence } from "remotion";

import type { AudioArtifactSummary } from "../voice/audioLib";
import { CanonicalAudioLibrary, NULL_AUDIO_LIBRARY } from "../voice/audioLib";
import type { Scene, SceneDefinition } from "../scenes/types";

/**
 * Legacy AudioLibrary interface — name → file path resolution for sfx/music.
 * The CLI side provides this; here we never touch the filesystem.
 */
export interface AudioLibrary {
  /** Resolve a sound effect name to an absolute file path (or null if missing). */
  resolveSfx(name: string): string | null;
  /** Resolve a music name to an absolute file path (or null if missing). */
  resolveMusic(name: string): string | null;
}

/** Backwards-compat null audio library (returns null for everything). */
export const NULL_AUDIO_LIB: AudioLibrary = {
  resolveSfx: () => null,
  resolveMusic: () => null,
};

interface Props {
  scene: Scene;
  sceneStartFrame: number;
  fps: number;
  audioLib: AudioLibrary | null;
  /**
   * PROMPT 8: per-narration artifact summaries keyed by narration_id.
   * If provided, the cue can resolve canonical artifact IDs.
   */
  narrationArtifacts?: AudioArtifactSummary[] | null;
  /**
   * Per-scene narration artifact_id (set by the renderer when wiring
   * NarrationTimeline entries to scenes).
   */
  sceneNarrationArtifactId?: string | null;
}

/**
 * SceneAudio — per-scene audio wiring: sfx + music + canonical narration.
 */
export const SceneAudio: React.FC<Props> = ({
  scene,
  sceneStartFrame,
  fps,
  audioLib,
  narrationArtifacts,
  sceneNarrationArtifactId,
}) => {
  const lib = audioLib ?? NULL_AUDIO_LIB;
  const canonicalLib = narrationArtifacts
    ? new CanonicalAudioLibrary(narrationArtifacts)
    : NULL_AUDIO_LIBRARY();
  return (
    <>
      {scene.sfx.map((cue, i) => {
        const src = lib.resolveSfx(cue.name);
        if (!src) return null; // explicit: no silent substitution
        const startFrame = sceneStartFrame + Math.round(cue.at_sec * fps);
        return (
          <Sequence key={`sfx-${cue.name}-${i}`} from={startFrame}>
            <Audio src={src} volume={cue.volume} />
          </Sequence>
        );
      })}
      {scene.music && (() => {
        const src = lib.resolveMusic(scene.music.name);
        if (!src) return null;
        // Apply gain_db → linear volume (gain_db = 20*log10(vol)).
        const linearVol = scene.music.gain_db <= -60
          ? 0
          : Math.pow(10, scene.music.gain_db / 20);
        return (
          <Sequence
            key={`music-${scene.music.name}`}
            from={sceneStartFrame}
          >
            <Audio src={src} volume={linearVol} />
          </Sequence>
        );
      })()}
      {sceneNarrationArtifactId && (() => {
        const uri = canonicalLib.resolve(sceneNarrationArtifactId);
        if (!uri) return null; // unapproved / missing — no silent substitution
        return (
          <Sequence
            key={`narration-${sceneNarrationArtifactId}`}
            from={sceneStartFrame}
          >
            <Audio src={uri} volume={1} />
          </Sequence>
        );
      })()}
    </>
  );
};

/**
 * Top-level audio wiring: per-scene sfx/music + track-level narration.
 * fs-free.
 */
interface DocumentaryAudioProps {
  sd: SceneDefinition;
  audioSrc: string | null;
  audioLib: AudioLibrary | null;
  /** PROMPT 8: canonical narration artifact summaries. */
  narrationArtifacts?: AudioArtifactSummary[] | null;
  /** PROMPT 8: scene_id → artifact_id map (derived from NarrationTimeline). */
  sceneNarrationArtifactMap?: Record<string, string> | null;
}

export const DocumentaryAudio: React.FC<DocumentaryAudioProps> = ({
  sd,
  audioSrc,
  audioLib,
  narrationArtifacts,
  sceneNarrationArtifactMap,
}) => {
  const { meta } = sd;
  return (
    <>
      {sd.scenes.map((scene) => {
        const startFrame = Math.round(scene.start_sec * meta.fps);
        const sceneNarrationArtifactId =
          sceneNarrationArtifactMap?.[scene.id] ?? null;
        return (
          <SceneAudio
            key={`audio-${scene.id}`}
            scene={scene}
            sceneStartFrame={startFrame}
            fps={meta.fps}
            audioLib={audioLib}
            narrationArtifacts={narrationArtifacts}
            sceneNarrationArtifactId={sceneNarrationArtifactId}
          />
        );
      })}
      {audioSrc && <Audio src={audioSrc} startFrom={0} volume={1} />}
    </>
  );
};

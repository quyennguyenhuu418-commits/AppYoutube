/**
 * Main documentary composition.
 *
 * PROMPT 7 §20 (L-021 resolution): Rewritten to consume the fs-free
 * asset adapter path. The CLI (`src/render_cli.tsx`) loads the
 * SceneDefinition and AssetSystemPackage from disk, builds the
 * AssetAdapter in the Node-side loader, and passes it as a prop.
 *
 * For studio preview (`Root.tsx`), the demo SceneDefinition is used
 * without an asset adapter.
 *
 * PROMPT 7 §23 (C-004 resolution): Scene.sfx and Scene.music are wired
 * to Remotion <Audio> via DocumentaryAudio. No silent substitution.
 *
 * PROMPT 8 §35: NarrationArtifacts (canonical AudioArtifact summaries)
 * + sceneNarrationArtifactMap (scene_id → artifact_id) flow into
 * DocumentaryAudio so canonical narration audio plays.
 *
 * Note: Remotion serializes inputProps as JSON, so we accept the
 * underlying AssetPackageSummary (plain data) and reconstruct the
 * adapter inside the bundle via loadAssetAdapter().
 */
import React from "react";
import { AbsoluteFill, Sequence } from "remotion";

import { AnimationDriver } from "../components/AnimationDriver";
import { DocumentaryAudio, type AudioLibrary } from "../components/AudioCue";
import { loadAssetAdapter, type AssetPackageSummary } from "../lib/assetAdapter";
import type { AnimationPlan } from "../animation/runtime";
import type { SceneDefinition } from "../scenes/types";
import type { AudioArtifactSummary } from "../voice/audioLib";

interface Props {
  sceneDefinition: SceneDefinition;
  audioSrc: string | null;
  /** Total narration duration in seconds (for the audio track length). */
  narrationDurationSec: number;
  /** Optional: per-scene animation plans indexed by scene_id. */
  animationPlans?: Record<string, AnimationPlan> | null;
  /** Optional: asset package data; adapter is reconstructed from it. */
  assetPackage?: AssetPackageSummary | null;
  /** Optional: audio library for sfx/music (CLI-side resolves paths). */
  audioLib?: AudioLibrary | null;
  /** PROMPT 8: canonical narration artifact summaries. */
  narrationArtifacts?: AudioArtifactSummary[] | null;
  /** PROMPT 8: scene_id → artifact_id map (from NarrationTimeline). */
  sceneNarrationArtifactMap?: Record<string, string> | null;
}

export const Documentary: React.FC<Props> = ({
  sceneDefinition,
  audioSrc,
  narrationDurationSec,
  animationPlans,
  assetPackage,
  audioLib,
  narrationArtifacts,
  sceneNarrationArtifactMap,
}) => {
  const { meta } = sceneDefinition;
  // Reconstruct adapter inside the bundle (fs-free).
  const adapter = loadAssetAdapter(sceneDefinition, assetPackage ?? null);

  return (
    <AbsoluteFill style={{ backgroundColor: meta ? "#000" : "#000" }}>
      {sceneDefinition.scenes.map((scene) => {
        const startFrame = Math.round(scene.start_sec * meta.fps);
        const durationFrames = Math.max(
          1,
          Math.round((scene.end_sec - scene.start_sec) * meta.fps),
        );
        const plan = animationPlans?.[scene.id] ?? null;
        return (
          <Sequence
            key={scene.id}
            from={startFrame}
            durationInFrames={durationFrames}
            name={scene.id}
          >
            <AnimationDriver
              scene={scene}
              sd={sceneDefinition}
              plan={plan}
              adapter={adapter}
              durationInFrames={durationFrames}
              fps={meta.fps}
            />
          </Sequence>
        );
      })}

      <DocumentaryAudio
        sd={sceneDefinition}
        audioSrc={audioSrc}
        audioLib={audioLib ?? null}
        narrationArtifacts={narrationArtifacts ?? null}
        sceneNarrationArtifactMap={sceneNarrationArtifactMap ?? null}
      />
    </AbsoluteFill>
  );
};

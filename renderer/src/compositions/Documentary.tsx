/**
 * Main documentary composition.
 *
 * Receives the SceneDefinition as a Remotion `props` object so the studio
 * can preview it. In production the CLI (`src/index.ts`) loads the JSON
 * from disk and passes it through.
 */
import React from "react";
import { AbsoluteFill, Audio, Sequence } from "remotion";

import type { SceneDefinition } from "../scenes/types";
import { SceneRenderer } from "../scenes/SceneRenderer";

interface Props {
  sceneDefinition: SceneDefinition;
  audioSrc: string | null;
  /** Total narration duration in seconds (for the audio track length). */
  narrationDurationSec: number;
}

export const Documentary: React.FC<Props> = ({
  sceneDefinition,
  audioSrc,
  narrationDurationSec,
}) => {
  const { meta } = sceneDefinition;

  return (
    <AbsoluteFill style={{ backgroundColor: meta ? "#000" : "#000" }}>
      {sceneDefinition.scenes.map((scene) => {
        const startFrame = Math.round(scene.start_sec * meta.fps);
        const durationFrames = Math.max(
          1,
          Math.round((scene.end_sec - scene.start_sec) * meta.fps),
        );
        return (
          <Sequence
            key={scene.id}
            from={startFrame}
            durationInFrames={durationFrames}
            name={scene.id}
          >
            <SceneRenderer
              scene={scene}
              sd={sceneDefinition}
              durationInFrames={durationFrames}
            />
          </Sequence>
        );
      })}

      {audioSrc && (
        <Audio
          src={audioSrc}
          startFrom={0}
          volume={1}
        />
      )}
    </AbsoluteFill>
  );
};

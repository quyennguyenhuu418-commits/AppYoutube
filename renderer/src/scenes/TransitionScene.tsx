import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";

import type { Scene, SceneDefinition } from "./types";

interface Props {
  scene: Scene;
  sd: SceneDefinition;
}

/**
 * A simple cross-fade transition. Renders a color overlay that fades in
 * then out across the scene duration. Used between two environments.
 */
export const TransitionScene: React.FC<Props> = ({ scene, sd }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneDurFrames = Math.max(1, Math.round((scene.end_sec - scene.start_sec) * fps));
  const t = frame / sceneDurFrames;
  const opacity = interpolate(t, [0, 0.5, 1], [0, 1, 0], { extrapolateRight: "clamp" });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: sd.style.background_color,
        opacity,
      }}
    />
  );
};

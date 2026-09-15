/**
 * Renders a single scene. Switches on `scene.kind`.
 */
import React from "react";
import { AbsoluteFill } from "remotion";

import { Camera } from "../components/Camera";
import type { Scene, SceneDefinition } from "./types";
import { DiagramScene } from "./DiagramScene";
import { NarrationScene } from "./NarrationScene";
import { TitleScene } from "./TitleScene";
import { TransitionScene } from "./TransitionScene";

interface Props {
  scene: Scene;
  sd: SceneDefinition;
  durationInFrames: number;
}

export const SceneRenderer: React.FC<Props> = ({ scene, sd, durationInFrames }) => {
  // Look up the environment for background fill.
  const env = sd.environments.find((e) => e.id === scene.environment_id);
  const backgroundStyle: React.CSSProperties = {
    backgroundColor: sd.style.background_color,
    backgroundImage: env?.background_asset ? `url(/${env.background_asset})` : undefined,
    backgroundSize: "cover",
    backgroundPosition: "center",
  };

  let inner: React.ReactNode;
  switch (scene.kind) {
    case "narration":
      inner = <NarrationScene scene={scene} sd={sd} />;
      break;
    case "diagram":
      inner = <DiagramScene scene={scene} sd={sd} />;
      break;
    case "title":
      inner = <TitleScene scene={scene} sd={sd} />;
      break;
    case "transition":
      inner = <TransitionScene scene={scene} sd={sd} />;
      break;
    default:
      inner = null;
  }

  return (
    <AbsoluteFill style={backgroundStyle}>
      <Camera camera={scene.camera} durationInFrames={durationInFrames}>
        {inner}
      </Camera>
    </AbsoluteFill>
  );
};

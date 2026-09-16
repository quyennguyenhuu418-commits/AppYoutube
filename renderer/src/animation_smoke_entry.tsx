/**
 * Minimal Remotion bundle entrypoint for the animation smoke test.
 *
 * This file is fs-free (uses no node:* APIs) so it can be safely bundled
 * by webpack. Composition wires in the Documentary with AnimationDriver.
 */
import React from "react";
import { Composition, registerRoot } from "remotion";

import { Documentary } from "./compositions/Documentary";
import { loadAssetAdapter, type AssetPackageSummary } from "./lib/assetAdapter";
import type { AnimationPlan } from "./animation/runtime";
import type { SceneDefinition } from "./scenes/types";

interface Props {
  sceneDefinition: SceneDefinition;
  audioSrc: string | null;
  narrationDurationSec: number;
  animationPlans: Record<string, AnimationPlan> | null;
  assetPackage: AssetPackageSummary | null;
}

const SmokeRoot: React.FC = () => {
  // Remotion requires concrete fps/duration at composition level. We
  // accept these from the CLI's inputProps.
  const fps = 30;
  const width = 640;
  const height = 360;
  const durationSec = 6;
  const durationFrames = Math.round(durationSec * fps);

  return (
    <Composition
      id="AnimationSmoke"
      component={Documentary as unknown as React.FC<Record<string, unknown>>}
      durationInFrames={durationFrames}
      fps={fps}
      width={width}
      height={height}
      defaultProps={{
        sceneDefinition: undefined as unknown as SceneDefinition,
        audioSrc: null,
        narrationDurationSec: durationSec,
        animationPlans: null,
        assetPackage: null,
      } as unknown as Props}
    />
  );
};

registerRoot(SmokeRoot);

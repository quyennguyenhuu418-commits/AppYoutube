/**
 * Editorial smoke Remotion entry point (bundled by @remotion/bundler).
 *
 * This file is the entry point passed to `bundle()`. It registers the
 * `EditorialSmoke` Composition with the placeholder dimensions; the actual
 * `RenderPlan` is supplied at render time via `inputProps` and replaces
 * the placeholder dimensions through `selectComposition` + `renderMedia`.
 *
 * NOTE: This file MUST call `registerRoot` so Remotion's bundler accepts
 * it as the entry point.
 */
import React from "react";
import { Composition, registerRoot } from "remotion";

import { EditorialSmokeEntry } from "./editorial_smoke_entry";

const PLACEHOLDER_FPS = 30;
const PLACEHOLDER_WIDTH = 1280;
const PLACEHOLDER_HEIGHT = 720;
const PLACEHOLDER_DURATION_FRAMES = 60;

const EditorialSmokeRoot: React.FC = () => (
  <Composition
    id="EditorialSmoke"
    component={EditorialSmokeEntry as React.FC}
    durationInFrames={PLACEHOLDER_DURATION_FRAMES}
    fps={PLACEHOLDER_FPS}
    width={PLACEHOLDER_WIDTH}
    height={PLACEHOLDER_HEIGHT}
  />
);

registerRoot(EditorialSmokeRoot);

export { EditorialSmokeRoot };

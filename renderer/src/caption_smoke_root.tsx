/**
 * Remotion root registration shim for the caption smoke composition.
 *
 * Remotion requires `registerRoot` to be called at module load time.
 * This file exists separately so the composition (`caption_smoke_entry.tsx`)
 * can be imported and tested without side effects.
 *
 * IMPORTANT: We register a proper `<Composition id="CaptionSmoke" />` so
 * `selectComposition({ id: "CaptionSmoke", inputProps })` (called by
 * render_caption_smoke.tsx) can locate it and inject the sceneDefinition,
 * audioSrc, and captionTrack props at render time.
 *
 * Static defaults are used here. The renderer (`render_caption_smoke.tsx`)
 * overrides `durationInFrames` after selectComposition to match the actual
 * scene length, so the placeholder values below only need to be non-zero
 * and consistent with each other.
 */
import React from "react";
import { Composition, registerRoot } from "remotion";

import { CaptionSmokeComposition } from "./caption_smoke_entry";

const DEFAULT_FPS = 30;
const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 720;
const DEFAULT_DURATION_FRAMES = 150; // 5s @ 30fps placeholder

const CaptionSmokeRoot: React.FC = () => (
  <Composition
    id="CaptionSmoke"
    component={CaptionSmokeComposition as React.FC}
    durationInFrames={DEFAULT_DURATION_FRAMES}
    fps={DEFAULT_FPS}
    width={DEFAULT_WIDTH}
    height={DEFAULT_HEIGHT}
  />
);

registerRoot(CaptionSmokeRoot);

export { CaptionSmokeRoot };

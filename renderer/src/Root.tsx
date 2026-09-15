/**
 * Remotion studio root. Wires up the Documentary composition so it can be
 * previewed in `npm run dev`. The CLI in `src/index.ts` uses the same
 * composition for the actual render.
 */
import React from "react";
import { Composition } from "remotion";

import { Documentary } from "./compositions/Documentary";
import { loadSceneDefinition } from "./lib/loadScene";
import type { SceneDefinition } from "./scenes/types";

const DEFAULT_JOB_DIR = process.env.VIDEOAI_JOB_DIR ?? "../../workspace/demo";

// We load the demo at module init; for production the CLI bypasses this.
const sd: SceneDefinition = (() => {
  try {
    return loadSceneDefinition(DEFAULT_JOB_DIR);
  } catch {
    return {
      meta: { title: "Demo", fps: 30, width: 1920, height: 1080, target_duration_sec: 60 },
      style: { primary_color: "#FF6B35", accent_color: "#FFD166",
               background_color: "#1D1D2C", text_color: "#FFFFFF", font_family: "Inter" },
      characters: [],
      environments: [],
      scenes: [
        {
          id: "demo_title", kind: "title",
          start_sec: 0, end_sec: 60,
          environment_id: "x",
          narration_text: "",
          narration_words: [],
          camera: { pan_x: 0.5, pan_y: 0.5, zoom: 1, easing: "ease_in_out" },
          actors: [], props: [],
          overlay_text: [
            { text: "Demo composition", x: 0.5, y: 0.5, font_size: 96,
              enter_at_sec: 0.5, exit_at_sec: null, color: "#FFFFFF" },
          ],
          sfx: [], music: null,
        },
      ],
    };
  }
})();

export const RemotionRoot: React.FC = () => {
  const durationFrames = Math.round(sd.meta.target_duration_sec * sd.meta.fps);
  return (
    <Composition
      id="Documentary"
      component={Documentary}
      durationInFrames={durationFrames}
      fps={sd.meta.fps}
      width={sd.meta.width}
      height={sd.meta.height}
      defaultProps={{
        sceneDefinition: sd,
        audioSrc: null,
        narrationDurationSec: sd.meta.target_duration_sec,
      }}
    />
  );
};

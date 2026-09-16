/**
 * Minimal Remotion bundle entrypoint that avoids Node.js fs imports.
 *
 * This file is used only by the render smoke test to isolate
 * webpack plugin issues from the production renderer chain.
 * The main CLI entry point remains src/index.ts.
 */
import React from "react";
import { Composition, registerRoot } from "remotion";

import { Documentary } from "./compositions/Documentary";

interface SceneDefinition {
  meta: {
    title: string;
    fps: number;
    width: number;
    height: number;
    target_duration_sec: number;
  };
}

// Hardcoded minimal config for smoke testing
const sd: SceneDefinition = {
  meta: {
    title: "PROMPT 6.5 Smoke Test",
    fps: 30,
    width: 640,
    height: 360,
    target_duration_sec: 3.0,
  },
};

export const SmokeRoot: React.FC = () => {
  const durationFrames = Math.round(sd.meta.target_duration_sec * sd.meta.fps);
  return (
    <Composition
      id="Documentary"
      component={Documentary as React.FC}
      durationInFrames={durationFrames}
      fps={sd.meta.fps}
      width={sd.meta.width}
      height={sd.meta.height}
      defaultProps={{
        sceneDefinition: {
          meta: sd.meta,
          style: {
            primary_color: "#FF6B35",
            accent_color: "#FFD166",
            background_color: "#1D1D2C",
            text_color: "#FFFFFF",
            font_family: "Inter",
          },
          characters: [],
          environments: [],
          scenes: [
            {
              id: "smoke_title",
              kind: "title" as const,
              start_sec: 0,
              end_sec: 3,
              environment_id: "x",
              narration_text: "",
              narration_words: [],
              camera: { pan_x: 0.5, pan_y: 0.5, zoom: 1, easing: "ease_in_out" as const },
              actors: [],
              props: [],
              overlay_text: [
                { text: "PROMPT 6.5 Smoke", x: 0.5, y: 0.5, font_size: 64,
                  enter_at_sec: 0, exit_at_sec: null, color: "#FFFFFF" },
              ],
              sfx: [],
              music: null,
            },
          ],
        },
        audioSrc: null,
        narrationDurationSec: sd.meta.target_duration_sec,
      }}
    />
  );
};

registerRoot(SmokeRoot);

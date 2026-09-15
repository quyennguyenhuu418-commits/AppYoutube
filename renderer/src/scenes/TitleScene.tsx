import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";

import type { Scene, SceneDefinition } from "./types";

interface Props {
  scene: Scene;
  sd: SceneDefinition;
}

export const TitleScene: React.FC<Props> = ({ scene, sd }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneDurFrames = Math.max(1, Math.round((scene.end_sec - scene.start_sec) * fps));
  const t = interpolate(frame, [0, sceneDurFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });

  return (
    <>
      {scene.overlay_text.map((ot, i) => {
        const enter = Math.min(1, Math.max(0, (t - i * 0.1) * 2));
        return (
          <div
            key={`title-${i}`}
            style={{
              position: "absolute",
              left: `${ot.x * 100}%`,
              top: `${ot.y * 100}%`,
              transform: `translate(-50%, -50%) translateY(${(1 - enter) * 20}px)`,
              fontFamily: sd.style.font_family,
              fontSize: ot.font_size,
              fontWeight: 800,
              color: ot.color,
              textAlign: "center",
              opacity: enter,
              textShadow: "0 4px 24px rgba(0,0,0,0.6)",
              letterSpacing: "-0.02em",
              maxWidth: "80%",
            }}
          >
            {ot.text}
          </div>
        );
      })}
    </>
  );
};

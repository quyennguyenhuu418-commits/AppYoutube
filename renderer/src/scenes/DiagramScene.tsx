import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";

import { PropRenderer } from "../components/Props";
import { Camera } from "../components/Camera";
import type { Prop, Scene, SceneDefinition } from "./types";

interface Props {
  scene: Scene;
  sd: SceneDefinition;
}

export const DiagramScene: React.FC<Props> = ({ scene, sd }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneDurFrames = Math.max(1, Math.round((scene.end_sec - scene.start_sec) * fps));
  const t = interpolate(frame, [0, sceneDurFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });

  return (
    <>
      {scene.props.map((prop: Prop, i) => {
        const stagger = i * 0.15;
        const enter = Math.min(1, Math.max(0, t * 2 - stagger));
        return (
          <div
            key={`${prop.kind}-${i}`}
            style={{
              position: "absolute",
              left: `${prop.x * 100}%`,
              top: `${prop.y * 100}%`,
              transform: `translate(-50%, -50%) scale(${prop.scale * (0.7 + 0.3 * enter)}) rotate(${prop.rotation_deg}deg)`,
              opacity: enter,
              color: sd.style.text_color,
            }}
          >
            <PropRenderer kind={prop.kind} />
          </div>
        );
      })}
      {/* Diagram captions are just overlay_text in white. */}
      {scene.overlay_text.map((ot, i) => {
        const enter = Math.min(1, Math.max(0, (t - 0.2) * 1.5));
        return (
          <div
            key={`ot-${i}`}
            style={{
              position: "absolute",
              left: `${ot.x * 100}%`,
              top: `${ot.y * 100}%`,
              transform: "translate(-50%, -50%)",
              fontFamily: sd.style.font_family,
              fontSize: ot.font_size,
              fontWeight: 700,
              color: ot.color,
              textShadow: "0 2px 6px rgba(0,0,0,0.4)",
              opacity: enter,
            }}
          >
            {ot.text}
          </div>
        );
      })}
    </>
  );
};

/**
 * Camera wrapper — applies pan + zoom to its children.
 *
 * Pan values are 0..1 of the frame; zoom is 0.5..3 (1 = no zoom).
 * We wrap children in a `<div>` whose transform is animated by Remotion's
 * `interpolate` helpers.
 */
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";

import type { Camera, EasingName } from "../scenes/types";

interface Props {
  camera: Camera;
  durationInFrames: number;
  children: React.ReactNode;
}

const EASING: Record<EasingName, (t: number) => number> = {
  none: Easing.linear,
  ease_in: Easing.in(Easing.cubic),
  ease_out: Easing.out(Easing.cubic),
  ease_in_out: Easing.inOut(Easing.cubic),
};

export const Camera: React.FC<Props> = ({ camera, durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const t = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASING[camera.easing],
  });

  // Pan: 0..1 → translate so pan_x=0.5 puts the focal point at the center.
  const translateX = (camera.pan_x - 0.5) * width * (camera.zoom - 1);
  const translateY = (camera.pan_y - 0.5) * height * (camera.zoom - 1);

  // Smooth the zoom a touch across the scene so it feels alive.
  const easedZoom = 1 + (camera.zoom - 1) * (0.6 + 0.4 * t);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        transform: `translate(${translateX}px, ${translateY}px) scale(${easedZoom})`,
        transformOrigin: "center center",
        width: "100%",
        height: "100%",
      }}
    >
      {children}
    </div>
  );
};

/**
 * AnimatedCamera — Renders the camera transform based on the AnimationPlan.
 *
 * PROMPT 7 §12 + §17: Camera engine consumes Storyboard camera intent
 * deterministically. Camera state is always derived from plan.camera.
 *
 * This component is fs-free.
 */
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";

import type { AnimationPlan, Interpolation } from "../animation/runtime";

interface Props {
  plan: AnimationPlan;
  durationInFrames: number;
  children: React.ReactNode;
}

const EASING_FN: Record<Interpolation, (t: number) => number> = {
  linear: (t) => t,
  ease_in: (t) => t * t * t,
  ease_out: (t) => {
    const v = 1 - t;
    return 1 - v * v * v;
  },
  ease_in_out: (t) => {
    if (t < 0.5) return 4 * t * t * t;
    const v = 1 - t;
    return 1 - 4 * v * v * v;
  },
  hold: (_t) => 0, // not used for camera (no keyframes)
};

export const AnimatedCamera: React.FC<Props> = ({ plan, durationInFrames, children }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const totalFrames = Math.max(1, durationInFrames);
  const t = Math.min(1, frame / totalFrames);
  const easing = EASING_FN[plan.camera.easing] ?? EASING_FN.linear;

  const panX = interpolate(
    t,
    [0, 1],
    [plan.camera.start_pan_x, plan.camera.end_pan_x],
    { extrapolateRight: "clamp", easing },
  );
  const panY = interpolate(
    t,
    [0, 1],
    [plan.camera.start_pan_y, plan.camera.end_pan_y],
    { extrapolateRight: "clamp", easing },
  );
  const zoom = interpolate(
    t,
    [0, 1],
    [plan.camera.start_zoom, plan.camera.end_zoom],
    { extrapolateRight: "clamp", easing },
  );

  const translateX = (panX - 0.5) * width * (zoom - 1);
  const translateY = (panY - 0.5) * height * (zoom - 1);
  const easedZoom = 1 + (zoom - 1) * (0.6 + 0.4 * t);

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

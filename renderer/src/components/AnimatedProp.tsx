/**
 * AnimatedProp — Renders a Prop using the AnimationPlan.
 *
 * PROMPT 7 §11: Prop motion + character interaction (PropAnchor).
 * If the prop is attached to a character at the current time, the prop's
 * position is computed relative to the character's hand anchor.
 *
 * This component is fs-free.
 */
import React from "react";
import { useCurrentFrame } from "remotion";

import type { AnimationPlan } from "../animation/runtime";
import { computeFrameState } from "../animation/runtime";
import type { PropKind } from "../scenes/types";
import { PropRenderer } from "./Props";

interface Props {
  propId: string;
  propKind: PropKind;
  plan: AnimationPlan;
  baseX?: number;
  baseY?: number;
  scale?: number;
  /** Pixel offsets for character anchor in canvas coordinates. */
  anchorOffset?: { x: number; y: number };
}

export const AnimatedProp: React.FC<Props> = ({
  propId,
  propKind,
  plan,
  baseX = 0.5,
  baseY = 0.5,
  scale = 1.0,
  anchorOffset,
}) => {
  const frame = useCurrentFrame();
  const timeSec = frame / 30;
  const state = computeFrameState(plan, timeSec);

  const propState = state.props.find((p) => p.prop_id === propId);
  if (!propState) {
    return (
      <div
        style={{
          position: "absolute",
          left: `${baseX * 100}%`,
          top: `${baseY * 100}%`,
          transform: `translate(-50%, -50%) scale(${scale})`,
          color: "#FFFFFF",
        }}
      >
        <PropRenderer kind={propKind} />
      </div>
    );
  }

  // If attached to a character, follow that character's position + anchor offset.
  let x = propState.x;
  let y = propState.y;
  if (propState.attached_to_character_id) {
    const charState = state.characters.find(
      (c) => c.character_id === propState.attached_to_character_id,
    );
    if (charState) {
      x = charState.x;
      y = charState.y - 0.05; // hand anchor ≈ slightly above body center
    }
  }
  // Apply optional canvas-space anchor offset.
  if (anchorOffset) {
    // Convert pixel offsets to normalized (assume 1920x1080 canvas).
    x += anchorOffset.x / 1920;
    y += anchorOffset.y / 1080;
  }

  return (
    <div
      style={{
        position: "absolute",
        left: `${x * 100}%`,
        top: `${y * 100}%`,
        transform: `translate(-50%, -50%) scale(${propState.scale * scale}) rotate(${propState.rotation_deg}deg)`,
        opacity: propState.opacity,
        color: "#FFFFFF",
      }}
    >
      <PropRenderer kind={propKind} />
    </div>
  );
};

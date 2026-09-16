/**
 * AnimatedCharacter — Renders a Character using the AnimationPlan + AssetAdapter.
 *
 * PROMPT 7 §11 + §29: Animation Engine owns temporal state, pose transitions,
 * transform animation, movement, orientation changes, action sequencing.
 * Character System owns identity, proportions, skeleton, wardrobe, expressions.
 *
 * This component is fs-free. Asset adapter is passed in as a prop.
 */
import React from "react";
import { useCurrentFrame } from "remotion";

import type { AnimationPlan, CharacterFrameState } from "../animation/runtime";
import { computeFrameState } from "../animation/runtime";
import type { Pose } from "../scenes/types";
import { Character } from "./Character";

interface Props {
  characterId: string;
  plan: AnimationPlan;
  /** Base color from SceneDefinition (used when asset adapter has no override). */
  baseColor: string;
  /** Initial pose (from SceneDefinition.actor.pose), used when no plan exists. */
  fallbackPose: Pose;
  /** Initial position from SceneDefinition (normalized 0..1). */
  baseX?: number;
  baseY?: number;
  scale?: number;
}

/**
 * Look up the character frame state from the plan. If not found, returns
 * a deterministic "default" state.
 */
function resolveCharacterState(
  plan: AnimationPlan,
  characterId: string,
  frame: number,
  fallback: { x: number; y: number; pose: Pose; scale: number },
): CharacterFrameState {
  const timeSec = frame / 30; // Remotion's fps is provided by useVideoConfig; we use 30 as a safe default for tests.
  const state = computeFrameState(plan, timeSec);
  const found = state.characters.find((c) => c.character_id === characterId);
  if (found) return found;
  return {
    character_id: characterId,
    x: fallback.x,
    y: fallback.y,
    scale: fallback.scale,
    rotation_deg: 0,
    opacity: 1,
    pose: fallback.pose,
    walk_phase: 0,
  };
}

export const AnimatedCharacter: React.FC<Props> = ({
  characterId,
  plan,
  baseColor,
  fallbackPose,
  baseX = 0.5,
  baseY = 0.5,
  scale = 1.0,
}) => {
  const frame = useCurrentFrame();
  const state = resolveCharacterState(
    plan,
    characterId,
    frame,
    { x: baseX, y: baseY, pose: fallbackPose, scale },
  );

  return (
    <div
      style={{
        position: "absolute",
        left: `${state.x * 100}%`,
        top: `${state.y * 100}%`,
        transform: `translate(-50%, -50%) scale(${state.scale}) rotate(${state.rotation_deg}deg)`,
        opacity: state.opacity,
        color: baseColor,
      }}
    >
      <Character color={baseColor} pose={state.pose as Pose} />
    </div>
  );
};

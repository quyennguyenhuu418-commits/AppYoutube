import React from "react";
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from "remotion";

import { Camera } from "../components/Camera";
import { Caption } from "../components/Caption";
import { Character } from "../components/Character";
import type { Actor, AnimName, Scene, SceneDefinition } from "./types";

interface Props {
  scene: Scene;
  sd: SceneDefinition;
}

const ENTER_EASINGS = {
  none: Easing.linear,
  fade_in: Easing.out(Easing.cubic),
  slide_left: Easing.out(Easing.cubic),
  slide_right: Easing.out(Easing.cubic),
  pop: Easing.out(Easing.back(1.4)),
  zoom_in: Easing.out(Easing.cubic),
} as const;

function enterOffset(anim: AnimName, t: number): { x: number; y: number; scale: number; opacity: number } {
  const k = Math.min(1, Math.max(0, t));
  switch (anim) {
    case "none":
      return { x: 0, y: 0, scale: 1, opacity: 1 };
    case "fade_in":
      return { x: 0, y: 0, scale: 1, opacity: k };
    case "slide_left":
      return { x: (1 - k) * -300, y: 0, scale: 1, opacity: k };
    case "slide_right":
      return { x: (1 - k) * 300, y: 0, scale: 1, opacity: k };
    case "pop":
      return { x: 0, y: 0, scale: 0.3 + 0.7 * k, opacity: k };
    case "zoom_in":
      return { x: 0, y: 0, scale: 0.5 + 0.5 * k, opacity: k };
  }
}

export const NarrationScene: React.FC<Props> = ({ scene, sd }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const sceneDurFrames = Math.max(1, Math.round((scene.end_sec - scene.start_sec) * fps));
  const enterT = interpolate(frame, [0, Math.min(20, sceneDurFrames / 2)], [0, 1], {
    extrapolateRight: "clamp",
    easing: ENTER_EASINGS[scene.actors[0]?.enter_anim ?? "fade_in"],
  });

  return (
    <>
      {scene.actors.map((actor: Actor, i) => {
        const char = sd.characters.find((c) => c.id === actor.character_id);
        if (!char) return null;
        const off = enterOffset(actor.enter_anim, enterT);
        // Slight per-actor stagger so entrances don't feel mechanical.
        const stagger = i * 0.05;
        const localT = Math.min(1, Math.max(0, enterT - stagger));
        const off2 = enterOffset(actor.enter_anim, localT);
        return (
          <div
            key={actor.character_id}
            style={{
              position: "absolute",
              left: `${actor.x * 100}%`,
              top: `${actor.y * 100}%`,
              transform: `translate(${off2.x}px, ${off2.y}px) scale(${actor.scale * off2.scale}) rotate(${actor.rotation_deg}deg)`,
              opacity: off2.opacity,
              color: char.color,
            }}
          >
            <Character color={char.color} pose={actor.pose} />
          </div>
        );
      })}
      <Caption
        text={scene.narration_text}
        words={scene.narration_words}
        sceneStartSec={scene.start_sec}
        color={sd.style.text_color}
        highlightColor={sd.style.accent_color}
      />
    </>
  );
};

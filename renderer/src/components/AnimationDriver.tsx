/**
 * AnimationDriver — orchestrates animated characters, props, camera per scene.
 *
 * PROMPT 7 §29: Reusable component that wires AnimatedCharacter, AnimatedProp,
 * AnimatedCamera together based on SceneDefinition + AnimationPlan + AssetAdapter.
 *
 * fs-free: all data is passed in as props.
 */
import React from "react";

import type { AnimationPlan } from "../animation/runtime";
import type { AssetAdapter } from "../lib/assetAdapter";
import type { SceneDefinition, Scene } from "../scenes/types";
import { AnimatedCamera } from "./AnimatedCamera";
import { AnimatedCharacter } from "./AnimatedCharacter";
import { AnimatedProp } from "./AnimatedProp";

interface Props {
  scene: Scene;
  sd: SceneDefinition;
  plan: AnimationPlan | null;
  adapter: AssetAdapter | null;
  durationInFrames: number;
  fps: number;
}

/**
 * Look up an Actor in SceneDefinition.
 */
function findActor(sd: SceneDefinition, scene: Scene, characterId: string) {
  return scene.actors.find((a) => a.character_id === characterId);
}

export const AnimationDriver: React.FC<Props> = ({
  scene,
  sd,
  plan,
  adapter,
  durationInFrames,
  fps,
}) => {
  const planToUse = plan ?? defaultPlan(scene, sd, fps);

  // Resolve environment mood → color (renderer_hints consumed).
  const env = sd.environments.find((e) => e.id === scene.environment_id);
  const moodColor = adapter && env ? adapter.getMoodColor(env.id) : null;
  const backgroundStyle: React.CSSProperties = {
    backgroundColor: moodColor ?? sd.style.background_color,
    backgroundImage: env?.background_asset ? `url(/${env.background_asset})` : undefined,
    backgroundSize: "cover",
    backgroundPosition: "center",
  };

  // Compute fps in seconds for runtime — runtime uses 30 fps by default
  // but we recompute here so AnimatedCharacter picks up the correct one.
  // The runtime is fps-agnostic (uses seconds).
  // For display: pass `durationInFrames` to AnimatedCamera.

  return (
    <div style={{ ...backgroundStyle, position: "absolute", inset: 0 }}>
      <AnimatedCamera plan={planToUse} durationInFrames={durationInFrames}>
        {/* Characters */}
        {scene.actors.map((actor) => {
          const char = sd.characters.find((c) => c.id === actor.character_id);
          if (!char) return null;
          return (
            <AnimatedCharacter
              key={actor.character_id}
              characterId={actor.character_id}
              plan={planToUse}
              baseColor={char.color}
              fallbackPose={actor.pose}
              baseX={actor.x}
              baseY={actor.y}
              scale={actor.scale}
            />
          );
        })}

        {/* Props */}
        {scene.props.map((prop, i) => (
          <AnimatedProp
            key={`${prop.kind}-${i}`}
            propId={prop.kind}
            propKind={prop.kind}
            plan={planToUse}
            baseX={prop.x}
            baseY={prop.y}
            scale={prop.scale}
          />
        ))}
      </AnimatedCamera>
    </div>
  );
};

/**
 * Build a deterministic default plan from a SceneDefinition when no plan
 * is provided. Keeps characters at their SceneDefinition positions and
 * uses the SceneDefinition's camera.
 */
function defaultPlan(
  scene: Scene,
  sd: SceneDefinition,
  fps: number,
): AnimationPlan {
  const durationSec = (scene.end_sec - scene.start_sec) || 1.0;
  return {
    metadata: {
      version: "1.0.0",
      plan_id: `default_${scene.id}`,
      scene_id: scene.id,
      job_id: "",
      duration_sec: durationSec,
      created_at: new Date(0).toISOString(), // deterministic
      source: "default",
    },
    duration_sec: durationSec,
    camera: {
      camera_id: "main",
      start_pan_x: scene.camera.pan_x,
      start_pan_y: scene.camera.pan_y,
      start_zoom: scene.camera.zoom,
      end_pan_x: scene.camera.pan_x,
      end_pan_y: scene.camera.pan_y,
      end_zoom: scene.camera.zoom,
      easing: "linear",
    },
    characters: scene.actors.map((actor) => ({
      character_id: actor.character_id,
      pose_sequence: [
        {
          start_sec: 0,
          end_sec: durationSec,
          action: "stand" as const,
          pose: actor.pose,
        },
      ],
      walk_cycle_params: null,
      motion_tracks: [],
    })),
    props: scene.props.map((prop, i) => ({
      prop_id: prop.kind,
      instance_id: String(i),
      motion_tracks: [],
      interactions: [],
    })),
    tracks: [],
    events: [],
    warnings: [],
    failures: [],
  };
}

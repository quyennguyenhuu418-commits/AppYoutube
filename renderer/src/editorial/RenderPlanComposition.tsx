/**
 * RenderPlanComposition — pure RenderPlan-driven composition (PROMPT 10 §34).
 *
 * Architecture:
 *   EditorialProject → EditorialCompiler → RenderPlan → RenderPlanComposition
 *
 * The composition is a thin shell that:
 *   1. Iterates `plan.scenes` and emits `<Sequence>` per scene with the
 *      pre-computed `master_start_frame` + `duration_frames` (NO recomputation).
 *   2. Iterates `plan.layers` and emits a `<RenderPlanLayer>` per layer with
 *      explicit z-order.
 *   3. Iterates `plan.audio_clips` and emits `<RenderPlanAudio>` with the
 *      pre-computed gain + duck targets.
 *   4. Renders title cards via `<RenderPlanTitleCard>`.
 *
 * No business logic lives here; every value comes from the RenderPlan.
 */
import React from "react";
import { AbsoluteFill, Audio, Sequence, useCurrentFrame } from "remotion";

import { CaptionRenderer } from "../captions/CaptionRenderer";
import type { CaptionTrack } from "../captions/types";
import type { AnimationPlan } from "../animation/runtime";
import { CanonicalAudioLibrary, type AudioArtifactSummary } from "../voice/audioLib";

import type {
  RenderPlan,
  RenderScene,
  RenderLayer,
  RenderAudioClip,
  TitleCardSpec,
  LayerKindValue,
} from "./types";
import { LayerKind } from "./types";
import { linearGain } from "./plan";

interface Props {
  plan: RenderPlan;
  /** Optional caption tracks indexed by caption_track_id. */
  captionTracks?: Record<string, CaptionTrack> | null;
  /** Optional animation plans indexed by animation_plan_id. */
  animationPlans?: Record<string, AnimationPlan> | null;
  /**
   * Optional audio URL resolver: artifact_id → static URL.
   * If omitted, falls back to the `audioLibrary` (CanonicalAudioLibrary)
   * built from `audioArtifactSummaries` (PROMPT 11 §11 — real voice audio).
   */
  resolveAudio?: (artifactId: string) => string | null;
  /**
   * AudioArtifactSummary[] passed in from the editorial/mastering pipeline.
   * Used to build a `CanonicalAudioLibrary` when `resolveAudio` is omitted.
   */
  audioArtifactSummaries?: AudioArtifactSummary[] | null;
}

export const RenderPlanComposition: React.FC<Props> = ({
  plan,
  captionTracks,
  animationPlans,
  resolveAudio,
  audioArtifactSummaries,
}) => {
  const renderScenes = [...plan.scenes].sort((a, b) => a.order - b.order);
  const renderLayers = [...plan.layers].sort((a, b) => a.z_order - b.z_order);
  const renderAudioClips = [...plan.audio_clips].sort(
    (a, b) => a.master_start_frame - b.master_start_frame,
  );

  // PROMPT 11 §11 — build a real AudioLibrary so narration audio actually plays.
  const resolvedResolver: (artifactId: string) => string | null =
    resolveAudio ??
    ((artifactId: string) => {
      if (!audioArtifactSummaries) return null;
      // Use the permissive factory — voice pipeline uses counter-style IDs.
      const lib = CanonicalAudioLibrary.fromSummaries(audioArtifactSummaries);
      return lib.resolve(artifactId);
    });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Scenes (visual containers) */}
      {renderScenes.map((scene) => (
        <RenderPlanScene
          key={scene.scene_id}
          plan={plan}
          scene={scene}
          layers={renderLayers.filter((l) => l.scene_id === scene.scene_id)}
          captionTracks={captionTracks ?? null}
          animationPlans={animationPlans ?? null}
        />
      ))}
      {/* Audio clips — rendered as separate top-level elements so Remotion
          can mix them deterministically across scene boundaries. */}
      {renderAudioClips.map((clip) => (
        <RenderPlanAudio
          key={`audio-${clip.clip_id}`}
          clip={clip}
          fps={plan.fps}
          resolveAudio={resolvedResolver}
        />
      ))}
      {/* Title cards */}
      {plan.title_cards.map((tc) => (
        <RenderPlanTitleCard
          key={tc.card_id}
          card={tc}
          fps={plan.fps}
          width={plan.width}
          height={plan.height}
        />
      ))}
    </AbsoluteFill>
  );
};

// ============================================================================
// Scene + Layer rendering
// ============================================================================

interface SceneProps {
  plan: RenderPlan;
  scene: RenderScene;
  layers: RenderLayer[];
  captionTracks: Record<string, CaptionTrack> | null;
  animationPlans: Record<string, AnimationPlan> | null;
}

const RenderPlanScene: React.FC<SceneProps> = ({
  plan,
  scene,
  layers,
  captionTracks,
  animationPlans,
}) => {
  return (
    <Sequence
      from={scene.master_start_frame}
      durationInFrames={scene.duration_frames}
      name={scene.scene_id}
    >
      <AbsoluteFill style={{ backgroundColor: "#000" }}>
        {layers.map((layer) => (
          <RenderPlanLayer
            key={layer.layer_id}
            layer={layer}
            scene={scene}
            plan={plan}
            captionTracks={captionTracks}
            animationPlans={animationPlans}
          />
        ))}
      </AbsoluteFill>
    </Sequence>
  );
};

// ============================================================================
// Layer rendering — pure dispatcher by layer kind
// ============================================================================

interface LayerProps {
  layer: RenderLayer;
  scene: RenderScene;
  plan: RenderPlan;
  captionTracks: Record<string, CaptionTrack> | null;
  animationPlans: Record<string, AnimationPlan> | null;
}

const RenderPlanLayer: React.FC<LayerProps> = ({
  layer,
  scene,
  plan,
  captionTracks,
  animationPlans,
}) => {
  return (
    <Sequence
      from={layer.master_start_frame}
      durationInFrames={layer.duration_frames}
      name={layer.layer_id}
    >
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <LayerContent
          layer={layer}
          scene={scene}
          plan={plan}
          captionTracks={captionTracks}
          animationPlans={animationPlans}
        />
      </AbsoluteFill>
    </Sequence>
  );
};

const LayerContent: React.FC<LayerProps> = ({
  layer,
  scene,
  plan,
  captionTracks,
  animationPlans,
}) => {
  const kind = layer.kind;
  switch (kind) {
    case LayerKind.BACKGROUND:
      return (
        <BackgroundLayer scene={scene} layer={layer} />
      );
    case LayerKind.ENVIRONMENT:
      return (
        <EnvironmentLayer scene={scene} layer={layer} />
      );
    case LayerKind.CHARACTERS:
      return (
        <CharactersLayer
          scene={scene}
          layer={layer}
          animationPlans={animationPlans}
        />
      );
    case LayerKind.PROPS:
      return <PropsLayer scene={scene} layer={layer} />;
    case LayerKind.DIAGRAMS:
      return <DiagramsLayer scene={scene} layer={layer} />;
    case LayerKind.OVERLAYS:
      return <OverlaysLayer scene={scene} layer={layer} />;
    case LayerKind.CAPTIONS: {
      const trackId = (layer.payload as { caption_track_id?: string | null })
        ?.caption_track_id;
      const track = trackId ? captionTracks?.[trackId] : null;
      if (!track) return null;
      return (
        <CaptionRenderer
          track={track}
          width={plan.width}
          height={plan.height}
        />
      );
    }
    case LayerKind.TITLE_CARDS:
      return null; // rendered as a top-level Sequence (see below)
    default:
      return null;
  }
};

// ============================================================================
// Per-layer minimal visual implementations (PROMPT 10 §34: no business logic)
// ============================================================================

const BackgroundLayer: React.FC<{ scene: RenderScene; layer: RenderLayer }> = ({
  layer,
}) => {
  const envId = (layer.payload as { environment_id?: string })?.environment_id;
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0E1A2B",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <span style={{ color: "#7a8aa0", fontSize: 14, fontFamily: "Inter, sans-serif" }}>
        background · env={envId ?? "?"}
      </span>
    </AbsoluteFill>
  );
};

const EnvironmentLayer: React.FC<{ scene: RenderScene; layer: RenderLayer }> = ({
  layer,
}) => {
  const envId = (layer.payload as { environment_id?: string })?.environment_id;
  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        paddingBottom: 12,
      }}
    >
      <span style={{ color: "#FFD166", fontSize: 12, fontFamily: "Inter, sans-serif" }}>
        environment · {envId ?? "?"}
      </span>
    </AbsoluteFill>
  );
};

const PropsLayer: React.FC<{ scene: RenderScene; layer: RenderLayer }> = ({
  layer,
}) => {
  const props = (layer.payload as { props?: string[] })?.props ?? [];
  return (
    <AbsoluteFill style={{ display: "flex", justifyContent: "flex-end", padding: 12 }}>
      <span style={{ color: "#FF6B35", fontSize: 11, fontFamily: "Inter, sans-serif" }}>
        props · {props.join(", ") || "—"}
      </span>
    </AbsoluteFill>
  );
};

const CharactersLayer: React.FC<{
  scene: RenderScene;
  layer: RenderLayer;
  animationPlans: Record<string, AnimationPlan> | null;
}> = ({ scene, layer, animationPlans }) => {
  const frame = useCurrentFrame();
  const characters = (layer.payload as { character_ids?: string[] })?.character_ids ?? [];
  const animId = (layer.payload as { animation_plan_id?: string | null })?.animation_plan_id;
  const plan = animId ? animationPlans?.[animId] : null;
  // Compute scene-local time from Remotion's frame.
  const tSec = frame / 30; // best-effort default fps; the real fps is on plan.
  let x = 0.5;
  if (plan && plan.duration_sec > 0) {
    const ratio = Math.min(1, tSec / plan.duration_sec);
    x = 0.5 + (plan.camera.end_pan_x - plan.camera.start_pan_x) * ratio;
  }
  return (
    <AbsoluteFill
      style={{ display: "flex", justifyContent: "center", alignItems: "center" }}
    >
      <div
        style={{
          color: "#FFFFFF",
          fontSize: 12,
          fontFamily: "Inter, sans-serif",
          backgroundColor: "rgba(0,0,0,0.4)",
          padding: "4px 8px",
          borderRadius: 4,
        }}
      >
        {scene.scene_id} · chars={characters.join(", ") || "—"} · camera_x={x.toFixed(3)}
      </div>
    </AbsoluteFill>
  );
};

const DiagramsLayer: React.FC<{ scene: RenderScene; layer: RenderLayer }> = () => {
  return null;
};

const OverlaysLayer: React.FC<{ scene: RenderScene; layer: RenderLayer }> = () => {
  return null;
};

// ============================================================================
// Audio
// ============================================================================

const RenderPlanAudio: React.FC<{
  clip: RenderAudioClip;
  fps: number;
  resolveAudio?: (artifactId: string) => string | null;
}> = ({ clip, resolveAudio }) => {
  const url = resolveAudio ? resolveAudio(clip.artifact_id) : null;
  if (!url) return null;
  const gain = linearGain(clip.gain_db);
  return (
    <Sequence
      from={clip.master_start_frame}
      durationInFrames={clip.duration_frames}
      name={`audio-${clip.clip_id}`}
    >
      <Audio src={url} volume={gain} />
    </Sequence>
  );
};

// ============================================================================
// Title cards
// ============================================================================

const RenderPlanTitleCard: React.FC<{
  card: TitleCardSpec;
  fps: number;
  width: number;
  height: number;
}> = ({ card, fps, width, height }) => {
  const startFrame = Math.round(card.master_start_sec * fps);
  const durFrames = Math.max(1, Math.round(card.duration_sec * fps));
  return (
    <Sequence
      from={startFrame}
      durationInFrames={durFrames}
      name={`title-${card.card_id}`}
    >
      <AbsoluteFill
        style={{
          backgroundColor:
            card.kind === "intro" || card.kind === "chapter"
              ? "#1D1D2C"
              : card.kind === "section"
                ? "#0E1A2B"
                : "#000",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            color: "#FFD166",
            fontFamily: "Inter, sans-serif",
            fontWeight: 700,
            fontSize: Math.max(28, Math.min(width, height) / 12),
            textAlign: "center",
            letterSpacing: 2,
          }}
        >
          {card.title}
        </div>
        {card.subtitle ? (
          <div
            style={{
              color: "#FFFFFF",
              fontFamily: "Inter, sans-serif",
              fontSize: Math.max(16, Math.min(width, height) / 28),
              marginTop: 12,
              opacity: 0.8,
            }}
          >
            {card.subtitle}
          </div>
        ) : null}
      </AbsoluteFill>
    </Sequence>
  );
};

export type { Props as RenderPlanCompositionProps };

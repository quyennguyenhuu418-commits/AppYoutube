/**
 * PROMPT 9 — Caption smoke composition.
 *
 * Reads `captionTrack` from inputProps, derives legacy `WordTimestamp[]`
 * from the canonical track, and feeds them to the existing `Caption.tsx`.
 * No timing is invented in this file — it is a pure adapter from the
 * canonical CaptionTrack JSON to the legacy caption component contract.
 */

import React from "react";
import { AbsoluteFill, Audio, Sequence, getInputProps, useCurrentFrame } from "remotion";

import type { SceneDefinition, WordTimestamp } from "./scenes/types";
import type { CaptionTrack } from "./captions/types";
import { toLegacyWordTimestamps } from "./captions/state";
import { Caption } from "./components/Caption";

/**
 * Pull props either from the React `props` argument (when the component is
 * invoked by the renderer with `inputProps`) or via `getInputProps()` as a
 * fallback (Remotion sometimes re-invokes the component without props).
 */
function resolveProps(p: Partial<Props> = {}): Props {
  const fallback = (getInputProps() ?? {}) as Partial<Props>;
  return { ...fallback, ...p };
}

interface Props {
  sceneDefinition?: SceneDefinition;
  audioSrc?: string | null;
  narrationDurationSec?: number;
  captionTrack?: CaptionTrack;
}

export const CaptionSmokeComposition: React.FC<Partial<Props>> = (rawProps) => {
  const { sceneDefinition, audioSrc, captionTrack } = resolveProps(rawProps);
  if (!sceneDefinition || !captionTrack) {
    return <AbsoluteFill style={{ backgroundColor: "#000" }} />;
  }
  const { meta } = sceneDefinition;
  const fps = meta.fps;
  const scene = sceneDefinition.scenes[0];

  // Derive legacy WordTimestamp[] from the canonical CaptionTrack.
  const words: WordTimestamp[] = toLegacyWordTimestamps(captionTrack);

  const Debug: React.FC = () => {
    const frame = useCurrentFrame();
    const t = scene ? scene.start_sec + frame / fps : frame / fps;
    return (
      <div
        style={{
          position: "absolute",
          top: 4,
          left: 4,
          color: "#FFD166",
          fontSize: 12,
          fontFamily: "Inter, sans-serif",
          fontWeight: 600,
          textShadow: "0 1px 2px rgba(0,0,0,0.8)",
        }}
      >
        frame={frame} t={t.toFixed(3)}s segs={captionTrack.segments.length}
      </div>
    );
  };

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {scene ? (
        <Sequence
          from={Math.round(scene.start_sec * fps)}
          durationInFrames={Math.max(
            1,
            Math.round((scene.end_sec - scene.start_sec) * fps),
          )}
          name={scene.id}
        >
          <Caption
            text={captionTrack.segments.map((s) => s.text).join(" ")}
            words={words}
            sceneStartSec={scene.start_sec}
            color={sceneDefinition.style?.text_color ?? "#FFFFFF"}
            highlightColor={sceneDefinition.style?.accent_color ?? "#FFD166"}
          />
        </Sequence>
      ) : null}
      {audioSrc ? (
        <Audio
          src={audioSrc}
          startFrom={Math.round(captionTrack.scene_start_sec * fps)}
        />
      ) : null}
      <Debug />
    </AbsoluteFill>
  );
};

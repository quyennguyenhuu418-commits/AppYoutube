/**
 * Word-by-word caption renderer.
 *
 * Highlights the currently-spoken word using the `narration_words` list
 * from the SceneDefinition. Words outside the list are dimmed.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";

import type { WordTimestamp } from "../scenes/types";

interface Props {
  text: string;
  words: WordTimestamp[];
  sceneStartSec: number;
  color?: string;
  highlightColor?: string;
  fontSize?: number;
}

export const Caption: React.FC<Props> = ({
  text,
  words,
  sceneStartSec,
  color = "#FFFFFF",
  highlightColor = "#FFD166",
  fontSize = 56,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentSec = sceneStartSec + frame / fps;

  // Build the highlighted display: split `text` into tokens that line up
  // with `words` as best we can. We split by whitespace and assume the
  // LLM/TTS gave us one word per token.
  const tokens = text.split(/\s+/).filter(Boolean);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 60,
        left: 0,
        right: 0,
        textAlign: "center",
        fontFamily: "Inter, sans-serif",
        fontSize,
        fontWeight: 600,
        textShadow: "0 2px 8px rgba(0,0,0,0.6)",
        padding: "0 5%",
      }}
    >
      {tokens.map((tok, i) => {
        const w = words[i];
        const active = w && currentSec >= w.start_sec && currentSec <= w.end_sec + 0.15;
        return (
          <span
            key={`${i}-${tok}`}
            style={{
              color: active ? highlightColor : color,
              marginRight: 12,
              transition: "color 80ms linear",
            }}
          >
            {tok}
          </span>
        );
      })}
    </div>
  );
};

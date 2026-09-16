/**
 * Canonical Remotion caption renderer (PROMPT 9 §25, §26, §52).
 *
 * Consumes a precompiled `CaptionTrack`. Does NOT inspect raw narration
 * text; does NOT call any LLM; does NOT use wall-clock or setInterval.
 *
 * Style is data-driven (PROMPT 9 §11). The renderer adapts layout to
 * the current video dimensions via safe-area percentages (PROMPT 9 §27,
 * §28). The same `CaptionTrack` works for 16:9, 9:16, and 1:1 — only
 * the `vertical_anchor` and safe-area math change.
 */

import React from "react";

import type {
  CaptionLine,
  CaptionSegment,
  CaptionStyle,
  CaptionTrack,
  CaptionWord,
} from "./types";
import {
  computeCaptionFrameState,
} from "./state";

interface Props {
  track: CaptionTrack;
  /** Override style (defaults to `track.style`). */
  style?: CaptionStyle;
  /** Optional 9:16 / Shorts preparation: explicit anchor override. */
  verticalAnchorOverride?: CaptionStyle["vertical_anchor"];
}

/**
 * Compute pixel layout from percentages. Pure.
 */
function resolveLayout(
  style: CaptionStyle,
  width: number,
  height: number,
): {
  left: number;
  right: number;
  top: number;
  bottom: number;
  anchorTop: number;
} {
  const safeLeft = style.safe_area_pct * width;
  const safeRight = width - safeLeft;
  const safeTop = style.vertical_safe_area_pct * height;
  const safeBottom = height - safeTop;
  const bottomMarginPx = style.bottom_margin_pct * height;

  let anchorTop: number;
  switch (style.vertical_anchor) {
    case "top":
      anchorTop = safeTop;
      break;
    case "center":
      anchorTop = (height - style.font_size_px * style.max_lines) / 2;
      break;
    case "bottom":
      anchorTop = safeBottom - bottomMarginPx
        - style.font_size_px * style.max_lines;
      break;
    case "lower_third":
    default:
      anchorTop = height - bottomMarginPx
        - style.font_size_px * style.max_lines;
      break;
  }

  return {
    left: safeLeft,
    right: safeRight,
    top: safeTop,
    bottom: safeBottom,
    anchorTop,
  };
}

/**
 * Render one word with the right visual treatment.
 */
function renderWord(
  word: CaptionWord,
  isActive: boolean,
  style: CaptionStyle,
): React.ReactElement {
  const color = isActive ? style.highlight_color : style.text_color;
  const shadow = style.shadow
    ? "0 2px 8px rgba(0,0,0,0.6)"
    : "none";
  return (
    <span
      key={`w-${word.start_sec}-${word.position_in_line}`}
      style={{
        color,
        textShadow: shadow,
        marginRight: 12,
        display: "inline-block",
      }}
    >
      {word.word}
    </span>
  );
}

function renderLine(
  line: CaptionLine,
  segment: CaptionSegment,
  activeWordIndex: number | null,
  style: CaptionStyle,
): React.ReactElement {
  return (
    <div
      key={`l-${line.line_index}`}
      style={{
        textAlign: style.alignment as "left" | "center" | "right" | "justify",
        fontSize: style.font_size_px,
        fontWeight: style.font_weight,
        fontFamily: style.font_family,
        letterSpacing: style.letter_spacing_px,
        lineHeight: 1.2,
        marginBottom: line.line_index === style.max_lines - 1 ? 0 : style.line_spacing_px,
      }}
    >
      {line.word_indices.map((wi) => {
        const w = segment.words[wi];
        if (!w) return null;
        const isActive = activeWordIndex === wi;
        return renderWord(w, isActive, style);
      })}
    </div>
  );
}

/**
 * The canonical caption component.
 */
export const CaptionRenderer: React.FC<Props & { width: number; height: number }> = ({
  track,
  style: styleOverride,
  verticalAnchorOverride,
  width,
  height,
}) => {
  // Apply vertical anchor override (used by 9:16 / Shorts later).
  const style: CaptionStyle = verticalAnchorOverride
    ? { ...(styleOverride ?? track.style), vertical_anchor: verticalAnchorOverride }
    : (styleOverride ?? track.style);

  const layout = resolveLayout(style, width, height);

  // The renderer is called at any absolute time. We need the scene's
  // start_sec as the origin. PROMPT 9 §26: seekability, no playback
  // counters, no Date.now(). We use the absolute scene start as the
  // offset and let the parent pass `currentTimeSec` (typically derived
  // from useCurrentFrame() / fps).
  return (
    <div
      style={{
        position: "absolute",
        left: layout.left,
        right: width - layout.right,
        top: layout.anchorTop,
        textAlign: "center",
        pointerEvents: "none",
      }}
      data-caption-track={track.caption_id}
      data-caption-source={track.timestamp_source}
    >
      <RenderInner track={track} style={style} />
    </div>
  );
};

const RenderInner: React.FC<{ track: CaptionTrack; style: CaptionStyle }> = ({
  track,
  style,
}) => {
  // The actual time lookup is done by the *parent* (Documentary) which
  // has access to useCurrentFrame() / useVideoConfig(). We expose the
  // active state via a pure function inside the parent's frame loop.
  // This inner component just renders whatever state it's given through
  // a context-free prop API.
  // To keep things simple in the bundled Remotion context, we duplicate
  // a tiny hook here (useCurrentFrame is allowed; it's deterministic).
  // The pure derivation lives in state.ts and is also unit-tested.
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { useCurrentFrame, useVideoConfig } = require("remotion");
  const frame: number = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tSec = track.scene_start_sec + frame / fps;
  const state = computeCaptionFrameState(track, tSec);
  if (!state.active || !state.segment) return null;

  return (
    <>
      {state.lines.map((ln) =>
        renderLine(ln, state.segment!, state.word?.word_index ?? null, style),
      )}
    </>
  );
};

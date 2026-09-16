/**
 * Editorial smoke entry — minimal pure RenderPlan consumer.
 *
 * This is the actual Remotion component the bundler + renderer drive.
 * It accepts a RenderPlan + optional audio library via inputProps, with
 * fallback via getInputProps (PROMPT 11 §11 — real voice audio).
 */
import React from "react";
import { getInputProps } from "remotion";

import { RenderPlanComposition } from "../src/editorial/RenderPlanComposition";
import type { RenderPlan } from "../src/editorial/types";
import { isRenderPlan } from "../src/editorial/types";
import type { AudioArtifactSummary } from "../src/voice/audioLib";

interface Props {
  plan?: RenderPlan | null;
  audioArtifactSummaries?: AudioArtifactSummary[] | null;
}

function resolveProps(p: Partial<Props> = {}): Props {
  const fallback = (getInputProps() ?? {}) as Partial<Props>;
  return { ...fallback, ...p };
}

export const EditorialSmokeEntry: React.FC<Partial<Props>> = (rawProps) => {
  const { plan, audioArtifactSummaries } = resolveProps(rawProps);
  if (!plan || !isRenderPlan(plan)) {
    return (
      <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }} />
    );
  }
  return (
    <RenderPlanComposition
      plan={plan}
      audioArtifactSummaries={audioArtifactSummaries ?? null}
    />
  );
};

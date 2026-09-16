/**
 * Editorial smoke renderer — CLI for the multi-scene MP4 smoke test.
 *
 * Reads a RenderPlan JSON from disk, wraps it in a Composition, and renders
 * to MP4 using the standard Remotion CLI. Uses @remotion/bundler +
 * @remotion/renderer to avoid pulling in a webpack/long-running dev server.
 *
 * Invoked by `scripts/editorial_smoke_test.py`.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

import { RenderPlanComposition } from "../src/editorial/RenderPlanComposition";
import type { RenderPlan } from "../src/editorial/types";
import { isRenderPlan } from "../src/editorial/types";
import type { AudioArtifactSummary } from "../src/voice/audioLib";

interface Args {
  jobDir: string;
  plan: string;
  out: string;
  audioLibrary?: string;
}

function parseArgs(argv: string[]): Args {
  const out: Partial<Args> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!;
    if (a === "--job-dir") out.jobDir = argv[++i]!;
    else if (a === "--plan") out.plan = argv[++i]!;
    else if (a === "--out") out.out = argv[++i]!;
    else if (a === "--audio-library") out.audioLibrary = argv[++i]!;
  }
  if (!out.jobDir || !out.plan || !out.out) {
    throw new Error(
      "Usage: render_editorial_smoke.tsx --job-dir <dir> --plan <render_plan.json> --out <mp4> [--audio-library <json>]",
    );
  }
  return out as Args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const planPath = path.resolve(args.plan);
  const outPath = path.resolve(args.out);
  const jobDir = path.resolve(args.jobDir);

  const blob = JSON.parse(fs.readFileSync(planPath, "utf-8")) as RenderPlan;
  if (!isRenderPlan(blob)) {
    throw new Error(
      `Plan at ${planPath} failed isRenderPlan check; aborting render.`,
    );
  }

  fs.mkdirSync(jobDir, { recursive: true });
  // The Remotion `Composition` is registered in `editorial_smoke_root.tsx`;
  // we just hand it a fresh inputProps object per render.

  // PROMPT 11 §11 — load AudioArtifactSummary[] from disk so the renderer
  // can resolve real narration WAVs.
  let audioArtifactSummaries: AudioArtifactSummary[] | null = null;
  if (args.audioLibrary) {
    const libPath = path.resolve(args.audioLibrary);
    if (fs.existsSync(libPath)) {
      audioArtifactSummaries = JSON.parse(
        fs.readFileSync(libPath, "utf-8"),
      ) as AudioArtifactSummary[];
      console.log(
        `[editorial-smoke] audio library: ${audioArtifactSummaries.length} artifact(s)`,
      );
    }
  }

  const rendererDir = path.resolve(__dirname);
  // __dirname for the smoke entry is the renderer/scripts directory.
  // The renderer base is one level up.
  const rendererBase = path.resolve(rendererDir, "..");
  console.log(`[editorial-smoke] renderer dir: ${rendererBase}`);
  console.log(`[editorial-smoke] bundling from ${rendererBase}/scripts/editorial_smoke_entry.tsx`);
  const bundleLocation = await bundle({
    entryPoint: path.join(rendererBase, "scripts", "editorial_smoke_root.tsx"),
    outDir: path.join(rendererBase, ".remotion", "editorial-bundle"),
  });

  // PROMPT 11 §11 — stage AudioArtifact WAVs into the bundle root so
  // Remotion can resolve `voice_audio/<file>.wav` URLs.
  if (audioArtifactSummaries && audioArtifactSummaries.length > 0) {
    const bundleAudioDir = path.join(bundleLocation, "voice_audio");
    fs.mkdirSync(bundleAudioDir, { recursive: true });
    const publicVoiceAudio = path.join(rendererBase, "public", "voice_audio");
    let staged = 0;
    for (const art of audioArtifactSummaries) {
      const fileName = path.basename(art.uri);
      const src = path.join(publicVoiceAudio, fileName);
      if (fs.existsSync(src)) {
        const dst = path.join(bundleAudioDir, fileName);
        fs.copyFileSync(src, dst);
        staged += 1;
      } else {
        console.warn(`[editorial-smoke] missing audio file: ${src}`);
      }
    }
    console.log(`[editorial-smoke] staged ${staged} audio file(s) into bundle`);
  }

  console.log(`[editorial-smoke] selecting composition EditorialSmoke`);
  const comp = await selectComposition({
    serveUrl: bundleLocation,
    id: "EditorialSmoke",
    inputProps: {
      plan: blob,
      audioArtifactSummaries,
    },
  });

  // Use the plan's duration as authoritative.
  const finalDuration = Math.max(comp.durationInFrames, blob.total_duration_frames);
  console.log(`[editorial-smoke] rendering ${finalDuration} frames @ ${blob.fps}fps -> ${outPath}`);
  await renderMedia({
    composition: { ...comp, durationInFrames: finalDuration },
    serveUrl: bundleLocation,
    outputLocation: outPath,
    inputProps: {
      plan: blob,
      audioArtifactSummaries,
    },
    codec: "h264",
    pixelFormat: "yuv420p",
    crf: 23,
    concurrency: 1,
  });

  console.log(`[editorial-smoke] done -> ${outPath}`);
}

main().catch((err) => {
  console.error("[editorial-smoke] fatal:", err);
  process.exit(1);
});

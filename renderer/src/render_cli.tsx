/**
 * Actual production renderer entrypoint for the smoke test.
 *
 * This version uses Remotion's bundle() function (the same as
 * src/index.ts) but uses a separate smoke_entry.tsx that is fs-free
 * (avoiding the webpack node:fs scheme issue).
 *
 * Asset adapter is built BEFORE bundle() in a separate pre-step.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

import { loadSceneDefinition } from "./lib/loadScene";

async function main() {
  const jobDir = process.argv[2];
  if (!jobDir) {
    console.error("Usage: tsx src/render_cli.tsx <job_dir>");
    process.exit(1);
  }

  const absJobDir = path.resolve(jobDir);
  if (!fs.existsSync(absJobDir)) {
    console.error(`Job dir not found: ${absJobDir}`);
    process.exit(1);
  }

  console.log(`[render_cli] job_dir=${absJobDir}`);
  const sd = loadSceneDefinition(absJobDir);

  // Stage assets into the renderer public dir
  const publicDir = path.join(__dirname, "..", "public");
  fs.mkdirSync(publicDir, { recursive: true });
  for (const env of sd.environments) {
    if (!env.background_asset) continue;
    const src = path.join(absJobDir, env.background_asset);
    if (!fs.existsSync(src)) {
      console.warn(`[render_cli] missing asset: ${src}`);
      continue;
    }
    const dst = path.join(publicDir, env.background_asset);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
  }

  const outputPath = path.join(absJobDir, "output.mp4");
  const durationFrames = Math.round(sd.meta.target_duration_sec * sd.meta.fps);

  console.log("[render_cli] bundling...");
  const bundleLocation = await bundle({
    entryPoint: path.join(__dirname, "smoke_entry.tsx"),
    outDir: path.join(__dirname, "..", ".remotion", "bundle"),
  });

  console.log("[render_cli] selecting composition...");
  const comp = await selectComposition({
    serveUrl: bundleLocation,
    id: "Documentary",
    inputProps: {
      sceneDefinition: sd,
      audioSrc: null,
      narrationDurationSec: sd.meta.target_duration_sec,
    },
  });

  console.log(`[render_cli] rendering ${durationFrames} frames @ ${sd.meta.fps}fps -> ${outputPath}`);
  await renderMedia({
    composition: { ...comp, durationInFrames: durationFrames },
    serveUrl: bundleLocation,
    outputLocation: outputPath,
    inputProps: {
      sceneDefinition: sd,
      audioSrc: null,
      narrationDurationSec: sd.meta.target_duration_sec,
    },
    codec: "h264",
    concurrency: 1,
    crf: 23,
    pixelFormat: "yuv420p",
  });

  console.log(`[render_cli] done -> ${outputPath}`);
}

main().catch((err) => {
  console.error("[render_cli] fatal:", err);
  process.exit(1);
});

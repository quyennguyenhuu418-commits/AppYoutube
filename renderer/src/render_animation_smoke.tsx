/**
 * Animation smoke test renderer — fs-free variant.
 *
 * This entrypoint loads:
 *   - scene_definition.json  (from job_dir)
 *   - asset_system_package.json (optional, from job_dir)
 *   - animation_plan.json (optional, from job_dir)
 *
 * It bundles with smoke_entry-like minimal Composition, then renders.
 *
 * Used ONLY by scripts/animation_smoke_test.py.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

import type { AnimationPlan } from "./animation/runtime";
import type { AssetPackageSummary } from "./lib/assetAdapter";
import { loadAssetAdapterFromJob } from "./lib/assetAdapterLoader";
import { loadSceneDefinition } from "./lib/loadScene";

async function main() {
  const jobDir = process.argv[2];
  if (!jobDir) {
    console.error("Usage: tsx src/render_animation_smoke.tsx <job_dir>");
    process.exit(1);
  }
  const absJobDir = path.resolve(jobDir);
  if (!fs.existsSync(absJobDir)) {
    console.error(`Job dir not found: ${absJobDir}`);
    process.exit(1);
  }

  console.log(`[render_anim_smoke] job_dir=${absJobDir}`);
  const sd = loadSceneDefinition(absJobDir);

  // Load asset adapter from disk (CLI side). The adapter itself is NOT
  // passable to Remotion (it has class methods that don't survive JSON
  // round-trip). Instead we pass the raw asset package as inputProps and
  // let the bundle reconstruct the adapter via loadAssetAdapter().
  const pkgPath = path.join(absJobDir, "asset_system_package.json");
  let assetPackage: AssetPackageSummary | null = null;
  if (fs.existsSync(pkgPath)) {
    try {
      const raw = fs.readFileSync(pkgPath, "utf-8");
      assetPackage = JSON.parse(raw) as AssetPackageSummary;
    } catch {
      assetPackage = null;
    }
  }
  // Use the loader for any CLI-side work that needs the live adapter.
  // (Currently only needed for resolving hints at the Node layer.)
  void loadAssetAdapterFromJob(absJobDir, sd);

  // Stage assets.
  const publicDir = path.join(__dirname, "..", "public");
  fs.mkdirSync(publicDir, { recursive: true });
  for (const env of sd.environments) {
    if (!env.background_asset) continue;
    const src = path.join(absJobDir, env.background_asset);
    if (!fs.existsSync(src)) {
      console.warn(`[render_anim_smoke] missing asset: ${src}`);
      continue;
    }
    const dst = path.join(publicDir, env.background_asset);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
  }

  // Load animation plans (per scene_id).
  const plansPath = path.join(absJobDir, "animation_plan.json");
  let animationPlans: Record<string, AnimationPlan> | null = null;
  if (fs.existsSync(plansPath)) {
    const raw = fs.readFileSync(plansPath, "utf-8");
    const plan: AnimationPlan = JSON.parse(raw);
    animationPlans = { [plan.metadata.scene_id]: plan };
    console.log(`[render_anim_smoke] loaded plan for scene ${plan.metadata.scene_id}`);
  }

  const outputPath = path.join(absJobDir, "output.mp4");
  const durationFrames = Math.round(sd.meta.target_duration_sec * sd.meta.fps);

  console.log("[render_anim_smoke] bundling...");
  const bundleLocation = await bundle({
    entryPoint: path.join(__dirname, "animation_smoke_entry.tsx"),
    outDir: path.join(__dirname, "..", ".remotion", "anim_smoke_bundle"),
  });

  console.log("[render_anim_smoke] selecting composition...");
  const comp = await selectComposition({
    serveUrl: bundleLocation,
    id: "AnimationSmoke",
    inputProps: {
      sceneDefinition: sd,
      audioSrc: null,
      narrationDurationSec: sd.meta.target_duration_sec,
      animationPlans,
      assetPackage,
    },
  });

  console.log(`[render_anim_smoke] rendering ${durationFrames} frames @ ${sd.meta.fps}fps -> ${outputPath}`);
  await renderMedia({
    composition: { ...comp, durationInFrames: durationFrames },
    serveUrl: bundleLocation,
    outputLocation: outputPath,
    inputProps: {
      sceneDefinition: sd,
      audioSrc: null,
      narrationDurationSec: sd.meta.target_duration_sec,
      animationPlans,
      assetPackage,
    },
    codec: "h264",
    concurrency: 1,
    crf: 23,
    pixelFormat: "yuv420p",
  });

  console.log(`[render_anim_smoke] done -> ${outputPath}`);
}

main().catch((err) => {
  console.error("[render_anim_smoke] fatal:", err);
  process.exit(1);
});

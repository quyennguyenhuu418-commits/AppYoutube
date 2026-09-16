/**
 * PROMPT 9 — Caption + Audio Smoke Test Renderer Entry Point.
 *
 * Loads:
 *   - scene_definition.json  (from job_dir)
 *   - voice_audio/  (canonical audio artifacts from Python TTS pipeline)
 *   - caption_track.json (canonical P9 CaptionTrack JSON from Python)
 *
 * The renderer:
 *   1. Loads the CaptionTrack.
 *   2. Derives legacy `WordTimestamp[]` from the canonical track via
 *      `toLegacyWordTimestamps(track)` — proving the canonical contract
 *      drives the existing Caption component.
 *   3. Renders an MP4 with video + audio + canonical captions.
 *
 * Used ONLY by scripts/caption_smoke_test.py.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

import type { SceneDefinition } from "./scenes/types";
import type { CaptionTrack } from "./captions/types";
import { loadSceneDefinition } from "./lib/loadScene";

function copyToDir(src: string, dstDir: string, relPath: string): void {
  const dst = path.join(dstDir, relPath);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
}

async function main() {
  const jobDir = process.argv[2];
  if (!jobDir) {
    console.error("Usage: tsx src/render_caption_smoke.tsx <job_dir>");
    process.exit(1);
  }

  const absJobDir = path.resolve(jobDir);
  if (!fs.existsSync(absJobDir)) {
    console.error(`Job dir not found: ${absJobDir}`);
    process.exit(1);
  }

  console.log(`[render_caption_smoke] job_dir=${absJobDir}`);
  const sd: SceneDefinition = loadSceneDefinition(absJobDir);

  // --- Load canonical CaptionTrack JSON ---
  const captionPath = path.join(absJobDir, "caption_track.json");
  if (!fs.existsSync(captionPath)) {
    console.error(`[render_caption_smoke] missing caption_track.json: ${captionPath}`);
    process.exit(1);
  }
  const track: CaptionTrack = JSON.parse(fs.readFileSync(captionPath, "utf-8"));
  console.log(
    `[render_caption_smoke] caption track: caption_id=${track.caption_id} `
    + `scene_id=${track.scene_id} segments=${track.segments.length} `
    + `source=${track.timestamp_source}`,
  );

  // --- Remove old bundle ---
  const bundleDir = path.join(__dirname, "..", ".remotion", "caption_smoke_bundle");
  try {
    if (fs.existsSync(bundleDir)) {
      fs.rmSync(bundleDir, { recursive: true });
    }
  } catch { /* ignore */ }

  // Also remove the shared smoke bundle to avoid stale cache.
  const sharedBundle = path.join(__dirname, "..", ".remotion", "audio_smoke_bundle");
  try {
    if (fs.existsSync(sharedBundle)) {
      fs.rmSync(sharedBundle, { recursive: true });
    }
  } catch { /* ignore */ }

  // --- Stage assets ---
  const stagingDir = path.join(__dirname, "..", ".remotion", "caption_smoke_staging");
  fs.mkdirSync(stagingDir, { recursive: true });

  for (const env of sd.environments) {
    if (!env.background_asset) continue;
    const src = path.join(absJobDir, env.background_asset);
    if (!fs.existsSync(src)) {
      console.warn(`[render_caption_smoke] missing background: ${src}`);
      continue;
    }
    copyToDir(src, stagingDir, env.background_asset);
  }

  const audioSrcDir = path.join(absJobDir, "voice_audio");
  if (fs.existsSync(audioSrcDir)) {
    for (const file of fs.readdirSync(audioSrcDir)) {
      copyToDir(path.join(audioSrcDir, file), stagingDir, path.join("voice_audio", file));
    }
  }

  // --- Bundle ---
  console.log("[render_caption_smoke] bundling...");
  const bundleLocation = await bundle({
    entryPoint: path.join(__dirname, "caption_smoke_root.tsx"),
    outDir: bundleDir,
  });
  const serveUrl = bundleLocation;

  // --- Copy staged assets into bundle location ---
  for (const env of sd.environments) {
    if (!env.background_asset) continue;
    const src = path.join(stagingDir, env.background_asset);
    if (fs.existsSync(src)) {
      copyToDir(src, bundleLocation, env.background_asset);
    }
  }
  const stagedAudioDir = path.join(stagingDir, "voice_audio");
  if (fs.existsSync(stagedAudioDir)) {
    for (const file of fs.readdirSync(stagedAudioDir)) {
      copyToDir(path.join(stagedAudioDir, file), bundleLocation, path.join("voice_audio", file));
    }
  }

  // --- Copy into bundle's public dir ---
  const bundlePublicDir = path.join(bundleLocation, "public");
  fs.mkdirSync(bundlePublicDir, { recursive: true });
  for (const env of sd.environments) {
    if (!env.background_asset) continue;
    const src = path.join(stagingDir, env.background_asset);
    if (fs.existsSync(src)) {
      copyToDir(src, bundlePublicDir, env.background_asset);
    }
  }
  if (fs.existsSync(stagedAudioDir)) {
    for (const file of fs.readdirSync(stagedAudioDir)) {
      copyToDir(path.join(stagedAudioDir, file), bundlePublicDir, path.join("voice_audio", file));
    }
  }

  // --- Extract audioSrc from scene definition ---
  const firstScene = sd.scenes[0] as unknown as Record<string, unknown> | undefined;
  const audioSrc: string | null =
    (firstScene?.audioSrc as string | null | undefined) ?? null;
  console.log(`[render_caption_smoke] audioSrc=${audioSrc}`);

  const outputPath = path.join(absJobDir, "output.mp4");
  const durationFrames = Math.round(sd.meta.target_duration_sec * sd.meta.fps);

  const inputProps = {
    sceneDefinition: sd,
    audioSrc,
    narrationDurationSec: sd.meta.target_duration_sec,
    captionTrack: track,
  };

  console.log("[render_caption_smoke] selecting composition...");
  const comp = await selectComposition({
    serveUrl: bundleLocation,
    id: "CaptionSmoke",
    inputProps,
  });

  console.log(
    `[render_caption_smoke] rendering ${durationFrames} frames @ ${sd.meta.fps}fps -> ${outputPath}`,
  );
  await renderMedia({
    composition: { ...comp, durationInFrames: durationFrames },
    serveUrl: bundleLocation,
    outputLocation: outputPath,
    inputProps,
    codec: "h264",
    concurrency: 1,
    crf: 23,
    pixelFormat: "yuv420p",
  });

  console.log(`[render_caption_smoke] done -> ${outputPath}`);
}

main().catch((err) => {
  console.error("[render_caption_smoke] fatal:", err);
  process.exit(1);
});

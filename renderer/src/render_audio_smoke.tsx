/**
 * PROMPT 8 — Narration Audio Smoke Test Renderer Entry Point.
 *
 * Loads:
 *   - scene_definition.json  (from job_dir)
 *   - voice_audio/  (canonical audio artifacts from Python TTS pipeline)
 *
 * Passes `audioSrc` from the scene's `audioSrc` field to the Documentary
 * composition so the MP4 contains audio.
 *
 * Asset staging:
 *   1. Stage backgrounds + audio from job_dir into a temp staging dir
 *   2. Bundle
 *   3. Copy staged files into bundle's public dir (before rendering)
 *
 * Used ONLY by scripts/voice_audio_smoke_test.py.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

import type { SceneDefinition } from "./scenes/types";
import { loadSceneDefinition } from "./lib/loadScene";

function copyToDir(src: string, dstDir: string, relPath: string) {
  const dst = path.join(dstDir, relPath);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
}

async function main() {
  const jobDir = process.argv[2];
  if (!jobDir) {
    console.error("Usage: tsx src/render_audio_smoke.tsx <job_dir>");
    process.exit(1);
  }

  const absJobDir = path.resolve(jobDir);
  if (!fs.existsSync(absJobDir)) {
    console.error(`Job dir not found: ${absJobDir}`);
    process.exit(1);
  }

  console.log(`[render_audio_smoke] job_dir=${absJobDir}`);
  const sd: SceneDefinition = loadSceneDefinition(absJobDir);

  // --- Remove old bundle to avoid stale cache ---
  const bundleDir = path.join(__dirname, "..", ".remotion", "audio_smoke_bundle");
  try {
    if (fs.existsSync(bundleDir)) {
      fs.rmSync(bundleDir, { recursive: true });
    }
  } catch { /* ignore */ }

  // --- Stage all assets into a temp staging directory ---
  const stagingDir = path.join(__dirname, "..", ".remotion", "audio_smoke_staging");
  fs.mkdirSync(stagingDir, { recursive: true });

  // Stage backgrounds.
  for (const env of sd.environments) {
    if (!env.background_asset) continue;
    const src = path.join(absJobDir, env.background_asset);
    if (!fs.existsSync(src)) {
      console.warn(`[render_audio_smoke] missing background: ${src}`);
      continue;
    }
    copyToDir(src, stagingDir, env.background_asset);
  }

  // Stage audio files from job_dir.
  const audioSrcDir = path.join(absJobDir, "voice_audio");
  if (fs.existsSync(audioSrcDir)) {
    for (const file of fs.readdirSync(audioSrcDir)) {
      copyToDir(
        path.join(audioSrcDir, file),
        stagingDir,
        path.join("voice_audio", file),
      );
    }
    console.log(`[render_audio_smoke] staged audio: ${fs.readdirSync(audioSrcDir).join(", ")}`);
  }

  // --- Bundle (will recreate the bundle dir) ---
  console.log("[render_audio_smoke] bundling...");
  const bundleLocation = await bundle({
    entryPoint: path.join(__dirname, "smoke_entry.tsx"),
    outDir: bundleDir,
  });
  console.log(`[render_audio_smoke] bundleLocation=${bundleLocation}`);

  // --- Copy staged assets into bundle location (Remotion looks here) ---
  // Remotion's renderer resolves audio URLs relative to the bundle root
  // AND also looks in the bundle's "public/" subfolder. We stage in BOTH
  // locations for maximum compatibility.

  // Copy into bundle root.
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
      copyToDir(
        path.join(stagedAudioDir, file),
        bundleLocation,
        path.join("voice_audio", file),
      );
    }
  }

  // Copy into bundle's public dir.
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
      copyToDir(
        path.join(stagedAudioDir, file),
        bundlePublicDir,
        path.join("voice_audio", file),
      );
    }
    console.log(`[render_audio_smoke] staged ${fs.readdirSync(stagedAudioDir).length} audio file(s) into bundle`);
  }

  // Verify.
  const finalAudioDir = path.join(bundlePublicDir, "voice_audio");
  if (fs.existsSync(finalAudioDir)) {
    console.log(`[render_audio_smoke] bundle audio: ${fs.readdirSync(finalAudioDir).join(", ")}`);
  } else {
    console.warn(`[render_audio_smoke] no voice_audio in bundle public`);
  }

  // --- Extract audioSrc from scene definition ---
  const firstScene = sd.scenes[0] as unknown as Record<string, unknown> | undefined;
  const audioSrc: string | null =
    (firstScene?.audioSrc as string | null | undefined) ?? null;
  console.log(`[render_audio_smoke] audioSrc=${audioSrc}`);

  const outputPath = path.join(absJobDir, "output.mp4");
  const durationFrames = Math.round(
    sd.meta.target_duration_sec * sd.meta.fps,
  );

  // --- Select composition ---
  console.log("[render_audio_smoke] selecting composition...");
  const comp = await selectComposition({
    serveUrl: bundleLocation,
    id: "Documentary",
    inputProps: {
      sceneDefinition: sd,
      audioSrc,
      narrationDurationSec: sd.meta.target_duration_sec,
    },
  });

  // --- Render ---
  console.log(
    `[render_audio_smoke] rendering ${durationFrames} frames @ ${sd.meta.fps}fps -> ${outputPath}`
  );
  await renderMedia({
    composition: { ...comp, durationInFrames: durationFrames },
    serveUrl: bundleLocation,
    outputLocation: outputPath,
    inputProps: {
      sceneDefinition: sd,
      audioSrc,
      narrationDurationSec: sd.meta.target_duration_sec,
    },
    codec: "h264",
    concurrency: 1,
    crf: 23,
    pixelFormat: "yuv420p",
  });

  console.log(`[render_audio_smoke] done -> ${outputPath}`);
}

main().catch((err) => {
  console.error("[render_audio_smoke] fatal:", err);
  process.exit(1);
});

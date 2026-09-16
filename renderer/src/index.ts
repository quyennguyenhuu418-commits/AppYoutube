/**
 * Renderer CLI entrypoint.
 *
 * Called by the Python orchestrator as:
 *   npx tsx src/index.ts <job_id> [--repo-root=<path>]
 *
 * Resolves the job's workspace, copies assets into the Remotion public
 * dir, then renders the Documentary composition to MP4 via
 * @remotion/renderer.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

import { Documentary } from "./compositions/Documentary";
import { loadSceneDefinition } from "./lib/loadScene";

const REPO_ROOT = process.env.VIDEOAI_REPO_ROOT ?? path.resolve(__dirname, "../..");
const WORKSPACE = process.env.VIDEOAI_WORKSPACE ?? path.join(REPO_ROOT, "workspace");

async function main() {
  const jobId = process.argv[2];
  if (!jobId) {
    console.error("Usage: tsx src/index.ts <job_id>");
    process.exit(1);
  }
  const jobDir = path.join(WORKSPACE, jobId);
  if (!fs.existsSync(jobDir)) {
    console.error(`Job directory not found: ${jobDir}`);
    process.exit(1);
  }

  console.log(`[renderer] job=${jobId} repo=${REPO_ROOT}`);
  const sd = loadSceneDefinition(jobDir);

  // Stage assets into the renderer public dir so Remotion can serve them.
  const publicDir = path.join(__dirname, "..", "public");
  fs.mkdirSync(publicDir, { recursive: true });
  for (const env of sd.environments) {
    if (!env.background_asset) continue;
    const src = path.join(jobDir, env.background_asset);
    if (!fs.existsSync(src)) {
      console.warn(`[renderer] missing asset: ${src}`);
      continue;
    }
    const dst = path.join(publicDir, env.background_asset);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
  }

  // Locate the narration MP3 (relative path).
  const audioPath = path.join(jobDir, "narration.mp3");
  let audioSrc: string | null = null;
  if (fs.existsSync(audioPath)) {
    fs.copyFileSync(audioPath, path.join(publicDir, "narration.mp3"));
    audioSrc = "/narration.mp3";
  } else {
    console.warn("[renderer] no narration.mp3 found; video will be silent");
  }

  const outputPath = path.join(jobDir, "final.mp4");
  const durationFrames = Math.round(sd.meta.target_duration_sec * sd.meta.fps);

        console.log(`[renderer] bundling...`);
        const bundleLocation = await bundle({
            entryPoint: path.join(__dirname, "Root.tsx"),
            outDir: path.join(__dirname, "..", ".remotion", "bundle"),
            webpackOverride: (config) => {
                // Remotion renderMedia chạy trong Node.js (không phải browser)
                // nên cần cho phép dùng Node built-ins như 'fs', 'path'.
                // Fix "Reading from node:fs is not handled" bằng cách resolve
                // cả 'node:fs' và 'fs' về cùng module.
                const webpack = require("webpack");
                config.plugins = config.plugins || [];
                config.plugins.push(
                    new webpack.NormalModuleReplacementPlugin(
                        /^node:(.+)$/,
                        (resource: any) => {
                            resource.request = resource.request.replace(/^node:/, "");
                        },
                    ),
                );
                // Mark Node built-ins as not browser-only (allow resolve)
                if (config.resolve) {
                    config.resolve.fallback = {
                        ...config.resolve.fallback,
                        fs: false,
                        path: false,
                        os: false,
                        crypto: false,
                        stream: false,
                        util: false,
                        assert: false,
                        url: false,
                        zlib: false,
                        buffer: false,
                        events: false,
                        child_process: false,
                    };
                }
                return config;
            },
        });

        // Copy backgrounds vào bundle/public/ để Remotion serve được
        const bundlePublicDir = path.join(bundleLocation, "public");
        fs.mkdirSync(bundlePublicDir, { recursive: true });
        for (const env of sd.environments) {
            if (!env.background_asset) continue;
            const src = path.join(jobDir, env.background_asset);
            if (fs.existsSync(src)) {
                const dst = path.join(bundlePublicDir, env.background_asset);
                fs.mkdirSync(path.dirname(dst), { recursive: true });
                fs.copyFileSync(src, dst);
                console.log(`[renderer] staged to bundle: ${env.background_asset}`);
            }
        }

  console.log(`[renderer] selecting composition...`);
  const comp = await selectComposition({
    serveUrl: bundleLocation,
    id: "Documentary",
    inputProps: {
      sceneDefinition: sd,
      audioSrc,
      narrationDurationSec: sd.meta.target_duration_sec,
    },
  });

  // Defensive: ensure composition duration covers the longest scene.
  const sceneEndFrame = Math.round(
    Math.max(...sd.scenes.map((s) => s.end_sec)) * sd.meta.fps,
  );
  const finalDuration = Math.max(comp.durationInFrames, sceneEndFrame, durationFrames);

  console.log(`[renderer] rendering ${finalDuration} frames @ ${sd.meta.fps}fps -> ${outputPath}`);
  await renderMedia({
    composition: { ...comp, durationInFrames: finalDuration },
    serveUrl: bundleLocation,
    outputLocation: outputPath,
    inputProps: {
      sceneDefinition: sd,
      audioSrc,
      narrationDurationSec: sd.meta.target_duration_sec,
    },
    codec: "h264",
    audioCodec: "aac",
    pixelFormat: "yuv420p",
    crf: 23,
    concurrency: 1,
    // Chromium headless args để tránh sandbox issues trên Windows
    chromiumOptions: {
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
      ],
      disableWebSecurity: true,
    },
  });

  console.log(`[renderer] done -> ${outputPath}`);
}

main().catch((err) => {
  console.error("[renderer] fatal:", err);
  process.exit(1);
});

/**
 * Voice / TTS / Audio Index.
 *
 * PROMPT 8 — re-exports for the renderer-side voice layer.
 * - `types`      canonical TS types (mirror of Python schemas)
 * - `timeline`   NarrationTimeline → scene timing conversion helpers
 * - `audioLib`   AudioLibrary extension that resolves canonical artifact IDs
 */

export * from "./types";
export * from "./timeline";
export * from "./audioLib";

# Remotion renderer

A Node + Remotion renderer that consumes `scene_definition.json` and produces
an MP4. Called by the Python orchestrator via `npx tsx src/index.ts <job_id>`.

## Why two languages?

The orchestrator is Python (LLMs, file I/O, async APIs are Python-strong).
The renderer is React + Remotion because that's the fastest path to a
production-quality video pipeline (GSAP, headless Chrome rendering,
FFmpeg muxing, captions, etc.).

They communicate through the filesystem only — no shared memory, no
network call. The contract is `scene_definition.json`.

## Develop

```
npm install
npm run dev          # Remotion studio at http://localhost:3000
npm run render       # CLI render (called by orchestrator)
```

## Files

- `src/index.ts` — CLI entrypoint
- `src/Root.tsx` — Remotion studio root (preview composition)
- `src/compositions/Documentary.tsx` — main composition
- `src/scenes/*` — deterministic scene renderers (one per `scene.kind`)
- `src/components/*` — Character, Camera, Caption, Props
- `src/lib/loadScene.ts` — reads and validates `scene_definition.json`

/**
 * Loads the SceneDefinition JSON emitted by the orchestrator.
 *
 * The Python orchestrator writes `scene_definition.json` inside each
 * job's workspace. We resolve it relative to either an explicit absolute
 * path (when run via CLI) or `process.cwd()`.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import type { SceneDefinition } from "../scenes/types";

export function loadSceneDefinition(jobDir: string): SceneDefinition {
  const file = path.join(jobDir, "scene_definition.json");
  if (!fs.existsSync(file)) {
    throw new Error(`Scene definition not found at ${file}`);
  }
  const raw = fs.readFileSync(file, "utf-8");
  const parsed = JSON.parse(raw) as SceneDefinition;

  // Lightweight runtime sanity checks. Pydantic did the heavy validation
  // upstream; this is a defense-in-depth check so the renderer doesn't
  // crash on a malformed file with confusing React errors.
  if (!parsed.meta || !Array.isArray(parsed.scenes)) {
    throw new Error("Malformed scene_definition.json: missing meta or scenes");
  }
  for (const s of parsed.scenes) {
    if (typeof s.start_sec !== "number" || typeof s.end_sec !== "number") {
      throw new Error(`Scene ${s.id} has invalid start/end times`);
    }
    if (s.end_sec <= s.start_sec) {
      throw new Error(`Scene ${s.id} has end_sec <= start_sec`);
    }
  }
  return parsed;
}

/**
 * Loader for the AssetAdapter. This file is intentionally separate
 * from assetAdapter.ts so that compositions can import assetAdapter.ts
 * (fs-free, webpack-safe) while the CLI/loader code (which uses node:fs)
 * lives here.
 */
import * as fs from "node:fs";
import * as path from "node:path";

import { loadAssetAdapter, type AssetAdapter, type AssetPackageSummary } from "./assetAdapter";
import type { SceneDefinition } from "../scenes/types";

/**
 * Load asset adapter from a job directory.
 * Reads asset_system_package.json (if present) and combines with the
 * supplied SceneDefinition.
 */
export function loadAssetAdapterFromJob(jobDir: string, sd: SceneDefinition): AssetAdapter {
  const pkgPath = path.join(jobDir, "asset_system_package.json");
  let pkg: AssetPackageSummary | null = null;

  if (fs.existsSync(pkgPath)) {
    try {
      const raw = fs.readFileSync(pkgPath, "utf-8");
      pkg = JSON.parse(raw) as AssetPackageSummary;
    } catch {
      // ignore - fall through with null
    }
  }

  return loadAssetAdapter(sd, pkg);
}

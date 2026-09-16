/**
 * AssetReference adapter for the Remotion renderer.
 *
 * This module provides a bridge between the canonical AssetReference
 * data from AssetSystemPackage and the renderer's existing component
 * structure.
 *
 * IMPORTANT: This module is intentionally fs-free so it can be safely
 * imported by compositions that get bundled by webpack (which does not
 * handle node:* schemes by default).
 *
 * The asset data resolution is delegated to a renderer-side helper in
 * src/lib/loadScene.ts which already handles filesystem I/O. For
 * renderer-side use, call `loadAssetAdapter()` AFTER the scene data
 * has been loaded.
 */
import type { SceneDefinition } from "../scenes/types";

export interface ResolvedEnvironment {
  id: string;
  name: string;
  background_asset: string;
  mood: string;
  palette?: {
    primary: string;
    secondary?: string;
    accent?: string;
  };
  lighting?: {
    primary: string;
    weather: string;
    time_of_day: string;
  };
  renderer_hints: Record<string, unknown>;
}

export interface ResolvedProp {
  id: string;
  kind: string;
  category: string;
  primary_color: string;
  anchors: Array<{ id: string; name: string; x: number; y: number }>;
  renderer_hints: Record<string, unknown>;
}

export interface AssetAdapter {
  /** Initialize the adapter with a SceneDefinition (no fs imports). */
  init(sceneDefinition: SceneDefinition, assetPackage?: AssetPackageSummary | null): AssetAdapter;

  /** Get a resolved environment by environment_id. */
  getEnvironment(envId: string): ResolvedEnvironment | null;

  /** Get a resolved prop by prop_id. */
  getProp(propId: string): ResolvedProp | null;

  /** Get mood color for an environment. */
  getMoodColor(envId: string): string;

  /** Check if an asset_id is known (registered in the system). */
  isKnownAsset(assetId: string): boolean;

  /** Get all known environment IDs. */
  getKnownEnvironments(): string[];

  /** Get all known prop IDs. */
  getKnownProps(): string[];
}

export interface AssetPackageSummary {
  environments: Array<{
    asset_id: string;
    name?: string;
    primary_asset_uri?: string;
    mood?: string;
    palette_profile?: { primary?: string; secondary?: string; accent?: string };
    lighting_profile?: { primary?: string; weather?: string; time_of_day?: string };
  }>;
  props: Array<{
    asset_id: string;
    name?: string;
    category?: string;
    primary_color?: string;
    anchor_points?: Array<{ anchor_id?: string; name?: string; x?: number; y?: number }>;
  }>;
  asset_references: Array<{ asset_id: string; renderer_hints: Record<string, unknown> }>;
}

/**
 * Default mood color mapping for environments.
 */
const MOOD_COLORS: Record<string, string> = {
  calm: "#4A6FA5",
  tense: "#8B4513",
  triumphant: "#B45309",
  mysterious: "#312E81",
  warm: "#D97706",
};

class AssetAdapterImpl implements AssetAdapter {
  private _sd: SceneDefinition | null = null;
  private _pkg: AssetPackageSummary | null = null;

  init(sceneDefinition: SceneDefinition, assetPackage?: AssetPackageSummary | null): AssetAdapter {
    this._sd = sceneDefinition;
    this._pkg = assetPackage ?? null;
    return this;
  }

  getEnvironment(envId: string): ResolvedEnvironment | null {
    // First try from SceneDefinition.environments (always present)
    if (this._sd) {
      const env = this._sd.environments.find((e) => e.id === envId);
      if (env) {
        const pkgEnv = this._pkg?.environments.find((e) => e.asset_id === envId);
        return {
          id: env.id,
          name: env.name,
          background_asset: env.background_asset || `backgrounds/${env.id}.png`,
          mood: env.mood || pkgEnv?.mood || "calm",
          palette: pkgEnv?.palette_profile ? {
            primary: pkgEnv.palette_profile.primary || "#4A5568",
            secondary: pkgEnv.palette_profile.secondary,
            accent: pkgEnv.palette_profile.accent,
          } : undefined,
          lighting: pkgEnv?.lighting_profile ? {
            primary: pkgEnv.lighting_profile.primary || "natural",
            weather: pkgEnv.lighting_profile.weather || "clear",
            time_of_day: pkgEnv.lighting_profile.time_of_day || "midday",
          } : undefined,
          renderer_hints: this._getHints(envId),
        };
      }
    }

    // Fall back to asset package
    if (this._pkg) {
      const pkgEnv = this._pkg.environments.find((e) => e.asset_id === envId);
      if (pkgEnv) {
        return {
          id: pkgEnv.asset_id,
          name: pkgEnv.name || pkgEnv.asset_id,
          background_asset: pkgEnv.primary_asset_uri || `backgrounds/${pkgEnv.asset_id}.png`,
          mood: pkgEnv.mood || "calm",
          palette: pkgEnv.palette_profile ? {
            primary: pkgEnv.palette_profile.primary || "#4A5568",
            secondary: pkgEnv.palette_profile.secondary,
            accent: pkgEnv.palette_profile.accent,
          } : undefined,
          lighting: pkgEnv.lighting_profile ? {
            primary: pkgEnv.lighting_profile.primary || "natural",
            weather: pkgEnv.lighting_profile.weather || "clear",
            time_of_day: pkgEnv.lighting_profile.time_of_day || "midday",
          } : undefined,
          renderer_hints: this._getHints(envId),
        };
      }
    }

    return null;
  }

  getProp(propId: string): ResolvedProp | null {
    if (!this._pkg) return null;
    const prop = this._pkg.props.find((p) => p.asset_id === propId);
    if (!prop) return null;
    return {
      id: prop.asset_id,
      kind: prop.asset_id,
      category: prop.category || "abstract",
      primary_color: prop.primary_color || "#FFFFFF",
      anchors: (prop.anchor_points || []).map((a) => ({
        id: a.anchor_id || "center",
        name: a.name || "Center",
        x: a.x || 0,
        y: a.y || 0,
      })),
      renderer_hints: this._getHints(propId),
    };
  }

  getMoodColor(envId: string): string {
    const env = this.getEnvironment(envId);
    if (!env) return MOOD_COLORS.calm;
    if (env.palette?.primary) return env.palette.primary;
    return MOOD_COLORS[env.mood] || MOOD_COLORS.calm;
  }

  isKnownAsset(assetId: string): boolean {
    if (this._sd) {
      if (this._sd.characters.some((c) => c.id === assetId)) return true;
      if (this._sd.environments.some((e) => e.id === assetId)) return true;
    }
    if (this._pkg) {
      if (this._pkg.environments.some((e) => e.asset_id === assetId)) return true;
      if (this._pkg.props.some((p) => p.asset_id === assetId)) return true;
      if (this._pkg.asset_references.some((r) => r.asset_id === assetId)) return true;
    }
    return false;
  }

  getKnownEnvironments(): string[] {
    if (this._sd) {
      return this._sd.environments.map((e) => e.id);
    }
    return [];
  }

  getKnownProps(): string[] {
    if (!this._pkg) return [];
    return this._pkg.props.map((p) => p.asset_id);
  }

  private _getHints(assetId: string): Record<string, unknown> {
    const ref = this._pkg?.asset_references.find((r) => r.asset_id === assetId);
    return ref?.renderer_hints || {};
  }
}

/** Convenience function to create an asset adapter. */
export function loadAssetAdapter(
  sceneDefinition: SceneDefinition,
  assetPackage?: AssetPackageSummary | null
): AssetAdapter {
  return new AssetAdapterImpl().init(sceneDefinition, assetPackage);
}


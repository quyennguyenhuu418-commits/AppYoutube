/**
 * AssetAdapter tests — verify the fs-free asset bridge works correctly.
 *
 * PROMPT 7 §36: Renderer tests must cover assetAdapter.
 */
import { describe, expect, it } from "vitest";

import { loadAssetAdapter } from "./assetAdapter";
import type { SceneDefinition } from "../scenes/types";

function makeSceneDefinition(): SceneDefinition {
  return {
    meta: { title: "t", fps: 30, width: 1920, height: 1080, target_duration_sec: 5 },
    style: {
      primary_color: "#FF6B35",
      accent_color: "#FFD166",
      background_color: "#1D1D2C",
      text_color: "#FFFFFF",
      font_family: "Inter",
    },
    characters: [
      {
        id: "alice",
        name: "Alice",
        color: "#FF0000",
        default_pose: "stand",
        description: "",
      },
    ],
    environments: [
      {
        id: "cave",
        name: "Cave",
        background_asset: "backgrounds/cave.png",
        mood: "mysterious",
      },
    ],
    scenes: [],
  };
}

describe("loadAssetAdapter", () => {
  it("initializes an adapter with scene definition", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    expect(adapter).toBeDefined();
  });

  it("returns environment from SceneDefinition when no package", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    const env = adapter.getEnvironment("cave");
    expect(env).not.toBeNull();
    expect(env!.name).toBe("Cave");
    expect(env!.mood).toBe("mysterious");
    expect(env!.background_asset).toBe("backgrounds/cave.png");
  });

  it("returns null for unknown environment", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    expect(adapter.getEnvironment("unknown")).toBeNull();
  });

  it("returns null for prop when no asset package provided", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    expect(adapter.getProp("spear")).toBeNull();
  });

  it("returns prop when asset package has it", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, {
      environments: [],
      props: [
        {
          asset_id: "spear",
          category: "weapon",
          primary_color: "#8B4513",
          anchor_points: [{ anchor_id: "grip", name: "Grip", x: 0, y: 0 }],
        },
      ],
      asset_references: [],
    });
    const prop = adapter.getProp("spear");
    expect(prop).not.toBeNull();
    expect(prop!.primary_color).toBe("#8B4513");
    expect(prop!.anchors).toHaveLength(1);
    expect(prop!.anchors[0]!.id).toBe("grip");
  });

  it("returns mood color from environment mood", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    const color = adapter.getMoodColor("cave");
    // "mysterious" mood → purple
    expect(color).toBe("#312E81");
  });

  it("returns default mood color for unknown environment", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    const color = adapter.getMoodColor("unknown");
    expect(color).toBe("#4A6FA5"); // calm default
  });

  it("isKnownAsset returns true for known character", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    expect(adapter.isKnownAsset("alice")).toBe(true);
  });

  it("isKnownAsset returns true for known environment", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    expect(adapter.isKnownAsset("cave")).toBe(true);
  });

  it("isKnownAsset returns false for unknown asset", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    expect(adapter.isKnownAsset("unknown")).toBe(false);
  });

  it("getKnownEnvironments returns environment IDs", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, null);
    expect(adapter.getKnownEnvironments()).toEqual(["cave"]);
  });

  it("returns renderer_hints from asset references", () => {
    const sd = makeSceneDefinition();
    const adapter = loadAssetAdapter(sd, {
      environments: [],
      props: [],
      asset_references: [
        {
          asset_id: "cave",
          renderer_hints: { lighting: "moonlight", palette: "#000000" },
        },
      ],
    });
    const env = adapter.getEnvironment("cave");
    expect(env!.renderer_hints["lighting"]).toBe("moonlight");
  });
});

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { assetApi, AssetInfo, AssetListResponse, RegistryInfo, AssetQualityScore } from "@/lib/api";

interface Props {
  jobId: string;
}

const ASSET_TYPE_COLORS: Record<string, string> = {
  environment: "bg-blue-800 text-blue-200",
  prop: "bg-amber-800 text-amber-200",
  character: "bg-emerald-800 text-emerald-200",
  diagram: "bg-violet-800 text-violet-200",
  overlay: "bg-pink-800 text-pink-200",
};

const LIFECYCLE_COLORS: Record<string, string> = {
  draft: "bg-slate-700 text-slate-200",
  generating: "bg-yellow-800 text-yellow-200",
  generated: "bg-blue-700 text-blue-200",
  validated: "bg-teal-700 text-teal-200",
  review: "bg-amber-700 text-amber-200",
  approved: "bg-emerald-700 text-emerald-200",
  rejected: "bg-rose-700 text-rose-200",
  deprecated: "bg-orange-700 text-orange-200",
  archived: "bg-slate-800 text-slate-400",
};

const ASSET_DIMENSION_LABELS: Record<string, string> = {
  identity_consistency: "Identity",
  semantic_correctness: "Semantic",
  style_consistency: "Style",
  composition_quality: "Composition",
  resolution_quality: "Resolution",
  format_quality: "Format",
  continuity_readiness: "Continuity",
  reuse_quality: "Reuse",
  renderer_compatibility: "Renderer",
  metadata_completeness: "Metadata",
  animation_readiness: "Animation",
};

type ViewTab = "all" | "environments" | "props" | "registry";

export default function AssetsPage({ jobId }: Props) {
  const [assets, setAssets] = useState<AssetInfo[]>([]);
  const [registry, setRegistry] = useState<RegistryInfo | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<AssetInfo | null>(null);
  const [quality, setQuality] = useState<AssetQualityScore | null>(null);
  const [tab, setTab] = useState<ViewTab>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [list, reg] = await Promise.all([
        assetApi.listAssets(jobId),
        assetApi.getRegistry(jobId),
      ]);
      setAssets(list.assets);
      setRegistry(reg);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function loadQuality(assetId: string) {
    try {
      const q = await assetApi.getQuality(assetId, jobId);
      if (q.quality_score) {
        setQuality(q as unknown as AssetQualityScore);
      }
    } catch {
      setQuality(null);
    }
  }

  useEffect(() => {
    load();
  }, [jobId]);

  useEffect(() => {
    if (selectedAsset) {
      loadQuality(selectedAsset.asset_id);
    } else {
      setQuality(null);
    }
  }, [selectedAsset]);

  const filteredAssets = assets.filter((a) => {
    if (tab === "environments") return a.asset_type === "environment";
    if (tab === "props") return a.asset_type === "prop";
    return true;
  });

  const statusClass = (status: string) =>
    LIFECYCLE_COLORS[status] || "bg-slate-700 text-slate-200";

  const typeClass = (type: string) =>
    ASSET_TYPE_COLORS[type] || "bg-slate-700 text-slate-200";

  if (loading) {
    return (
      <main className="max-w-7xl mx-auto p-8">
        <div className="text-slate-400">Loading assets…</div>
      </main>
    );
  }

  return (
    <main className="max-w-7xl mx-auto p-8 space-y-6">
      {/* Header */}
      <div>
        <Link href={`/jobs/${jobId}`} className="text-sm text-slate-400 hover:text-accent">
          ← Back to job
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Assets</h1>
          {registry && (
            <div className="text-sm text-slate-400 mt-1">
              {registry.asset_count} assets registered ·{" "}
              {registry.global_assets.length} global
            </div>
          )}
        </div>

        {/* Stats */}
        {registry && (
          <div className="flex gap-3">
            <div className="bg-slate-800 rounded px-4 py-2 text-center">
              <div className="text-2xl font-bold">{registry.asset_count}</div>
              <div className="text-xs text-slate-400">Total Assets</div>
            </div>
            <div className="bg-slate-800 rounded px-4 py-2 text-center">
              <div className="text-2xl font-bold">
                {assets.filter((a) => a.asset_type === "environment").length}
              </div>
              <div className="text-xs text-slate-400">Environments</div>
            </div>
            <div className="bg-slate-800 rounded px-4 py-2 text-center">
              <div className="text-2xl font-bold">
                {assets.filter((a) => a.asset_type === "prop").length}
              </div>
              <div className="text-xs text-slate-400">Props</div>
            </div>
            <div className="bg-slate-800 rounded px-4 py-2 text-center">
              <div className="text-2xl font-bold">
                {registry.global_assets.length}
              </div>
              <div className="text-xs text-slate-400">Global</div>
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-rose-900/30 border border-rose-700 rounded p-4">
          <div className="text-rose-300">Error: {error}</div>
          <div className="text-slate-400 text-sm mt-2">
            Asset system may not have been run yet.
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700">
        {(["all", "environments", "props", "registry"] as ViewTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t !== "registry" && (
              <span className="ml-2 text-xs text-slate-500">
                {t === "all"
                  ? assets.length
                  : assets.filter((a) =>
                      t === "environments"
                        ? a.asset_type === "environment"
                        : a.asset_type === "prop"
                    ).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Registry tab */}
      {tab === "registry" && registry && (
        <div className="bg-slate-800 rounded p-6 space-y-4">
          <h2 className="text-xl font-bold">Asset Registry</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-slate-400">Project ID</div>
              <div className="font-mono">{registry.project_id || "(default)"}</div>
            </div>
            <div>
              <div className="text-slate-400">Total Assets</div>
              <div className="text-xl font-bold">{registry.asset_count}</div>
            </div>
            <div>
              <div className="text-slate-400">Global Assets</div>
              <div className="space-y-1 mt-1">
                {registry.global_assets.length === 0 ? (
                  <div className="text-slate-500">None</div>
                ) : (
                  registry.global_assets.map((ga) => (
                    <div key={ga} className="flex items-center gap-2">
                      <span className="font-mono text-xs bg-slate-700 px-2 py-0.5 rounded">
                        {ga}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
            <div>
              <div className="text-slate-400">Last Updated</div>
              <div className="text-slate-300">
                {new Date(registry.updated_at).toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Assets grid */}
      {tab !== "registry" && (
        <>
          {filteredAssets.length === 0 ? (
            <div className="bg-slate-800 rounded p-8 text-center text-slate-400">
              No assets found. Run the Asset System to generate assets.
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Sidebar list */}
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
                  {tab === "all" ? "All Assets" : tab === "environments" ? "Environments" : "Props"}
                </h2>
                {filteredAssets.map((asset) => {
                  const isSelected = asset.asset_id === selectedAsset?.asset_id;
                  return (
                    <div
                      key={asset.asset_id}
                      onClick={() => setSelectedAsset(asset)}
                      className={`p-3 rounded cursor-pointer border transition-colors ${
                        isSelected
                          ? "bg-slate-700 border-slate-500"
                          : "bg-slate-800 border-slate-700 hover:border-slate-600"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm">{asset.asset_id}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${typeClass(asset.asset_type)}`}>
                          {asset.asset_type}
                        </span>
                      </div>
                      {asset.name && (
                        <div className="text-sm text-slate-300 mt-1">{asset.name}</div>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`px-2 py-0.5 rounded text-xs ${statusClass(asset.lifecycle)}`}>
                          {asset.lifecycle}
                        </span>
                        <span className="text-xs text-slate-500">v{asset.version}</span>
                        {asset.quality_score !== null && asset.quality_score !== undefined && (
                          <span className="text-xs text-slate-400 ml-auto">
                            {(asset.quality_score * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Detail panel */}
              <div className="lg:col-span-2 space-y-4">
                {selectedAsset ? (
                  <>
                    {/* Asset header */}
                    <div className="bg-slate-800 rounded p-4">
                      <div className="flex items-start justify-between">
                        <div>
                          <h2 className="text-2xl font-bold">
                            {selectedAsset.name || selectedAsset.asset_id}
                          </h2>
                          <div className="text-sm text-slate-400 mt-1">
                            <span className="font-mono">{selectedAsset.asset_id}</span>
                            {selectedAsset.semantic_role && (
                              <span> · {selectedAsset.semantic_role}</span>
                            )}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <span className={`px-3 py-1 rounded text-sm ${typeClass(selectedAsset.asset_type)}`}>
                            {selectedAsset.asset_type}
                          </span>
                          <span className={`px-3 py-1 rounded text-sm ${statusClass(selectedAsset.lifecycle)}`}>
                            {selectedAsset.lifecycle}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 mt-3 text-sm text-slate-400">
                        <span>version: {selectedAsset.version}</span>
                        <span>scenes: {selectedAsset.scene_count}</span>
                        <span>created: {new Date(selectedAsset.created_at).toLocaleDateString()}</span>
                      </div>

                      {selectedAsset.semantic_role && (
                        <p className="text-sm text-slate-300 mt-3">{selectedAsset.semantic_role}</p>
                      )}

                      {selectedAsset.primary_asset_uri && (
                        <div className="mt-3 text-sm">
                          <div className="text-slate-400">URI</div>
                          <div className="font-mono text-xs text-slate-300 bg-slate-900 rounded px-2 py-1 mt-1">
                            {selectedAsset.primary_asset_uri}
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex gap-2 mt-4">
                        {selectedAsset.lifecycle !== "approved" && (
                          <button
                            onClick={async () => {
                              await assetApi.approveAsset(selectedAsset.asset_id);
                              await load();
                            }}
                            className="px-3 py-1 bg-emerald-700 hover:bg-emerald-600 rounded text-sm"
                          >
                            Approve
                          </button>
                        )}
                        {selectedAsset.lifecycle !== "deprecated" && (
                          <button
                            onClick={async () => {
                              const reason = window.prompt("Deprecation reason (optional):") || "";
                              await assetApi.deprecateAsset(selectedAsset.asset_id, reason);
                              await load();
                            }}
                            className="px-3 py-1 bg-rose-700 hover:bg-rose-600 rounded text-sm"
                          >
                            Deprecate
                          </button>
                        )}
                        <button
                          onClick={async () => {
                            await assetApi.validateAsset(selectedAsset.asset_id);
                            await load();
                          }}
                          className="px-3 py-1 bg-blue-800 hover:bg-blue-700 rounded text-sm"
                        >
                          Validate
                        </button>
                      </div>
                    </div>

                    {/* Quality score */}
                    {quality ? (
                      <div className="bg-slate-800 rounded p-4">
                        <h3 className="text-sm font-semibold text-slate-400 mb-3">
                          Quality Score:{" "}
                          <span className="text-white">
                            {quality.overall_score > 0
                              ? `${(quality.overall_score * 100).toFixed(1)}%`
                              : "—"}
                          </span>
                        </h3>
                        <div className="grid grid-cols-2 gap-2">
                          {Object.entries(quality.dimension_scores).map(([dim, score]) => (
                            <div key={dim} className="flex items-center gap-2">
                              <div className="flex-1">
                                <div className="text-xs text-slate-400 flex justify-between">
                                  <span>{ASSET_DIMENSION_LABELS[dim] || dim}</span>
                                  <span>{(score * 100).toFixed(0)}%</span>
                                </div>
                                <div className="h-1.5 bg-slate-700 rounded mt-1">
                                  <div
                                    className="h-full bg-blue-500 rounded"
                                    style={{ width: `${score * 100}%` }}
                                  />
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>

                        {quality.warnings.length > 0 && (
                          <div className="mt-3 space-y-1">
                            {quality.warnings.map((w, i) => (
                              <div key={i} className="text-xs text-amber-300">⚠ {w}</div>
                            ))}
                          </div>
                        )}
                        {quality.failures.length > 0 && (
                          <div className="mt-3 space-y-1">
                            {quality.failures.map((f, i) => (
                              <div key={i} className="text-xs text-rose-300">✗ {f}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="bg-slate-800 rounded p-4">
                        <div className="text-sm text-slate-400">
                          Click "Validate" to compute quality score
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="bg-slate-800 rounded p-4 text-slate-400 text-center py-12">
                    Select an asset to view details
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </main>
  );
}

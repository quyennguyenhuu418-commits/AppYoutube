"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { characterApi, CharacterPreview, CharacterInfo, CharacterQualityScore } from "@/lib/api";

interface Props {
  jobId: string;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-700 text-slate-200",
  design: "bg-amber-700 text-amber-100",
  approved: "bg-emerald-700 text-emerald-100",
  active: "bg-blue-700 text-blue-100",
  deprecated: "bg-rose-700 text-rose-200",
};

const DIMENSION_LABELS: Record<string, string> = {
  identity_consistency: "Identity",
  proportion_consistency: "Proportions",
  silhouette_quality: "Silhouette",
  style_consistency: "Style",
  wardrobe_consistency: "Wardrobe",
  pose_coverage: "Pose Coverage",
  expression_coverage: "Expression",
  component_completeness: "Components",
  animation_readiness: "Animation",
  asset_format_quality: "Asset Format",
  continuity_readiness: "Continuity",
};

export default function CharactersPage({ jobId }: Props) {
  const [preview, setPreview] = useState<CharacterPreview | null>(null);
  const [characters, setCharacters] = useState<CharacterInfo[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [quality, setQuality] = useState<Record<string, CharacterQualityScore>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [svgData, setSvgData] = useState<string>("");
  const [loadingSvg, setLoadingSvg] = useState(false);

  async function load() {
    try {
      const prev = await characterApi.getPreview(jobId);
      setPreview(prev);

      const list = await characterApi.listCharacters(jobId);
      setCharacters(list.characters);

      // Load quality scores for all characters
      const qScores: Record<string, CharacterQualityScore> = {};
      for (const char of list.characters) {
        try {
          qScores[char.character_id] = await characterApi.getQuality(jobId, char.character_id);
        } catch {
          // Quality may not be available
        }
      }
      setQuality(qScores);

      // Auto-select first character
      if (list.characters.length > 0 && !selectedId) {
        setSelectedId(list.characters[0].character_id);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function loadSvg(characterId: string) {
    setLoadingSvg(true);
    try {
      const res = await fetch(`/api/characters/${jobId}/characters/${characterId}/preview`);
      if (res.ok) {
        setSvgData(await res.text());
      }
    } catch {
      // SVG may not be available
    } finally {
      setLoadingSvg(false);
    }
  }

  useEffect(() => {
    load();
  }, [jobId]);

  useEffect(() => {
    if (selectedId) {
      loadSvg(selectedId);
    }
  }, [selectedId, jobId]);

  async function approveChar(characterId: string) {
    await characterApi.approveCharacter(jobId, characterId);
    await load();
  }

  async function deprecateChar(characterId: string) {
    const reason = window.prompt("Deprecation reason (optional):") || "";
    await characterApi.deprecateCharacter(jobId, characterId, reason);
    await load();
  }

  if (loading) {
    return (
      <main className="max-w-6xl mx-auto p-8">
        <div className="text-slate-400">Loading characters…</div>
      </main>
    );
  }

  if (error && !preview) {
    return (
      <main className="max-w-6xl mx-auto p-8 space-y-4">
        <div>
          <Link href={`/jobs/${jobId}`} className="text-sm text-slate-400 hover:text-accent">
            ← Back to job
          </Link>
        </div>
        <h1 className="text-3xl font-bold">Characters</h1>
        <div className="bg-rose-900/30 border border-rose-700 rounded p-4">
          <div className="text-rose-300">Error: {error}</div>
          <div className="text-slate-400 text-sm mt-2">
            Character system may not have been run yet. Make sure the job has run s5_storyboard first.
          </div>
        </div>
      </main>
    );
  }

  const selected = characters.find((c) => c.character_id === selectedId);
  const selectedQuality = selectedId ? quality[selectedId] : null;

  return (
    <main className="max-w-6xl mx-auto p-8 space-y-6">
      <div>
        <Link href={`/jobs/${jobId}`} className="text-sm text-slate-400 hover:text-accent">
          ← Back to job
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Characters</h1>
          {preview && (
            <div className="text-sm text-slate-400 mt-1">
              {preview.character_count} characters · {preview.instance_count} scene instances
            </div>
          )}
        </div>
        {preview && (
          <div className="flex gap-3">
            <div className="bg-slate-800 rounded px-4 py-2 text-center">
              <div className="text-2xl font-bold">{preview.character_count}</div>
              <div className="text-xs text-slate-400">Characters</div>
            </div>
            <div className="bg-slate-800 rounded px-4 py-2 text-center">
              <div className="text-2xl font-bold">{preview.pose_count}</div>
              <div className="text-xs text-slate-400">Poses</div>
            </div>
            <div className="bg-slate-800 rounded px-4 py-2 text-center">
              <div className="text-2xl font-bold">{preview.expression_count}</div>
              <div className="text-xs text-slate-400">Expressions</div>
            </div>
            <div className="bg-slate-800 rounded px-4 py-2 text-center">
              <div className="text-2xl font-bold">
                {preview.overall_quality_score > 0
                  ? `${(preview.overall_quality_score * 100).toFixed(0)}%`
                  : "—"}
              </div>
              <div className="text-xs text-slate-400">Quality</div>
            </div>
          </div>
        )}
      </div>

      {preview && preview.warnings.length > 0 && (
        <div className="bg-amber-900/30 border border-amber-700 rounded p-4">
          <div className="text-amber-300 font-medium mb-2">Warnings ({preview.warnings.length})</div>
          <ul className="space-y-1 text-sm">
            {preview.warnings.slice(0, 5).map((w, i) => (
              <li key={i} className="text-amber-200">• {w}</li>
            ))}
          </ul>
        </div>
      )}

      {preview && preview.failures.length > 0 && (
        <div className="bg-rose-900/30 border border-rose-700 rounded p-4">
          <div className="text-rose-300 font-medium mb-2">Failures ({preview.failures.length})</div>
          <ul className="space-y-1 text-sm">
            {preview.failures.map((f, i) => (
              <li key={i} className="text-rose-200">• {f}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Character list */}
      {characters.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Sidebar: character list */}
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
              All Characters
            </h2>
            {characters.map((char) => {
              const q = quality[char.character_id];
              const isSelected = char.character_id === selectedId;
              const statusClass = STATUS_COLORS[char.status] || "bg-slate-700 text-slate-200";
              return (
                <div
                  key={char.character_id}
                  onClick={() => setSelectedId(char.character_id)}
                  className={`p-3 rounded cursor-pointer border transition-colors ${
                    isSelected
                      ? "bg-slate-700 border-slate-500"
                      : "bg-slate-800 border-slate-700 hover:border-slate-600"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm">{char.character_id}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${statusClass}`}>
                      {char.status}
                    </span>
                  </div>
                  {char.name && (
                    <div className="text-sm text-slate-300 mt-1">{char.name}</div>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className="w-3 h-3 rounded-sm"
                      style={{ backgroundColor: char.color }}
                      title={char.color}
                    />
                    <span className="text-xs text-slate-400">{char.category}</span>
                    {q && (
                      <span className="text-xs text-slate-400 ml-auto">
                        {q.overall_score > 0 ? `${(q.overall_score * 100).toFixed(0)}%` : "—"}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Detail panel */}
          <div className="lg:col-span-2 space-y-4">
            {selected ? (
              <>
                {/* Character header */}
                <div className="bg-slate-800 rounded p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h2 className="text-2xl font-bold">{selected.name || selected.character_id}</h2>
                      <div className="text-sm text-slate-400 mt-1">
                        <span className="font-mono">{selected.character_id}</span>
                        {selected.role && <span> · {selected.role}</span>}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {selected.status !== "approved" && selected.status !== "deprecated" && (
                        <button
                          onClick={() => approveChar(selected.character_id)}
                          className="px-3 py-1 bg-emerald-700 hover:bg-emerald-600 rounded text-sm"
                        >
                          Approve
                        </button>
                      )}
                      {selected.status !== "deprecated" && (
                        <button
                          onClick={() => deprecateChar(selected.character_id)}
                          className="px-3 py-1 bg-rose-700 hover:bg-rose-600 rounded text-sm"
                        >
                          Deprecate
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 mt-3 text-sm">
                    <span
                      className="px-3 py-1 rounded"
                      style={{ backgroundColor: selected.color, color: "#fff" }}
                      title={selected.color}
                    >
                      {selected.color}
                    </span>
                    <span className="text-slate-400">pose: {selected.default_pose}</span>
                    <span className="text-slate-400">expr: {selected.default_expression}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[selected.status] || ""}`}>
                      {selected.status}
                    </span>
                    <span className="text-slate-500 text-xs">v{selected.version}</span>
                  </div>

                  {selected.description && (
                    <p className="text-sm text-slate-300 mt-3">{selected.description}</p>
                  )}
                </div>

                {/* SVG Preview */}
                <div className="bg-slate-800 rounded p-4">
                  <h3 className="text-sm font-semibold text-slate-400 mb-3">Preview</h3>
                  <div className="flex justify-center">
                    {loadingSvg ? (
                      <div className="text-slate-500 text-sm">Loading preview…</div>
                    ) : svgData ? (
                      <div
                        dangerouslySetInnerHTML={{ __html: svgData }}
                        className="max-w-xs"
                      />
                    ) : (
                      <div className="text-slate-500 text-sm">No preview available</div>
                    )}
                  </div>
                </div>

                {/* Quality score */}
                {selectedQuality && (
                  <div className="bg-slate-800 rounded p-4">
                    <h3 className="text-sm font-semibold text-slate-400 mb-3">
                      Quality Score:{" "}
                      <span className="text-white">
                        {selectedQuality.overall_score > 0
                          ? `${(selectedQuality.overall_score * 100).toFixed(1)}%`
                          : "—"}
                      </span>
                    </h3>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(selectedQuality.dimension_scores).map(([dim, score]) => (
                        <div key={dim} className="flex items-center gap-2">
                          <div className="flex-1">
                            <div className="text-xs text-slate-400 flex justify-between">
                              <span>{DIMENSION_LABELS[dim] || dim}</span>
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

                    {selectedQuality.warnings.length > 0 && (
                      <div className="mt-3 space-y-1">
                        {selectedQuality.warnings.map((w, i) => (
                          <div key={i} className="text-xs text-amber-300">⚠ {w}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div className="bg-slate-800 rounded p-4 text-slate-400 text-center py-12">
                Select a character to view details
              </div>
            )}
          </div>
        </div>
      )}

      {characters.length === 0 && preview && (
        <div className="bg-slate-800 rounded p-8 text-center text-slate-400">
          No characters found. Make sure the job has a storyboard with character requirements.
        </div>
      )}
    </main>
  );
}

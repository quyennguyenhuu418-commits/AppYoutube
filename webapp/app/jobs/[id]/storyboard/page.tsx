"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  StoryboardPackage,
  StoryboardBeat,
  StoryboardPreview,
} from "@/lib/api";

interface Props {
  jobId: string;
}

const VISUAL_MODE_COLORS: Record<string, string> = {
  character: "bg-emerald-700 text-emerald-100",
  environment: "bg-sky-700 text-sky-100",
  diagram: "bg-indigo-700 text-indigo-100",
  map: "bg-amber-700 text-amber-100",
  timeline: "bg-purple-700 text-purple-100",
  comparison: "bg-rose-700 text-rose-100",
  artifact: "bg-orange-700 text-orange-100",
  text_graphic: "bg-slate-700 text-slate-100",
  data_visualization: "bg-teal-700 text-teal-100",
  archival: "bg-stone-700 text-stone-100",
  hybrid: "bg-fuchsia-700 text-fuchsia-100",
};

export default function StoryboardPage({ jobId }: Props) {
  const [preview, setPreview] = useState<StoryboardPreview | null>(null);
  const [pkg, setPkg] = useState<StoryboardPackage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [p, full] = await Promise.all([
        api.getStoryboardPreview(jobId),
        api.getStoryboard(jobId).catch(() => null),
      ]);
      setPreview(p);
      setPkg(full);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [jobId]);

  async function approve() {
    await api.approveStoryboard(jobId);
    await load();
  }

  async function reject() {
    const notes = window.prompt("Rejection notes (optional):") || "";
    await api.rejectStoryboard(jobId, notes);
    await load();
  }

  if (loading) {
    return (
      <main className="max-w-5xl mx-auto p-8">
        <div className="text-slate-400">Loading storyboard…</div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="max-w-5xl mx-auto p-8 space-y-4">
        <div>
          <Link href={`/jobs/${jobId}`} className="text-sm text-slate-400 hover:text-accent">
            ← Back to job
          </Link>
        </div>
        <h1 className="text-3xl font-bold">Storyboard</h1>
        <div className="bg-rose-900/30 border border-rose-700 rounded p-4">
          <div className="text-rose-300">Error: {error}</div>
          <div className="text-slate-400 text-sm mt-2">
            Make sure the job has run s2_thesis (story package) and s5_storyboard stages.
          </div>
        </div>
      </main>
    );
  }

  if (!preview) {
    return (
      <main className="max-w-5xl mx-auto p-8">
        <div className="text-slate-400">No storyboard data.</div>
      </main>
    );
  }

  return (
    <main className="max-w-5xl mx-auto p-8 space-y-6">
      <div>
        <Link href={`/jobs/${jobId}`} className="text-sm text-slate-400 hover:text-accent">
          ← Back to job
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Storyboard</h1>
          <div className="text-sm text-slate-400 mt-1">
            {preview.storyboard_package_id}
          </div>
        </div>
        <div className="flex gap-2 items-center">
          <Link
            href={`/jobs/${jobId}/characters`}
            className="px-4 py-2 bg-blue-700 hover:bg-blue-600 rounded text-sm font-medium"
          >
            View Characters →
          </Link>
          <Link
            href={`/jobs/${jobId}/assets`}
            className="px-4 py-2 bg-blue-700 hover:bg-blue-600 rounded text-sm font-medium"
          >
            View Assets →
          </Link>
          <button
            onClick={approve}
            disabled={preview.status === "approved"}
            className="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 disabled:bg-slate-700 disabled:text-slate-500 rounded font-medium"
          >
            Approve
          </button>
          <button
            onClick={reject}
            disabled={preview.status === "rejected"}
            className="px-4 py-2 bg-rose-700 hover:bg-rose-600 disabled:bg-slate-700 disabled:text-slate-500 rounded font-medium"
          >
            Reject
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Beats" value={preview.beat_count} />
        <StatCard label="Scenes" value={preview.scene_candidate_count} />
        <StatCard label="Assets" value={preview.asset_count} />
        <StatCard
          label="Quality"
          value={`${(preview.quality_overall * 100).toFixed(0)}%`}
        />
      </div>

      <div className="bg-slate-800 rounded p-4">
        <div className="text-sm text-slate-400 mb-2">Status</div>
        <div className="text-lg capitalize">{preview.status}</div>
      </div>

      {preview.warnings.length > 0 && (
        <div className="bg-amber-900/30 border border-amber-700 rounded p-4">
          <div className="text-amber-300 font-medium mb-2">
            Warnings ({preview.warnings.length})
          </div>
          <ul className="space-y-1 text-sm">
            {preview.warnings.map((w, i) => (
              <li key={i} className="text-amber-200">
                • {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {preview.failures.length > 0 && (
        <div className="bg-rose-900/30 border border-rose-700 rounded p-4">
          <div className="text-rose-300 font-medium mb-2">
            Failures ({preview.failures.length})
          </div>
          <ul className="space-y-1 text-sm">
            {preview.failures.map((f, i) => (
              <li key={i} className="text-rose-200">
                • {f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {pkg?.visual_beats && (
        <div>
          <h2 className="text-xl font-bold mb-3">Visual Beats</h2>
          <div className="space-y-3">
            {pkg.visual_beats.map((beat: StoryboardBeat) => (
              <BeatCard key={beat.beat_id} beat={beat} />
            ))}
          </div>
        </div>
      )}

      {pkg?.asset_requirements && pkg.asset_requirements.length > 0 && (
        <div>
          <h2 className="text-xl font-bold mb-3">Asset Requirements</h2>
          <div className="grid grid-cols-2 gap-3">
            {pkg.asset_requirements.map((a) => (
              <div key={a.asset_id} className="bg-slate-800 rounded p-3">
                <div className="font-mono text-sm">{a.asset_id}</div>
                <div className="text-xs text-slate-400 mt-1">
                  {a.asset_class} · {a.requirement}
                </div>
                {a.purpose && (
                  <div className="text-sm mt-1">{a.purpose}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-slate-800 rounded p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}

function BeatCard({ beat }: { beat: StoryboardBeat }) {
  const modeClass = VISUAL_MODE_COLORS[beat.visual_mode] || "bg-slate-700 text-slate-100";

  return (
    <div className="bg-slate-800 rounded p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm">{beat.beat_id}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${modeClass}`}>
            {beat.visual_mode}
          </span>
          <span className="text-xs text-slate-400">
            {beat.start_time.toFixed(1)}s → {beat.end_time.toFixed(1)}s
          </span>
        </div>
        <span className="text-xs text-slate-500">
          {beat.purpose} · {beat.visual_function}
        </span>
      </div>

      {beat.action && (
        <div className="text-sm text-slate-300">
          <span className="text-slate-500">Action:</span> {beat.action}
        </div>
      )}

      {beat.visual_rationale && (
        <div className="text-xs text-slate-400 italic">
          {beat.visual_rationale}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-slate-500">Characters</div>
          <div>{beat.characters.length}</div>
        </div>
        <div>
          <div className="text-slate-500">Camera</div>
          <div>{beat.camera?.type || "—"}</div>
        </div>
        <div>
          <div className="text-slate-500">Transition</div>
          <div>{beat.transition}</div>
        </div>
      </div>

      {beat.claim_ids.length > 0 && (
        <div className="text-xs text-slate-400">
          Claims: {beat.claim_ids.join(", ")}
        </div>
      )}
    </div>
  );
}

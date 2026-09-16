"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { mediaApi, type ShortsStageResult } from "@/lib/api";

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(1);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

const QUALITY_BADGE: Record<string, { bg: string; label: string }> = {
  draft:    { bg: "bg-slate-700 text-slate-300", label: "Draft" },
  standard: { bg: "bg-blue-900/60 text-blue-200", label: "Standard" },
  high:     { bg: "bg-green-900/60 text-green-200", label: "High" },
  max:      { bg: "bg-purple-900/60 text-purple-200", label: "Max" },
};

const QA_BADGE: Record<string, { bg: string; icon: string }> = {
  true:  { bg: "bg-green-900/60 text-green-200", icon: "✓" },
  false: { bg: "bg-red-900/60 text-red-200", icon: "✗" },
};

export default function ShortsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [result, setResult] = useState<ShortsStageResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mediaApi.getShorts(id)
      .then(setResult)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <main className="max-w-4xl mx-auto p-8">
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
        <div className="mt-8 text-slate-400">Loading shorts...</div>
      </main>
    );
  }

  if (error || !result) {
    return (
      <main className="max-w-4xl mx-auto p-8 space-y-6">
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
        <h1 className="text-3xl font-bold">Shorts</h1>
        <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
          Shorts not available: {error || "no shorts generated yet"}
        </div>
      </main>
    );
  }

  const { shorts, fingerprint } = result;

  return (
    <main className="max-w-5xl mx-auto p-8 space-y-8">
      <div>
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
      </div>

      <header className="flex items-center gap-4">
        <h1 className="text-3xl font-bold">SHORTS</h1>
        <span className="px-3 py-1 rounded text-sm font-medium bg-blue-900/60 text-blue-200">
          {shorts.length} clip{shorts.length !== 1 ? "s" : ""}
        </span>
      </header>

      {/* Pipeline note */}
      <div className="rounded-lg bg-slate-800/50 border border-slate-700 px-4 py-3 text-sm text-slate-300">
        <strong>9:16 Vertical Clips</strong> — Each short is an intelligent crop from the 16:9 horizontal video,
        optimized for TikTok, YouTube Shorts, and Instagram Reels.
        Crop center is determined by subject tracking and scene composition.
      </div>

      {/* Shorts grid */}
      {shorts.length === 0 ? (
        <div className="text-slate-400 text-center py-12">
          No shorts generated yet. Run the shorts stage to generate 9:16 clips.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {shorts.map((short) => {
            const qa = short.qa;
            const qaIcon = QA_BADGE[String(qa.passed)] ?? QA_BADGE.false;

            return (
              <div key={short.shorts_id} className="rounded-xl overflow-hidden bg-slate-800/60 border border-slate-700">
                {/* Video preview */}
                <div className="aspect-[9/16] bg-black relative">
                  <video
                    controls
                    preload="metadata"
                    src={mediaApi.shortsVideoUrl(id, short.shorts_id)}
                    className="w-full h-full object-cover"
                  />
                </div>

                {/* Info */}
                <div className="p-4 space-y-3">
                  {/* Scene label */}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-sm">{short.scene_label}</p>
                      <p className="text-xs text-slate-400">Scene: {short.scene_id}</p>
                    </div>
                    <span className={`shrink-0 w-6 h-6 rounded-full grid place-items-center text-xs ${qaIcon.bg}`}>
                      {qaIcon.icon}
                    </span>
                  </div>

                  {/* Metadata */}
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Duration</span>
                      <span className="font-mono">{formatDuration(short.duration_sec)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Resolution</span>
                      <span className="font-mono">{short.output_resolution}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Start</span>
                      <span className="font-mono">{formatDuration(short.start_sec)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Crop center</span>
                      <span className="font-mono">{short.crop_center_x.toFixed(1)}, {short.crop_center_y.toFixed(1)}</span>
                    </div>
                  </div>

                  {/* QA */}
                  <div className="pt-2 border-t border-slate-700 space-y-1">
                    <div className="flex items-center gap-2 text-xs">
                      <span className={`px-2 py-0.5 rounded ${qaIcon.bg}`}>
                        {qa.passed ? "QA PASS" : "QA FAIL"}
                      </span>
                      <span className="text-slate-400">
                        {qa.format_valid ? "✓ Format" : "✗ Format"}
                        {qa.aspect_ratio_correct ? " ✓ Aspect" : " ✗ Aspect"}
                        {qa.duration_within_limits ? " ✓ Duration" : " ✗ Duration"}
                      </span>
                    </div>
                    {qa.notes.length > 0 && (
                      <p className="text-xs text-slate-400 truncate">{qa.notes.join("; ")}</p>
                    )}
                  </div>

                  {/* Download */}
                  <a
                    href={mediaApi.shortsVideoUrl(id, short.shorts_id)}
                    download={`short-${short.scene_id}.mp4`}
                    className="flex items-center justify-center gap-2 w-full py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-medium transition-colors"
                  >
                    ⬇ Download MP4
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Fingerprint */}
      <div className="pt-4 border-t border-slate-800">
        <p className="text-xs text-slate-500">
          Shorts fingerprint: <span className="font-mono">{fingerprint}</span>
        </p>
      </div>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { mediaApi, type ThumbnailStageResult } from "@/lib/api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

const FORMAT_BADGE: Record<string, { bg: string }> = {
  webp:  { bg: "bg-blue-900/60 text-blue-200" },
  jpeg:  { bg: "bg-green-900/60 text-green-200" },
  png:   { bg: "bg-purple-900/60 text-purple-200" },
};

const QA_BADGE: Record<string, { bg: string; icon: string }> = {
  true:  { bg: "bg-green-900/60 text-green-200", icon: "✓" },
  false: { bg: "bg-red-900/60 text-red-200", icon: "✗" },
};

export default function ThumbnailsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [result, setResult] = useState<ThumbnailStageResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mediaApi.getThumbnails(id)
      .then(setResult)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <main className="max-w-5xl mx-auto p-8">
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
        <div className="mt-8 text-slate-400">Loading thumbnails...</div>
      </main>
    );
  }

  if (error || !result) {
    return (
      <main className="max-w-5xl mx-auto p-8 space-y-6">
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
        <h1 className="text-3xl font-bold">Thumbnails</h1>
        <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
          Thumbnails not available: {error || "no thumbnails generated yet"}
        </div>
      </main>
    );
  }

  const { thumbnails, fingerprint } = result;

  return (
    <main className="max-w-5xl mx-auto p-8 space-y-8">
      <div>
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
      </div>

      <header className="flex items-center gap-4">
        <h1 className="text-3xl font-bold">THUMBNAILS</h1>
        <span className="px-3 py-1 rounded text-sm font-medium bg-blue-900/60 text-blue-200">
          {thumbnails.length} image{thumbnails.length !== 1 ? "s" : ""}
        </span>
      </header>

      {/* Info */}
      <div className="rounded-lg bg-slate-800/50 border border-slate-700 px-4 py-3 text-sm text-slate-300">
        <strong>Static Preview Images</strong> — Thumbnails represent the video in previews and listings
        across YouTube, Twitter, and Instagram. Generated from key scenes and the title card.
      </div>

      {/* Thumbnails grid */}
      {thumbnails.length === 0 ? (
        <div className="text-slate-400 text-center py-12">
          No thumbnails generated yet. Run the thumbnail stage to generate preview images.
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {thumbnails.map((tn) => {
            const qa = tn.qa;
            const qaBadge = QA_BADGE[String(qa.passed)] ?? QA_BADGE.false;
            const formatBadge = FORMAT_BADGE[tn.format] ?? { bg: "bg-slate-700 text-slate-300" };

            return (
              <div
                key={tn.thumbnail_id}
                className="rounded-xl overflow-hidden bg-slate-800/60 border border-slate-700"
              >
                {/* Image */}
                <div className="aspect-video bg-black relative">
                  <img
                    src={mediaApi.thumbnailUrl(id, tn.thumbnail_id)}
                    alt={tn.caption || tn.output_filename}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  {/* Format badge */}
                  <span className={`absolute top-2 right-2 px-2 py-0.5 rounded text-xs font-medium ${formatBadge.bg}`}>
                    {tn.format.toUpperCase()}
                  </span>
                </div>

                {/* Info */}
                <div className="p-3 space-y-2">
                  {/* Caption */}
                  {tn.caption && (
                    <p className="text-xs text-slate-300 line-clamp-2 leading-snug">
                      {tn.caption}
                    </p>
                  )}

                  {/* Metadata */}
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>{tn.dimensions}</span>
                    <span>{formatBytes(qa.file_size_bytes)}</span>
                  </div>

                  {/* QA */}
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${qaBadge.bg}`}>
                      {qaBadge.icon} {qa.passed ? "OK" : "FAIL"}
                    </span>
                    {tn.output_filename && (
                      <span className="text-xs text-slate-500 truncate">{tn.output_filename}</span>
                    )}
                  </div>

                  {/* Download */}
                  <a
                    href={mediaApi.thumbnailUrl(id, tn.thumbnail_id)}
                    download={tn.output_filename}
                    className="flex items-center justify-center gap-1 w-full py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-xs font-medium transition-colors"
                  >
                    ⬇ Save
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
          Thumbnail plan fingerprint: <span className="font-mono">{fingerprint}</span>
        </p>
      </div>
    </main>
  );
}

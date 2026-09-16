"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { api, type JobDetail } from "@/lib/api";
import { StageTimeline } from "@/components/StageTimeline";
import { VideoPlayer } from "@/components/VideoPlayer";
import { vi } from "@/lib/i18n";

const POLL_MS = 2500;

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const j = await api.getJob(id);
        if (cancelled) return;
        setJob(j);
        if (j.status === "running" || j.status === "pending") {
          timer = setTimeout(tick, POLL_MS);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  if (error) return <div className="text-red-400">{vi.errorLoadJob}: {error}</div>;
  if (!job) return <div className="text-slate-400">{vi.loading}</div>;

  return (
    <main className="max-w-4xl mx-auto p-8 space-y-8">
      <div>
        <Link href="/" className="text-sm text-slate-400 hover:text-accent">{vi.backToHome}</Link>
      </div>

      <header>
        <h1 className="text-3xl font-bold">{job.title || job.topic}</h1>
        <div className="text-slate-400 text-sm mt-1">
          Chủ đề: {job.topic}
        </div>
        <div className="text-slate-500 text-xs mt-1">
          Trạng thái: <span className="font-mono">{vi.status[job.status as keyof typeof vi.status] || job.status}</span>
        </div>
      </header>

      <section>
        <h2 className="text-xl font-semibold mb-3">{vi.pipeline}</h2>
        <StageTimeline stages={job.stages} />
      </section>

      <section>
        <div className="flex gap-3 flex-wrap">
          <Link
            href={`/jobs/${id}/storyboard`}
            className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium"
          >
            {vi.viewStoryboard}
          </Link>
          <Link
            href={`/jobs/${id}/characters`}
            className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium"
          >
            {vi.viewCharacters}
          </Link>
          <Link
            href={`/jobs/${id}/assets`}
            className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium"
          >
            {vi.viewAssets}
          </Link>
          <Link
            href={`/jobs/${id}/render`}
            className="inline-block px-4 py-2 bg-accent text-slate-900 hover:opacity-90 rounded text-sm font-medium"
          >
            {vi.finalRender}
          </Link>
        </div>
      </section>

      {/* Distribution & Publishing shortcuts (P13 + P14 + P15) */}
      <section>
        <h2 className="text-xl font-semibold mb-3">Distribution</h2>
        <div className="flex gap-3 flex-wrap">
          <Link
            href={`/jobs/${id}/shorts`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-900/40 hover:bg-blue-900/60 border border-blue-700 rounded text-sm font-medium text-blue-200 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="3" width="12" height="10" rx="1" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M6 7l2.5 1.5L6 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Shorts (9:16)
          </Link>
          <Link
            href={`/jobs/${id}/thumbnails`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-900/40 hover:bg-purple-900/60 border border-purple-700 rounded text-sm font-medium text-purple-200 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <rect x="1.5" y="2.5" width="13" height="11" rx="1" stroke="currentColor" strokeWidth="1.5"/>
              <circle cx="5.5" cy="6" r="1" fill="currentColor"/>
              <path d="M1.5 11l3.5-3 2 2 3-3 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Thumbnails
          </Link>
          <Link
            href={`/jobs/${id}/publishing`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-green-900/40 hover:bg-green-900/60 border border-green-700 rounded text-sm font-medium text-green-200 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M8 1L1 5v11h14V5L8 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
              <path d="M6 11.5l1.5-3 1.5 3M5.5 11.5h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Publish to YouTube / TikTok / Facebook
          </Link>
        </div>
      </section>

      {job.status === "completed" && (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">{vi.result}</h2>
          {job.artifacts?.video && (
            <VideoPlayer src={`/api${job.artifacts.video}`} label={vi.documentaryLabel} />
          )}
        </section>
      )}

      {job.status === "failed" && (
        <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
          {vi.jobFailed}: {job.error}
        </div>
      )}
    </main>
  );
}

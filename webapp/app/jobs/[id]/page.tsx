"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { api, type JobDetail } from "@/lib/api";
import { StageTimeline } from "@/components/StageTimeline";
import { VideoPlayer } from "@/components/VideoPlayer";

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

  if (error) return <div className="text-red-400">{error}</div>;
  if (!job) return <div className="text-slate-400">Loading...</div>;

  return (
    <main className="max-w-4xl mx-auto p-8 space-y-8">
      <div>
        <Link href="/" className="text-sm text-slate-400 hover:text-accent">← New video</Link>
      </div>

      <header>
        <h1 className="text-3xl font-bold">{job.title || job.topic}</h1>
        <div className="text-slate-400 text-sm mt-1">
          Topic: {job.topic}
        </div>
        <div className="text-slate-500 text-xs mt-1">
          Status: <span className="font-mono">{job.status}</span>
        </div>
      </header>

      <section>
        <h2 className="text-xl font-semibold mb-3">Pipeline</h2>
        <StageTimeline stages={job.stages} />
      </section>

      <section>
        <div className="flex gap-3">
          <Link
            href={`/jobs/${id}/storyboard`}
            className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium"
          >
            View Storyboard →
          </Link>
          <Link
            href={`/jobs/${id}/characters`}
            className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium"
          >
            View Characters →
          </Link>
          <Link
            href={`/jobs/${id}/assets`}
            className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium"
          >
            View Assets →
          </Link>
        </div>
      </section>

      {job.status === "completed" && (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Result</h2>
          {job.artifacts?.video && (
            <VideoPlayer src={`/api${job.artifacts.video}`} label="Final documentary (16:9)" />
          )}
        </section>
      )}

      {job.status === "failed" && (
        <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
          Job failed: {job.error}
        </div>
      )}
    </main>
  );
}

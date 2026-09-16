"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { renderApi, type RenderArtifact, type RenderQAReport, type RenderStatus } from "@/lib/api";

const STATUS_BADGE: Record<string, { bg: string; icon: string; label: string }> = {
  queued:     { bg: "bg-slate-700 text-slate-300",     icon: "•", label: "Queued" },
  preparing:  { bg: "bg-blue-900/60 text-blue-200",     icon: "⟳", label: "Preparing" },
  preflight:  { bg: "bg-blue-900/60 text-blue-200",     icon: "⟳", label: "Preflight" },
  rendering:  { bg: "bg-blue-900/60 text-blue-200",     icon: "⟳", label: "Rendering" },
  mastering:  { bg: "bg-blue-900/60 text-blue-200",     icon: "⟳", label: "Mastering" },
  qa:         { bg: "bg-blue-900/60 text-blue-200",     icon: "⟳", label: "QA" },
  finalizing: { bg: "bg-blue-900/60 text-blue-200",     icon: "⟳", label: "Finalizing" },
  approved:   { bg: "bg-green-900/60 text-green-200",   icon: "✓", label: "Approved" },
  failed:     { bg: "bg-red-900/60 text-red-200",       icon: "✗", label: "Failed" },
  cancelled:  { bg: "bg-slate-700 text-slate-300",     icon: "—", label: "Cancelled" },
};

const QA_STATUS_BADGE: Record<string, { bg: string; icon: string }> = {
  pass:        { bg: "bg-green-900/60 text-green-200",   icon: "✓" },
  warn:        { bg: "bg-amber-900/60 text-amber-200",   icon: "!" },
  fail:        { bg: "bg-red-900/60 text-red-200",       icon: "✗" },
  unavailable: { bg: "bg-slate-700 text-slate-300",      icon: "?" },
};

const POLL_MS = 2000;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(2);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function FinalRenderInspectorPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [status, setStatus] = useState<RenderStatus | null>(null);
  const [artifact, setArtifact] = useState<RenderArtifact | null>(null);
  const [qa, setQA] = useState<RenderQAReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      if (cancelled) return;
      try {
        const s = await renderApi.status(id);
        if (cancelled) return;
        setStatus(s);
        if (s.is_terminal && s.final_artifact_id) {
          try {
            const [a, q] = await Promise.all([
              renderApi.artifact(id),
              renderApi.qa(id).catch(() => null),
            ]);
            if (cancelled) return;
            setArtifact(a);
            setQA(q);
          } catch (e) {
            if (!cancelled) setError(String(e));
          }
        } else {
          // Re-poll while running
          timer = setTimeout(tick, POLL_MS);
        }
      } catch (e) {
        if (!cancelled) {
          setError(String(e));
          // Re-poll even on transient errors
          timer = setTimeout(tick, POLL_MS);
        }
      }
    }
    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  if (error && !status) {
    return (
      <main className="max-w-4xl mx-auto p-8 space-y-6">
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
        <h1 className="text-3xl font-bold">Final Render Inspector</h1>
        <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
          Error: {error}
        </div>
      </main>
    );
  }

  if (!status) {
    return (
      <main className="max-w-4xl mx-auto p-8 space-y-6">
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
        <h1 className="text-3xl font-bold">Final Render Inspector</h1>
        <div className="text-slate-400">Loading render status...</div>
      </main>
    );
  }

  const badge = STATUS_BADGE[status.lifecycle] ?? STATUS_BADGE.queued;
  const isApproved = status.lifecycle === "approved";
  const isFailed = status.lifecycle === "failed" || status.lifecycle === "cancelled";

  return (
    <main className="max-w-4xl mx-auto p-8 space-y-8">
      <div>
        <Link href={`/jobs/${id}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
      </div>

      <header className="flex items-center gap-4">
        <h1 className="text-3xl font-bold">FINAL RENDER</h1>
        <span className={`px-3 py-1 rounded text-sm font-medium ${badge.bg}`}>
          {badge.icon} {badge.label}
        </span>
      </header>

      <section>
        <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">Topic</h2>
        <p className="text-xl">{status.topic}</p>
      </section>

      {/* Pipeline Stages */}
      <section>
        <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">Pipeline</h2>
        <ol className="space-y-2">
          {status.stages.map((s) => {
            const b = STATUS_BADGE[s.status === "completed" ? "approved" : s.status === "failed" ? "failed" : s.status === "running" ? "rendering" : "queued"] ?? STATUS_BADGE.queued;
            return (
              <li key={s.name} className="flex items-center gap-3 rounded-lg bg-slate-800/50 px-4 py-2">
                <span className={`w-6 h-6 rounded-full grid place-items-center text-xs ${b.bg}`}>
                  {b.icon}
                </span>
                <span className="flex-1 capitalize">{s.label}</span>
                <span className="text-xs text-slate-500">{s.status}</span>
                {s.error && <span className="text-xs text-red-300 truncate max-w-md">{s.error}</span>}
              </li>
            );
          })}
        </ol>
        {status.error && (
          <div className="mt-4 rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
            <strong>{status.error_stage || "Failed"}:</strong> {status.error}
          </div>
        )}
      </section>

      {/* Approved — Video Preview */}
      {isApproved && artifact && (
        <>
          <section>
            <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">Final Video</h2>
            <div className="rounded-lg overflow-hidden bg-black">
              <video
                controls
                src={renderApi.videoUrl(id)}
                onError={() => setVideoError("Failed to load video. Try downloading instead.")}
                className="w-full"
              >
                Your browser does not support HTML5 video.
              </video>
              {videoError && (
                <div className="px-4 py-2 text-xs text-red-300">{videoError}</div>
              )}
            </div>
            <div className="mt-3 flex gap-3">
              <a
                href={renderApi.videoUrl(id)}
                download={`render-${id}.mp4`}
                className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium"
              >
                ⬇ Download MP4
              </a>
            </div>
          </section>

          {/* Media Metadata */}
          <section>
            <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">Media Metadata</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Resolution</dt>
                <dd className="font-mono">{artifact.width}×{artifact.height}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">FPS</dt>
                <dd className="font-mono">{artifact.fps.toFixed(2)}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Duration</dt>
                <dd className="font-mono">{formatDuration(artifact.duration_sec)}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">File Size</dt>
                <dd className="font-mono">{formatBytes(artifact.file_size_bytes)}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Video Codec</dt>
                <dd className="font-mono">{artifact.video_codec}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Audio Codec</dt>
                <dd className="font-mono">{artifact.audio_codec}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Sample Rate</dt>
                <dd className="font-mono">{artifact.audio_sample_rate_hz} Hz</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Channels</dt>
                <dd className="font-mono">{artifact.audio_channels}</dd>
              </div>
            </dl>
          </section>

          {/* Audio QA */}
          <section>
            <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">Audio QA</h2>
            <dl className="grid grid-cols-3 gap-4">
              <div className="rounded-lg bg-slate-800/50 px-4 py-3">
                <dt className="text-xs text-slate-400 uppercase tracking-wider">Integrated Loudness</dt>
                <dd className="text-2xl font-mono mt-1">
                  {artifact.loudness_lufs != null ? `${artifact.loudness_lufs.toFixed(1)} LUFS` : "—"}
                </dd>
              </div>
              <div className="rounded-lg bg-slate-800/50 px-4 py-3">
                <dt className="text-xs text-slate-400 uppercase tracking-wider">True Peak</dt>
                <dd className="text-2xl font-mono mt-1">
                  {artifact.true_peak_dbtp != null ? `${artifact.true_peak_dbtp.toFixed(1)} dBTP` : "—"}
                </dd>
              </div>
              <div className="rounded-lg bg-slate-800/50 px-4 py-3">
                <dt className="text-xs text-slate-400 uppercase tracking-wider">LRA</dt>
                <dd className="text-2xl font-mono mt-1">
                  {artifact.loudness_range_lu != null ? `${artifact.loudness_range_lu.toFixed(1)} LU` : "—"}
                </dd>
              </div>
            </dl>
          </section>

          {/* QA Report */}
          {qa && (
            <section>
              <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">
                QA Status — overall <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${QA_STATUS_BADGE[qa.overall_status]?.bg ?? "bg-slate-700"}`}>
                  {qa.overall_status}
                </span>
              </h2>
              <ul className="space-y-1 text-sm">
                {qa.checks.map((c) => {
                  const b = QA_STATUS_BADGE[c.status] ?? QA_STATUS_BADGE.unavailable;
                  return (
                    <li key={c.check_id} className="flex items-center gap-3 rounded-lg bg-slate-800/30 px-3 py-2">
                      <span className={`w-5 h-5 rounded-full grid place-items-center text-xs ${b.bg}`}>
                        {b.icon}
                      </span>
                      <span className="font-mono text-xs uppercase tracking-wider w-48">{c.check_id}</span>
                      <span className="text-slate-400 flex-1 truncate">{c.explanation}</span>
                    </li>
                  );
                })}
              </ul>
              {qa.warnings.length > 0 && (
                <div className="mt-3 text-sm text-amber-300">
                  <strong>Warnings:</strong>
                  <ul className="list-disc list-inside">
                    {qa.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}
              {qa.failures.length > 0 && (
                <div className="mt-3 text-sm text-red-300">
                  <strong>Failures:</strong>
                  <ul className="list-disc list-inside">
                    {qa.failures.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                </div>
              )}
            </section>
          )}

          {/* Checksum + Fingerprint */}
          <section>
            <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">Integrity</h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-xs text-slate-400 uppercase tracking-wider">SHA-256 Checksum</dt>
                <dd className="font-mono text-xs break-all bg-slate-800/30 px-3 py-2 rounded">
                  {artifact.checksum_sha256}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400 uppercase tracking-wider">Fingerprint</dt>
                <dd className="font-mono text-xs break-all bg-slate-800/30 px-3 py-2 rounded">
                  {artifact.fingerprint}
                </dd>
              </div>
            </dl>
          </section>

          {/* Provenance */}
          <section>
            <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">Provenance</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Renderer</dt>
                <dd className="font-mono text-xs">{artifact.renderer_version || "—"}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">FFmpeg</dt>
                <dd className="font-mono text-xs">{qa?.ffmpeg_version ?? "—"}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Render Profile</dt>
                <dd className="font-mono text-xs">{artifact.render_profile_id ?? "—"}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-800 py-1">
                <dt className="text-slate-400">Mastering Profile</dt>
                <dd className="font-mono text-xs">{artifact.mastering_profile_id ?? "—"}</dd>
              </div>
            </dl>
          </section>
        </>
      )}

      {/* Failure / Cancelled */}
      {isFailed && (
        <section className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3">
          <h2 className="font-semibold text-red-200">Render Failed</h2>
          {status.error && <p className="text-sm text-red-300 mt-2">{status.error}</p>}
          {status.error_stage && <p className="text-xs text-red-400 mt-1">Failed at stage: {status.error_stage}</p>}
        </section>
      )}

      {/* Running state */}
      {!isApproved && !isFailed && (
        <section className="text-sm text-slate-400">
          <p>Render in progress. This page polls every {POLL_MS / 1000}s.</p>
          <p className="mt-1">Progress: <span className="font-mono">{status.progress_pct}%</span></p>
        </section>
      )}
    </main>
  );
}

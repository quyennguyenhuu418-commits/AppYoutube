"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

interface PlatformPublishRequest {
  job_id: string;
  topic: string;
  title: string;
  description: string;
  tags: string[];
  platforms: string[];
  visibility: string;
  auto_publish: boolean;
}

interface PublishingIssue {
  severity: string;
  field: string;
  message: string;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

const PLATFORM_LABELS: Record<string, { name: string; icon: string; color: string }> = {
  youtube: { name: "YouTube", icon: "▶", color: "red" },
  tiktok: { name: "TikTok", icon: "♪", color: "pink" },
  facebook: { name: "Facebook", icon: "f", color: "blue" },
};

const PLATFORM_COLORS: Record<string, string> = {
  youtube: "border-red-700 bg-red-900/20",
  tiktok: "border-pink-700 bg-pink-900/20",
  facebook: "border-blue-700 bg-blue-900/20",
};

const PLATFORM_TEXT: Record<string, string> = {
  youtube: "text-red-300",
  tiktok: "text-pink-300",
  facebook: "text-blue-300",
};

const STATUS_BADGE: Record<string, { bg: string; label: string }> = {
  draft: { bg: "bg-slate-700 text-slate-300", label: "Draft" },
  pending: { bg: "bg-blue-900/60 text-blue-200", label: "Pending" },
  published: { bg: "bg-green-900/60 text-green-200", label: "Published" },
  failed: { bg: "bg-red-900/60 text-red-200", label: "Failed" },
  rate_limited: { bg: "bg-amber-900/60 text-amber-200", label: "Rate Limited" },
};

export default function PublishingPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [platforms, setPlatforms] = useState<Set<string>>(new Set(["youtube", "tiktok", "facebook"]));
  const [autoPublish, setAutoPublish] = useState(false);

  // State
  const [loading, setLoading] = useState(false);
  const [preflight, setPreflight] = useState<{
    status: string;
    errors: PublishingIssue[];
    warnings: PublishingIssue[];
    platforms_prepared: string[];
    video_available: boolean;
    short_available: boolean;
    thumbnail_available: boolean;
  } | null>(null);
  const [plan, setPlan] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"form" | "preview" | "done">("form");

  // Load job data for initial values
  useEffect(() => {
    if (!jobId) return;
    fetch(`/api/jobs/${jobId}`)
      .then(r => r.json())
      .then((job: { title?: string; topic?: string }) => {
        if (job.title) setTitle(job.title);
        if (job.topic) setDescription(`AI-generated documentary about ${job.topic}.`);
      })
      .catch(() => {});
  }, [jobId]);

  const togglePlatform = (p: string) => {
    const next = new Set(platforms);
    if (next.has(p)) {
      if (next.size > 1) next.delete(p);  // Keep at least 1
    } else {
      next.add(p);
    }
    setPlatforms(next);
  };

  const handlePreflight = async () => {
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    setError(null);
    setLoading(true);

    const body: PlatformPublishRequest = {
      job_id: jobId,
      topic: title,
      title: title,
      description: description,
      tags: tagsInput.split(",").map(t => t.trim()).filter(Boolean),
      platforms: Array.from(platforms),
      visibility,
      auto_publish: false,
    };

    try {
      const result = await http<typeof preflight>(
        "/api/publishing/preflight",
        { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" } }
      );
      setPreflight(result as typeof preflight);
      setStep("preview");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleFinalize = async () => {
    if (!title.trim()) return;
    setError(null);
    setLoading(true);

    const body: PlatformPublishRequest = {
      job_id: jobId,
      topic: title,
      title: title,
      description: description,
      tags: tagsInput.split(",").map(t => t.trim()).filter(Boolean),
      platforms: Array.from(platforms),
      visibility,
      auto_publish: autoPublish,
    };

    try {
      const result = await http<{ status: string; plan_id: string; message: string }>(
        "/api/publishing/finalize",
        { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" } }
      );
      if (result.status === "ok" || result.status === "draft" || result.status === "pending") {
        setStep("done");
      } else {
        setError(result.message || "Publishing failed");
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="max-w-4xl mx-auto p-8 space-y-8">
      <div>
        <Link href={`/jobs/${jobId}`} className="text-sm text-slate-400 hover:text-accent">← Back to job</Link>
      </div>

      <header>
        <h1 className="text-3xl font-bold">PUBLISHING</h1>
        <p className="text-slate-400 text-sm mt-1">
          Prepare metadata and publish to YouTube, TikTok, and Facebook.
        </p>
      </header>

      {/* Platform selection */}
      <section className="rounded-xl bg-slate-800/40 border border-slate-700 p-6 space-y-4">
        <h2 className="text-sm uppercase tracking-wider text-slate-400">Target Platforms</h2>
        <div className="flex flex-wrap gap-3">
          {(["youtube", "tiktok", "facebook"] as const).map(platform => {
            const info = PLATFORM_LABELS[platform];
            const selected = platforms.has(platform);
            const color = PLATFORM_COLORS[platform];
            const text = PLATFORM_TEXT[platform];
            return (
              <button
                key={platform}
                onClick={() => togglePlatform(platform)}
                className={`flex items-center gap-2 px-4 py-3 rounded-xl border-2 transition-all ${
                  selected
                    ? `${color} ${text} border-opacity-100`
                    : "border-slate-700 text-slate-500 border-opacity-50"
                }`}
              >
                <span className="text-lg">{selected ? "✓" : "○"}</span>
                <span className="font-medium">{info.name}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* Form */}
      {step === "form" && (
        <section className="space-y-6">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Title <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              maxLength={150}
              placeholder="Enter video title"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
            />
            <div className="flex justify-between mt-1">
              <span className="text-xs text-slate-500">
                {platforms.has("tiktok") ? "Max 150 for TikTok" : "Max 100 for YouTube"}
              </span>
              <span className="text-xs text-slate-500">{title.length}/150</span>
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium mb-2">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={5}
              maxLength={5000}
              placeholder="Enter video description"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500 resize-y"
            />
            <div className="flex justify-end mt-1">
              <span className="text-xs text-slate-500">{description.length}/5000</span>
            </div>
          </div>

          {/* Tags */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Tags <span className="text-slate-500">(comma-separated)</span>
            </label>
            <input
              type="text"
              value={tagsInput}
              onChange={e => setTagsInput(e.target.value)}
              placeholder="documentary, ai, animation, education"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-slate-500 mt-1">
              Recommended tags: documentary, ai, animation, education, [your topic]
            </p>
          </div>

          {/* Visibility */}
          <div>
            <label className="block text-sm font-medium mb-2">Visibility</label>
            <div className="flex gap-3">
              {[
                { value: "public", label: "🌐 Public", desc: "Everyone can see" },
                { value: "unlisted", label: "🔗 Unlisted", desc: "Only with link" },
                { value: "private", label: "🔒 Private", desc: "Only you" },
              ].map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setVisibility(opt.value)}
                  className={`flex-1 px-4 py-2 rounded-lg border-2 text-sm transition-all ${
                    visibility === opt.value
                      ? "border-blue-600 bg-blue-900/20 text-blue-200"
                      : "border-slate-700 text-slate-400 hover:border-slate-600"
                  }`}
                >
                  <div className="font-medium">{opt.label}</div>
                  <div className="text-xs opacity-70">{opt.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handlePreflight}
              disabled={loading || !title.trim()}
              className="px-6 py-3 bg-blue-700 hover:bg-blue-600 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-medium text-sm transition-colors"
            >
              {loading ? "Checking..." : "Preview & Validate"}
            </button>
          </div>
        </section>
      )}

      {/* Preview */}
      {step === "preview" && preflight && (
        <section className="space-y-6">
          {/* Preflight results */}
          <div className="rounded-xl bg-slate-800/40 border border-slate-700 p-6 space-y-4">
            <h2 className="text-sm uppercase tracking-wider text-slate-400">Validation</h2>

            {/* Errors */}
            {preflight.errors.length > 0 && (
              <div className="space-y-2">
                {preflight.errors.map((issue, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm text-red-300">
                    <span className="mt-0.5">✗</span>
                    <span><strong>{issue.field}:</strong> {issue.message}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Warnings */}
            {preflight.warnings.length > 0 && (
              <div className="space-y-2">
                {preflight.warnings.map((issue, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm text-amber-300">
                    <span className="mt-0.5">!</span>
                    <span><strong>{issue.field}:</strong> {issue.message}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Availability */}
            <div className="grid grid-cols-3 gap-3 text-xs">
              <div className={`px-3 py-2 rounded-lg ${preflight.video_available ? "bg-green-900/20 text-green-300" : "bg-slate-700 text-slate-500"}`}>
                <div>{preflight.video_available ? "✓" : "✗"} Full Video</div>
              </div>
              <div className={`px-3 py-2 rounded-lg ${preflight.short_available ? "bg-green-900/20 text-green-300" : "bg-slate-700 text-slate-500"}`}>
                <div>{preflight.short_available ? "✓" : "✗"} Shorts</div>
              </div>
              <div className={`px-3 py-2 rounded-lg ${preflight.thumbnail_available ? "bg-green-900/20 text-green-300" : "bg-slate-700 text-slate-500"}`}>
                <div>{preflight.thumbnail_available ? "✓" : "✗"} Thumbnails</div>
              </div>
            </div>
          </div>

          {/* Platform summary */}
          <div className="rounded-xl bg-slate-800/40 border border-slate-700 p-6 space-y-4">
            <h2 className="text-sm uppercase tracking-wider text-slate-400">Platform Summary</h2>
            <div className="space-y-3">
              {preflight.platforms_prepared.map(platform => {
                const info = PLATFORM_LABELS[platform];
                const color = PLATFORM_COLORS[platform];
                const text = PLATFORM_TEXT[platform];
                return (
                  <div key={platform} className={`rounded-lg border p-4 ${color}`}>
                    <div className={`font-medium ${text}`}>{info.name}</div>
                    <div className="text-xs text-slate-400 mt-1">
                      {platform === "tiktok" ? "9:16 Short • " : ""}
                      Title: {title.slice(0, 40)}{title.length > 40 ? "..." : ""}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Note about credentials */}
          <div className="rounded-lg bg-amber-900/20 border border-amber-700 px-4 py-3 text-sm text-amber-200">
            <strong>Note:</strong> Publishing requires platform API credentials.
            Configure <code className="text-xs bg-amber-950 px-1 rounded">YOUTUBE_API_KEY</code>,
            <code className="text-xs bg-amber-950 px-1 rounded">TIKTOK_ACCESS_TOKEN</code>, and
            <code className="text-xs bg-amber-950 px-1 rounded">FACEBOOK_ACCESS_TOKEN</code>
            in your environment to enable auto-publishing.
          </div>

          {error && (
            <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => setStep("form")}
              className="px-6 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg font-medium text-sm transition-colors"
            >
              ← Edit
            </button>
            <button
              onClick={handleFinalize}
              disabled={loading || preflight.errors.length > 0}
              className="px-6 py-3 bg-green-700 hover:bg-green-600 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-medium text-sm transition-colors"
            >
              {loading ? "Creating Plan..." : "Create Publishing Plan"}
            </button>
          </div>
        </section>
      )}

      {/* Done */}
      {step === "done" && (
        <section className="space-y-6">
          <div className="rounded-xl bg-green-900/20 border border-green-700 p-8 text-center space-y-4">
            <div className="text-4xl">✓</div>
            <h2 className="text-2xl font-bold text-green-200">Publishing Plan Created!</h2>
            <p className="text-slate-400 text-sm">
              Your publishing plan is ready. Configure platform credentials to auto-publish.
            </p>
            <div className="flex justify-center gap-3">
              <Link
                href={`/jobs/${jobId}/shorts`}
                className="px-6 py-3 bg-blue-700 hover:bg-blue-600 rounded-lg font-medium text-sm transition-colors"
              >
                View Shorts
              </Link>
              <Link
                href={`/jobs/${jobId}/thumbnails`}
                className="px-6 py-3 bg-purple-700 hover:bg-purple-600 rounded-lg font-medium text-sm transition-colors"
              >
                View Thumbnails
              </Link>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}

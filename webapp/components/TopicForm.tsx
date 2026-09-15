"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

const EXAMPLES = [
  "How Did Ancient Humans Survive Deadly Winters?",
  "Why Did Civilizations Collapse After a Single Drought?",
  "What Did a Day in Pompeii Actually Look Like?",
  "How Did Sailors Cross the Pacific Without a Compass?",
];

export function TopicForm() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const job = await api.createJob(topic.trim());
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start job");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div>
        <label htmlFor="topic" className="block text-sm font-medium text-slate-300 mb-2">
          What should the documentary be about?
        </label>
        <textarea
          id="topic"
          rows={3}
          className="w-full rounded-lg bg-slate-800 border border-slate-700 px-4 py-3 text-lg
                     placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-accent"
          placeholder="e.g. How Did Ancient Humans Survive Deadly Winters?"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={busy}
        />
      </div>

      <button
        type="submit"
        disabled={!topic.trim() || busy}
        className="w-full rounded-lg bg-accent px-6 py-3 text-lg font-semibold text-ink
                   hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition"
      >
        {busy ? "Starting..." : "Generate Documentary"}
      </button>

      {error && (
        <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div>
        <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">
          Or try an example:
        </div>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setTopic(ex)}
              disabled={busy}
              className="text-xs rounded-full bg-slate-800 px-3 py-1.5 hover:bg-slate-700
                         disabled:opacity-50"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </form>
  );
}

"use client";

import { useEffect, useState } from "react";
import { api, type JobSummary } from "@/lib/api";
import Link from "next/link";

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-slate-600",
  running: "bg-blue-500 animate-pulse",
  completed: "bg-green-500",
  failed: "bg-red-500",
};

export function JobsList() {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listJobs().then(setJobs).catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return <div className="text-red-400">{error}</div>;
  }
  if (!jobs) {
    return <div className="text-slate-400">Loading...</div>;
  }
  if (jobs.length === 0) {
    return <div className="text-slate-400">No jobs yet. Start one from the home page.</div>;
  }

  return (
    <ul className="divide-y divide-slate-800">
      {jobs.map((j) => (
        <li key={j.id} className="py-3">
          <Link href={`/jobs/${j.id}`} className="flex items-center gap-3 hover:text-accent">
            <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[j.status] ?? "bg-slate-500"}`} />
            <span className="flex-1 truncate">{j.title || j.topic}</span>
            <span className="text-xs text-slate-500">
              {new Date(j.created_at).toLocaleString()}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

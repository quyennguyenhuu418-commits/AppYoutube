/**
 * Pure status badge mapping logic for the Final Render Inspector.
 * Extracted from page.tsx so it can be unit-tested without React rendering.
 */

export type BadgeVariant = {
  bg: string;
  icon: string;
  label?: string;  // label is optional — QA badges don't use it
};

export const STATUS_BADGE: Record<string, BadgeVariant> = {
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

export const QA_STATUS_BADGE: Record<string, BadgeVariant> = {
  pass:        { bg: "bg-green-900/60 text-green-200", icon: "✓" },
  warn:        { bg: "bg-amber-900/60 text-amber-200", icon: "!" },
  fail:        { bg: "bg-red-900/60 text-red-200",     icon: "✗" },
  unavailable: { bg: "bg-slate-700 text-slate-300",    icon: "?" },
};

export const TERMINAL_STATES = new Set(["approved", "failed", "cancelled"]);
export const RUNNING_STATES = new Set([
  "queued", "preparing", "preflight", "rendering", "mastering", "qa", "finalizing",
]);

export function getStatusBadge(lifecycle: string): BadgeVariant {
  return STATUS_BADGE[lifecycle] ?? STATUS_BADGE.queued;
}

export function getQAStatusBadge(status: string): BadgeVariant {
  return QA_STATUS_BADGE[status] ?? QA_STATUS_BADGE.unavailable;
}

export function isTerminal(lifecycle: string): boolean {
  return TERMINAL_STATES.has(lifecycle);
}

export function isFailed(lifecycle: string): boolean {
  return lifecycle === "failed" || lifecycle === "cancelled";
}

export function isApproved(lifecycle: string): boolean {
  return lifecycle === "approved";
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(2);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

import { StageInfo } from "@/lib/api";

const STATUS_BADGE: Record<string, { bg: string; icon: string }> = {
  pending: { bg: "bg-slate-700 text-slate-300", icon: "•" },
  running: { bg: "bg-blue-900/60 text-blue-200", icon: "⟳" },
  completed: { bg: "bg-green-900/60 text-green-200", icon: "✓" },
  failed: { bg: "bg-red-900/60 text-red-200", icon: "✗" },
  skipped: { bg: "bg-slate-800 text-slate-400", icon: "—" },
};

export function StageTimeline({ stages }: { stages: StageInfo[] }) {
  if (stages.length === 0) {
    return <div className="text-slate-400">Stages haven't started yet...</div>;
  }
  return (
    <ol className="space-y-2">
      {stages.map((s) => {
        const badge = STATUS_BADGE[s.status] ?? STATUS_BADGE.pending;
        return (
          <li key={s.name} className="flex items-center gap-3 rounded-lg bg-slate-800/50 px-4 py-2">
            <span className={`w-6 h-6 rounded-full grid place-items-center text-xs ${badge.bg}`}>
              {badge.icon}
            </span>
            <span className="flex-1">{s.label}</span>
            {s.error && <span className="text-xs text-red-300 truncate max-w-md">{s.error}</span>}
          </li>
        );
      })}
    </ol>
  );
}

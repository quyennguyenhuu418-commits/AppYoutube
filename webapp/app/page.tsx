import Link from "next/link";
import { TopicForm } from "@/components/TopicForm";
import { vi } from "@/lib/i18n";

export default function HomePage() {
  return (
    <main className="max-w-2xl mx-auto p-8 space-y-8">
      <header className="space-y-2">
        <div className="text-xs uppercase tracking-wider text-accent">{vi.appName}</div>
        <h1 className="text-4xl font-bold">{vi.homeTitle}</h1>
        <p className="text-slate-400">
          {vi.homeDescription}
        </p>
      </header>

      <TopicForm />

      <div className="pt-4 border-t border-slate-800">
        <Link href="/jobs" className="text-sm text-slate-400 hover:text-accent">
          {vi.jobsLink}
        </Link>
      </div>
    </main>
  );
}

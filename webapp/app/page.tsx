import Link from "next/link";
import { TopicForm } from "@/components/TopicForm";

export default function HomePage() {
  return (
    <main className="max-w-2xl mx-auto p-8 space-y-8">
      <header className="space-y-2">
        <div className="text-xs uppercase tracking-wider text-accent">AI Documentary Factory</div>
        <h1 className="text-4xl font-bold">Turn a topic into a documentary.</h1>
        <p className="text-slate-400">
          Type a question or topic. The system will research, script, narrate, animate, and
          render a 2-minute educational video — then automatically crop a 9:16 Short.
        </p>
      </header>

      <TopicForm />

      <div className="pt-4 border-t border-slate-800">
        <Link href="/jobs" className="text-sm text-slate-400 hover:text-accent">
          See all jobs →
        </Link>
      </div>
    </main>
  );
}

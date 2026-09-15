import Link from "next/link";
import { JobsList } from "@/components/JobsList";

export default function JobsPage() {
  return (
    <main className="max-w-3xl mx-auto p-8 space-y-6">
      <div>
        <Link href="/" className="text-sm text-slate-400 hover:text-accent">← Home</Link>
      </div>
      <h1 className="text-3xl font-bold">Jobs</h1>
      <JobsList />
    </main>
  );
}

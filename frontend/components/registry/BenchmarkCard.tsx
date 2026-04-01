import Link from "next/link";

import { StatusPill } from "@/components/ui/StatusPill";
import { BenchmarkListItem } from "@/lib/types";

export function BenchmarkCard({ benchmark }: { benchmark: BenchmarkListItem }) {
  return (
    <Link
      href={`/registry/${benchmark.slug}`}
      className="block border p-6 transition-colors duration-200 hover:border-[var(--text-dim)]"
      style={{ borderColor: "var(--border)", background: "var(--bg)" }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="mono">{benchmark.domain.join(" · ")}</div>
        {benchmark.is_verified ? <div className="mono text-[var(--text)]">Verified</div> : null}
      </div>
      <div className="mt-5 font-[var(--font-display)] text-[26px] leading-tight">{benchmark.name}</div>
      <p className="mt-3 max-w-2xl text-[14px] leading-7 text-[var(--text-dim)]">
        {benchmark.description}
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-4 font-[var(--font-mono)] text-[11px] uppercase tracking-[0.12em] text-[var(--muted)]">
        <span>{benchmark.task_type ?? "untyped"}</span>
        <span>{benchmark.latest_num_examples?.toLocaleString() ?? "Unknown"} examples</span>
        <span>Latest: {benchmark.latest_version ?? "—"}</span>
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <StatusPill status={benchmark.latest_contamination_status ?? "pending"} />
        <span className="mono">{benchmark.total_versions} versions</span>
        <span className="mono">{benchmark.total_citations.toLocaleString()} citations</span>
      </div>
    </Link>
  );
}


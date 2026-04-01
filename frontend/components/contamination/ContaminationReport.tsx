import { ContaminationReport as ReportType } from "@/lib/types";

import { StatusPill } from "@/components/ui/StatusPill";

export function ContaminationReport({ reports }: { reports: ReportType[] }) {
  return (
    <div className="space-y-6">
      {reports.map((report) => (
        <section
          key={report.id}
          className="rounded-sm border p-5"
          style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="mono mb-2">{report.corpus_name}</div>
              <div className="text-[15px] text-[var(--text-dim)]">
                Overlap score: {report.overlap_score ?? 0} · Flagged examples:{" "}
                {report.num_flagged_examples ?? 0}
              </div>
            </div>
            <StatusPill status={report.status} />
          </div>
          {report.flagged_examples && report.flagged_examples.length > 0 ? (
            <div className="mt-5 space-y-4">
              {report.flagged_examples.slice(0, 3).map((item) => (
                <div key={`${report.id}-${item.example_index}`} className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-sm border p-4" style={{ borderColor: "var(--border)" }}>
                    <div className="mono mb-2">Benchmark example</div>
                    <p className="text-[14px] text-[var(--text-dim)]">{item.benchmark_example}</p>
                  </div>
                  <div className="rounded-sm border p-4" style={{ borderColor: "var(--border)" }}>
                    <div className="mono mb-2">Corpus match</div>
                    <p className="text-[14px] text-[var(--text-dim)]">{item.corpus_match}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ))}
    </div>
  );
}


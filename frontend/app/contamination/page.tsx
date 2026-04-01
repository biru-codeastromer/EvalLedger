"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { useState } from "react";

import { ContaminationReport as ReportList } from "@/components/contamination/ContaminationReport";
import { OverlapVisualizer } from "@/components/contamination/OverlapVisualizer";
import { getCorpora, getJob, runAdHocCheck } from "@/lib/api";
import { ContaminationReport } from "@/lib/types";

export default function ContaminationPage() {
  const { data: corpora = [] } = useQuery({ queryKey: ["corpora"], queryFn: () => getCorpora(true) });
  const [selected, setSelected] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [reports, setReports] = useState<ContaminationReport[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (!file) {
      return;
    }
    setLoading(true);
    setError(null);
    setReports([]);
    try {
      const formData = new FormData();
      formData.append("artifact", file);
      formData.append("corpus_ids", JSON.stringify(selected));
      const job = await runAdHocCheck(formData);
      const interval = window.setInterval(async () => {
        try {
          const status = await getJob(job.job_id);
          if (status.status === "completed") {
            const result = status.result as { corpora: ContaminationReport[] };
            setReports(result.corpora);
            setLoading(false);
            window.clearInterval(interval);
          }
          if (status.status === "failed") {
            setError("The contamination job failed before results were returned.");
            setLoading(false);
            window.clearInterval(interval);
          }
        } catch {
          setError("We could not refresh the contamination job status.");
          setLoading(false);
          window.clearInterval(interval);
        }
      }, 1000);
    } catch {
      setLoading(false);
      setError("We could not start the contamination check. Confirm the API is reachable and try again.");
    }
  }

  return (
    <div className="section-space">
      <div className="page-frame">
        <div className="relative mb-12 h-[320px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
          <Image src="/images/04-microscope-slide.jpg" alt="Microscope slide accent" fill className="editorial-image" />
          <div className="absolute inset-0 bg-[rgba(245,243,238,0.62)]" />
          <div className="absolute inset-0 flex items-end px-8 py-8">
            <h1 className="display-lg max-w-3xl">Check your benchmark for contamination.</h1>
          </div>
        </div>
        <div className="grid gap-10 md:grid-cols-[minmax(0,1fr)_320px]">
          <section>
            <div
              className="flex min-h-[260px] flex-col items-center justify-center rounded-sm border-2 border-dashed p-8 text-center"
              style={{ borderColor: "var(--border)" }}
            >
              <div className="mono mb-4">Upload artifact</div>
              <p className="max-w-md text-[16px] text-[var(--text-dim)]">
                Drag a JSON, JSONL, CSV, or Parquet artifact here, or choose a file to run a public
                contamination check.
              </p>
              <input
                type="file"
                className="mt-6"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
            </div>
            <div className="mt-8">
              <div className="mono mb-4">Reference corpora</div>
              <div className="grid gap-3 md:grid-cols-2">
                {corpora.map((corpus) => (
                  <label key={corpus.id} className="surface flex cursor-pointer items-start gap-3 rounded-sm p-4">
                    <input
                      type="checkbox"
                      checked={selected.includes(corpus.id)}
                      onChange={() =>
                        setSelected((current) =>
                          current.includes(corpus.id)
                            ? current.filter((item) => item !== corpus.id)
                            : [...current, corpus.id]
                        )
                      }
                    />
                    <div>
                      <div className="text-[16px]">{corpus.name}</div>
                      <div className="text-[14px] text-[var(--text-dim)]">{corpus.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <button
              type="button"
              className="btn-primary mt-8"
              onClick={handleSubmit}
              disabled={loading || file === null}
            >
              {loading ? "Running..." : "Run Check"}
            </button>
            {error ? (
              <p className="ui-copy mt-4 text-[14px] text-[var(--status-contaminated)]">{error}</p>
            ) : null}
          </section>
          <aside className="space-y-6">
            <div className="relative h-[280px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
              <Image src="/images/15-petri-dish.jpg" alt="Petri dish accent" fill className="editorial-image" />
            </div>
            {reports.length > 0 ? <OverlapVisualizer reports={reports} /> : null}
          </aside>
        </div>
        {reports.length > 0 ? (
          <div className="mt-10">
            <ReportList reports={reports} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

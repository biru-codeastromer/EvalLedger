"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { useEffect, useState } from "react";

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
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    if (!activeJobId) {
      return;
    }
    const MAX_ATTEMPTS = 60;
    let attempts = 0;
    let cancelled = false;
    const stop = () => {
      if (interval !== undefined) {
        window.clearInterval(interval);
        interval = undefined;
      }
    };
    let interval: number | undefined = window.setInterval(async () => {
      attempts += 1;
      try {
        const status = await getJob(activeJobId);
        if (cancelled) {
          return;
        }
        if (status.status === "unavailable") {
          setError("Background processing is not available on this deployment.");
          setLoading(false);
          setActiveJobId(null);
          stop();
          return;
        }
        if (status.status === "completed") {
          const result = status.result as { corpora: ContaminationReport[] };
          setReports(result.corpora);
          setLoading(false);
          setActiveJobId(null);
          stop();
          return;
        }
        if (status.status === "failed") {
          setError("The contamination job failed before results were returned.");
          setLoading(false);
          setActiveJobId(null);
          stop();
          return;
        }
        if (attempts >= MAX_ATTEMPTS) {
          setError("The contamination job timed out before results were returned. Please try again.");
          setLoading(false);
          setActiveJobId(null);
          stop();
        }
      } catch {
        if (cancelled) {
          return;
        }
        setError("We could not refresh the contamination job status.");
        setLoading(false);
        setActiveJobId(null);
        stop();
      }
    }, 1000);

    return () => {
      cancelled = true;
      stop();
    };
  }, [activeJobId]);

  async function handleSubmit() {
    if (!file) {
      return;
    }
    setLoading(true);
    setError(null);
    setReports([]);
    setActiveJobId(null);
    try {
      const formData = new FormData();
      formData.append("artifact", file);
      formData.append("corpus_ids", JSON.stringify(selected));
      const job = await runAdHocCheck(formData) as { job_id: string; status: string; message?: string };
      if (job.status === "unavailable") {
        setLoading(false);
        setError(
          job.message ??
            "Background processing is not available on this deployment. Contamination checks require a worker process."
        );
        return;
      }
      setActiveJobId(job.job_id);
    } catch {
      setLoading(false);
      setError("We could not start the contamination check. Confirm the API is reachable and try again.");
    }
  }

  return (
    <div className="section-space">
      <div className="page-frame">
        <div className="relative mb-12 h-[320px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
          <Image
            src="/images/04-microscope-slide.jpg"
            alt="Microscope slide accent"
            fill
            priority
            quality={72}
            sizes="100vw"
            className="editorial-image"
          />
          <div className="absolute inset-0 bg-[rgba(var(--scrim-rgb),0.62)]" />
          <div className="absolute inset-0 flex items-end px-8 py-8">
            <h1 className="display-lg max-w-3xl">Check your benchmark for contamination.</h1>
          </div>
        </div>
        <div className="grid gap-10 md:grid-cols-[minmax(0,1fr)_320px]">
          <section>
            <div
              className="flex min-h-[260px] flex-col items-center justify-center rounded-sm border-2 border-dashed p-8 text-center transition-colors"
              style={{
                borderColor: dragActive ? "var(--accent)" : "var(--border)",
                background: dragActive ? "var(--surface)" : "transparent",
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                setDragActive(false);
              }}
              onDrop={(event) => {
                event.preventDefault();
                setDragActive(false);
                const dropped = event.dataTransfer.files?.[0] ?? null;
                if (dropped) {
                  setFile(dropped);
                }
              }}
            >
              <div className="mono mb-4">Upload artifact</div>
              <p className="max-w-md text-[16px] text-[var(--text-dim)]">
                Drag a JSON, JSONL, CSV, or Parquet artifact here, or choose a file to run a public
                contamination check.
              </p>
              <div className="mt-6 flex flex-col items-center gap-3">
                <label className="btn-secondary cursor-pointer">
                  Choose file
                  <input
                    type="file"
                    accept=".json,.jsonl,.csv,.parquet"
                    className="sr-only"
                    onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                  />
                </label>
                <span className="ui-copy text-[14px] text-[var(--muted)]">
                  {file ? file.name : "No file selected"}
                </span>
              </div>
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
              <Image
                src="/images/15-petri-dish.jpg"
                alt="Petri dish accent"
                fill
                quality={72}
                sizes="(min-width: 768px) 320px, 100vw"
                className="editorial-image"
              />
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

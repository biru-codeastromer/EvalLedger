"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { startTransition, useDeferredValue, useMemo } from "react";

import { BenchmarkCard } from "@/components/registry/BenchmarkCard";
import { getBenchmarks } from "@/lib/api";
import { useRegistryStore } from "@/lib/useRegistryStore";

const DOMAIN_OPTIONS = ["reasoning", "knowledge", "math", "code", "safety"];
const TASK_TYPES = ["multiple_choice", "generation", "code_completion"];

export function RegistryExplorer({ initialQuery = "" }: { initialQuery?: string }) {
  const { query, setQuery, taskType, setTaskType, domains, toggleDomain } = useRegistryStore();
  const deferredQuery = useDeferredValue(query || initialQuery);
  const { data = [], isLoading } = useQuery({
    queryKey: ["benchmarks", deferredQuery],
    queryFn: () => getBenchmarks(deferredQuery)
  });

  const filtered = useMemo(() => {
    return data.filter((item) => {
      const domainMatch = domains.length === 0 || domains.every((domain) => item.domain.includes(domain));
      const taskMatch = !taskType || item.task_type === taskType;
      return domainMatch && taskMatch;
    });
  }, [data, domains, taskType]);

  return (
    <div className="page-frame section-space">
      <div className="mb-8 overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
        <div className="relative h-[240px]">
          <Image src="/images/13-aerial-grid.jpg" alt="Registry hero banner" fill className="editorial-image" />
          <div className="absolute inset-0 bg-[rgba(245,243,238,0.56)]" />
          <div className="absolute inset-0 flex items-end justify-between gap-8 px-8 py-8">
            <div>
              <div className="mono mb-3">Registry</div>
              <h1 className="display-lg max-w-xl">Versioned benchmark records with provenance you can cite.</h1>
            </div>
            <p className="max-w-sm text-[16px] text-[var(--text-dim)]">
              Filter by domain, search by title, and inspect the latest pinned version without losing context.
            </p>
          </div>
        </div>
      </div>
      <div className="grid gap-8 md:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="border-r pr-6" style={{ borderColor: "var(--border)" }}>
          <div className="relative mb-8 h-[220px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
            <Image src="/images/03-card-catalog.jpg" alt="Card catalog" fill className="editorial-image" />
          </div>
          <div className="space-y-8">
            <div>
              <div className="mono mb-3">Search</div>
              <input
                value={query || initialQuery}
                onChange={(event) =>
                  startTransition(() => {
                    setQuery(event.target.value);
                  })
                }
                placeholder="Search benchmarks"
                className="w-full rounded-sm border px-3 py-3 text-[14px]"
                style={{ borderColor: "var(--border)", background: "var(--bg)" }}
              />
            </div>
            <div>
              <div className="mono mb-3">Domains</div>
              <div className="space-y-3">
                {DOMAIN_OPTIONS.map((option) => (
                  <label key={option} className="flex cursor-pointer items-center gap-3 text-[14px] text-[var(--text-dim)]">
                    <span
                      className="flex h-4 w-4 items-center justify-center rounded-[2px] border"
                      style={{
                        borderColor: "var(--border)",
                        background: domains.includes(option) ? "var(--text)" : "transparent",
                        color: "var(--bg)"
                      }}
                    >
                      {domains.includes(option) ? "✓" : ""}
                    </span>
                    <input
                      type="checkbox"
                      checked={domains.includes(option)}
                      onChange={() => toggleDomain(option)}
                      className="hidden"
                    />
                    {option}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <div className="mono mb-3">Task type</div>
              <div className="space-y-3">
                {TASK_TYPES.map((option) => (
                  <label key={option} className="flex cursor-pointer items-center gap-3 text-[14px] text-[var(--text-dim)]">
                    <span
                      className="flex h-4 w-4 items-center justify-center rounded-[2px] border"
                      style={{
                        borderColor: "var(--border)",
                        background: taskType === option ? "var(--text)" : "transparent",
                        color: "var(--bg)"
                      }}
                    >
                      {taskType === option ? "•" : ""}
                    </span>
                    <input
                      type="radio"
                      name="taskType"
                      checked={taskType === option}
                      onChange={() => setTaskType(taskType === option ? "" : option)}
                      className="hidden"
                    />
                    {option.replaceAll("_", " ")}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </aside>
        <div className="space-y-4">
          {isLoading ? (
            <p className="text-[var(--text-dim)]">Loading the registry...</p>
          ) : (
            filtered.map((item) => <BenchmarkCard key={item.id} benchmark={item} />)
          )}
        </div>
      </div>
    </div>
  );
}


import Link from "next/link";

import { CitationBlock } from "@/components/registry/CitationBlock";
import { ContaminationBadge } from "@/components/registry/ContaminationBadge";
import { ReportButton } from "@/components/registry/ReportButton";
import { VersionBadge } from "@/components/registry/VersionBadge";
import { ActivityFeed } from "@/components/ui/ActivityFeed";
import { getBenchmark, getBenchmarkActivity, getVersion, getVersions } from "@/lib/api";

export default async function BenchmarkDetailPage({ params }: { params: { slug: string } }) {
  const benchmark = await getBenchmark(params.slug);
  const versions = await getVersions(params.slug);
  const latest = versions[0] ? await getVersion(params.slug, versions[0].version) : null;
  const activity = await getBenchmarkActivity(params.slug);

  return (
    <div className="page-frame section-space">
      <div className="mono mb-6">
        <Link href="/registry">Registry</Link> → {benchmark.name}
      </div>
      <div className="grid gap-10 md:grid-cols-[minmax(0,1fr)_340px]">
        <section>
          <h1 className="display-xl max-w-4xl">{benchmark.name}</h1>
          <div className="mt-5 flex flex-wrap gap-4">
            {benchmark.domain.map((item) => (
              <span key={item} className="mono">
                {item}
              </span>
            ))}
            <span className="mono">{benchmark.task_type}</span>
            {benchmark.is_verified ? <span className="mono text-[var(--text)]">Verified</span> : null}
            <ReportButton resourceType="benchmark" resourceSlug={benchmark.slug} />
          </div>
          <p className="mt-8 max-w-3xl text-[18px] leading-9 text-[var(--text-dim)]">
            {benchmark.description}
          </p>
          <div className="mt-12 overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
            <table className="w-full border-collapse">
              <thead style={{ background: "var(--surface)" }}>
                <tr className="text-left font-[var(--font-mono)] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
                  <th className="px-4 py-4">Version</th>
                  <th className="px-4 py-4">Released</th>
                  <th className="px-4 py-4">SHA-256</th>
                  <th className="px-4 py-4">Contamination</th>
                  <th className="px-4 py-4">Examples</th>
                  <th className="px-4 py-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((version) => (
                  <tr key={version.id} className="border-t hover:bg-[var(--surface)]" style={{ borderColor: "var(--border)" }}>
                    <td className="px-4 py-4">
                      <VersionBadge version={version.version} />
                    </td>
                    <td className="px-4 py-4 text-[14px] text-[var(--text-dim)]">
                      {version.released_at ? new Date(version.released_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-4 py-4 font-[var(--font-mono)] text-[12px] text-[var(--text-dim)]">
                      {version.artifact_sha256 ? `${version.artifact_sha256.slice(0, 8)}...` : "unavailable"}
                    </td>
                    <td className="px-4 py-4">
                      <ContaminationBadge status={version.contamination_status} />
                    </td>
                    <td className="px-4 py-4 text-[14px] text-[var(--text-dim)]">
                      {version.num_examples?.toLocaleString() ?? "—"}
                    </td>
                    <td className="px-4 py-4 text-[14px]">
                      <Link href={`/registry/${benchmark.slug}/${version.version}`}>Inspect</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-12 space-y-4">
            <div className="mono">Audit trail</div>
            <ActivityFeed
              events={activity}
              emptyMessage="No public audit events have been recorded for this benchmark yet."
            />
          </div>
        </section>
        {latest ? <CitationBlock citations={latest.citations} /> : null}
      </div>
    </div>
  );
}

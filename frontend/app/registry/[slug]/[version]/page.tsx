import Image from "next/image";
import Link from "next/link";

import { ContaminationReport } from "@/components/contamination/ContaminationReport";
import { OverlapVisualizer } from "@/components/contamination/OverlapVisualizer";
import { ActivityFeed } from "@/components/ui/ActivityFeed";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { StatusPill } from "@/components/ui/StatusPill";
import { getContamination, getVersion, getVersionActivity } from "@/lib/api";

export default async function VersionPage({
  params
}: {
  params: { slug: string; version: string };
}) {
  const version = await getVersion(params.slug, params.version);
  const reports = await getContamination(params.slug, params.version);
  const activity = await getVersionActivity(params.slug, params.version);

  return (
    <div className="page-frame section-space">
      <div className="mono mb-6">
        <Link href="/registry">Registry</Link> → <Link href={`/registry/${params.slug}`}>{params.slug}</Link> →{" "}
        {params.version}
      </div>
      <div className="grid gap-10 md:grid-cols-[minmax(0,1fr)_320px]">
        <section className="space-y-10">
          <div className="flex flex-wrap items-center gap-5">
            <h1 className="display-lg">{params.slug}</h1>
            <StatusPill status={version.contamination_status} />
          </div>
          <div className="grid gap-6 rounded-sm border p-6 md:grid-cols-[120px_minmax(0,1fr)]" style={{ borderColor: "var(--border)", background: "var(--surface)" }}>
            <div className="relative h-[120px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
              <Image src="/images/06-wax-seal.jpg" alt="Verified block accent" fill className="editorial-image" />
            </div>
            <div>
              <div className="mono mb-2">Integrity record</div>
              <p className="text-[15px] text-[var(--text-dim)]">
                EvalLedger stores the exact artifact hash for versioned records when an artifact has been
                uploaded. Seeded legacy imports remain explicit about missing pinned files.
              </p>
            </div>
          </div>
          <div>
            <div className="mono mb-3">SHA-256</div>
            <CodeBlock code={version.artifact_sha256 ?? "No artifact hash recorded for this legacy import."} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {[
              ["Artifact size", version.artifact_size_bytes ? `${version.artifact_size_bytes} bytes` : "Unavailable"],
              ["Upload date", new Date(version.created_at).toLocaleString()],
              ["License", version.license ?? "Unspecified"],
              ["Language", version.language?.join(", ") ?? "Unspecified"],
              ["Splits", version.splits ? JSON.stringify(version.splits) : "Unspecified"],
              ["Paper", version.paper_url ?? "Unavailable"]
            ].map(([label, value]) => (
              <div key={label} className="rounded-sm border p-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }}>
                <div className="mono mb-2">{label}</div>
                <div className="text-[15px] text-[var(--text-dim)]">{value}</div>
              </div>
            ))}
          </div>
          <div>
            <div className="display-lg mb-5">Contamination reports</div>
            <OverlapVisualizer reports={reports} />
            <div className="mt-6">
              <ContaminationReport reports={reports} />
            </div>
          </div>
          <div>
            <div className="mono mb-3">Verification command</div>
            <CodeBlock code={`evalledger verify ${params.slug} ${params.version}`} />
          </div>
          <div>
            <div className="mono mb-3">Audit trail</div>
            <ActivityFeed
              events={activity}
              emptyMessage="No audit events have been recorded for this version yet."
            />
          </div>
        </section>
      </div>
    </div>
  );
}

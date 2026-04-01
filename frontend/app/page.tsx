import Image from "next/image";
import Link from "next/link";

import { CodeBlock } from "@/components/ui/CodeBlock";
import { StatCounter } from "@/components/ui/StatCounter";
import { StatusPill } from "@/components/ui/StatusPill";
import { getOverview, getRecent } from "@/lib/api";

async function safeOverview() {
  try {
    return await getOverview();
  } catch {
    return {
      total_benchmarks: 15,
      total_versions: 15,
      contamination_checks: 0,
      benchmarks_flagged: 0
    };
  }
}

async function safeRecent() {
  try {
    return await getRecent();
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const [overview, recent] = await Promise.all([safeOverview(), safeRecent()]);

  return (
    <>
      <section className="section-space">
        <div className="page-frame grid gap-12 md:grid-cols-[1.1fr_0.9fr] md:items-start">
          <div className="space-y-8">
            <div className="mono">Registry</div>
            <h1 className="display-xl max-w-3xl">The open registry for AI benchmark provenance.</h1>
            <div className="flex flex-wrap items-center gap-4">
              <Link href="/registry" className="btn-primary">
                Browse Registry
              </Link>
              <CodeBlock code="pip install evalledger" inline />
            </div>
          </div>
          <div className="space-y-6 pt-4">
            <div className="body-copy max-w-xl text-[18px] leading-9">
              Version, cite, and verify every benchmark. Detect contamination before it poisons your
              evaluation. EvalLedger is the system-of-record the AI research community has been
              missing.
            </div>
            <div className="relative ml-auto h-[240px] max-w-[360px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
              <Image src="/images/02-ledger-book.jpg" alt="Ledger book" fill className="editorial-image" />
            </div>
          </div>
        </div>
      </section>

      <section className="border-y" style={{ borderColor: "var(--border)" }}>
        <div className="page-frame relative py-10">
          <div className="pointer-events-none absolute left-0 top-0 h-full w-20 overflow-hidden opacity-30">
            <Image src="/images/11-tally-marks.jpg" alt="Tally marks accent" fill className="editorial-image" />
          </div>
          <div className="grid gap-8 pl-16 md:grid-cols-4">
            <StatCounter value={overview.total_benchmarks} label="Total Benchmarks" />
            <StatCounter value={overview.total_versions} label="Total Versions" />
            <StatCounter value={overview.contamination_checks} label="Contamination Checks" />
            <StatCounter value={overview.benchmarks_flagged} label="Benchmarks Flagged" />
          </div>
        </div>
      </section>

      <section className="section-space">
        <div className="page-frame grid gap-10 md:grid-cols-[100px_1fr_0.9fr] md:items-center">
          <div className="mono text-[28px]">01</div>
          <div>
            <div className="display-lg mb-4">Provenance that survives citations.</div>
            <p className="body-copy max-w-2xl">
              Every benchmark record pins a concrete artifact, a version string, and a canonical
              EvalLedger identifier so papers can reference the exact evaluation substrate they used.
            </p>
          </div>
          <div className="relative h-[480px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
            <Image src="/images/01-filing-cabinets.jpg" alt="Filing cabinets" fill className="editorial-image" />
          </div>
        </div>
      </section>

      <section className="section-space" style={{ background: "var(--surface)" }}>
        <div className="page-frame grid gap-10 md:grid-cols-[100px_0.9fr_1fr] md:items-center">
          <div className="mono text-[28px]">02</div>
          <div className="relative h-[420px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
            <Image src="/images/07-fingerprint.jpg" alt="Fingerprint" fill className="editorial-image" />
          </div>
          <div>
            <div className="display-lg mb-4">Contamination checks before claims harden into fact.</div>
            <p className="body-copy max-w-2xl">
              EvalLedger compares submitted artifacts against reference corpora with MinHash-based
              approximate matching, surfacing overlap before a benchmark quietly becomes part of the
              training data story.
            </p>
          </div>
        </div>
      </section>

      <section className="section-space">
        <div className="page-frame grid gap-10 md:grid-cols-[100px_1fr_0.9fr] md:items-center">
          <div className="mono text-[28px]">03</div>
          <div>
            <div className="display-lg mb-4">Reproducibility that does not depend on memory.</div>
            <p className="body-copy max-w-2xl">
              Release notes, hashes, corpus reports, and citation formats are all kept together so a
              benchmark can be revisited years later without hand-waving over what exactly was used.
            </p>
          </div>
          <div className="relative h-[420px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
            <Image src="/images/05-stacked-papers.jpg" alt="Stacked papers" fill className="editorial-image" />
          </div>
        </div>
      </section>

      <section className="section-space border-y" style={{ borderColor: "var(--border)" }}>
        <div className="page-frame text-center">
          <div className="mono mb-6">Trust</div>
          <div className="mx-auto mb-6 max-w-3xl display-lg">
            A benchmark registry should feel closer to a ledger room than a launch page.
          </div>
          <p className="mx-auto max-w-2xl body-copy">
            The point is not hype. The point is custody, traceability, and enough public structure
            that researchers can disagree about models without disagreeing about the artifact.
          </p>
          <div className="relative mx-auto mt-10 h-[320px] w-full max-w-[420px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
            <Image src="/images/12-balance-scale.jpg" alt="Balance scale" fill className="editorial-image" />
          </div>
        </div>
      </section>

      <section className="section-space overflow-hidden">
        <div className="page-frame">
          <div className="mb-6 flex items-center justify-between gap-6">
            <div className="display-lg">Recent submissions</div>
            <Link href="/registry" className="btn-secondary">
              View all
            </Link>
          </div>
          <div className="overflow-hidden border-y py-5" style={{ borderColor: "var(--border)" }}>
            <div className="ticker-track">
              {[...recent, ...recent].map((item) => (
                <div key={`${item.id}-${item.version}`} className="flex min-w-[320px] items-center gap-4">
                  <span className="font-[var(--font-display)] text-[28px]">{item.benchmark_name}</span>
                  <span className="mono">{item.version}</span>
                  <StatusPill status={item.contamination_status} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}


import Image from "next/image";
import type { Route } from "next";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="ui-copy border-t" style={{ borderColor: "var(--border)" }}>
      <div className="page-frame py-12">
        <div className="grid gap-12 md:grid-cols-4">
          <div>
            <p className="mono mb-4">About EvalLedger</p>
            <p className="max-w-sm text-[15px] text-[var(--text-dim)]">
              A public registry for benchmark provenance, contamination detection, and reproducible
              evaluation metadata.
            </p>
          </div>
          <div>
            <p className="mono mb-4">Registry</p>
            <div className="space-y-2 text-[15px] text-[var(--text-dim)]">
              <Link href="/registry" className="block">
                Browse benchmarks
              </Link>
              <Link href="/search" className="block">
                Search records
              </Link>
              <Link href="/submit" className="block">
                Submit a benchmark
              </Link>
            </div>
          </div>
          <div>
            <p className="mono mb-4">Documentation</p>
            <div className="space-y-2 text-[15px] text-[var(--text-dim)]">
              <Link href="/standard" className="block">
                Metadata Standard
              </Link>
              <Link href="/docs" className="block">
                Documentation
              </Link>
              <a
                href="https://github.com/biru-codeastromer/EvalLedger/blob/main/docs/README.md"
                target="_blank"
                rel="noreferrer"
                className="block"
              >
                Runbooks
              </a>
              <a
                href="https://github.com/biru-codeastromer/EvalLedger"
                target="_blank"
                rel="noreferrer"
                className="block"
              >
                GitHub
              </a>
            </div>
          </div>
          <div>
            <p className="mono mb-4">Policies</p>
            <div className="space-y-2 text-[15px] text-[var(--text-dim)]">
              <Link href={"/privacy" as Route} className="block">
                Privacy
              </Link>
              <Link href={"/terms" as Route} className="block">
                Terms
              </Link>
              <Link href={"/acceptable-use" as Route} className="block">
                Acceptable use
              </Link>
            </div>
          </div>
        </div>
        <div
          className="mt-12 flex flex-col gap-4 border-t pt-6 md:flex-row md:items-center md:justify-between"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center gap-4">
            <div className="relative h-14 w-14 overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
              <Image
                src="/images/14-punch-cards.jpg"
                alt="Punch cards accent"
                fill
                className="editorial-image"
              />
            </div>
            <span className="mono">Copyright 2026 EvalLedger</span>
          </div>
          <div className="flex flex-wrap gap-4 text-[14px] text-[var(--text-dim)]">
            <Link href={"/privacy" as Route}>Privacy</Link>
            <Link href={"/terms" as Route}>Terms</Link>
            <Link href={"/acceptable-use" as Route}>Acceptable Use</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

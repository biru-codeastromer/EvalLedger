import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="ui-copy border-t" style={{ borderColor: "var(--border)" }}>
      <div className="page-frame py-12">
        <div className="grid gap-12 md:grid-cols-3">
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
            <p className="mono mb-4">Standard</p>
            <div className="space-y-2 text-[15px] text-[var(--text-dim)]">
              <Link href="/standard" className="block">
                Metadata Standard
              </Link>
              <a href="/docs" className="block">
                Documentation
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
        </div>
      </div>
    </footer>
  );
}

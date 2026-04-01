import Link from "next/link";

export function Nav() {
  return (
    <header
      className="ui-copy sticky top-0 z-40 border-b bg-[var(--bg)]"
      style={{ borderColor: "var(--border)" }}
    >
      <div className="page-frame flex items-center justify-between gap-6 py-4">
        <Link href="/" className="font-[var(--font-display)] text-[18px] font-bold tracking-tight">
          EvalLedger
        </Link>
        <nav className="hidden items-center gap-8 text-[14px] text-[var(--text-dim)] md:flex">
          <Link href="/registry">Registry</Link>
          <Link href="/contamination">Contamination</Link>
          <Link href="/standard">Standard</Link>
          <a href="/docs">
            Docs
          </a>
        </nav>
        <div className="flex items-center gap-3">
          <a href="/login" className="text-[14px] text-[var(--text-dim)]">
            Sign In
          </a>
          <Link href="/submit" className="btn-primary">
            Submit Benchmark
          </Link>
        </div>
      </div>
    </header>
  );
}

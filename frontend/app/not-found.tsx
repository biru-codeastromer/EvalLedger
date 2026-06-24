import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page-frame section-space text-center">
      <div className="mono mb-4">404 / Not Found</div>
      <h1 className="display-lg mb-6">This page isn&apos;t in the ledger.</h1>
      <p className="mx-auto mb-10 max-w-2xl text-[16px] text-[var(--text-dim)]">
        The link may be outdated, or the record was never registered in EvalLedger.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link href="/" className="btn-primary inline-flex">
          Back to home
        </Link>
        <Link href="/registry" className="btn-secondary inline-flex">
          Browse the registry
        </Link>
      </div>
    </div>
  );
}

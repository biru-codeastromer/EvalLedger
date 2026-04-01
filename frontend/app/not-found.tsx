import Image from "next/image";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page-frame section-space text-center">
      <div className="mono mb-4">404</div>
      <h1 className="display-lg mb-6">The record you requested is not on the shelf.</h1>
      <p className="mx-auto mb-10 max-w-2xl text-[16px] text-[var(--text-dim)]">
        The link may be outdated, or the benchmark has not yet been registered in EvalLedger.
      </p>
      <div className="relative mx-auto h-[400px] max-w-[720px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
        <Image src="/images/09-reading-room.jpg" alt="Reading room" fill className="editorial-image" />
      </div>
      <Link href="/registry" className="btn-primary mt-8 inline-flex">
        Browse Registry
      </Link>
    </div>
  );
}


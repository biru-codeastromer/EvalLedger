"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function Error({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="page-frame section-space text-center">
      <div className="mono mb-4">Error</div>
      <h1 className="display-lg mb-6">Something went wrong on our shelves.</h1>
      <p className="mx-auto mb-10 max-w-2xl text-[16px] text-[var(--text-dim)]">
        We&apos;re sorry &mdash; an unexpected error interrupted this page. You can try again,
        and if the problem persists, return to the home page.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <button type="button" onClick={() => reset()} className="btn-primary inline-flex">
          Try again
        </button>
        <Link href="/" className="btn-secondary inline-flex">
          Back to home
        </Link>
      </div>
    </div>
  );
}

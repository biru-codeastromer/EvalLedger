"use client";

import type { Route } from "next";
import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/layout/BrandMark";
import { loadSession, subscribeToSessionChange } from "@/lib/session";
import { AuthResponse } from "@/lib/types";

export function Nav() {
  const [session, setSession] = useState<AuthResponse | null>(null);

  useEffect(() => {
    const sync = () => setSession(loadSession());
    sync();
    return subscribeToSessionChange(sync);
  }, []);

  return (
    <header
      className="ui-copy sticky top-0 z-40 border-b bg-[var(--bg)]"
      style={{ borderColor: "var(--border)" }}
    >
      <div className="page-frame flex items-center justify-between gap-6 py-4">
        <Link href="/" className="flex items-center gap-3 font-[var(--font-display)] tracking-tight">
          <BrandMark className="h-8 w-8 shrink-0" />
          <span className="text-[20px] font-bold">EvalLedger</span>
        </Link>
        <nav className="hidden items-center gap-8 text-[14px] text-[var(--text-dim)] md:flex">
          <Link href="/registry">Registry</Link>
          <Link href="/contamination">Contamination</Link>
          <Link href="/standard">Standard</Link>
          {session?.user.is_admin ? <Link href={"/review" as Route}>Review</Link> : null}
          <a href="/docs">
            Docs
          </a>
        </nav>
        <div className="flex items-center gap-3">
          <Link
            href={(session ? "/account" : "/login") as Route}
            className="text-[14px] text-[var(--text-dim)]"
          >
            {session ? "Account" : "Sign In"}
          </Link>
          <Link href="/submit" className="btn-primary">
            Submit Benchmark
          </Link>
        </div>
      </div>
    </header>
  );
}

"use client";

import type { Route } from "next";
import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/layout/BrandMark";
import { loadSession, subscribeToSessionChange } from "@/lib/session";
import { AuthResponse } from "@/lib/types";

export function Nav() {
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const sync = () => setSession(loadSession());
    sync();
    return subscribeToSessionChange(sync);
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const closeMenu = () => setMenuOpen(false);

  return (
    <header
      className="ui-copy sticky top-0 z-40 border-b bg-[var(--bg)]"
      style={{
        borderColor: "var(--border)",
        borderBottomWidth: scrolled ? "1.5px" : "1px",
        boxShadow: scrolled ? "0 1px 12px rgba(0, 0, 0, 0.06)" : "none",
        transition: "box-shadow 180ms ease-out, border-bottom-width 180ms ease-out"
      }}
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
          <button
            type="button"
            aria-label="Toggle menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border text-[var(--text-dim)] md:hidden"
            style={{ borderColor: "var(--border)" }}
          >
            <span aria-hidden="true" className="text-[18px] leading-none">
              {menuOpen ? "✕" : "☰"}
            </span>
          </button>
        </div>
      </div>
      {menuOpen ? (
        <nav
          className="page-frame flex flex-col gap-4 border-t py-4 text-[14px] text-[var(--text-dim)] md:hidden"
          style={{ borderColor: "var(--border)" }}
        >
          <Link href="/registry" onClick={closeMenu}>
            Registry
          </Link>
          <Link href="/contamination" onClick={closeMenu}>
            Contamination
          </Link>
          <Link href="/standard" onClick={closeMenu}>
            Standard
          </Link>
          {session?.user.is_admin ? (
            <Link href={"/review" as Route} onClick={closeMenu}>
              Review
            </Link>
          ) : null}
          <a href="/docs" onClick={closeMenu}>
            Docs
          </a>
        </nav>
      ) : null}
    </header>
  );
}

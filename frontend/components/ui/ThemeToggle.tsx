"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "evalledger.theme";

function readTheme(): Theme {
  if (typeof document !== "undefined") {
    const fromDom = document.documentElement.dataset.theme;
    if (fromDom === "light" || fromDom === "dark") {
      return fromDom;
    }
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
  } catch {
    // ignore storage access errors
  }
  if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function ThemeToggle() {
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(readTheme());
    setMounted(true);
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore storage access errors
    }
    setTheme(next);
  };

  const isDark = theme === "dark";
  const label = isDark ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="inline-flex h-9 w-9 items-center justify-center rounded-md text-[18px] leading-none text-[var(--text-dim)] transition-colors hover:text-[var(--text)]"
    >
      <span aria-hidden="true" suppressHydrationWarning>
        {mounted && isDark ? "☀" : "☾"}
      </span>
    </button>
  );
}

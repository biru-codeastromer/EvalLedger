"use client";

import { useState } from "react";

export function CodeBlock({ code, inline = false }: { code: string; inline?: boolean }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  if (inline) {
    return (
      <button
        type="button"
        onClick={handleCopy}
        className="rounded-sm border px-4 py-3 text-left font-[var(--font-mono)] text-[13px]"
        style={{ borderColor: "var(--border)", background: "var(--surface-2)" }}
        aria-label={`Copy ${code}`}
      >
        {copied ? "Copied" : code}
      </button>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-sm border p-4" style={{ background: "var(--surface-2)", borderColor: "var(--border)" }}>
      <button
        type="button"
        onClick={handleCopy}
        className="absolute right-3 top-3 font-[var(--font-ui)] text-[12px] text-[var(--muted)]"
        aria-label="Copy code block"
      >
        {copied ? "Copied" : "Copy"}
      </button>
      <pre className="overflow-x-auto pr-14 font-[var(--font-mono)] text-[13px] leading-6 text-[var(--text)]">
        <code>{code}</code>
      </pre>
    </div>
  );
}

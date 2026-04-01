"use client";

import { useState } from "react";

import { CodeBlock } from "@/components/ui/CodeBlock";

type CitationFormats = {
  bibtex: string;
  apa: string;
  mla: string;
  cff: string;
  evalledger_id: string;
};

const TABS: Array<{ key: keyof CitationFormats; label: string }> = [
  { key: "bibtex", label: "BibTeX" },
  { key: "apa", label: "APA" },
  { key: "mla", label: "MLA" },
  { key: "cff", label: "Citation.cff" },
  { key: "evalledger_id", label: "EvalLedger ID" }
];

export function CitationBlock({ citations }: { citations: CitationFormats }) {
  const [selected, setSelected] = useState<keyof CitationFormats>("bibtex");

  return (
    <aside className="surface sticky top-24 rounded-sm p-5">
      <div className="mono mb-4">Cite this benchmark</div>
      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            type="button"
            key={tab.key}
            onClick={() => setSelected(tab.key)}
            className="rounded-sm border px-3 py-2 text-[13px]"
            style={{
              borderColor: selected === tab.key ? "var(--text)" : "var(--border)",
              background: selected === tab.key ? "var(--bg)" : "transparent"
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <CodeBlock code={citations[selected]} />
    </aside>
  );
}


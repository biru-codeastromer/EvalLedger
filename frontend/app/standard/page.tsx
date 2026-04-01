import Image from "next/image";

import { CodeBlock } from "@/components/ui/CodeBlock";

const schemaSnippet = `benchmark:
  name: "MMLU"
  slug: "mmlu"
  description: "..."
  domain:
    - reasoning
    - knowledge
  task_type: "multiple_choice"

version:
  version: "2.0.1"
  artifact_sha256: "a3f9..."
  num_examples: 15908`;

export default function StandardPage() {
  return (
    <div className="section-space">
      <div className="page-frame max-w-[680px]">
        <div className="relative mb-10 h-[280px] overflow-hidden rounded-sm border" style={{ borderColor: "var(--border)" }}>
          <Image src="/images/08-letterpress.jpg" alt="Letterpress header" fill className="editorial-image" />
        </div>
        <div className="mono mb-4">Metadata Standard</div>
        <h1 className="display-lg mb-8">EvalLedger Metadata Standard v0.1</h1>
        <div className="prose-rfc text-[16px] leading-[1.85] text-[var(--text-dim)]">
          <p>
            EvalLedger defines a minimal public contract for benchmark provenance. A record is not
            just a name and a paper link; it is a benchmark identity, a version, an artifact digest,
            and enough metadata to let another researcher reconstruct what was evaluated.
          </p>
          <p>
            The standard is intentionally narrow. Every field must justify its existence by improving
            citation, reproducibility, or contamination analysis. Fields that belong in downstream
            task-specific schemas are left out.
          </p>
          <CodeBlock code={schemaSnippet} />
          <p>
            Version identifiers SHOULD follow semantic versioning. Artifact hashes SHOULD be computed
            over the exact file submitted to EvalLedger. Legacy imports MAY omit a hash, but the
            absence must remain explicit and machine-readable.
          </p>
          <p>
            The complete machine schema is shipped with the repository as{" "}
            <code>standard/metadata_schema.json</code>. The human-readable specification lives in{" "}
            <code>standard/METADATA_STANDARD.md</code>.
          </p>
        </div>
      </div>
    </div>
  );
}


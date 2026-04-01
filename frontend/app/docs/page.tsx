import type { Route } from "next";
import Link from "next/link";

const REPOSITORY_URL = "https://github.com/biru-codeastromer/EvalLedger";
const REPOSITORY_BLOB_URL = `${REPOSITORY_URL}/blob/main`;

const DOC_SECTIONS = [
  {
    label: "Quick start",
    href: `${REPOSITORY_BLOB_URL}/README.md#quick-start`,
    title: "Run the stack locally in three commands.",
    body: "Follow the repository quick start if you want Docker, migrations, and seeded data before touching the registry."
  },
  {
    label: "API overview",
    href: `${REPOSITORY_BLOB_URL}/README.md#api-overview`,
    title: "Inspect the HTTP surface before integrating.",
    body: "Use the documented curl examples for benchmark lookup, submission, and contamination checks."
  },
  {
    label: "CLI usage",
    href: `${REPOSITORY_BLOB_URL}/README.md#cli`,
    title: "Work from the terminal with versioned submissions.",
    body: "The CLI reference covers submit, verify, search, and cite flows with concrete commands."
  }
];

const OPERATIONAL_DOCS = [
  {
    label: "Incident response",
    href: `${REPOSITORY_BLOB_URL}/docs/operations/incident-response.md`,
    body: "Severity levels, communication cadence, evidence capture, and owner roles during production incidents."
  },
  {
    label: "Backup and restore",
    href: `${REPOSITORY_BLOB_URL}/docs/operations/backup-restore.md`,
    body: "Database and artifact recovery expectations, restore order, and verification checks after a recovery drill."
  },
  {
    label: "Release process",
    href: `${REPOSITORY_BLOB_URL}/docs/maintainers/release-process.md`,
    body: "The release checklist for migrations, verification, deployment preparation, and post-release review."
  },
  {
    label: "Migration policy",
    href: `${REPOSITORY_BLOB_URL}/docs/maintainers/migration-policy.md`,
    body: "Schema evolution rules, compatibility expectations, and the minimum standard for every migration."
  }
];

export default function DocsPage() {
  return (
    <div className="section-space">
      <div className="page-frame">
        <div className="grid gap-10 border-b pb-12 md:grid-cols-[1.05fr_0.95fr]" style={{ borderColor: "var(--border)" }}>
          <div className="space-y-5">
            <div className="mono">Documentation</div>
            <h1 className="display-lg max-w-3xl">Read the registry, standard, and implementation notes in one place.</h1>
          </div>
          <div className="space-y-5 pt-2">
            <p className="body-copy max-w-xl text-[18px] leading-9">
              EvalLedger keeps its public-facing documentation close to the code: the repository
              README, the metadata standard, and the working frontend and API routes are meant to
              agree with each other.
            </p>
            <div className="flex flex-wrap gap-3 ui-copy">
              <Link href="/standard" className="btn-primary">
                Read the standard
              </Link>
              <a href={REPOSITORY_URL} target="_blank" rel="noreferrer" className="btn-secondary">
                Open the repository
              </a>
            </div>
          </div>
        </div>

        <div className="grid gap-6 py-12 md:grid-cols-3">
          {DOC_SECTIONS.map((section) => (
            <a
              key={section.label}
              href={section.href}
              target="_blank"
              rel="noreferrer"
              className="surface block rounded-sm p-6 transition-colors hover:border-[var(--text-dim)]"
            >
              <div className="mono mb-5">{section.label}</div>
              <div className="mb-4 font-[var(--font-display)] text-[30px] leading-[1.08] tracking-[-0.04em]">
                {section.title}
              </div>
              <p className="body-copy">{section.body}</p>
            </a>
          ))}
        </div>

        <div className="grid gap-10 border-t pt-12 md:grid-cols-[0.9fr_1.1fr]" style={{ borderColor: "var(--border)" }}>
          <div>
            <div className="mono mb-4">Direct references</div>
            <div className="space-y-3 ui-copy text-[15px] text-[var(--text-dim)]">
              <a href={`${REPOSITORY_BLOB_URL}/README.md#contamination-methodology`} target="_blank" rel="noreferrer" className="block">
                Contamination methodology
              </a>
              <a href={`${REPOSITORY_BLOB_URL}/README.md#contributing-a-benchmark`} target="_blank" rel="noreferrer" className="block">
                Contributing a benchmark
              </a>
              <a href={`${REPOSITORY_BLOB_URL}/CONTRIBUTING.md`} target="_blank" rel="noreferrer" className="block">
                Contributing code
              </a>
              <a href={`${REPOSITORY_BLOB_URL}/README.md#citing-evalledger`} target="_blank" rel="noreferrer" className="block">
                Citing EvalLedger
              </a>
            </div>
          </div>
          <div className="surface rounded-sm p-6">
            <div className="mono mb-4">What lives where</div>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <div className="ui-copy mb-3 text-[18px] font-medium text-[var(--text)]">Site routes</div>
                <p className="body-copy">
                  Use <span className="mono normal-case tracking-normal">/registry</span> for benchmark
                  records, <span className="mono normal-case tracking-normal">/contamination</span> for
                  ad hoc checks, and <span className="mono normal-case tracking-normal">/submit</span> for
                  the three-step submission flow.
                </p>
              </div>
              <div>
                <div className="ui-copy mb-3 text-[18px] font-medium text-[var(--text)]">Canonical docs</div>
                <p className="body-copy">
                  The metadata contract remains the most stable public artifact. Everything else in the
                  repo is expected to conform to it rather than drift away from it.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-6 border-t pt-12 md:grid-cols-2" style={{ borderColor: "var(--border)" }}>
          {OPERATIONAL_DOCS.map((section) => (
            <a
              key={section.label}
              href={section.href}
              target="_blank"
              rel="noreferrer"
              className="surface block rounded-sm p-6 transition-colors hover:border-[var(--text-dim)]"
            >
              <div className="mono mb-4">{section.label}</div>
              <p className="body-copy">{section.body}</p>
            </a>
          ))}
        </div>

        <div className="grid gap-10 border-t pt-12 md:grid-cols-[0.85fr_1.15fr]" style={{ borderColor: "var(--border)" }}>
          <div>
            <div className="mono mb-4">Product policies</div>
            <h2 className="display-lg text-[2.25rem]">Ship the product with visible guardrails.</h2>
          </div>
          <div className="flex flex-wrap gap-3">
              <Link href={"/privacy" as Route} className="btn-secondary">
                Privacy
              </Link>
            <Link href={"/terms" as Route} className="btn-secondary">
              Terms
            </Link>
            <Link href={"/acceptable-use" as Route} className="btn-secondary">
              Acceptable Use
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

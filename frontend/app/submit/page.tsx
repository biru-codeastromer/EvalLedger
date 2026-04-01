"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { CodeBlock } from "@/components/ui/CodeBlock";
import { APIError, createBenchmark, submitBenchmark } from "@/lib/api";
import { loadSession, subscribeToSessionChange } from "@/lib/session";
import { AuthResponse } from "@/lib/types";

const SEMVER_PATTERN = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

async function sha256File(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export default function SubmitPage() {
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [domain, setDomain] = useState("reasoning");
  const [taskType, setTaskType] = useState("multiple_choice");
  const [version, setVersion] = useState("1.0.0");
  const [license, setLicense] = useState("MIT");
  const [paperUrl, setPaperUrl] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [releaseNotes, setReleaseNotes] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sha, setSha] = useState("");
  const [progress, setProgress] = useState(0);
  const [submittedId, setSubmittedId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<AuthResponse | null>(null);

  useEffect(() => {
    const sync = () => setSession(loadSession());
    sync();
    return subscribeToSessionChange(sync);
  }, []);

  useEffect(() => {
    if (!slug) {
      setSlug(slugify(name));
    }
  }, [name, slug]);

  useEffect(() => {
    if (!file) {
      setSha("");
      return;
    }
    void sha256File(file).then(setSha);
  }, [file]);

  const cliCommand = useMemo(
    () =>
      `evalledger submit --name "${name || "MyBenchmark"}" --slug ${slug || "mybenchmark"} --version ${version} --file ./${file?.name ?? "bench.jsonl"} --domain ${domain} --task-type ${taskType} --license ${license}`,
    [domain, file?.name, license, name, slug, taskType, version]
  );

  const canAdvanceStepOne = name.trim().length > 0 && slug.trim().length > 0 && description.trim().length >= 20;
  const hasValidSemver = SEMVER_PATTERN.test(version.trim());
  const canAdvanceStepTwo = hasValidSemver && file !== null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !canAdvanceStepTwo) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setProgress(20);
    if (!session) {
      setSubmitting(false);
      setProgress(0);
      setError("Sign in before creating registry records or uploading benchmark artifacts.");
      return;
    }
    try {
      await createBenchmark({
        name,
        slug,
        description,
        domain: [domain],
        task_type: taskType
      });
    } catch (caughtError) {
      if (!(caughtError instanceof APIError) || caughtError.status !== 409) {
        setSubmitting(false);
        setProgress(0);
        setError(caughtError instanceof APIError ? caughtError.message : "Could not create the benchmark record.");
        return;
      }
    }
    try {
      setProgress(55);
      const formData = new FormData();
      formData.append("artifact", file);
      formData.append("slug", slug);
      formData.append("version", version);
      formData.append("license", license);
      formData.append("paper_url", paperUrl);
      formData.append("github_url", githubUrl);
      formData.append("release_notes", releaseNotes);
      const response = await submitBenchmark(formData);
      setProgress(100);
      setSubmittedId(response.canonical_id);
    } catch (caughtError) {
      setProgress(0);
      setError(
        caughtError instanceof APIError
          ? caughtError.message
          : "Submission failed. Check that the API is available and the version string is valid."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 opacity-[0.04]">
        <Image src="/images/10-graph-paper.jpg" alt="Graph paper background" fill className="editorial-image" />
      </div>
      <div className="page-frame section-space relative">
        <div className="mb-8 mono">Step {step} of 3</div>
        {!session ? (
          <div className="mb-8 rounded-sm border p-4 text-[15px] text-[var(--text-dim)]" style={{ borderColor: "var(--border)" }}>
            Sign in to claim benchmark ownership, upload artifacts, and generate durable provenance records.
            <Link href="/login" className="ml-2 text-[var(--text)] underline">
              Go to sign in
            </Link>
          </div>
        ) : null}
        <div className="grid gap-10 md:grid-cols-[minmax(0,1fr)_320px]">
          <form className="space-y-8" onSubmit={handleSubmit}>
            {step === 1 ? (
              <>
                <h1 className="display-lg">Register a benchmark.</h1>
                <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Benchmark name" className="w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                <input value={slug} onChange={(event) => setSlug(event.target.value)} placeholder="slug" className="w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" className="min-h-[180px] w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                <div className="grid gap-4 md:grid-cols-2">
                  <input value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="Domain" className="w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                  <input value={taskType} onChange={(event) => setTaskType(event.target.value)} placeholder="Task type" className="w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                </div>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => setStep(2)}
                  disabled={!canAdvanceStepOne}
                >
                  Continue
                </button>
              </>
            ) : null}

            {step === 2 ? (
              <>
                <h1 className="display-lg">Attach the artifact and version metadata.</h1>
                <div className="grid gap-4 md:grid-cols-2">
                  <input value={version} onChange={(event) => setVersion(event.target.value)} placeholder="Version" className="w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                  <input value={license} onChange={(event) => setLicense(event.target.value)} placeholder="License" className="w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                </div>
                <input value={paperUrl} onChange={(event) => setPaperUrl(event.target.value)} placeholder="Paper URL" className="w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                <input value={githubUrl} onChange={(event) => setGithubUrl(event.target.value)} placeholder="GitHub URL" className="w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                <textarea value={releaseNotes} onChange={(event) => setReleaseNotes(event.target.value)} placeholder="Release notes" className="min-h-[180px] w-full rounded-sm border px-4 py-4" style={{ borderColor: "var(--border)", background: "var(--bg)" }} />
                <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                {sha ? <CodeBlock code={sha} /> : null}
                <div className="flex gap-3">
                  <button type="button" className="btn-secondary" onClick={() => setStep(1)}>
                    Back
                  </button>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => setStep(3)}
                    disabled={!canAdvanceStepTwo}
                  >
                    Continue
                  </button>
                </div>
                {!hasValidSemver && version.trim().length > 0 ? (
                  <p className="ui-copy text-[14px] text-[var(--status-contaminated)]">
                    Version must follow semantic versioning like 1.0.0.
                  </p>
                ) : null}
              </>
            ) : null}

            {step === 3 ? (
              <>
                <h1 className="display-lg">Review before submission.</h1>
                <div className="surface rounded-sm p-6">
                  <div className="mono mb-4">Summary</div>
                  <p className="text-[16px] text-[var(--text-dim)]">
                    {name} · {slug} · {version} · {domain} · {taskType}
                  </p>
                  <div className="mt-4 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
                    <div className="h-full bg-[var(--text)] transition-all" style={{ width: `${progress}%` }} />
                  </div>
                </div>
                <div className="flex gap-3">
                  <button type="button" className="btn-secondary" onClick={() => setStep(2)}>
                    Back
                  </button>
                  <button type="submit" className="btn-primary" disabled={submitting || !canAdvanceStepTwo || !session}>
                    {submitting ? "Submitting..." : "Submit"}
                  </button>
                </div>
                {error ? (
                  <p className="ui-copy text-[14px] text-[var(--status-contaminated)]">{error}</p>
                ) : null}
                {submittedId ? (
                  <div className="space-y-4">
                    <div className="surface rounded-sm p-6">
                      <div className="mono mb-3">Registered</div>
                      <div className="display-lg text-[2rem]">{submittedId}</div>
                    </div>
                    <CodeBlock code={cliCommand} />
                  </div>
                ) : null}
              </>
            ) : null}
          </form>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { APIError, createReport } from "@/lib/api";

const REASONS: Array<{ value: string; label: string }> = [
  { value: "malicious", label: "Malicious content" },
  { value: "infringement", label: "Copyright infringement" },
  { value: "mislabeled", label: "Mislabeled or inaccurate" },
  { value: "privacy", label: "Privacy violation" },
  { value: "other", label: "Other" }
];

export function ReportButton({
  resourceType,
  resourceSlug
}: {
  resourceType: "benchmark" | "version";
  resourceSlug: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [reason, setReason] = useState(REASONS[0].value);
  const [detail, setDetail] = useState("");

  const reportMutation = useMutation({
    mutationFn: () =>
      createReport({
        resource_type: resourceType,
        resource_slug: resourceSlug,
        reason,
        detail: detail.trim() ? detail.trim() : undefined
      })
  });

  function handleCancel() {
    setIsOpen(false);
    setDetail("");
    setReason(REASONS[0].value);
    reportMutation.reset();
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    reportMutation.mutate();
  }

  if (reportMutation.isSuccess) {
    return (
      <p className="ui-copy text-[13px] text-[var(--text-dim)]">Report submitted — thank you.</p>
    );
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        className="btn-secondary text-[13px]"
        onClick={() => setIsOpen(true)}
      >
        Report
      </button>
    );
  }

  const isUnauthorized = reportMutation.error instanceof APIError && reportMutation.error.status === 401;

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-sm border p-4"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <div className="mono">Report this {resourceType}</div>
      <div className="space-y-2">
        <label htmlFor="report-reason" className="block text-[13px] text-[var(--text-dim)]">
          Reason
        </label>
        <select
          id="report-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          className="w-full rounded-sm border px-3 py-2 text-[14px]"
          style={{ borderColor: "var(--border)", background: "var(--bg)" }}
        >
          {REASONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-2">
        <label htmlFor="report-detail" className="block text-[13px] text-[var(--text-dim)]">
          Details <span className="text-[var(--muted)]">(optional)</span>
        </label>
        <textarea
          id="report-detail"
          value={detail}
          onChange={(event) => setDetail(event.target.value)}
          placeholder="Add any context that will help us review this report."
          className="min-h-[100px] w-full rounded-sm border px-3 py-2 text-[14px]"
          style={{ borderColor: "var(--border)", background: "var(--bg)" }}
        />
      </div>
      <div className="flex gap-3">
        <button type="submit" className="btn-primary text-[13px]" disabled={reportMutation.isPending}>
          {reportMutation.isPending ? "Submitting…" : "Submit"}
        </button>
        <button
          type="button"
          className="btn-secondary text-[13px]"
          onClick={handleCancel}
          disabled={reportMutation.isPending}
        >
          Cancel
        </button>
      </div>
      {reportMutation.isError ? (
        <p className="ui-copy text-[13px] text-[var(--status-contaminated)]">
          {isUnauthorized ? (
            <>
              You need to be signed in to submit a report.{" "}
              <Link href="/login" className="text-[var(--text)] underline">
                Go to sign in
              </Link>
            </>
          ) : reportMutation.error instanceof APIError ? (
            reportMutation.error.message
          ) : (
            "Could not submit the report. Please try again."
          )}
        </p>
      ) : null}
    </form>
  );
}

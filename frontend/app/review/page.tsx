"use client";

import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";

import { ActivityFeed } from "@/components/ui/ActivityFeed";
import {
  APIError,
  addReviewNote,
  getAdminAuditEvents,
  getAdminStats,
  getCurrentProfile,
  getReviewQueue,
  setBenchmarkVerification
} from "@/lib/api";
import type { ReviewQueueItem } from "@/lib/types";

// ---------------------------------------------------------------------------
// Small helper components
// ---------------------------------------------------------------------------

type ContaminationBadgeProps = { status: string | null };
function ContaminationBadge({ status }: ContaminationBadgeProps) {
  if (!status) return null;
  const styles: Record<string, string> = {
    clean: "bg-green-100 text-green-800 border-green-200",
    pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
    flagged: "bg-orange-100 text-orange-800 border-orange-200",
    contaminated: "bg-red-100 text-red-800 border-red-200",
    unchecked: "bg-gray-100 text-gray-600 border-gray-200"
  };
  const cls = styles[status] ?? "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {status}
    </span>
  );
}

type ProviderBadgeProps = { provider: string };
function ProviderBadge({ provider }: ProviderBadgeProps) {
  return (
    <span className="inline-flex items-center rounded border border-[var(--border)] bg-[var(--bg-subtle)] px-1.5 py-0.5 text-[11px] text-[var(--text-dim)]">
      {provider}
    </span>
  );
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Benchmark review card
// ---------------------------------------------------------------------------

type ReviewCardProps = {
  benchmark: ReviewQueueItem;
  onVerify: (slug: string, verified: boolean, note?: string) => void;
  onNote: (slug: string, note: string) => void;
  isPending: boolean;
};

function ReviewCard({ benchmark, onVerify, onNote, isPending }: ReviewCardProps) {
  const [noteText, setNoteText] = useState("");
  const [showNoteInput, setShowNoteInput] = useState(false);

  return (
    <div
      className="rounded-sm border p-5 space-y-3"
      style={{ borderColor: "var(--border)", background: "var(--bg)" }}
    >
      {/* Header row */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/registry/${benchmark.slug}` as Route}
              className="font-[var(--font-display)] text-[22px] hover:underline"
            >
              {benchmark.name}
            </Link>
            <ContaminationBadge status={benchmark.latest_contamination_status} />
            {benchmark.is_verified && (
              <span className="inline-flex items-center rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                verified
              </span>
            )}
          </div>
          <p className="text-[13px] text-[var(--text-dim)]">{benchmark.description}</p>
        </div>
        {/* Action buttons */}
        <div className="flex flex-shrink-0 gap-2">
          <button
            type="button"
            className="btn-secondary text-[13px]"
            disabled={isPending}
            onClick={() => setShowNoteInput((v) => !v)}
          >
            {showNoteInput ? "Cancel note" : "Add note"}
          </button>
          <button
            type="button"
            className="btn-primary text-[13px]"
            disabled={isPending}
            onClick={() => onVerify(benchmark.slug, !benchmark.is_verified, noteText || undefined)}
          >
            {benchmark.is_verified ? "Remove verification" : "Mark verified"}
          </button>
        </div>
      </div>

      {/* Metadata row */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-[var(--text-dim)]">
        {benchmark.submitter && (
          <span>
            Submitted by{" "}
            <span className="text-[var(--text)]">{benchmark.submitter.username}</span>
            {benchmark.submitter.affiliation && ` · ${benchmark.submitter.affiliation}`}
          </span>
        )}
        {benchmark.submitter_providers.length > 0 && (
          <span className="flex items-center gap-1">
            Auth via{" "}
            {benchmark.submitter_providers.map((p) => (
              <ProviderBadge key={p} provider={p} />
            ))}
          </span>
        )}
        {benchmark.total_versions > 0 && (
          <span>
            {benchmark.total_versions} version{benchmark.total_versions !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Integrity row */}
      {(benchmark.latest_artifact_sha256 || benchmark.latest_artifact_size_bytes !== null) && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-mono text-[var(--text-dim)]">
          {benchmark.latest_artifact_sha256 && (
            <span title={benchmark.latest_artifact_sha256}>
              sha256:{" "}
              <span className="text-[var(--text)]">
                {benchmark.latest_artifact_sha256.slice(0, 16)}…
              </span>
            </span>
          )}
          {benchmark.latest_artifact_size_bytes !== null && (
            <span>size: {formatBytes(benchmark.latest_artifact_size_bytes)}</span>
          )}
          {benchmark.latest_num_examples !== null && (
            <span>{benchmark.latest_num_examples.toLocaleString()} examples</span>
          )}
        </div>
      )}

      {/* Existing review note */}
      {benchmark.review_note && (
        <div className="rounded border border-[var(--border)] bg-[var(--bg-subtle)] px-3 py-2 text-[12px]">
          <span className="text-[var(--text-dim)]">Reviewer note: </span>
          <span className="text-[var(--text)]">{benchmark.review_note}</span>
          {benchmark.reviewed_by && (
            <span className="text-[var(--text-dim)]"> — {benchmark.reviewed_by.username}</span>
          )}
        </div>
      )}

      {/* Note input (inline) */}
      {showNoteInput && (
        <div className="space-y-2">
          <textarea
            className="w-full rounded border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-[13px] text-[var(--text)] placeholder-[var(--text-dim)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            rows={2}
            placeholder="Add a reviewer note (optional)…"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
          />
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-secondary text-[12px]"
              disabled={isPending || !noteText.trim()}
              onClick={() => {
                if (noteText.trim()) {
                  onNote(benchmark.slug, noteText.trim());
                  setNoteText("");
                  setShowNoteInput(false);
                }
              }}
            >
              Save note only
            </button>
            <span className="text-[11px] text-[var(--text-dim)] self-center">
              Or use &quot;Mark verified&quot; to save note + verify in one step.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type QueueStatus = "pending" | "verified" | "all";

export default function ReviewPage() {
  const queryClient = useQueryClient();
  const [queueStatus, setQueueStatus] = useState<QueueStatus>("pending");

  const [profileQuery, statsQuery, reviewQueueQuery, auditQuery] = useQueries({
    queries: [
      { queryKey: ["account"], queryFn: getCurrentProfile, retry: false },
      { queryKey: ["admin-stats"], queryFn: getAdminStats, retry: false },
      {
        queryKey: ["review-queue", queueStatus],
        queryFn: () => getReviewQueue(queueStatus),
        retry: false
      },
      { queryKey: ["admin-audit"], queryFn: getAdminAuditEvents, retry: false }
    ]
  });

  const verifyMutation = useMutation({
    mutationFn: ({ slug, verified, note }: { slug: string; verified: boolean; note?: string }) =>
      setBenchmarkVerification(slug, verified, note),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["review-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-audit"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-stats"] });
    }
  });

  const noteMutation = useMutation({
    mutationFn: ({ slug, note }: { slug: string; note: string }) => addReviewNote(slug, note),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["review-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-audit"] });
    }
  });

  if (profileQuery.isLoading) {
    return (
      <div className="page-frame section-space">
        <p className="text-[16px] text-[var(--text-dim)]">Loading…</p>
      </div>
    );
  }

  if (!profileQuery.data?.user.is_admin) {
    const errorMessage =
      profileQuery.error instanceof APIError
        ? profileQuery.error.message
        : "Administrator access is required to review and verify benchmark records.";
    return (
      <div className="page-frame section-space space-y-6">
        <div className="mono">Review</div>
        <h1 className="display-lg max-w-3xl">The review queue is restricted to administrator accounts.</h1>
        <p className="max-w-2xl text-[17px] leading-8 text-[var(--text-dim)]">{errorMessage}</p>
        <Link href={"/account" as Route} className="btn-secondary inline-flex">
          Return to account
        </Link>
      </div>
    );
  }

  const stats = statsQuery.data;
  const isActionPending = verifyMutation.isPending || noteMutation.isPending;

  return (
    <div className="page-frame section-space space-y-10">
      {/* Header */}
      <section className="space-y-4">
        <div className="mono">Review queue</div>
        <h1 className="display-lg max-w-4xl">
          Verify benchmark records and inspect administrative activity.
        </h1>

        {/* Stats bar */}
        {stats && (
          <div className="flex flex-wrap gap-4 text-[13px]">
            <span>
              <span className="font-semibold text-[var(--text)]">{stats.unverified_count}</span>
              <span className="text-[var(--text-dim)]"> pending verification</span>
            </span>
            <span className="text-[var(--text-dim)]">·</span>
            <span>
              <span className="font-semibold text-[var(--text)]">{stats.verified_count}</span>
              <span className="text-[var(--text-dim)]"> verified</span>
            </span>
            <span className="text-[var(--text-dim)]">·</span>
            <span>
              <span className="font-semibold text-[var(--text)]">{stats.total_benchmarks}</span>
              <span className="text-[var(--text-dim)]"> total benchmarks</span>
            </span>
            {stats.contamination_flagged_count > 0 && (
              <>
                <span className="text-[var(--text-dim)]">·</span>
                <span>
                  <span className="font-semibold text-orange-600">{stats.contamination_flagged_count}</span>
                  <span className="text-[var(--text-dim)]"> contamination flags</span>
                </span>
              </>
            )}
          </div>
        )}
      </section>

      {/* Filter tabs */}
      <section>
        <div className="flex gap-2 border-b border-[var(--border)] pb-0">
          {(["pending", "verified", "all"] as QueueStatus[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setQueueStatus(tab)}
              className={[
                "px-4 py-2 text-[13px] capitalize border-b-2 -mb-px transition-colors",
                queueStatus === tab
                  ? "border-[var(--accent)] text-[var(--text)] font-medium"
                  : "border-transparent text-[var(--text-dim)] hover:text-[var(--text)]"
              ].join(" ")}
            >
              {tab}
            </button>
          ))}
        </div>
      </section>

      {/* Review queue */}
      <section className="space-y-4">
        {reviewQueueQuery.isLoading ? (
          <p className="text-[14px] text-[var(--text-dim)]">Loading queue…</p>
        ) : reviewQueueQuery.isError ? (
          <p className="text-[14px] text-red-600">
            Failed to load queue:{" "}
            {reviewQueueQuery.error instanceof APIError
              ? reviewQueueQuery.error.message
              : "Unknown error"}
          </p>
        ) : reviewQueueQuery.data?.length ? (
          reviewQueueQuery.data.map((benchmark) => (
            <ReviewCard
              key={benchmark.id}
              benchmark={benchmark}
              isPending={isActionPending}
              onVerify={(slug, verified, note) =>
                verifyMutation.mutate({ slug, verified, note })
              }
              onNote={(slug, note) => noteMutation.mutate({ slug, note })}
            />
          ))
        ) : (
          <div className="rounded-sm border border-[var(--border)] px-5 py-8 text-center">
            <p className="text-[14px] text-[var(--text-dim)]">
              {queueStatus === "pending"
                ? "No benchmarks are currently waiting for review."
                : queueStatus === "verified"
                  ? "No verified benchmarks found."
                  : "No benchmarks found."}
            </p>
          </div>
        )}

        {/* Mutation error banner */}
        {(verifyMutation.isError || noteMutation.isError) && (
          <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
            Action failed:{" "}
            {(verifyMutation.error ?? noteMutation.error) instanceof APIError
              ? ((verifyMutation.error ?? noteMutation.error) as APIError).message
              : "Unknown error — please try again."}
          </div>
        )}
      </section>

      {/* Audit feed */}
      <section className="space-y-4">
        <div className="mono">Administrative activity</div>
        {auditQuery.isLoading ? (
          <p className="text-[14px] text-[var(--text-dim)]">Loading activity…</p>
        ) : (
          <ActivityFeed
            events={auditQuery.data ?? []}
            emptyMessage="Administrative actions will appear here once review work begins."
          />
        )}
      </section>
    </div>
  );
}

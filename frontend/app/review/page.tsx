"use client";

import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import type { Route } from "next";
import Link from "next/link";

import { ActivityFeed } from "@/components/ui/ActivityFeed";
import {
  APIError,
  getAdminAuditEvents,
  getCurrentProfile,
  getReviewQueue,
  setBenchmarkVerification
} from "@/lib/api";

export default function ReviewPage() {
  const queryClient = useQueryClient();
  const [profileQuery, reviewQueueQuery, auditQuery] = useQueries({
    queries: [
      { queryKey: ["account"], queryFn: getCurrentProfile, retry: false },
      { queryKey: ["review-queue"], queryFn: getReviewQueue, retry: false },
      { queryKey: ["admin-audit"], queryFn: getAdminAuditEvents, retry: false }
    ]
  });

  const verifyMutation = useMutation({
    mutationFn: ({ slug, verified }: { slug: string; verified: boolean }) =>
      setBenchmarkVerification(slug, verified),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["review-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-audit"] });
    }
  });

  if (profileQuery.isLoading || reviewQueueQuery.isLoading || auditQuery.isLoading) {
    return (
      <div className="page-frame section-space">
        <p className="text-[16px] text-[var(--text-dim)]">Loading the review queue…</p>
      </div>
    );
  }

  if (!profileQuery.data || !profileQuery.data.user.is_admin) {
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

  return (
    <div className="page-frame section-space space-y-12">
      <section className="space-y-4">
        <div className="mono">Review queue</div>
        <h1 className="display-lg max-w-4xl">Verify benchmark records and inspect the latest administrative activity.</h1>
      </section>

      <section className="space-y-4">
        {reviewQueueQuery.data?.length ? (
          reviewQueueQuery.data.map((benchmark) => (
            <div
              key={benchmark.id}
              className="rounded-sm border p-5"
              style={{ borderColor: "var(--border)", background: "var(--bg)" }}
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <Link href={`/registry/${benchmark.slug}`} className="font-[var(--font-display)] text-[30px]">
                    {benchmark.name}
                  </Link>
                  <p className="mt-2 max-w-3xl text-[15px] text-[var(--text-dim)]">{benchmark.description}</p>
                </div>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={verifyMutation.isPending}
                  onClick={() => verifyMutation.mutate({ slug: benchmark.slug, verified: !benchmark.is_verified })}
                >
                  {benchmark.is_verified ? "Remove verification" : "Mark verified"}
                </button>
              </div>
            </div>
          ))
        ) : (
          <p className="text-[15px] text-[var(--text-dim)]">No benchmarks are currently waiting for review.</p>
        )}
      </section>

      <section className="space-y-4">
        <div className="mono">Administrative activity</div>
        <ActivityFeed
          events={auditQuery.data ?? []}
          emptyMessage="Administrative actions will appear here once review work begins."
        />
      </section>
    </div>
  );
}

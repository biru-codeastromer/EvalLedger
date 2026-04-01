"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ActivityFeed } from "@/components/ui/ActivityFeed";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { APIError, createApiKey, getCurrentProfile, revokeApiKey } from "@/lib/api";
import { clearSession } from "@/lib/session";

export default function AccountPage() {
  const queryClient = useQueryClient();
  const [apiKeyName, setApiKeyName] = useState("CLI token");
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const profileQuery = useQuery({
    queryKey: ["account"],
    queryFn: getCurrentProfile,
    retry: false
  });

  const createKeyMutation = useMutation({
    mutationFn: createApiKey,
    onSuccess: (payload) => {
      setCreatedKey(payload.api_key);
      void queryClient.invalidateQueries({ queryKey: ["account"] });
    }
  });

  const revokeMutation = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["account"] });
    }
  });

  const accountError = useMemo(() => {
    if (!(profileQuery.error instanceof APIError)) {
      return null;
    }
    if (profileQuery.error.status === 401) {
      return "Sign in to view your account, API keys, and ownership activity.";
    }
    return profileQuery.error.message;
  }, [profileQuery.error]);

  if (profileQuery.isLoading) {
    return (
      <div className="page-frame section-space">
        <p className="text-[16px] text-[var(--text-dim)]">Loading your account…</p>
      </div>
    );
  }

  if (accountError || !profileQuery.data) {
    return (
      <div className="page-frame section-space space-y-6">
        <div className="mono">Account</div>
        <h1 className="display-lg max-w-3xl">Your authenticated workspace lives here.</h1>
        <p className="max-w-2xl text-[17px] leading-8 text-[var(--text-dim)]">{accountError}</p>
        <Link href="/login" className="btn-primary inline-flex">
          Sign In
        </Link>
      </div>
    );
  }

  const { user, api_keys, benchmarks, recent_activity } = profileQuery.data;

  return (
    <div className="page-frame section-space space-y-12">
      <section className="grid gap-8 md:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-5">
          <div className="mono">Account</div>
          <h1 className="display-lg max-w-3xl">Manage ownership, API keys, and your recent registry activity.</h1>
          <p className="max-w-2xl text-[17px] leading-8 text-[var(--text-dim)]">
            Signed in as {user.username}. Use this page to mint CLI credentials, inspect owned benchmarks,
            and review the latest actions recorded in the audit trail.
          </p>
        </div>
        <div className="surface rounded-sm p-6">
          <div className="mono mb-3">Profile</div>
          <div className="space-y-2 text-[15px] text-[var(--text-dim)]">
            <p>{user.email}</p>
            <p>{user.affiliation ?? "Independent researcher"}</p>
            <p>{user.is_admin ? "Administrator privileges enabled" : "Standard contributor access"}</p>
          </div>
          <button
            type="button"
            className="btn-secondary mt-6"
            onClick={() => {
              clearSession();
              window.location.href = "/login";
            }}
          >
            Sign Out
          </button>
        </div>
      </section>

      <section className="grid gap-8 md:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <div className="mono">Owned benchmarks</div>
          {benchmarks.length === 0 ? (
            <p className="text-[15px] text-[var(--text-dim)]">
              No benchmarks are attached to this account yet. Submit a versioned record to begin.
            </p>
          ) : (
            <div className="space-y-3">
              {benchmarks.map((benchmark) => (
                <Link
                  key={benchmark.id}
                  href={`/registry/${benchmark.slug}`}
                  className="block rounded-sm border p-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg)" }}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="font-[var(--font-display)] text-[26px]">{benchmark.name}</div>
                    <div className="mono">{benchmark.is_verified ? "Verified" : "Pending review"}</div>
                  </div>
                  <div className="mt-2 text-[15px] text-[var(--text-dim)]">
                    {benchmark.slug} · {benchmark.total_versions} version{benchmark.total_versions === 1 ? "" : "s"}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4 rounded-sm border p-6" style={{ borderColor: "var(--border)" }}>
          <div className="mono">API keys</div>
          <div className="flex gap-3">
            <input
              value={apiKeyName}
              onChange={(event) => setApiKeyName(event.target.value)}
              placeholder="Key name"
              className="w-full rounded-sm border px-4 py-3"
              style={{ borderColor: "var(--border)", background: "var(--bg)" }}
            />
            <button
              type="button"
              className="btn-primary"
              disabled={createKeyMutation.isPending || apiKeyName.trim().length < 2}
              onClick={() => createKeyMutation.mutate(apiKeyName.trim())}
            >
              Create
            </button>
          </div>
          {createdKey ? <CodeBlock code={createdKey} /> : null}
          <div className="space-y-3">
            {api_keys.map((item) => (
              <div
                key={item.id}
                className="rounded-sm border p-4"
                style={{ borderColor: "var(--border)", background: "var(--bg)" }}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[15px] font-medium text-[var(--text)]">{item.name ?? "Unnamed key"}</div>
                    <div className="text-[13px] text-[var(--muted)]">
                      Last used {item.last_used_at ? new Date(item.last_used_at).toLocaleString() : "never"}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={!item.is_active || revokeMutation.isPending}
                    onClick={() => revokeMutation.mutate(item.id)}
                  >
                    {item.is_active ? "Revoke" : "Revoked"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="mono">Recent activity</div>
        <ActivityFeed
          events={recent_activity}
          emptyMessage="No audit events have been recorded for this account yet."
        />
      </section>
    </div>
  );
}

"use client";

/**
 * OAuth callback handler.
 *
 * The backend redirects here after a successful OAuth login:
 *   GET /auth/callback?token=<jwt>
 *
 * This page reads the token from the URL, fetches the user profile,
 * stores the session in localStorage, and redirects to the app.
 *
 * On failure it shows an inline error with a link back to the login page.
 */

import type { Route } from "next";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { API_PUBLIC_URL } from "@/lib/api";
import { AuthResponse, MeResponse } from "@/lib/types";
import { saveSession } from "@/lib/session";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const oauthError = params.get("error");

    if (oauthError) {
      setError(decodeURIComponent(oauthError));
      return;
    }

    if (!token) {
      setError("No authentication token was returned. Please try signing in again.");
      return;
    }

    // Fetch the user profile using the token we just received.
    (async () => {
      try {
        const response = await fetch(`${API_PUBLIC_URL}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        });

        if (!response.ok) {
          setError("Could not verify your account. Please try signing in again.");
          return;
        }

        const me = (await response.json()) as MeResponse;
        const session: AuthResponse = {
          access_token: token,
          token_type: "bearer",
          user: me.user,
        };
        saveSession(session);
        router.replace((me.user.is_admin ? "/review" : "/account") as Route);
      } catch {
        setError("Something went wrong completing sign-in. Please try again.");
      }
    })();
  }, [router]);

  if (error) {
    return (
      <div className="section-space">
        <div className="page-frame max-w-xl space-y-6">
          <div className="mono">Authentication error</div>
          <h1 className="display-lg">Sign-in failed</h1>
          <p className="body-copy text-[var(--text-dim)]">{error}</p>
          <Link href={"/login" as Route} className="btn-primary inline-block">
            Back to sign-in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="section-space">
      <div className="page-frame max-w-xl space-y-4">
        <div className="mono">Completing sign-in…</div>
        <p className="body-copy text-[var(--text-dim)]">
          Verifying your account. You will be redirected in a moment.
        </p>
      </div>
    </div>
  );
}

"use client";

import { FormEvent, useState } from "react";

import { loginUser, registerUser } from "@/lib/api";
import { AuthResponse } from "@/lib/types";

type Mode = "login" | "register";

function persistSession(payload: AuthResponse): void {
  window.localStorage.setItem(
    "evalledger.session",
    JSON.stringify({
      access_token: payload.access_token,
      token_type: payload.token_type,
      user: payload.user
    })
  );
}

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload =
        mode === "login"
          ? await loginUser({ email, password })
          : await registerUser({ email, password, username, display_name: displayName });
      persistSession(payload);
      setSession(payload);
    } catch {
      setError(
        "We could not complete that request. If the backend is not running yet, start the API or point NEXT_PUBLIC_API_URL at the deployed service."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="section-space">
      <div className="page-frame grid gap-10 md:grid-cols-[0.95fr_1.05fr]">
        <div className="space-y-5">
          <div className="mono">Authentication</div>
          <h1 className="display-lg max-w-2xl">Sign in to manage submissions, API keys, and private provenance work.</h1>
          <p className="body-copy max-w-xl text-[18px] leading-9">
            EvalLedger uses JWT sessions for the web application and API keys for the CLI. The same
            account can create benchmark records, inspect ownership, and mint tokens for automated use.
          </p>
        </div>

        <div className="surface rounded-sm p-6">
          <div className="mb-6 flex gap-2 ui-copy">
            <button
              type="button"
              className="rounded-sm border px-4 py-2 text-[14px]"
              style={{
                borderColor: mode === "login" ? "var(--text)" : "var(--border)",
                background: mode === "login" ? "var(--bg)" : "transparent"
              }}
              onClick={() => setMode("login")}
            >
              Sign in
            </button>
            <button
              type="button"
              className="rounded-sm border px-4 py-2 text-[14px]"
              style={{
                borderColor: mode === "register" ? "var(--text)" : "var(--border)",
                background: mode === "register" ? "var(--bg)" : "transparent"
              }}
              onClick={() => setMode("register")}
            >
              Create account
            </button>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              placeholder="Email"
              className="w-full rounded-sm border px-4 py-4"
              style={{ borderColor: "var(--border)", background: "var(--bg)" }}
            />
            {mode === "register" ? (
              <>
                <input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="Username"
                  className="w-full rounded-sm border px-4 py-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg)" }}
                />
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Display name"
                  className="w-full rounded-sm border px-4 py-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg)" }}
                />
              </>
            ) : null}
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              placeholder="Password"
              className="w-full rounded-sm border px-4 py-4"
              style={{ borderColor: "var(--border)", background: "var(--bg)" }}
            />

            <button
              type="submit"
              className="btn-primary"
              disabled={
                submitting ||
                email.trim().length === 0 ||
                password.trim().length < 8 ||
                (mode === "register" && username.trim().length < 3)
              }
            >
              {submitting ? "Saving..." : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          {error ? (
            <p className="ui-copy mt-4 text-[14px] text-[var(--status-contaminated)]">{error}</p>
          ) : null}

          {session ? (
            <div className="mt-6 rounded-sm border bg-[var(--bg)] p-5" style={{ borderColor: "var(--border)" }}>
              <div className="mono mb-3">Session ready</div>
              <div className="ui-copy text-[18px] font-medium text-[var(--text)]">{session.user.username}</div>
              <p className="body-copy mt-2">
                The access token is stored in local storage for this browser session. You can now use
                the same account for API keys and protected submissions.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

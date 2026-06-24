"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg)",
          color: "var(--text)",
          fontFamily: "Georgia, serif",
          padding: "24px"
        }}
      >
        <div style={{ maxWidth: "32rem", textAlign: "center" }}>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 600, margin: "0 0 1rem" }}>
            Something went wrong.
          </h1>
          <p style={{ fontSize: "16px", color: "var(--text-dim)", margin: "0 0 2rem" }}>
            An unexpected error occurred while loading EvalLedger. Please reload the page to
            continue.
          </p>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              background: "var(--accent)",
              color: "var(--accent-fg)",
              fontSize: "16px",
              lineHeight: 1,
              fontWeight: 400,
              padding: "10px 20px",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer"
            }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}

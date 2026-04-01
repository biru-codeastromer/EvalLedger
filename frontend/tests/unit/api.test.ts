import { afterEach, describe, expect, it, vi } from "vitest";

import { APIError, createBenchmark, getOverview } from "@/lib/api";
import { saveSession } from "@/lib/session";

describe("api client", () => {
  const storage = (() => {
    const values = new Map<string, string>();
    return {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
      clear: () => values.clear()
    };
  })();

  Object.defineProperty(window, "localStorage", {
    value: storage,
    configurable: true
  });

  afterEach(() => {
    vi.restoreAllMocks();
    storage.clear();
  });

  it("parses overview payloads", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          total_benchmarks: 15,
          total_versions: 15,
          contamination_checks: 3,
          benchmarks_flagged: 1
        })
      )
    );

    const payload = await getOverview();
    expect(payload.total_benchmarks).toBe(15);
    fetchMock.mockRestore();
  });

  it("attaches the stored bearer token on authenticated requests", async () => {
    saveSession({
      access_token: "token-123",
      token_type: "bearer",
      user: {
        id: "user-1",
        email: "researcher@example.com",
        username: "researcher",
        is_verified: false,
        is_admin: false
      }
    });

    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "benchmark-1",
          slug: "mmlu",
          name: "MMLU",
          description: "Massive multitask language understanding.",
          domain: ["reasoning"],
          task_type: "multiple_choice",
          is_verified: false,
          total_versions: 1,
          total_citations: 0,
          created_at: "2026-04-02T00:00:00Z",
          updated_at: "2026-04-02T00:00:00Z",
          latest_version: "1.0.0",
          latest_contamination_status: "pending",
          latest_num_examples: 10
        })
      )
    );

    await createBenchmark({
      name: "MMLU",
      slug: "mmlu",
      description: "Massive multitask language understanding.",
      domain: ["reasoning"],
      task_type: "multiple_choice"
    });

    const request = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(request?.headers);
    expect(headers.get("Authorization")).toBe("Bearer token-123");
  });

  it("raises APIError with backend messages", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "forbidden", message: "Only owners may submit versions" } }), {
        status: 403
      })
    );

    await expect(
      createBenchmark({
        name: "MMLU",
        slug: "mmlu",
        description: "Massive multitask language understanding.",
        domain: ["reasoning"],
        task_type: "multiple_choice"
      })
    ).rejects.toBeInstanceOf(APIError);
  });
});

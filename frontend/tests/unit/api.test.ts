import { describe, expect, it, vi } from "vitest";

import { getOverview } from "@/lib/api";

describe("api client", () => {
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
});


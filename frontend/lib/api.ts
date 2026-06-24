import {
  AdminStats,
  APIKeyMetadata,
  AuditEvent,
  BenchmarkDetail,
  BenchmarkReviewContext,
  BenchmarkVerificationResponse,
  BenchmarkListItem,
  ContaminationReport,
  Corpus,
  MeResponse,
  OverviewStats,
  RecentSubmission,
  ReviewQueueItem,
  VersionDetail
} from "@/lib/types";
import { getAccessToken } from "@/lib/session";

const LOCALHOST_API_URL = "http://localhost:8000";

function resolveApiUrl(value: string | undefined, varName: string): string {
  if (value) {
    return value;
  }
  if (process.env.NODE_ENV === "production") {
    console.warn(
      `[EvalLedger] ${varName} is not set; falling back to ${LOCALHOST_API_URL}. ` +
        "This is almost certainly a misconfiguration in production."
    );
  }
  return LOCALHOST_API_URL;
}

const API_INTERNAL_URL = resolveApiUrl(process.env.API_INTERNAL_URL, "API_INTERNAL_URL");
export const API_PUBLIC_URL = resolveApiUrl(process.env.NEXT_PUBLIC_API_URL, "NEXT_PUBLIC_API_URL");

// Bound every JSON read with a timeout. Without this an unreachable or
// cold-starting backend makes a server-rendered page's fetch hang forever,
// which blocks the whole Vercel function and the site never opens. On timeout
// the fetch aborts and the caller renders its fallback/error UI instead.
const FETCH_TIMEOUT_MS = Number(process.env.API_FETCH_TIMEOUT_MS) || 10000;

export class APIError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.code = code;
  }
}

function getBaseUrl(clientSide = false): string {
  return clientSide ? API_PUBLIC_URL : API_INTERNAL_URL;
}

function buildAuthHeaders(headers?: HeadersInit): Headers {
  const merged = new Headers(headers);
  const token = getAccessToken();
  if (token) {
    merged.set("Authorization", `Bearer ${token}`);
  }
  return merged;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    let code: string | undefined;
    try {
      const payload = (await response.json()) as {
        error?: {
          message?: string;
          code?: string;
        };
      };
      message = payload.error?.message ?? message;
      code = payload.error?.code;
    } catch {
      // Ignore JSON parsing failures for non-JSON error responses.
    }
    throw new APIError(message, response.status, code);
  }
  return (await response.json()) as T;
}

async function fetchJSON<T>(
  path: string,
  options?: RequestInit,
  clientSide = false,
  authenticated = false
): Promise<T> {
  const response = await fetch(`${getBaseUrl(clientSide)}${path}`, {
    ...options,
    headers: authenticated ? buildAuthHeaders(options?.headers) : options?.headers,
    cache: "no-store",
    signal: options?.signal ?? AbortSignal.timeout(FETCH_TIMEOUT_MS)
  });
  return parseResponse<T>(response);
}

export async function getOverview(): Promise<OverviewStats> {
  return fetchJSON<OverviewStats>("/stats/overview");
}

export async function getRecent(): Promise<RecentSubmission[]> {
  return fetchJSON<RecentSubmission[]>("/stats/recent?limit=12");
}

export async function getBenchmarks(query = ""): Promise<BenchmarkListItem[]> {
  const payload = await fetchJSON<{ items: BenchmarkListItem[] }>(
    `/search?q=${encodeURIComponent(query)}`
  );
  return payload.items;
}

export async function getBenchmark(slug: string): Promise<BenchmarkDetail> {
  return fetchJSON<BenchmarkDetail>(`/benchmarks/${slug}`);
}

export async function getBenchmarkActivity(slug: string): Promise<AuditEvent[]> {
  return fetchJSON<AuditEvent[]>(`/benchmarks/${slug}/activity`);
}

export async function getVersions(slug: string): Promise<VersionDetail[]> {
  const versions = await fetchJSON<Array<Omit<VersionDetail, "citations">>>(`/benchmarks/${slug}/versions`);
  return versions as VersionDetail[];
}

export async function getVersion(slug: string, version: string): Promise<VersionDetail> {
  return fetchJSON<VersionDetail>(`/benchmarks/${slug}/${version}`);
}

export async function getVersionActivity(slug: string, version: string): Promise<AuditEvent[]> {
  return fetchJSON<AuditEvent[]>(`/benchmarks/${slug}/${version}/activity`);
}

export async function getContamination(slug: string, version: string): Promise<ContaminationReport[]> {
  return fetchJSON<ContaminationReport[]>(`/benchmarks/${slug}/${version}/contamination`);
}

export async function getCorpora(clientSide = true): Promise<Corpus[]> {
  return fetchJSON<Corpus[]>("/contamination/corpora", undefined, clientSide);
}

export async function submitBenchmark(formData: FormData): Promise<{
  canonical_id: string;
  contamination_job_ids: string[];
}> {
  const response = await fetch(`${getBaseUrl(true)}/benchmarks/${formData.get("slug")}/versions`, {
    method: "POST",
    body: formData,
    headers: buildAuthHeaders()
  });
  return parseResponse<{
    canonical_id: string;
    contamination_job_ids: string[];
  }>(response);
}

export async function createBenchmark(payload: Record<string, unknown>): Promise<BenchmarkDetail> {
  const response = await fetch(`${getBaseUrl(true)}/benchmarks`, {
    method: "POST",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload)
  });
  return parseResponse<BenchmarkDetail>(response);
}

export async function runAdHocCheck(formData: FormData): Promise<{ job_id: string }> {
  const response = await fetch(`${getBaseUrl(true)}/contamination/check`, {
    method: "POST",
    body: formData
  });
  return parseResponse<{ job_id: string }>(response);
}

export async function getJob(jobId: string): Promise<{
  status: string;
  result?: unknown;
}> {
  return fetchJSON<{ status: string; result?: unknown }>(`/contamination/jobs/${jobId}`, undefined, true);
}

/**
 * Fetch the current user's profile using an explicit Bearer token.
 * Used by the OAuth callback page before the token is stored in localStorage.
 */
export async function fetchMeWithToken(token: string): Promise<MeResponse> {
  const response = await fetch(`${API_PUBLIC_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return parseResponse<MeResponse>(response);
}

export async function getCurrentProfile(): Promise<MeResponse> {
  return fetchJSON<MeResponse>("/auth/me", undefined, true, true);
}

export async function createApiKey(name: string): Promise<{ api_key: string; metadata: APIKeyMetadata }> {
  const response = await fetch(`${getBaseUrl(true)}/auth/api-keys`, {
    method: "POST",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ name })
  });
  return parseResponse<{ api_key: string; metadata: APIKeyMetadata }>(response);
}

export async function revokeApiKey(id: string): Promise<void> {
  const response = await fetch(`${getBaseUrl(true)}/auth/api-keys/${id}`, {
    method: "DELETE",
    headers: buildAuthHeaders()
  });
  if (!response.ok) {
    await parseResponse<void>(response);
  }
}

export async function exportMyData(): Promise<unknown> {
  const response = await fetch(`${getBaseUrl(true)}/auth/me/export`, {
    headers: buildAuthHeaders()
  });
  return parseResponse<unknown>(response);
}

export async function deleteMyAccount(): Promise<void> {
  const response = await fetch(`${getBaseUrl(true)}/auth/me`, {
    method: "DELETE",
    headers: buildAuthHeaders()
  });
  if (!response.ok) {
    await parseResponse<void>(response);
  }
}

export async function getReviewQueue(status: "pending" | "verified" | "all" = "pending"): Promise<ReviewQueueItem[]> {
  return fetchJSON<ReviewQueueItem[]>(`/admin/review-queue?status=${status}`, undefined, true, true);
}

export async function getAdminAuditEvents(): Promise<AuditEvent[]> {
  return fetchJSON<AuditEvent[]>("/admin/audit-events", undefined, true, true);
}

export async function setBenchmarkVerification(
  slug: string,
  verified: boolean,
  note?: string
): Promise<BenchmarkVerificationResponse> {
  const response = await fetch(`${getBaseUrl(true)}/admin/benchmarks/${slug}/verification`, {
    method: "PATCH",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ verified, note })
  });
  return parseResponse<BenchmarkVerificationResponse>(response);
}

export async function getAdminStats(): Promise<AdminStats> {
  return fetchJSON<AdminStats>("/admin/stats", undefined, true, true);
}

export async function addReviewNote(slug: string, note: string): Promise<BenchmarkVerificationResponse> {
  const response = await fetch(`${getBaseUrl(true)}/admin/benchmarks/${slug}/notes`, {
    method: "POST",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ note })
  });
  return parseResponse<BenchmarkVerificationResponse>(response);
}

export async function getBenchmarkReviewContext(slug: string): Promise<BenchmarkReviewContext> {
  return fetchJSON<BenchmarkReviewContext>(`/admin/benchmarks/${slug}/context`, undefined, true, true);
}

import {
  AuthResponse,
  BenchmarkDetail,
  BenchmarkListItem,
  ContaminationReport,
  Corpus,
  OverviewStats,
  RecentSubmission,
  VersionDetail
} from "@/lib/types";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
export const API_PUBLIC_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getBaseUrl(clientSide = false): string {
  return clientSide ? API_PUBLIC_URL : API_INTERNAL_URL;
}

async function fetchJSON<T>(path: string, options?: RequestInit, clientSide = false): Promise<T> {
  const response = await fetch(`${getBaseUrl(clientSide)}${path}`, {
    ...options,
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
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

export async function getVersions(slug: string): Promise<VersionDetail[]> {
  const versions = await fetchJSON<Array<Omit<VersionDetail, "citations">>>(`/benchmarks/${slug}/versions`);
  return versions as VersionDetail[];
}

export async function getVersion(slug: string, version: string): Promise<VersionDetail> {
  return fetchJSON<VersionDetail>(`/benchmarks/${slug}/${version}`);
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
    body: formData
  });
  if (!response.ok) {
    throw new Error(`Submission failed: ${response.status}`);
  }
  return (await response.json()) as {
    canonical_id: string;
    contamination_job_ids: string[];
  };
}

export async function createBenchmark(payload: Record<string, unknown>): Promise<BenchmarkDetail> {
  const response = await fetch(`${getBaseUrl(true)}/benchmarks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`Benchmark creation failed: ${response.status}`);
  }
  return (await response.json()) as BenchmarkDetail;
}

export async function runAdHocCheck(formData: FormData): Promise<{ job_id: string }> {
  const response = await fetch(`${getBaseUrl(true)}/contamination/check`, {
    method: "POST",
    body: formData
  });
  if (!response.ok) {
    throw new Error(`Contamination check failed: ${response.status}`);
  }
  return (await response.json()) as { job_id: string };
}

export async function getJob(jobId: string): Promise<{
  status: string;
  result?: unknown;
}> {
  return fetchJSON<{ status: string; result?: unknown }>(`/contamination/jobs/${jobId}`, undefined, true);
}

export async function loginUser(payload: { email: string; password: string }): Promise<AuthResponse> {
  const response = await fetch(`${getBaseUrl(true)}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`Sign-in failed: ${response.status}`);
  }
  return (await response.json()) as AuthResponse;
}

export async function registerUser(payload: {
  email: string;
  username: string;
  password: string;
  display_name?: string;
}): Promise<AuthResponse> {
  const response = await fetch(`${getBaseUrl(true)}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(`Registration failed: ${response.status}`);
  }
  return (await response.json()) as AuthResponse;
}

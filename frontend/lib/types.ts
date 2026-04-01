export type ContaminationStatus = "clean" | "flagged" | "contaminated" | "pending" | "unchecked";

export interface BenchmarkListItem {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  domain: string[];
  task_type: string | null;
  is_verified: boolean;
  total_versions: number;
  total_citations: number;
  created_at: string;
  updated_at: string;
  latest_version: string | null;
  latest_contamination_status: ContaminationStatus | null;
  latest_num_examples: number | null;
}

export interface BenchmarkDetail extends BenchmarkListItem {
  submitter?: {
    username: string;
    display_name?: string | null;
    affiliation?: string | null;
  } | null;
}

export interface VersionDetail {
  id: string;
  benchmark_id: string;
  version: string;
  artifact_sha256: string | null;
  artifact_url: string | null;
  artifact_size_bytes: number | null;
  num_examples: number | null;
  splits: Record<string, number> | null;
  language: string[] | null;
  license: string | null;
  paper_url: string | null;
  paper_arxiv_id: string | null;
  github_url: string | null;
  release_notes: string | null;
  metadata: Record<string, unknown> | null;
  contamination_status: ContaminationStatus;
  released_at: string | null;
  created_at: string;
  citations: {
    bibtex: string;
    apa: string;
    mla: string;
    cff: string;
    evalledger_id: string;
  };
}

export interface OverviewStats {
  total_benchmarks: number;
  total_versions: number;
  contamination_checks: number;
  benchmarks_flagged: number;
}

export interface RecentSubmission {
  id: string;
  benchmark_slug: string;
  benchmark_name: string;
  version: string;
  contamination_status: ContaminationStatus;
  created_at: string;
}

export interface Corpus {
  id: string;
  name: string;
  description: string | null;
  version: string | null;
  size_tokens: number | null;
  source_url: string | null;
  is_active: boolean;
}

export interface ContaminationReport {
  id: string;
  corpus_id: string;
  corpus_name?: string | null;
  status: ContaminationStatus;
  overlap_score: number | null;
  num_flagged_examples: number | null;
  flagged_examples: Array<{
    example_index: number;
    benchmark_example: string;
    corpus_match: string;
    similarity: number;
  }> | null;
  minhash_threshold: number;
  job_started_at: string | null;
  job_completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  display_name?: string | null;
  affiliation?: string | null;
  is_verified: boolean;
  is_admin: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface APIKeyMetadata {
  id: string;
  name: string | null;
  last_used_at: string | null;
  created_at: string;
  is_active: boolean;
}

export interface OwnedBenchmark {
  id: string;
  slug: string;
  name: string;
  total_versions: number;
  is_verified: boolean;
  updated_at: string;
}

export interface AuditActor {
  id: string;
  username: string;
  display_name?: string | null;
  affiliation?: string | null;
  is_verified: boolean;
}

export interface AuditEvent {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  resource_slug: string | null;
  summary: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  actor: AuditActor | null;
}

export interface MeResponse {
  user: AuthUser;
  api_keys: APIKeyMetadata[];
  benchmarks: OwnedBenchmark[];
  recent_activity: AuditEvent[];
}

export interface BenchmarkVerificationResponse {
  benchmark: BenchmarkDetail;
}

# Review and Verification Workflow

This document describes how EvalLedger admins review and verify benchmark records. It covers the tools available, the expected workflow for new submissions, the data that informs review decisions, and how the audit trail is used for accountability.

---

## Overview

EvalLedger does not blindly accept benchmark records. Every benchmark submission starts in an **unverified** state and must be explicitly reviewed and approved by an administrator before it is considered trustworthy in the registry.

The review workflow is:

1. Submitter creates a benchmark and uploads one or more versions.
2. The benchmark appears in the admin **review queue** (unverified).
3. An admin inspects the submission — metadata, integrity, submitter identity, contamination status.
4. The admin either:
   - **Verifies** the benchmark (marks it as trustworthy), optionally with a note.
   - **Leaves a review note** without making a final decision (e.g. "waiting for license clarification").
   - Takes no action (benchmark remains unverified).
5. All review actions are recorded in the **audit trail** with actor, timestamp, and note.

---

## Who can review

Only users with `is_admin=true` can access the review endpoints and the `/review` frontend page. Non-admin requests receive **HTTP 403**.

To grant admin access, set the flag directly in the database:

```sql
UPDATE users SET is_admin = true WHERE email = 'admin@example.com';
```

There is currently no UI for promoting users; this is intentional to keep privileged access tightly controlled.

---

## Review queue

### Frontend

Navigate to **`/review`** in the EvalLedger web interface. The page shows:

| Section | Content |
|---|---|
| Stats bar | Total benchmarks, pending count, verified count, contamination flags |
| Filter tabs | Pending / Verified / All |
| Benchmark cards | Name, description, contamination badge, submitter info, OAuth providers, integrity fingerprint, existing review note |
| Action buttons | "Mark verified" / "Remove verification" (+ optional note), "Add note" (without deciding) |
| Activity feed | Recent admin audit events |

### API

```
GET /admin/review-queue
```

Query parameters:

| Param | Default | Description |
|---|---|---|
| `status` | `pending` | `pending` (unverified), `verified`, or `all` |
| `contamination` | — | Filter to benchmarks with at least one version of this contamination status (e.g. `flagged`, `contaminated`) |
| `limit` | 50 | 1–100 |

The queue is sorted **oldest first** for the pending view so that submissions that have waited longest surface at the top.

---

## Reviewer context

For a single benchmark, the full review context is available at:

```
GET /admin/benchmarks/{slug}/context
```

Response includes:
- All benchmark metadata and current verification state
- Submitter identity and OAuth providers used (GitHub, Google)
- All versions with:
  - `contamination_status` — clean / pending / flagged / contaminated / unchecked
  - `artifact_sha256` — integrity fingerprint
  - `artifact_size_bytes` — upload size
  - `num_examples` — dataset size
  - Links (paper URL, GitHub URL, license)
- Full audit trail for this benchmark (all past review actions)

Use this endpoint to open a detail view before committing to a verification decision.

---

## Making a verification decision

### Verify a benchmark

```http
PATCH /admin/benchmarks/{slug}/verification
Content-Type: application/json

{
  "verified": true,
  "note": "Reviewed metadata, artifact integrity confirmed, no contamination detected."
}
```

Effects:
- Sets `benchmarks.is_verified = true`
- Persists `note` to `benchmarks.review_note` for quick display in the UI
- Sets `benchmarks.reviewed_at` to the current timestamp
- Sets `benchmarks.reviewed_by_id` to the admin's user ID
- Creates an audit event with action `benchmark.verified`

### Unverify a benchmark

```http
PATCH /admin/benchmarks/{slug}/verification
Content-Type: application/json

{
  "verified": false,
  "note": "Dataset license terms do not meet registry requirements."
}
```

Creates an audit event with action `benchmark.unverified`.

### Add a review note without deciding

```http
POST /admin/benchmarks/{slug}/notes
Content-Type: application/json

{
  "note": "Waiting for submitter to provide proper dataset license documentation."
}
```

Effects:
- Persists `note` to `benchmarks.review_note` (does **not** change `is_verified`)
- Sets `benchmarks.reviewed_at` and `benchmarks.reviewed_by_id`
- Creates an audit event with action `benchmark.review_note`

Notes are intended for mid-review observations — e.g. flagging a concern, requesting more information, or recording why a decision is pending.

---

## Admin statistics

```
GET /admin/stats
```

Returns aggregate counts for the admin dashboard header:

```json
{
  "total_benchmarks": 142,
  "unverified_count": 8,
  "verified_count": 134,
  "contamination_pending_count": 12,
  "contamination_flagged_count": 2
}
```

`contamination_flagged_count` is the count of benchmark versions with `contamination_status` of `"flagged"` or `"contaminated"`. A non-zero value warrants attention — filter the review queue by `?contamination=flagged` to find the affected benchmarks.

---

## Audit trail

### Audit events

Every review action creates an `AuditEvent` record:

| Field | Content |
|---|---|
| `action` | Event name — see table below |
| `actor_user_id` | Admin who performed the action |
| `benchmark_id` | Linked benchmark |
| `resource_slug` | Benchmark slug |
| `summary` | Human-readable note (from the review payload) |
| `metadata_json` | Structured data — `{"verified": true, "note": "..."}` |
| `created_at` | Timestamp |

### Review-specific event actions

| Action | Trigger |
|---|---|
| `benchmark.verified` | Admin sets `is_verified = true` |
| `benchmark.unverified` | Admin sets `is_verified = false` |
| `benchmark.review_note` | Admin adds a note without changing verification |

### Querying audit events

```
GET /admin/audit-events
```

Filter parameters:

| Param | Description |
|---|---|
| `action` | Exact action string, e.g. `benchmark.verified` |
| `resource_type` | Resource type, e.g. `benchmark` |
| `benchmark_slug` | Limit to events for one benchmark |
| `limit` | 1–100 (default 100) |

Examples:

```bash
# All verification decisions
GET /admin/audit-events?action=benchmark.verified

# Full history for a specific benchmark
GET /admin/audit-events?benchmark_slug=mmlu

# Recent unverifications (removals)
GET /admin/audit-events?action=benchmark.unverified
```

---

## What to check during review

Use this checklist when evaluating a benchmark submission:

### Metadata quality
- [ ] Name and description are clear and accurate
- [ ] Domain and task type are correctly categorised
- [ ] Version follows semantic versioning (e.g. `1.0.0`)

### Submitter provenance
- [ ] Submitter has a verified email (OAuth provider shown on the card)
- [ ] Affiliation is plausible for the claimed dataset
- [ ] No duplicate submissions for the same dataset under a different name

### Dataset integrity
- [ ] Artifact SHA-256 fingerprint is present
- [ ] `num_examples` is plausible for the claimed dataset size
- [ ] License is present and compatible with open research use

### Contamination
- [ ] `contamination_status` is `clean` or `unchecked` (not `flagged` / `contaminated`)
- [ ] If `flagged`, review the contamination report before verifying

### Paper / citation
- [ ] `paper_url` or `paper_arxiv_id` resolves to the correct paper
- [ ] Citation string is present and matches the paper

---

## Verification state and public visibility

`is_verified` is a trust signal — it is displayed on benchmark pages and returned in search results. It does **not** gate access — unverified benchmarks are still publicly readable.

Reviewers should treat `is_verified` as meaning:
> "An EvalLedger administrator has inspected this submission and considers it a legitimate, trustworthy benchmark record."

Removal of verification (`is_verified = false`) should be documented with a note explaining why, for the audit trail.

---

## Database fields reference

### `benchmarks` table review columns

| Column | Type | Description |
|---|---|---|
| `is_verified` | `boolean` | Current verification state |
| `review_note` | `text` | Most recent reviewer note (updated on each decision) |
| `reviewed_at` | `timestamptz` | Timestamp of the most recent review action |
| `reviewed_by_id` | `uuid` FK | Admin who made the most recent review action |

The `review_note`, `reviewed_at`, and `reviewed_by_id` fields reflect only the **most recent** review action. Full history is always available in `audit_events`.

---

## Limitations

- There is no multi-step approval workflow (e.g. two-reviewer sign-off). A single admin can verify.
- Verification is at the benchmark level only — individual versions do not have their own verification state.
- There is no automatic notification to submitters when their benchmark is verified or rejected.
- The contamination check must be re-run manually if the submitter replaces an artifact; contamination status is per-version and does not reset on verification.

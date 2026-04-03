# EvalLedger

EvalLedger is a registry for AI benchmark provenance. It exists to make benchmark versions citable, benchmark artifacts verifiable, and contamination checks inspectable instead of implicit.

## Why it exists

The current benchmark ecosystem makes it hard to answer three basic questions:

1. Which exact artifact was evaluated?
2. Was the benchmark likely seen during pretraining?
3. Can another researcher reproduce the result later?

EvalLedger stores benchmark metadata, version records, artifact hashes, and contamination reports in one public ledger so those questions have durable answers.

## Quick start

```bash
docker compose up --build
cd backend && uv run alembic upgrade head
cd backend && uv run python -m app.scripts.seed
```

Then open [http://localhost:3000](http://localhost:3000) for the web interface and [http://localhost:8000/docs](http://localhost:8000/docs) for the API.

## Repository guide

- Contributor workflow: `CONTRIBUTING.md`
- Metadata standard: `standard/METADATA_STANDARD.md`
- Machine-readable schema: `standard/metadata_schema.json`
- Maintainer and operations runbooks: `docs/README.md`

## Authentication

Sign in via **GitHub** or **Google** at `/login`. No password required. After signing in, mint an API key from your account page for CLI and programmatic access.

## CLI

```bash
cd cli
uv sync
uv run evalledger login --api-key el_your_api_key_here
uv run evalledger submit --name "MMLU" --slug mmlu --version 2.0.0 --file ./mmlu.jsonl --domain reasoning --task-type multiple_choice --paper https://arxiv.org/abs/2009.03300 --license MIT
uv run evalledger verify mmlu 2.0.0
```

API keys are created from the account page (`/account`) after signing in with GitHub or Google.

## API overview

```bash
curl http://localhost:8000/search?q=reasoning
curl http://localhost:8000/benchmarks/mmlu
curl http://localhost:8000/stats/overview
```

## Contamination methodology

EvalLedger uses MinHash sketches to approximate textual overlap between submitted artifacts and reference corpora. Each example is tokenized, hashed into a fixed-size sketch, queried against a corpus-local LSH index, and then rechecked with exact token-level Jaccard similarity before being flagged. The result is not a proof of contamination; it is a reproducible, inspectable overlap signal.

## Metadata standard

The repository ships the human-readable standard in `standard/METADATA_STANDARD.md` and the machine schema in `standard/metadata_schema.json`.

## Contributing a benchmark

1. Register the benchmark metadata through the CLI or web submit flow.
2. Upload a versioned artifact with a semantic version.
3. Review the generated contamination report before citing the record publicly.

## Contributing code

Use `make dev` for local development, `make migrate` after schema changes, `make seed` to load reference data, `make test` for automated checks, and `make lint` for static analysis.

## Operations

Operational runbooks live in `docs/operations/` and maintainer process notes live in `docs/maintainers/`. They cover incident response, backup and restore drills, release flow, and migration discipline.

## Load testing

Use the local harness below to get a first-pass latency and throughput read on the API:

```bash
cd backend
uv run python -m app.scripts.loadtest --url http://localhost:8000/health/live --requests 200 --concurrency 20
```

The harness reports success rate, throughput, and p50/p95/p99 latency. It is intended for controlled local or staging checks rather than internet-scale benchmarking.

## Product policies

Draft product-facing policy pages ship with the frontend at `/privacy`, `/terms`, and `/acceptable-use`. They are implementation-complete, but they should still receive legal review before a public launch.

## Roadmap

1. Replace miniature local reference indices with large-scale corpus builders.
2. Add first-class citation ingestion and external paper backlink tracking.
3. Publish signed export snapshots for long-term archival use.

## Citing EvalLedger

```bibtex
@software{evalledger_2026,
  title  = {EvalLedger},
  year   = {2026},
  url    = {https://evalledger.dev},
  note   = {Registry for benchmark provenance and contamination reporting}
}
```

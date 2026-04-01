# EvalLedger Metadata Standard v0.1

EvalLedger defines a minimal interoperable metadata contract for benchmark registration.

## Benchmark block

```yaml
benchmark:
  name: "MMLU"
  slug: "mmlu"
  description: "Massive Multitask Language Understanding."
  domain:
    - reasoning
    - knowledge
  task_type: "multiple_choice"
  paper_url: "https://arxiv.org/abs/2009.03300"
  github_url: "https://github.com/hendrycks/test"
```

## Version block

```yaml
version:
  version: "2.0.1"
  artifact_sha256: "a3f9..."
  num_examples: 15908
  splits:
    test: 14042
    validation: 1531
  language: ["en"]
  license: "MIT"
  released_at: "2024-03-15"
  release_notes: "Refreshed examples and corrected metadata."
```

## Notes

- Descriptions are required and should be descriptive enough to stand on their own in a citation index.
- Semantic versioning is recommended for submitted versions.
- Legacy imported records may omit `artifact_sha256` and `artifact_url`, but that omission must remain explicit.
- The registry identifier format is `el:<slug>:<version>`.


from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.benchmark import Benchmark
from app.models.contamination import ReferenceCorpus
from app.models.user import User
from app.models.version import BenchmarkVersion
from app.security import hash_password
from app.services.corpus_index import serialize_corpus_index
from app.services.storage import StorageService
from app.services.versioning import VersioningService


@dataclass(slots=True)
class SeedBenchmark:
    name: str
    slug: str
    description: str
    domain: list[str]
    task_type: str
    paper_url: str
    github_url: str
    num_examples: int | None = None
    splits: dict[str, int] | None = None
    language: list[str] | None = None
    license: str | None = None
    released_at: datetime | None = None


@dataclass(slots=True)
class SeedCorpus:
    name: str
    description: str
    version: str
    size_tokens: int | None
    source_url: str
    entries: list[str]


SEED_BENCHMARKS: list[SeedBenchmark] = [
    SeedBenchmark(
        name="MMLU",
        slug="mmlu",
        description="Massive Multitask Language Understanding spanning 57 academic and professional subjects.",
        domain=["reasoning", "knowledge"],
        task_type="multiple_choice",
        paper_url="https://arxiv.org/abs/2009.03300",
        github_url="https://github.com/hendrycks/test",
        num_examples=15908,
        language=["en"],
    ),
    SeedBenchmark(
        name="HumanEval",
        slug="humaneval",
        description="Hand-written Python programming problems for functional correctness evaluation.",
        domain=["code"],
        task_type="code_completion",
        paper_url="https://arxiv.org/abs/2107.03374",
        github_url="https://github.com/openai/human-eval",
        num_examples=164,
        language=["en"],
        license="MIT",
    ),
    SeedBenchmark(
        name="BIG-Bench Hard",
        slug="big-bench-hard",
        description="A focused subset of BIG-Bench tasks that remain difficult for frontier language models.",
        domain=["reasoning"],
        task_type="multiple_choice",
        paper_url="https://arxiv.org/abs/2210.09261",
        github_url="https://github.com/suzgunmirac/BIG-Bench-Hard",
        language=["en"],
    ),
    SeedBenchmark(
        name="GSM8K",
        slug="gsm8k",
        description="Grade school math word problems for multi-step mathematical reasoning.",
        domain=["math"],
        task_type="generation",
        paper_url="https://arxiv.org/abs/2110.14168",
        github_url="https://github.com/openai/grade-school-math",
        num_examples=1319,
        language=["en"],
    ),
    SeedBenchmark(
        name="MATH",
        slug="math",
        description="Competition-level mathematics problems spanning algebra, geometry, counting, and number theory.",
        domain=["math"],
        task_type="generation",
        paper_url="https://arxiv.org/abs/2103.03874",
        github_url="https://github.com/hendrycks/math",
        language=["en"],
    ),
    SeedBenchmark(
        name="HellaSwag",
        slug="hellaswag",
        description="Adversarial commonsense completion benchmark for grounded natural language inference.",
        domain=["reasoning"],
        task_type="multiple_choice",
        paper_url="https://arxiv.org/abs/1905.07830",
        github_url="https://github.com/rowanz/hellaswag",
        language=["en"],
    ),
    SeedBenchmark(
        name="ARC Challenge",
        slug="arc-challenge",
        description="The challenge subset of the AI2 Reasoning Challenge science question benchmark.",
        domain=["reasoning"],
        task_type="multiple_choice",
        paper_url="https://arxiv.org/abs/1803.05457",
        github_url="https://github.com/allenai/ARC-Solvers",
        language=["en"],
    ),
    SeedBenchmark(
        name="TruthfulQA",
        slug="truthfulqa",
        description="A question answering benchmark measuring whether models imitate common falsehoods.",
        domain=["safety"],
        task_type="generation",
        paper_url="https://arxiv.org/abs/2109.07958",
        github_url="https://github.com/sylinrl/TruthfulQA",
        num_examples=817,
        language=["en"],
    ),
    SeedBenchmark(
        name="WinoGrande",
        slug="winogrande",
        description="Large-scale adversarial Winograd schema benchmark for commonsense reasoning.",
        domain=["reasoning"],
        task_type="multiple_choice",
        paper_url="https://arxiv.org/abs/1907.10641",
        github_url="https://github.com/allenai/winogrande",
        language=["en"],
    ),
    SeedBenchmark(
        name="MBPP",
        slug="mbpp",
        description="Mostly Basic Python Problems for measuring code generation from short task descriptions.",
        domain=["code"],
        task_type="code_completion",
        paper_url="https://arxiv.org/abs/2108.07732",
        github_url="https://github.com/google-research/google-research/tree/master/mbpp",
        num_examples=974,
        language=["en"],
    ),
    SeedBenchmark(
        name="APPS",
        slug="apps",
        description="A code generation benchmark built from competitive programming and interview-style problems.",
        domain=["code"],
        task_type="code_completion",
        paper_url="https://arxiv.org/abs/2105.09938",
        github_url="https://github.com/hendrycks/apps",
        language=["en"],
    ),
    SeedBenchmark(
        name="DROP",
        slug="drop",
        description="Discrete reasoning over paragraphs with numeracy and compositional question answering.",
        domain=["reasoning"],
        task_type="generation",
        paper_url="https://arxiv.org/abs/1903.00161",
        github_url="https://github.com/allenai/drop",
        language=["en"],
    ),
    SeedBenchmark(
        name="QuALITY",
        slug="quality",
        description="Question answering with long-form documents intended to require deep passage understanding.",
        domain=["reasoning"],
        task_type="multiple_choice",
        paper_url="https://arxiv.org/abs/2112.08608",
        github_url="https://github.com/nyu-mll/quality",
        language=["en"],
    ),
    SeedBenchmark(
        name="SWE-bench",
        slug="swe-bench",
        description="Issue-resolution benchmark built from real GitHub repositories and pull requests.",
        domain=["code"],
        task_type="code_completion",
        paper_url="https://arxiv.org/abs/2310.06770",
        github_url="https://github.com/princeton-nlp/SWE-bench",
        language=["en"],
    ),
    SeedBenchmark(
        name="LiveCodeBench",
        slug="livecodebench",
        description="Continually refreshed coding benchmark intended to reduce benchmark saturation and leakage.",
        domain=["code"],
        task_type="code_completion",
        paper_url="https://arxiv.org/abs/2403.07974",
        github_url="https://github.com/LiveCodeBench/LiveCodeBench",
        language=["en"],
    ),
]

CORPORA: list[SeedCorpus] = [
    SeedCorpus(
        name="The Pile",
        description="Miniature local development index representing The Pile-style heterogeneous web text.",
        version="sample-dev-1",
        size_tokens=825_000_000_000,
        source_url="https://pile.eleuther.ai/",
        entries=[
            "This archive preserves benchmark provenance through versioned artifacts and transparent metadata.",
            "Researchers need repeatable evaluation baselines when comparing language models across time.",
        ],
    ),
    SeedCorpus(
        name="C4",
        description="Miniature local development index representing the Colossal Clean Crawled Corpus.",
        version="sample-dev-1",
        size_tokens=305_000_000_000,
        source_url="https://www.tensorflow.org/datasets/catalog/c4",
        entries=[
            "A clean crawl of the web can still contain benchmark examples that later contaminate evaluations.",
            "Metadata standards matter when publishing datasets for the research community.",
        ],
    ),
    SeedCorpus(
        name="RedPajama-Data-1T",
        description="Miniature local development index representing RedPajama mixture sources.",
        version="sample-dev-1",
        size_tokens=1_200_000_000_000,
        source_url="https://www.together.ai/blog/redpajama-data-v2",
        entries=[
            "Approximate nearest neighbor search with MinHash can surface suspicious textual overlap efficiently.",
            "Pinned benchmark versions make evaluation results easier to reproduce and cite.",
        ],
    ),
    SeedCorpus(
        name="Dolma",
        description="Stub corpus entry for future Dolma-scale indices.",
        version="stub",
        size_tokens=None,
        source_url="https://allenai.org/dolma",
        entries=[],
    ),
    SeedCorpus(
        name="FineWeb",
        description="Stub corpus entry for future FineWeb-scale indices.",
        version="stub",
        size_tokens=None,
        source_url="https://huggingface.co/datasets/HuggingFaceFW/fineweb",
        entries=[],
    ),
]


async def seed() -> None:
    storage = StorageService.from_settings()
    await storage.ensure_ready()
    versioning = VersioningService()
    async with SessionLocal() as session:
        system_user = await session.scalar(select(User).where(User.username == "evalledger"))
        if system_user is None:
            system_user = User(
                email="registry@evalledger.dev",
                username="evalledger",
                password_hash=hash_password("evalledger-dev-password"),
                display_name="EvalLedger Registry",
                affiliation="EvalLedger",
                is_verified=True,
            )
            session.add(system_user)
            await session.flush()

        for corpus_payload in CORPORA:
            existing_corpus = await session.scalar(
                select(ReferenceCorpus).where(ReferenceCorpus.name == corpus_payload.name)
            )
            if existing_corpus is not None:
                continue
            settings = get_settings()
            entries: dict[str, str] = {}
            for index, corpus_entry in enumerate(corpus_payload.entries):
                key = f"{corpus_payload.name.lower().replace(' ', '-')}-{index}"
                entries[key] = corpus_entry
            index_bytes = serialize_corpus_index(
                entries,
                num_perm=settings.contamination_num_perm,
                shingle_size=settings.contamination_shingle_size,
            )
            stored = await storage.upload_bytes(
                f"{corpus_payload.name.lower().replace(' ', '-')}.json",
                index_bytes,
                directory="corpora",
            )
            storage_reference = (
                stored.artifact_url if storage.settings.storage_backend == "local" else stored.storage_key
            )
            session.add(
                ReferenceCorpus(
                    name=corpus_payload.name,
                    description=corpus_payload.description,
                    version=corpus_payload.version,
                    size_tokens=corpus_payload.size_tokens,
                    source_url=corpus_payload.source_url,
                    minhash_index_path=storage_reference,
                    is_active=True,
                )
            )

        for entry in SEED_BENCHMARKS:
            existing_benchmark = await session.scalar(
                select(Benchmark).where(Benchmark.slug == entry.slug)
            )
            if existing_benchmark is not None:
                continue
            benchmark = Benchmark(
                name=entry.name,
                slug=entry.slug,
                description=entry.description,
                domain=entry.domain,
                task_type=entry.task_type,
                submitter_id=system_user.id,
                is_verified=True,
                total_versions=1,
                total_citations=0,
            )
            session.add(benchmark)
            await session.flush()
            version_record = BenchmarkVersion(
                benchmark_id=benchmark.id,
                version="0.0.0",
                artifact_sha256=None,
                artifact_url=None,
                artifact_size_bytes=None,
                num_examples=entry.num_examples,
                splits=entry.splits,
                language=entry.language,
                license=entry.license,
                paper_url=entry.paper_url,
                github_url=entry.github_url,
                metadata_json={"seeded": True, "legacy_import": True},
                release_notes=(
                    "Legacy placeholder imported during initial registry seeding. "
                    "A canonical artifact has not yet been pinned in EvalLedger."
                ),
                released_at=entry.released_at,
                submitter_id=system_user.id,
                contamination_status="unchecked",
            )
            versioning.apply_citation_string(benchmark, version_record)
            session.add(version_record)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())

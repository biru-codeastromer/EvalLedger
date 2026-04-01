from __future__ import annotations

import asyncio
import csv
import io
import json
import pickle
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pyarrow.parquet as pq
from datasketch import MinHashLSH
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import AppError
from app.logging import logger
from app.models.contamination import ContaminationReport, ReferenceCorpus
from app.models.version import BenchmarkVersion
from app.services.storage import StorageService
from app.utils.minhash import build_minhash, jaccard_tokens, tokenize

settings = get_settings()


@dataclass(slots=True)
class LSHIndexBundle:
    corpus: ReferenceCorpus
    lsh: MinHashLSH
    entries: dict[str, str]


class ContaminationEngine:
    def __init__(
        self,
        session: AsyncSession,
        storage_service: StorageService,
        *,
        num_perm: int = settings.contamination_num_perm,
        threshold: float = settings.contamination_default_threshold,
    ) -> None:
        self.session = session
        self.storage_service = storage_service
        self.num_perm = num_perm
        self.threshold = threshold

    def compute_minhash(self, text: str) -> Any:
        return build_minhash(text, num_perm=self.num_perm)

    def _collect_strings(self, payload: Any) -> list[str]:
        collected: list[str] = []
        if isinstance(payload, str):
            value = payload.strip()
            if value:
                collected.append(value)
        elif isinstance(payload, dict):
            for value in payload.values():
                collected.extend(self._collect_strings(value))
        elif isinstance(payload, list):
            for item in payload:
                collected.extend(self._collect_strings(item))
        return collected

    def _extract_json_examples(self, data: Any) -> Iterator[str]:
        if isinstance(data, list):
            for item in data:
                strings = self._collect_strings(item)
                if strings:
                    yield " ".join(strings)
            return
        if isinstance(data, dict):
            if "examples" in data and isinstance(data["examples"], list):
                for item in data["examples"]:
                    strings = self._collect_strings(item)
                    if strings:
                        yield " ".join(strings)
                return
            strings = self._collect_strings(data)
            if strings:
                yield " ".join(strings)
            return
        strings = self._collect_strings(data)
        if strings:
            yield " ".join(strings)

    def extract_examples(self, artifact_name: str, artifact_bytes: bytes) -> Iterator[str]:
        suffix = Path(artifact_name).suffix.lower()
        if suffix == ".json":
            yield from self._extract_json_examples(json.loads(artifact_bytes.decode("utf-8")))
            return
        if suffix == ".jsonl":
            for line in artifact_bytes.decode("utf-8").splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                strings = self._collect_strings(payload)
                if strings:
                    yield " ".join(strings)
            return
        if suffix == ".csv":
            reader = csv.DictReader(io.StringIO(artifact_bytes.decode("utf-8")))
            for row in reader:
                strings = self._collect_strings(row)
                if strings:
                    yield " ".join(strings)
            return
        if suffix == ".parquet":
            table = pq.read_table(io.BytesIO(artifact_bytes))
            for row in table.to_pylist():
                strings = self._collect_strings(row)
                if strings:
                    yield " ".join(strings)
            return
        decoded = artifact_bytes.decode("utf-8", errors="ignore")
        for line in decoded.splitlines():
            line = line.strip()
            if line:
                yield line

    async def _load_bundle(self, corpus: ReferenceCorpus) -> LSHIndexBundle:
        if corpus.minhash_index_path is None:
            return LSHIndexBundle(
                corpus=corpus,
                lsh=MinHashLSH(threshold=self.threshold, num_perm=self.num_perm),
                entries={},
            )
        raw_bytes = await self.storage_service.read_bytes(corpus.minhash_index_path)
        payload = cast(dict[str, object], await asyncio.to_thread(pickle.loads, raw_bytes))
        entries = payload.get("entries")
        lsh = payload.get("lsh")
        if not isinstance(entries, dict) or lsh is None:
            raise AppError("invalid_corpus_index", "Reference corpus index is invalid", status_code=500)
        return LSHIndexBundle(
            corpus=corpus,
            lsh=cast(MinHashLSH, lsh),
            entries={str(key): str(value) for key, value in entries.items()},
        )

    def _classify(self, overlap_score: float) -> str:
        if overlap_score < 0.05:
            return "clean"
        if overlap_score <= 0.2:
            return "flagged"
        return "contaminated"

    async def _store_report(
        self,
        *,
        version: BenchmarkVersion,
        corpus: ReferenceCorpus,
        status: str,
        overlap_score: float,
        flagged_examples: list[dict[str, Any]],
        started_at: datetime,
        completed_at: datetime,
    ) -> ContaminationReport:
        report = ContaminationReport(
            version_id=version.id,
            corpus_id=corpus.id,
            status=status,
            overlap_score=overlap_score,
            num_flagged_examples=len(flagged_examples),
            flagged_examples=flagged_examples,
            minhash_threshold=self.threshold,
            job_started_at=started_at,
            job_completed_at=completed_at,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def run_detection(
        self,
        *,
        artifact_name: str,
        artifact_location: str,
        corpus_ids: list[str],
        version_id: str | None = None,
    ) -> dict[str, Any]:
        started_at = datetime.now(UTC)
        logger.info(
            "contamination.job.started",
            extra={"version_id": version_id, "artifact_name": artifact_name, "corpora": corpus_ids},
        )
        artifact_bytes = await self.storage_service.read_bytes(artifact_location)
        examples = list(self.extract_examples(artifact_name, artifact_bytes))
        total_examples = len(examples)
        corpus_statement = select(ReferenceCorpus).where(ReferenceCorpus.id.in_([UUID(item) for item in corpus_ids]))
        corpora = list((await self.session.scalars(corpus_statement)).all())
        bundles = [await self._load_bundle(corpus) for corpus in corpora]

        results: list[dict[str, Any]] = []
        version = None
        if version_id is not None:
            version = await self.session.get(BenchmarkVersion, UUID(version_id))

        for bundle in bundles:
            flagged_examples: list[dict[str, Any]] = []
            for index, example in enumerate(examples):
                minhash = self.compute_minhash(example)
                candidates = bundle.lsh.query(minhash)
                best_match_text = None
                best_score = 0.0
                for candidate_key in candidates:
                    candidate_text = bundle.entries.get(candidate_key)
                    if candidate_text is None:
                        continue
                    score = jaccard_tokens(tokenize(example), tokenize(candidate_text))
                    if score > best_score:
                        best_score = score
                        best_match_text = candidate_text
                if best_match_text is not None and best_score >= self.threshold:
                    flagged_examples.append(
                        {
                            "example_index": index,
                            "benchmark_example": example,
                            "corpus_match": best_match_text,
                            "similarity": round(best_score, 4),
                        }
                    )
            overlap_score = len(flagged_examples) / total_examples if total_examples else 0.0
            status = self._classify(overlap_score)
            completed_at = datetime.now(UTC)
            report_payload = {
                "corpus_id": str(bundle.corpus.id),
                "corpus_name": bundle.corpus.name,
                "status": status,
                "overlap_score": round(overlap_score, 4),
                "num_flagged_examples": len(flagged_examples),
                "flagged_examples": flagged_examples,
                "job_started_at": started_at.isoformat(),
                "job_completed_at": completed_at.isoformat(),
            }
            if version is not None:
                report = await self._store_report(
                    version=version,
                    corpus=bundle.corpus,
                    status=status,
                    overlap_score=overlap_score,
                    flagged_examples=flagged_examples,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                report_payload["report_id"] = str(report.id)
            results.append(report_payload)

        if version is not None:
            worst_status = "clean"
            if any(item["status"] == "contaminated" for item in results):
                worst_status = "contaminated"
            elif any(item["status"] == "flagged" for item in results):
                worst_status = "flagged"
            version.contamination_status = worst_status
            await self.session.commit()

        completed_at = datetime.now(UTC)
        payload = {
            "version_id": version_id,
            "artifact_name": artifact_name,
            "total_examples": total_examples,
            "threshold": self.threshold,
            "corpora": results,
            "completed_at": completed_at.isoformat(),
        }
        logger.info(
            "contamination.job.completed",
            extra={"version_id": version_id, "artifact_name": artifact_name, "total_examples": total_examples},
        )
        return payload

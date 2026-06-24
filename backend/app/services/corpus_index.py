"""Safe (non-pickle) serialisation for reference-corpus MinHash indices.

The previous format pickled a live ``MinHashLSH`` object and an ``entries``
dict.  Unpickling bytes fetched from object storage is an arbitrary-code-
execution risk if the bucket is ever writable or compromised, so this module
stores a plain JSON document holding each entry's text plus its MinHash
permutation ``hashvalues`` and rebuilds the LSH at load time.

The LSH is rebuilt at a permissive *recall* threshold (:data:`LSH_RECALL_THRESHOLD`)
that is intentionally decoupled from the caller's configurable similarity
threshold: the LSH is only a candidate filter, and the real cutoff is applied
later by an exact shingle-Jaccard recheck.  Building the LSH at a high
build-time threshold would silently prune true matches that score below it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from datasketch import MinHashLSH

from app.utils.minhash import (
    DEFAULT_SHINGLE_SIZE,
    build_minhash,
    minhash_from_list,
    minhash_to_list,
)

CORPUS_INDEX_FORMAT = "evalledger-corpus-index/1"
LSH_RECALL_THRESHOLD = 0.4


@dataclass(slots=True)
class LoadedCorpusIndex:
    lsh: MinHashLSH
    entries: dict[str, str]


def serialize_corpus_index(
    entries: dict[str, str],
    *,
    num_perm: int,
    shingle_size: int = DEFAULT_SHINGLE_SIZE,
) -> bytes:
    """Serialise a corpus index to safe JSON bytes (no pickle)."""
    payload = {
        "format": CORPUS_INDEX_FORMAT,
        "num_perm": num_perm,
        "shingle_size": shingle_size,
        "entries": [
            {
                "key": key,
                "text": text,
                "hashvalues": minhash_to_list(
                    build_minhash(text, num_perm=num_perm, shingle_size=shingle_size)
                ),
            }
            for key, text in entries.items()
        ],
    }
    return json.dumps(payload).encode("utf-8")


def load_corpus_index(raw: bytes, *, recall_threshold: float = LSH_RECALL_THRESHOLD) -> LoadedCorpusIndex:
    """Rebuild an LSH + entries map from :func:`serialize_corpus_index` output.

    Raises ``ValueError`` if the payload is not the expected format.
    """
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != CORPUS_INDEX_FORMAT:
        raise ValueError("unrecognised corpus index format")
    num_perm = payload.get("num_perm")
    raw_entries = payload.get("entries")
    if not isinstance(num_perm, int) or not isinstance(raw_entries, list):
        raise ValueError("corpus index missing num_perm or entries")

    lsh = MinHashLSH(threshold=recall_threshold, num_perm=num_perm)
    entries: dict[str, str] = {}
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        key = str(item["key"])
        text = str(item["text"])
        hashvalues = [int(value) for value in item["hashvalues"]]
        lsh.insert(key, minhash_from_list(hashvalues, num_perm=num_perm))
        entries[key] = text
    return LoadedCorpusIndex(lsh=lsh, entries=entries)


def empty_corpus_index(*, num_perm: int, recall_threshold: float = LSH_RECALL_THRESHOLD) -> LoadedCorpusIndex:
    """Return an empty index (used when a corpus has no built index path)."""
    return LoadedCorpusIndex(lsh=MinHashLSH(threshold=recall_threshold, num_perm=num_perm), entries={})

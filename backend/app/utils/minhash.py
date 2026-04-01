from __future__ import annotations

import re
from collections.abc import Iterable

from datasketch import MinHash

WORD_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def build_minhash(text: str, *, num_perm: int) -> MinHash:
    minhash = MinHash(num_perm=num_perm)
    for token in tokenize(text):
        minhash.update(token.encode("utf-8"))
    return minhash


def jaccard_tokens(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


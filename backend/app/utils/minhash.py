from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np
from datasketch import MinHash

WORD_RE = re.compile(r"\w+", re.UNICODE)

# Default word-shingle (n-gram) size. Shingling captures local word order, so
# reordered or paraphrased text no longer collapses to the same bag of tokens
# the way a plain unigram set would — reducing both false positives (shared
# vocabulary, different meaning) and false negatives (reordered duplicates).
DEFAULT_SHINGLE_SIZE = 5


def tokenize(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def shingles(text: str, *, size: int = DEFAULT_SHINGLE_SIZE) -> list[str]:
    """Return the word n-grams of *text* as space-joined strings.

    Texts shorter than *size* yield a single shingle made of all their tokens
    so that very short examples still hash to something stable rather than to
    the empty set.
    """
    tokens = tokenize(text)
    if not tokens:
        return []
    if len(tokens) < size:
        return [" ".join(tokens)]
    return [" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)]


def build_minhash(text: str, *, num_perm: int, shingle_size: int = DEFAULT_SHINGLE_SIZE) -> MinHash:
    minhash = MinHash(num_perm=num_perm)
    for shingle in shingles(text, size=shingle_size):
        minhash.update(shingle.encode("utf-8"))
    return minhash


def minhash_to_list(minhash: MinHash) -> list[int]:
    """Serialise a MinHash to a plain list of ints (its permutation hashvalues).

    This is the safe, code-execution-free alternative to pickling the object.
    """
    return [int(value) for value in minhash.hashvalues]


def minhash_from_list(values: list[int], *, num_perm: int) -> MinHash:
    """Rebuild a MinHash from hashvalues produced by :func:`minhash_to_list`."""
    hashvalues = np.array(values, dtype=np.uint64)
    return MinHash(num_perm=num_perm, hashvalues=hashvalues)


def jaccard_shingles(left_text: str, right_text: str, *, size: int = DEFAULT_SHINGLE_SIZE) -> float:
    """Exact Jaccard similarity over the two texts' word-n-gram (shingle) sets."""
    left_set = set(shingles(left_text, size=size))
    right_set = set(shingles(right_text, size=size))
    if not left_set or not right_set:
        # Two empty shingle sets are not meaningful contamination, so an empty
        # side never scores a (spurious) perfect match.
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def jaccard_tokens(left: Iterable[str], right: Iterable[str]) -> float:
    """Jaccard similarity over two unigram token iterables (retained helper)."""
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)

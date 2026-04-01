from __future__ import annotations

from app.services.contamination_engine import ContaminationEngine


class DummySession:
    pass


class DummyStorage:
    async def read_bytes(self, _: str) -> bytes:
        return b'{"examples":[{"question":"What is provenance?","answer":"The history of an artifact."}]}\n'


def test_extract_examples_from_json() -> None:
    engine = ContaminationEngine(DummySession(), DummyStorage())
    payload = b'{"examples":[{"question":"What is provenance?","answer":"The history of an artifact."}]}'
    examples = list(engine.extract_examples("sample.json", payload))
    assert len(examples) == 1
    assert "What is provenance?" in examples[0]


def test_classification_thresholds() -> None:
    engine = ContaminationEngine(DummySession(), DummyStorage())
    assert engine._classify(0.01) == "clean"
    assert engine._classify(0.08) == "flagged"
    assert engine._classify(0.25) == "contaminated"


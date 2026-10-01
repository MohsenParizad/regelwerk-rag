"""Quality contract on the real corpus: runs only after `python -m regelrag.ingest`.

These are the same numbers the evaluation gate checks, so a change that makes the
system worse fails the tests, not only the report.
"""
import pytest
import yaml

from regelrag.config import DATA, GATE, TESTSET
from regelrag.evaluate import evaluate, gate
from regelrag.pipeline import Pipeline

pytestmark = pytest.mark.skipif(not (DATA / "passages.jsonl").exists(), reason="run ingest first")


@pytest.fixture(scope="module")
def result():
    import json
    passages = [json.loads(line) for line in open(DATA / "passages.jsonl", encoding="utf-8")]
    testset = yaml.safe_load(TESTSET.read_text(encoding="utf-8"))
    return evaluate(Pipeline("extractive", passages=passages), testset)


def test_testset_is_consistent():
    testset = yaml.safe_load(TESTSET.read_text(encoding="utf-8"))
    ids = [t["id"] for t in testset]
    assert len(ids) == len(set(ids))
    for t in testset:
        assert bool(t["relevant"]) == t["answerable"], t["id"]


def test_offline_baseline_passes_the_gate(result):
    metrics, _ = result
    passed, fails = gate(metrics)
    assert passed, fails


def test_every_extractive_sentence_is_supported(result):
    _, rows = result
    assert all(not r["unsupported"] for r in rows)


def test_gate_limits_are_sane():
    assert 0 < GATE["min_hit_at_k"] <= 1 and 0 <= GATE["max_false_abstention"] < 1

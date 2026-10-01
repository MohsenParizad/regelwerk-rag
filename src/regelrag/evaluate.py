"""Step 8: measure the quality of the whole system on the golden test set, then apply the gate.

Metrics (each answers one question an interviewer may ask about GenAI quality)
  hit_at_k            Retrieval: is a correct passage among the top-k?           (did we find it?)
  mrr                 Retrieval: 1/rank of the first correct passage            (how high up?)
  citation_precision  Generation: share of cited passages that are relevant     (right sources?)
  faithfulness        Generation: share of answer sentences the validator supports (grounded?)
  key_fact_recall     Generation: expected facts present in the answer          (correct?)
  correct_abstention  Unanswerable questions answered with "no basis"           (knows its limits?)
  false_abstention    Answerable questions wrongly refused                       (too cautious?)
  latency_ms          Mean time per question                                     (usable?)

Plus a threshold sweep for the abstention parameter, because choosing it is a trade-off
between refusing too often and answering out-of-scope questions.

Output: reports/eval_<generator>.json and .md, a row in the eval_runs table.
Exit code 1 if the gate fails (CI blocks the merge).

Usage: python -m regelrag.evaluate [--generator anthropic]
"""
import argparse
import json
import sys
import time

import yaml

from .config import DATABASE_URL, GATE, GENERATOR, REPORTS, TESTSET, TOP_K
from .db import get_engine, save_eval
from .pipeline import Pipeline
from .validate import faithfulness


def key_fact_recall(answer_text: str, key_facts: list[str]) -> float:
    if not key_facts:
        return 1.0
    text = answer_text.lower()
    found = sum(any(alt.strip().lower() in text for alt in fact.split("|")) for fact in key_facts)
    return found / len(key_facts)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def evaluate(pipeline: Pipeline, testset: list[dict]) -> tuple[dict, list[dict]]:
    rows = []
    for t in testset:
        t0 = time.perf_counter()
        a = pipeline.ask(t["question"])
        latency = (time.perf_counter() - t0) * 1000
        ids = [h.passage["id"] for h in a.hits]
        rank = next((i + 1 for i, pid in enumerate(ids) if pid in t["relevant"]), None)
        cited = [c for s in a.sentences for c in s.citations]
        rows.append({
            "question_id": t["id"], "question": t["question"], "answerable": t["answerable"],
            "abstained": a.abstained, "hit": rank is not None, "rank": rank,
            "coverage": round(max((h.coverage for h in a.hits[:2]), default=0.0), 3),
            "citation_precision": (sum(c in t["relevant"] for c in cited) / len(cited)) if cited else None,
            "faithfulness": faithfulness(a),
            "key_fact_recall": 0.0 if a.abstained else key_fact_recall(a.text, t["key_facts"]),
            "answer": a.text, "unsupported": [s.text for s in a.sentences if not s.supported],
            "latency_ms": round(latency, 1),
        })
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    metrics = {
        "hit_at_k": mean([r["hit"] for r in ans]),
        "mrr": mean([1 / r["rank"] if r["rank"] else 0 for r in ans]),
        "citation_precision": mean([r["citation_precision"] for r in ans]),
        "faithfulness": mean([r["faithfulness"] for r in rows]),
        "key_fact_recall": mean([r["key_fact_recall"] for r in ans]),
        "correct_abstention": mean([r["abstained"] for r in unans]),
        "false_abstention": mean([r["abstained"] for r in ans]),
        "latency_ms": mean([r["latency_ms"] for r in rows]),
    }
    return metrics, rows


def threshold_sweep(rows: list[dict]) -> list[dict]:
    """What would other abstention thresholds have done? (Uses the stored coverage per question.)"""
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    return [{"threshold": th,
             "correct_abstention": round(sum(r["coverage"] < th for r in unans) / max(len(unans), 1), 2),
             "false_abstention": round(sum(r["coverage"] < th for r in ans) / max(len(ans), 1), 2)}
            for th in (0.3, 0.4, 0.5, 0.6, 0.7)]


def gate(m: dict) -> tuple[bool, list[str]]:
    fails = []
    for key, limit in GATE.items():
        name = key.split("_", 1)[1]
        value = m[name]
        if key.startswith("min_") and value < limit:
            fails.append(f"{name} {value:.2f} < {limit}")
        if key.startswith("max_") and value > limit:
            fails.append(f"{name} {value:.2f} > {limit}")
    return not fails, fails


def write_report(name: str, m: dict, rows: list[dict], passed: bool, fails: list[str]) -> None:
    REPORTS.mkdir(exist_ok=True)
    sweep = threshold_sweep(rows)
    (REPORTS / f"eval_{name}.json").write_text(json.dumps(
        {"generator": name, "metrics": m, "gate": {"passed": passed, "failures": fails, "limits": GATE},
         "threshold_sweep": sweep, "questions": rows}, indent=2, ensure_ascii=False))
    md = [f"# Evaluation: generator `{name}`", "",
          f"{len(rows)} questions ({sum(r['answerable'] for r in rows)} answerable, "
          f"{sum(not r['answerable'] for r in rows)} not answerable from the corpus), top-k = {TOP_K}", "",
          "| Metric | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in m.items()] + [
          "", f"**Gate: {'PASSED' if passed else 'FAILED'}** " + ("; ".join(fails) if fails else ""), "",
          "## Abstention threshold sweep", "", "| threshold | correct abstention | false abstention |",
          "|---|---|---|"] + [f"| {s['threshold']} | {s['correct_abstention']} | {s['false_abstention']} |"
                              for s in sweep] + [
          "", "## Questions that need attention", "",
          "| id | issue | answer (shortened) |", "|---|---|---|"]
    for r in rows:
        issue = []
        if r["answerable"] and not r["hit"]:
            issue.append("retrieval miss")
        if r["answerable"] and r["abstained"]:
            issue.append("false abstention")
        if not r["answerable"] and not r["abstained"]:
            issue.append("answered out-of-scope question")
        if r["answerable"] and not r["abstained"] and r["key_fact_recall"] < 1:
            issue.append(f"key facts {r['key_fact_recall']:.0%}")
        if r["unsupported"]:
            issue.append(f"{len(r['unsupported'])} unsupported sentence(s)")
        if issue:
            md.append(f"| {r['question_id']} | {', '.join(issue)} | {r['answer'][:120].replace('|', '/')} |")
    (REPORTS / f"eval_{name}.md").write_text("\n".join(md) + "\n")


def main(generator: str = GENERATOR) -> bool:
    testset = yaml.safe_load(TESTSET.read_text(encoding="utf-8"))
    pipeline = Pipeline(generator)
    name = pipeline.generator.name.replace(":", "_")
    metrics, rows = evaluate(pipeline, testset)
    passed, fails = gate(metrics)
    write_report(name, metrics, rows, passed, fails)
    save_eval(get_engine(DATABASE_URL), name, metrics, rows, passed)
    print(json.dumps(metrics, indent=2))
    print("GATE PASSED" if passed else "GATE FAILED: " + "; ".join(fails))
    return passed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--generator", default=GENERATOR, choices=["extractive", "anthropic"])
    sys.exit(0 if main(ap.parse_args().generator) else 1)

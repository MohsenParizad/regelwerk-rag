"""The question-answering process (BPMN lane "Anfrage"): retrieve -> enough evidence? -> generate -> validate.

Usage: python -m regelrag.pipeline "Wie hoch ist die Aufwandspauschale?"
"""
import json
import sys

from .config import DATA, DATABASE_URL, GENERATOR
from .db import get_engine, load_passages
from .generate import AnthropicGenerator, Answer, ExtractiveGenerator
from .retrieve import Retriever
from .validate import validate


class Pipeline:
    def __init__(self, generator: str = GENERATOR, db_url: str = DATABASE_URL, passages=None):
        if passages is None:
            passages = load_passages(get_engine(db_url))
        if not passages and (DATA / "passages.jsonl").exists():   # e.g. fresh clone / Streamlit Cloud
            with open(DATA / "passages.jsonl", encoding="utf-8") as f:
                passages = [json.loads(line) for line in f]
        if not passages:
            raise RuntimeError("Knowledge base is empty. Run: python -m regelrag.ingest")
        self.retriever = Retriever(passages)
        if generator == "anthropic":
            self.generator = AnthropicGenerator()
        else:
            self.generator = ExtractiveGenerator(self.retriever.bm25.idf, self.retriever.vocab)

    def ask(self, question: str) -> Answer:
        hits = self.retriever.search(question)
        if not self.retriever.enough_evidence(hits):           # BPMN gateway "Ausreichende Grundlage?"
            return Answer(question, abstained=True, hits=hits, note="retrieval: not enough evidence")
        return validate(self.generator.generate(question, hits))


if __name__ == "__main__":
    a = Pipeline().ask(" ".join(sys.argv[1:]) or "Wie hoch ist die Aufwandspauschale?")
    print(a.text)
    for s in a.sentences:
        print(f"  [{'OK' if s.supported else 'NICHT BELEGT'}] {', '.join(s.citations)} ({s.reason})")
    if a.abstained:
        print(f"  ({a.note})")

"""Step 5: find the passages that can answer a question (BM25 keyword search).

Why BM25 and not embeddings? Legal questions use the same terms as the law ("Prüfquote",
"Aufwandspauschale"), BM25 is fast, needs no model download, runs offline in CI and every
score can be explained. Embeddings are the natural next step for paraphrased questions.

Output per hit: passage, BM25 score, and 'coverage' = idf-weighted share of the question's
terms found in the passage. Coverage drives the abstention decision: if even the best
passage covers too little of the question, the system answers "no basis found".
"""
import math
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from .config import MIN_SCORE, REF_BOOST, TOP_K
from .text import absatz_refs, paragraph_refs, tokens


@dataclass
class Hit:
    passage: dict
    score: float
    coverage: float


class Retriever:
    def __init__(self, passages: list[dict]):
        self.passages = passages
        # Title is indexed with the text: "Aufwandspauschale" questions also match on the paragraph title.
        raw = [p["title"] + " " + p["text"] for p in passages]
        self.vocab = {t for r in raw for t in tokens(r) if len(t) >= 4}
        self.docs = [tokens(r, self.vocab) for r in raw]
        self.bm25 = BM25Okapi(self.docs)
        n = len(self.docs)
        self.unseen_idf = math.log((n + 0.5) / 0.5 + 1)   # idf of a term that occurs in no passage
        self.doc_sets = [set(d) for d in self.docs]

    def coverage(self, q_tokens: list[str], i: int) -> float:
        """Share of the question's information (idf-weighted) that appears in passage i."""
        # Terms that never occur in the corpus get the highest weight: they are the clearest
        # signal that the question is about something the knowledge base does not cover.
        weights = {t: max(self.bm25.idf.get(t, self.unseen_idf), 0.0) for t in set(q_tokens)}
        total = sum(weights.values())
        if total == 0:
            return 0.0
        return sum(w for t, w in weights.items() if t in self.doc_sets[i]) / total

    def search(self, question: str, k: int = TOP_K) -> list[Hit]:
        q = tokens(question, self.vocab)
        if not q:
            return []
        scores = self.bm25.get_scores(q)
        refs, abs_refs = paragraph_refs(question), absatz_refs(question)
        hits = []
        for i, p in enumerate(self.passages):
            s = float(scores[i])
            if refs and p["paragraph"].lower() in refs:
                s += REF_BOOST          # the user named the paragraph explicitly
            if (p["paragraph"].lower(), p["absatz"]) in abs_refs:
                s += REF_BOOST          # ... and the Absatz
            hits.append(Hit(p, s, self.coverage(q, i)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]

    @staticmethod
    def enough_evidence(hits: list[Hit]) -> bool:
        """Abstain unless the best passage covers enough of the question."""
        return bool(hits) and max(h.coverage for h in hits[:2]) >= MIN_SCORE

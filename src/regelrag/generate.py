"""Step 6: write the answer from the retrieved passages, with a citation for every sentence.

Two interchangeable generators (same interface, chosen in config.GENERATOR):

ExtractiveGenerator  offline baseline. Picks the sentences of the retrieved passages that best
                     match the question and returns them verbatim. Deterministic, free, no API key,
                     so the whole pipeline and its evaluation run in CI. It cannot paraphrase.

AnthropicGenerator   LLM (Claude). Must answer through a tool call with a fixed schema: every
                     sentence carries the ids of the passages it is based on, or it abstains.
                     The prompt only allows the given passages as a source.

Both return an Answer; the validator (Step 7) then checks every sentence independently.
"""
import os
from dataclasses import dataclass, field

from .config import ANTHROPIC_MODEL
from .retrieve import Hit
from .text import absatz_refs, paragraph_refs, sentences, tokens


@dataclass
class Sentence:
    text: str
    citations: list[str]
    supported: bool | None = None     # set by the validator
    reason: str = ""


@dataclass
class Answer:
    question: str
    abstained: bool
    sentences: list[Sentence] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    note: str = ""

    @property
    def text(self) -> str:
        if self.abstained:
            return "Dazu finde ich in den hinterlegten Rechtsgrundlagen keine Antwort."
        return " ".join(s.text for s in self.sentences)


class ExtractiveGenerator:
    name = "extractive"

    def __init__(self, idf: dict[str, float], vocab: set[str], max_sentences: int = 2):
        self.idf, self.vocab, self.max_sentences = idf, vocab, max_sentences

    def score(self, q: set[str], sentence: str) -> float:
        s = set(tokens(sentence, self.vocab))
        return sum(self.idf.get(t, 0.0) for t in q & s)

    def generate(self, question: str, hits: list[Hit]) -> Answer:
        q = set(tokens(question, self.vocab))
        # Use the passages the retriever ranked best; if the question names a paragraph, only those.
        pool = hits[:3]
        named = [h for h in hits if h.passage["paragraph"].lower() in paragraph_refs(question)]
        if named:
            pool = named[:1] if absatz_refs(question) else named[:3]
        candidates = [(self.score(q, s), s, h.passage["id"])
                      for h in pool for s in sentences(h.passage["text"])]
        candidates.sort(key=lambda c: c[0], reverse=True)
        if not candidates or candidates[0][0] == 0:
            return Answer(question, abstained=True, hits=hits, note="no matching sentence")
        best = candidates[0][0]
        chosen = [c for c in candidates[: self.max_sentences] if c[0] >= 0.6 * best]
        return Answer(question, abstained=False, hits=hits,
                      sentences=[Sentence(text, [pid]) for _, text, pid in chosen])


ANSWER_TOOL = {
    "name": "submit_answer",
    "description": "Antwort auf die Frage, ausschließlich aus den bereitgestellten Gesetzesauszügen.",
    "input_schema": {
        "type": "object",
        "properties": {
            "abstain": {"type": "boolean",
                        "description": "true, wenn die Auszüge die Frage nicht beantworten."},
            "sentences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Ein Satz der Antwort, auf Deutsch."},
                        "citations": {"type": "array", "items": {"type": "string"},
                                      "description": "IDs der Auszüge, die diesen Satz belegen."},
                    },
                    "required": ["text", "citations"],
                },
            },
        },
        "required": ["abstain", "sentences"],
    },
}

SYSTEM_PROMPT = """Du beantwortest Fragen zur Krankenhausabrechnung und Rehabilitation
ausschließlich auf Grundlage der bereitgestellten Gesetzesauszüge (SGB V, KHG).

Regeln:
1. Verwende nur Informationen aus den Auszügen. Kein Allgemeinwissen, keine Vermutungen.
2. Jeder Satz der Antwort nennt in "citations" die ID des Auszugs, der ihn belegt.
3. Übernimm Zahlen, Fristen und Beträge wörtlich aus dem Auszug.
4. Wenn die Auszüge die Frage nicht beantworten, setze abstain=true und gib keine Sätze zurück.
5. Antworte knapp: höchstens drei Sätze."""


class AnthropicGenerator:
    name = "anthropic"

    def __init__(self, model: str = ANTHROPIC_MODEL, client=None):
        if client is None:              # tests pass a fake client; real use needs the API key
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.client = client
        self.model = model
        self.name = f"anthropic:{model}"

    def generate(self, question: str, hits: list[Hit]) -> Answer:
        context = "\n\n".join(f"[{h.passage['id']}] ({h.passage['title']})\n{h.passage['text']}"
                              for h in hits)
        msg = self.client.messages.create(
            model=self.model, max_tokens=800, temperature=0, system=SYSTEM_PROMPT,
            tools=[ANSWER_TOOL], tool_choice={"type": "tool", "name": "submit_answer"},
            messages=[{"role": "user", "content": f"Auszüge:\n\n{context}\n\nFrage: {question}"}],
        )
        data = next(b.input for b in msg.content if b.type == "tool_use")
        if data.get("abstain") or not data.get("sentences"):
            return Answer(question, abstained=True, hits=hits, note="model abstained")
        return Answer(question, abstained=False, hits=hits,
                      sentences=[Sentence(s["text"], list(s.get("citations", [])))
                                 for s in data["sentences"]])

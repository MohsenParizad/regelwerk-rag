"""Step 7: check every answer sentence against the passages it cites, independently of the generator.

"Don't let the model grade its own homework": the component that writes a sentence is never
the one that decides whether the sentence is true. The check is deliberately simple and
deterministic, so it is fast, free and explainable:

  1. The sentence must cite at least one passage that was actually retrieved.
  2. Numbers in the sentence (deadlines, amounts, percentages) must appear in the cited text.
     A wrong number is the most harmful hallucination in this domain ("300 Euro" vs "400 Euro").
  3. At least SUPPORT_THRESHOLD of the sentence's content words must appear in the cited text.

Limits: it does not understand negation or paraphrase. A sentence that reuses the words of the
law but reverses its meaning would pass. For that, add a second check (an NLI model or an LLM
judge calibrated on human ratings).
"""
from .config import SUPPORT_THRESHOLD
from .generate import Answer
from .text import numbers, tokens


def validate(answer: Answer) -> Answer:
    retrieved = {h.passage["id"]: h.passage["text"] for h in answer.hits}
    for s in answer.sentences:
        cited = [retrieved[c] for c in s.citations if c in retrieved]
        if not cited:
            s.supported, s.reason = False, "no valid citation"
            continue
        source = " ".join(cited)
        missing_numbers = numbers(s.text) - numbers(source)
        if missing_numbers:
            s.supported, s.reason = False, f"numbers not in source: {sorted(missing_numbers)}"
            continue
        words = set(tokens(s.text))
        overlap = len(words & set(tokens(source))) / max(len(words), 1)
        s.supported = overlap >= SUPPORT_THRESHOLD
        s.reason = f"word overlap {overlap:.0%}"
    return answer


def faithfulness(answer: Answer) -> float | None:
    """Share of supported sentences; None for an abstention (nothing to check)."""
    if answer.abstained or not answer.sentences:
        return None
    return sum(bool(s.supported) for s in answer.sentences) / len(answer.sentences)

"""Retrieval, abstention, generation, validation and the database layer."""
from types import SimpleNamespace

from regelrag.db import get_engine, load_passages, save_eval, save_passages
from regelrag.evaluate import gate, key_fact_recall
from regelrag.generate import AnthropicGenerator, Answer, Sentence
from regelrag.pipeline import Pipeline
from regelrag.validate import faithfulness, validate


def test_retrieval_finds_the_right_absatz(retriever):
    hits = retriever.search("Wie hoch ist die Aufwandspauschale?")
    assert hits[0].passage["id"] == "SGB V § 275c Abs. 1"


def test_named_paragraph_is_boosted(retriever):
    hits = retriever.search("Was steht in § 39?")
    assert hits[0].passage["paragraph"] == "§ 39"


def test_out_of_scope_question_abstains(passages):
    a = Pipeline(passages=passages).ask("Wie hoch ist der Landesbasisfallwert in Bayern?")
    assert a.abstained


def test_answer_cites_source_and_contains_fact(passages):
    a = Pipeline(passages=passages).ask("Wie hoch ist die Aufwandspauschale nach einer Prüfung ohne Minderung?")
    assert not a.abstained
    assert "300 Euro" in a.text
    assert a.sentences[0].citations == ["SGB V § 275c Abs. 1"]
    assert faithfulness(a) == 1.0


def test_validator_catches_a_wrong_number(retriever):
    hits = retriever.search("Aufwandspauschale")
    a = validate(Answer("q", False, [Sentence("Die Aufwandspauschale beträgt 400 Euro.",
                                              ["SGB V § 275c Abs. 1"])], hits))
    assert a.sentences[0].supported is False
    assert "400" in a.sentences[0].reason


def test_validator_rejects_citation_of_unretrieved_passage(retriever):
    hits = retriever.search("Aufwandspauschale")
    a = validate(Answer("q", False, [Sentence("Irgendetwas.", ["SGB V § 1 Abs. 1"])], hits))
    assert a.sentences[0].supported is False


def test_validator_rejects_unrelated_sentence(retriever):
    hits = retriever.search("Aufwandspauschale")
    a = validate(Answer("q", False, [Sentence("Der Patient erhält kostenlos ein Einzelzimmer mit Ausblick.",
                                              ["SGB V § 275c Abs. 1"])], hits))
    assert a.sentences[0].supported is False


class FakeClient:
    """Stands in for anthropic.Anthropic: returns a fixed tool call, no network, no key."""
    def __init__(self, tool_input):
        self.messages = SimpleNamespace(create=lambda **kw: SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", input=tool_input)]))


def test_llm_answer_is_parsed_and_validated(retriever):
    hits = retriever.search("Aufwandspauschale")
    gen = AnthropicGenerator(model="test", client=FakeClient({"abstain": False, "sentences": [
        {"text": "Die Aufwandspauschale beträgt 300 Euro.", "citations": ["SGB V § 275c Abs. 1"]},
        {"text": "Sie beträgt außerdem 999 Euro.", "citations": ["SGB V § 275c Abs. 1"]}]}))
    a = validate(gen.generate("Aufwandspauschale?", hits))
    assert [s.supported for s in a.sentences] == [True, False]
    assert faithfulness(a) == 0.5


def test_llm_abstention(retriever):
    gen = AnthropicGenerator(model="test", client=FakeClient({"abstain": True, "sentences": []}))
    assert gen.generate("?", retriever.search("Prüfung")).abstained


def test_key_fact_recall_with_alternatives():
    assert key_fact_recall("Die Frist beträgt vier Monate.", ["vier Monate", "Krankenkasse | Kasse"]) == 0.5
    assert key_fact_recall("anything", []) == 1.0


def test_gate_reports_each_failure():
    ok, fails = gate({"hit_at_k": 0.5, "faithfulness": 1, "key_fact_recall": 1,
                      "correct_abstention": 1, "false_abstention": 0.5})
    assert not ok and len(fails) == 2


def test_database_roundtrip(tmp_path, passages):
    engine = get_engine(f"sqlite:///{tmp_path / 't.db'}")
    save_passages(engine, passages, [{"law": "SGB V", "origin": "test", "sha256": "x" * 64}])
    assert [p["id"] for p in load_passages(engine)] == [p["id"] for p in passages]
    run_id = save_eval(engine, "extractive", {"hit_at_k": 1, "mrr": 1, "faithfulness": 1, "key_fact_recall": 1,
                                              "correct_abstention": 1, "false_abstention": 0},
                       [{"question_id": "q1", "answerable": True, "abstained": True, "hit": True,
                         "faithfulness": None, "key_fact_recall": 0.0, "answer": "-"}], True)
    assert run_id == 1

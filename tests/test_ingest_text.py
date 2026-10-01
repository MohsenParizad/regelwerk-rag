"""Parsing the official XML and the German text helpers."""
import pytest

from regelrag.ingest import parse_law
from regelrag.text import absatz_refs, numbers, paragraph_refs, sentences, tokens
from tests.conftest import MINI_XML


def test_one_passage_per_absatz_and_unwanted_norms_skipped(passages):
    ids = [p["id"] for p in passages]
    assert ids == ["SGB V § 275c Abs. 1", "SGB V § 275c Abs. 2", "SGB V § 39 Abs. 2"]


def test_repealed_absatz_is_dropped(passages):
    assert not any("weggefallen" in p["text"] for p in passages)


def test_list_items_keep_their_spacing(passages):
    text = passages[1]["text"]
    assert "beträgt 1. bis zu 5 Prozent, 2. bis zu 10 Prozent." in text


def test_missing_paragraph_raises():
    with pytest.raises(ValueError, match="§ 40"):
        parse_law(MINI_XML, "SGB V", ["§ 40"])


def test_stemming_unifies_word_forms():
    assert tokens("Krankenhäuser")[0] == tokens("Krankenhaus")[0]


def test_zu_infix_is_removed():
    assert tokens("einzuleiten") == tokens("einleiten")


def test_stopwords_removed():
    assert tokens("Wie hoch ist die Pauschale?") == tokens("hoch Pauschale")


def test_unknown_compound_is_split_into_known_parts():
    vocab = {"krankenhaus", "rechnung"}
    assert tokens("Krankenhausrechnung", vocab) == ["krankenhaus", "rechnung"]


@pytest.mark.parametrize("text,expected", [
    ("300 Euro und 12,5 Prozent", {"300", "12,5"}),
    ("am 1. Januar 2020.", {"1", "2020"}),
    ("keine Zahl", set()),
])
def test_numbers(text, expected):
    assert numbers(text) == expected


def test_references():
    assert paragraph_refs("Was regelt § 275c und §39?") == {"§ 275c", "§ 39"}
    assert absatz_refs("§ 17c Absatz 2a und § 39 Abs. 4") == {("§ 17c", "2a"), ("§ 39", "4")}


def test_sentences_do_not_split_dates_or_abbreviations():
    s = sentences("Ab dem 1. Januar 2020 gilt Abs. 2 entsprechend für alle Fälle. Die Kasse zahlt 300 Euro sofort.")
    assert len(s) == 2

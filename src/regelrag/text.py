"""German text helpers shared by retrieval, generation and validation."""
import re

import snowballstemmer

_stemmer = snowballstemmer.stemmer("german")

STOPWORDS = set("""
aber alle allem allen aller als also am an andere anderen auch auf aus bei beim bis bzw da damit dann
das dass daß dem den denen der deren des dessen die dies diese diesem diesen dieser dieses doch dort du
durch ein eine einem einen einer eines er es für gegen hat haben hatte ich ihm ihn ihr ihre im in
ist ja jede jedem jeden jeder jedes kann kein keine können man mit muss müssen nach nicht noch nur
ob oder ohne sein seine sich sie sind so soll sollen sowie über um und uns unter vom von vor
war was welche welchem welchen welcher welches wenn wer werden wie wird wo wurde zu zum zur
gilt gelten satz absatz nummer nr abs gibt geben darf dürfen wann womit wieviel viel viele
wozu wofür warum weshalb wieso welch versteht verstehen bedeutet heißt dient droht passiert geschehen
hoch lang lange groß
""".split())

_TOKEN = re.compile(r"[a-zäöüß0-9]+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_PARA_REF = re.compile(r"§\s*(\d+[a-z]?)", re.IGNORECASE)
# Sentence end: '.' or ';' followed by an upper-case letter or '('.
# Not after abbreviations ("Abs.", "Nr.") or ordinal numbers ("1. Januar").
_SENT_SPLIT = re.compile(r"(?<!\bAbs\.)(?<!\bNr\.)(?<![0-9]\.)(?<=[.;])\s+(?=[A-ZÄÖÜ(])")


_ZU_INFIX = re.compile(r"^(an|auf|aus|ab|ein|vor|nach|mit|durch|zurück|fest|dar|her|hin)zu(\w{4,})$")
_PARA_ABS_REF = re.compile(r"§\s*(\d+[a-z]?)\s*(?:Abs\.|Absatz)\s*(\d+[a-z]?)", re.IGNORECASE)


def stem(word: str) -> str:
    """Snowball stem; separable verbs lose the 'zu' infix first ('einzuleiten' -> 'einleiten')."""
    return _stemmer.stemWord(_ZU_INFIX.sub(r"\1\2", word))


def split_compound(word: str, vocab: set[str]) -> list[str]:
    """German compounds: 'krankenhausrechnung' -> ['krankenhaus', 'rechnung'] if both parts are known stems.

    Tries every split point; allows the linking 's' ('Prüfungsergebnis' -> 'prüfung' + 'ergebnis').
    Returns [] if no split into two known parts exists.
    """
    for i in range(len(word) - 4, 3, -1):           # prefer a long first part
        left, right = word[:i], word[i:]
        for l in (left, left[:-1] if left.endswith("s") else None):
            if l and stem(l) in vocab and stem(right) in vocab:
                return [stem(l), stem(right)]
    return []


def tokens(text: str, vocab: set[str] | None = None) -> list[str]:
    """Lower-case, remove stop words, stem; with a vocabulary also add the parts of long compounds.

    'Krankenhäuser' and 'Krankenhaus' become the same token; 'Krankenhausrechnung' additionally
    yields 'krankenhaus' and 'rechnung', so it matches 'Rechnung des Krankenhauses'.
    """
    out = []
    for t in _TOKEN.findall(text.lower()):
        if t in STOPWORDS:
            continue
        st = stem(t)
        parts = split_compound(t, vocab) if vocab is not None and len(t) >= 10 else []
        if parts and st not in vocab:
            out += parts            # unknown compound: replace it by its known parts
        else:
            out.append(st)
            out += parts            # known compound: keep it and add the parts
    return out


def numbers(text: str) -> set[str]:
    """Numbers as written ('300', '12,5', '2024'): used to check that figures in an answer exist in the source."""
    return {n.rstrip(".,") for n in _NUMBER.findall(text)}


def paragraph_refs(text: str) -> set[str]:
    """'Was regelt § 275c?' -> {'§ 275c'}"""
    return {f"§ {m.lower()}" for m in _PARA_REF.findall(text)}


def absatz_refs(text: str) -> set[tuple[str, str]]:
    """'§ 275c Absatz 7' -> {('§ 275c', '7')}"""
    return {(f"§ {p.lower()}", a.lower()) for p, a in _PARA_ABS_REF.findall(text)}


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 20]

"""Step 1-3: download the laws, split selected paragraphs into Absätze, store them.

Input : official XML from gesetze-im-internet.de (fallback: daily GitHub mirror)
Output: data/raw/<law>.xml, data/raw/manifest.json (SHA-256 = data version),
        data/passages.jsonl and the 'passages' table in the database

Usage: python -m regelrag.ingest            (download, then parse)
       python -m regelrag.ingest --offline  (parse the files already in data/raw)
"""
import hashlib
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from .config import DATA, LAWS, RAW
from .db import get_engine, save_passages

ABSATZ_RE = re.compile(r"^\((\d+[a-z]?)\)\s*")
SKIP_TAGS = {"FnR", "Footnotes", "FnArea"}   # footnote markers are not part of the legal text


def download(law: str, cfg: dict) -> tuple[bytes, str]:
    """Return (xml_bytes, origin). Try the official ZIP first, then the mirror."""
    try:
        with urllib.request.urlopen(cfg["official"], timeout=60) as r:
            with zipfile.ZipFile(io.BytesIO(r.read())) as z:
                name = next(n for n in z.namelist() if n.endswith(".xml"))
                return z.read(name), cfg["official"]
    except Exception as e:  # network blocked, site down, format changed
        print(f"[{law}] official source failed ({e.__class__.__name__}), using mirror")
        with urllib.request.urlopen(cfg["mirror"], timeout=120) as r:
            return r.read(), cfg["mirror"]


def element_text(el: ET.Element) -> str:
    """Flatten XML to text. Inserts spaces between list items (DT/DD) so '1.' and the item don't merge."""
    parts = []

    def walk(e):
        if e.tag in SKIP_TAGS:
            if e.tail:
                parts.append(e.tail)
            return
        if e.text:
            parts.append(e.text)
        for child in e:
            if child.tag in ("DL", "DT", "DD", "LA", "P", "Row"):
                parts.append(" ")
            walk(child)
            if child.tag in ("DT", "DD", "LA", "P", "Row"):
                parts.append(" ")
        if e.tail:
            parts.append(e.tail)

    walk(el)
    text = " ".join("".join(parts).split())
    return re.sub(r"\s+([,.;:])", r"\1", text)


def parse_law(xml: bytes, law: str, wanted: list[str]) -> list[dict]:
    """One passage per <P> (= Absatz) of each wanted paragraph."""
    root = ET.fromstring(xml)
    passages = []
    for norm in root.iter("norm"):
        enbez = norm.findtext("metadaten/enbez")
        if enbez not in wanted:
            continue
        title = norm.findtext("metadaten/titel") or ""
        content = norm.find("textdaten/text/Content")
        if content is None:
            continue
        for pos, p in enumerate(content.findall("P"), start=1):
            text = element_text(p)
            if not text or re.fullmatch(r"(\(\w+\)\s*)?\(?weggefallen\)?", text):
                continue
            m = ABSATZ_RE.match(text)
            absatz = m.group(1) if m else str(pos)
            passages.append({"id": f"{law} {enbez} Abs. {absatz}", "law": law, "paragraph": enbez,
                             "absatz": absatz, "position": pos, "title": " ".join(title.split()),
                             "text": text})
    found = {p["paragraph"] for p in passages}
    missing = [n for n in wanted if n not in found]
    if missing:
        raise ValueError(f"{law}: paragraphs not found in XML: {missing}")
    return passages


def run(offline: bool = False) -> list[dict]:
    RAW.mkdir(parents=True, exist_ok=True)
    passages, versions, manifest = [], [], {}
    for law, cfg in LAWS.items():
        path = RAW / cfg["file"]
        if offline:
            xml, origin = path.read_bytes(), f"local:{path.name}"
        else:
            xml, origin = download(law, cfg)
            path.write_bytes(xml)
        sha = hashlib.sha256(xml).hexdigest()
        manifest[law] = {"origin": origin, "sha256": sha}
        versions.append({"law": law, "origin": origin[:300], "sha256": sha})
        passages += parse_law(xml, law, cfg["norms"])

    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=2))
    with open(DATA / "passages.jsonl", "w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    save_passages(get_engine(), passages, versions)
    print(f"{len(passages)} passages from {len(LAWS)} laws stored "
          f"({', '.join(k + ': ' + v['sha256'][:12] for k, v in manifest.items())})")
    return passages


if __name__ == "__main__":
    run(offline="--offline" in sys.argv)

"""Step 9: user interface (Streamlit). Run: streamlit run app.py"""
import json
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))   # so "import regelrag" works without installing

from regelrag.config import RAW, REPORTS
from regelrag.pipeline import Pipeline

st.set_page_config(page_title="Regelwerk-Assistent", page_icon="§", layout="wide")

EXAMPLES = [
    "Innerhalb welcher Frist muss die Prüfung einer Krankenhausrechnung eingeleitet werden?",
    "Wie hoch ist der Aufschlag bei beanstandeten Abrechnungen ab dem 12. Dezember 2024?",
    "Darf ein Krankenhaus seine Abrechnung nach der Übermittlung noch korrigieren?",
    "Wann gilt eine Anschlussrehabilitation als unmittelbar?",
    "Wie hoch ist der Landesbasisfallwert in Nordrhein-Westfalen?",
]


@st.cache_resource
def pipeline(generator: str) -> Pipeline:
    return Pipeline(generator)


st.title("Regelwerk-Assistent: Krankenhausabrechnung & Reha")
st.caption("Antworten ausschließlich aus SGB V (§§ 39, 40, 107–109, 111, 112, 275, 275c, 301) und KHG § 17c, "
           "jede Aussage mit Quelle. Demonstrationsprojekt, keine Rechtsberatung.")

with st.sidebar:
    options = ["extractive"] + (["anthropic"] if os.getenv("ANTHROPIC_API_KEY") else [])
    generator = st.radio("Antwortgenerator", options,
                         help="extractive: zitiert passende Sätze wörtlich (offline). "
                              "anthropic: formuliert mit Claude (API-Schlüssel nötig).")
    st.markdown("**Beispielfragen**")
    for q in EXAMPLES:
        if st.button(q, use_container_width=True):
            st.session_state["q"] = q
    manifest = RAW / "manifest.json"
    if manifest.exists():
        st.markdown("**Datenstand**")
        for law, v in json.loads(manifest.read_text()).items():
            st.caption(f"{law}: {v['sha256'][:12]}")

tab_ask, tab_eval = st.tabs(["Fragen", "Qualität"])

with tab_ask:
    question = st.text_input("Ihre Frage", key="q")
    if question:
        a = pipeline(generator).ask(question)
        if a.abstained:
            st.warning(a.text)
            st.caption(f"Grund: {a.note}")
        else:
            for s in a.sentences:
                icon = "✅" if s.supported else "⚠️"
                st.markdown(f"{icon} {s.text}  \n<small>Quelle: {', '.join(s.citations)} · {s.reason}</small>",
                            unsafe_allow_html=True)
            if any(not s.supported for s in a.sentences):
                st.error("Mindestens eine Aussage ist nicht durch die zitierte Quelle belegt. Bitte prüfen.")
        with st.expander("Gefundene Gesetzesstellen"):
            for h in a.hits:
                st.markdown(f"**{h.passage['id']}** — {h.passage['title']}  \n"
                            f"<small>BM25 {h.score:.2f} · Abdeckung der Frage {h.coverage:.0%}</small>",
                            unsafe_allow_html=True)
                st.write(h.passage["text"])

with tab_eval:
    reports = sorted(REPORTS.glob("eval_*.json"))
    if not reports:
        st.info("Noch keine Evaluation. Ausführen: python -m regelrag.evaluate")
    for path in reports:
        r = json.loads(path.read_text())
        st.subheader(f"Generator: {r['generator']} — Gate {'bestanden' if r['gate']['passed'] else 'NICHT bestanden'}")
        cols = st.columns(4)
        for i, (k, v) in enumerate(r["metrics"].items()):
            cols[i % 4].metric(k, v)
        st.markdown("**Schwellenwert für 'keine Grundlage' (Abwägung)**")
        st.dataframe(r["threshold_sweep"], hide_index=True)

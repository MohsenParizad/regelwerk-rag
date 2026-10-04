# Regelwerk-Assistent: RAG für Krankenhausabrechnung und Reha – mit messbarer Qualität
![CI](https://github.com/MohsenParizad/regelwerk-rag/actions/workflows/ci.yml/badge.svg)
Ein bewusst kleines, nachvollziehbares **Retrieval-Augmented-Generation-System**, das Fragen zur
Abrechnungsprüfung von Krankenhausleistungen und zur Rehabilitation beantwortet –
**ausschließlich** aus den Gesetzestexten, **jede Aussage mit Quelle**, und mit „Dazu finde ich keine
Antwort“, wenn die Rechtsgrundlage fehlt.

Der Schwerpunkt liegt nicht auf der Chat-Oberfläche, sondern auf der Frage, die bei generativer KI
entscheidet: **Woran erkenne ich, ob die Antworten gut sind?** Dafür gibt es ein Testset, acht
Kennzahlen, eine unabhängige Prüfung jeder Aussage und ein Quality Gate in der CI.

![Prozessmodell (BPMN 2.0)](docs/regelrag_process.png)

*Prozessmodell in BPMN 2.0 (`docs/regelrag_process.bpmn`, bearbeitbar in [bpmn.io](https://demo.bpmn.io) oder Camunda Modeler).*

![Oberfläche](docs/app_screenshot.png)

---

## Wissensbasis

| Gesetz | Paragraphen | Thema |
|---|---|---|
| SGB V | § 39, § 40 | Krankenhausbehandlung, medizinische Rehabilitation |
| SGB V | § 107, § 108, § 109, § 111, § 112 | Krankenhäuser und Reha-Einrichtungen, Zulassung, Versorgungsverträge, Verjährung |
| SGB V | § 275, § 275c | Medizinischer Dienst, Prüfung der Krankenhausabrechnung, Prüfquote, Aufschlag |
| SGB V | § 301 | Datenübermittlung Krankenhaus/Reha-Einrichtung → Krankenkasse |
| KHG | § 17c | Prüfung der Abrechnung, Korrekturverbot, Erörterung, Schlichtung, Statistik |

72 Absätze, geladen aus dem amtlichen XML von [gesetze-im-internet.de](https://www.gesetze-im-internet.de)
(Rückfall: täglicher Spiegel auf GitHub). Der SHA-256-Hash jeder Datei in `data/raw/manifest.json` ist die Datenversion.

## Ergebnisse (Offline-Baseline, 43 Testfragen)

| Kennzahl | Bedeutung | Wert | Gate |
|---|---|---|---|
| Hit@5 | Richtiger Absatz unter den 5 Treffern | **1,00** | ≥ 0,85 |
| MRR | Wie weit oben der richtige Absatz steht | 0,92 | – |
| Citation precision | Zitierte Absätze, die tatsächlich relevant sind | 0,77 | – |
| Faithfulness | Antwortsätze, die durch die zitierte Quelle belegt sind | 1,00 | ≥ 0,90 |
| Key-fact recall | Erwartete Fakten (Fristen, Beträge) in der Antwort | **0,87** | ≥ 0,60 |
| Richtige Ablehnung | Nicht beantwortbare Fragen mit „keine Grundlage“ | **0,88** | ≥ 0,75 |
| Falsche Ablehnung | Beantwortbare Fragen fälschlich abgelehnt | 0,06 | ≤ 0,15 |
| Latenz | pro Frage | ~50 ms | – |

Vollständiger Bericht mit allen Problemfällen: [`reports/eval_extractive.md`](reports/eval_extractive.md).

**Ehrliche Einordnung.** Die Offline-Baseline zitiert Sätze wörtlich – Faithfulness 1,0 ist daher
erwartbar und kein Verdienst. Aussagekräftig wird diese Kennzahl beim LLM-Generator
(`make eval-llm`), der frei formuliert. Bewusst im Testset: zwei „Fallen“ (u03, u05), deren
Stichwörter im Gesetz vorkommen, deren Antwort aber nicht. u05 wird von der Baseline fälschlich
beantwortet – genau die Schwäche einer rein lexikalischen Relevanzprüfung.

---

## Pipeline: jeder Schritt und sein Ergebnis

| Schritt | Befehl / Datei | Was passiert | Ergebnis |
|---|---|---|---|
| 0 Prozessmodell | `scripts/make_bpmn.py` | Lebenszyklus in BPMN 2.0, 4 Lanes | `docs/regelrag_process.bpmn` |
| 1 Laden | `make ingest` → `ingest.py` | Amtliches XML laden (Rückfall: Spiegel), SHA-256 | `data/raw/*.xml`, `manifest.json` |
| 2 Zerlegen | `ingest.py` | Ausgewählte §§ in Absätze; Listen, Fußnoten, „(weggefallen)“ bereinigt | 72 Passagen |
| 3 Speichern | `db.py` | SQLAlchemy: SQLite (Standard) oder **SQL Server** | Tabelle `passages`, `data/passages.jsonl` |
| 4 Testset | `data/testset/testset.yaml` | 35 beantwortbare + 8 nicht beantwortbare Fragen mit Quelle und Schlüsselfakten | Goldstandard |
| 5 Suchen | `retrieve.py` | BM25, deutsche Stammformen, Kompositazerlegung, §-Bonus, Abdeckungsmaß | Top-5 Absätze |
| 6 Antworten | `generate.py` | Offline-Extraktion **oder** Claude mit erzwungenem Tool-Call und Zitaten | Sätze + Quellen |
| 7 Prüfen | `validate.py` | Jede Aussage unabhängig: Zitat gültig? Zahlen in der Quelle? Wortüberdeckung? | belegt / nicht belegt |
| 8 Evaluieren | `make eval` → `evaluate.py` | 8 Kennzahlen, Schwellenwert-Analyse, Gate (Exit-Code 1) | `reports/eval_*.md/.json`, Tabelle `eval_runs` |
| 9 Oberfläche | `make app` → `app.py` | Streamlit: Frage, Antwort mit Quellen, Qualitäts-Tab | http://localhost:8501 |
| 10 CI | `.github/workflows/ci.yml` | Tests + Evaluation + Gate; zweiter Job gegen echten SQL Server | grüner/roter Build |
| 11 Monitoring | `.github/workflows/law-watch.yml` | Montags: Gesetze neu laden; bei Änderung Evaluation + Issue | GitHub-Issue |

## Schnellstart

Ausführliche Anleitung (GitHub, SQL Server, Claude, öffentliche Demo): [`docs/SETUP.md`](docs/SETUP.md).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
make ingest      # Gesetze laden
make test        # 29 Tests
make eval        # Evaluation + Quality Gate
make app         # Oberfläche
make ask Q="Wie hoch ist die Aufwandspauschale?"
```

**Mit Claude als Generator:** `.env.example` nach `.env` kopieren, `ANTHROPIC_API_KEY` eintragen,
dann `export $(cat .env | xargs) && make eval-llm`.

**Mit SQL Server statt SQLite:**

```bash
docker compose up -d mssql                     # SQL Server 2022 Developer Edition
pip install -r requirements-mssql.txt          # plus Microsoft ODBC Driver 18
export DATABASE_URL="mssql+pyodbc://sa:YourStrong!Passw0rd@localhost:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
make ingest eval                               # gleicher Code, andere Datenbank
```

Unter Windows funktioniert alternativ SQL Server Express mit `localhost\SQLEXPRESS`.

## Designentscheidungen

| Entscheidung | Begründung |
|---|---|
| Absatz als Einheit | Gesetze werden absatzgenau zitiert; die Quelle ist für Fachleute sofort prüfbar. |
| BM25 statt Embeddings | Fachbegriffe sind im Gesetz und in der Frage identisch; offline, schnell, jeder Score erklärbar. Embeddings sind der nächste Schritt für umformulierte Fragen. |
| Kompositazerlegung | „Krankenhausrechnung“ findet „Rechnung des Krankenhauses“ – ein typisches Problem deutscher Texte. |
| Ablehnen vor dem Generieren | Wenn die Suche zu wenig findet, wird das Modell gar nicht erst gefragt – keine Gelegenheit zu halluzinieren. |
| Unabhängige Prüfung | Das Modell bewertet nicht seine eigene Antwort. Zahlen werden gesondert geprüft: „300 Euro“ statt „400 Euro“ ist der teuerste Fehler. |
| Zwei Generatoren | Die Offline-Baseline macht Pipeline und Evaluation ohne API-Schlüssel und Kosten in der CI lauffähig; das LLM wird mit denselben Kennzahlen gemessen. |
| SQLAlchemy | Ein Code für SQLite und SQL Server; `UnicodeText` wird auf SQL Server zu `NVARCHAR(max)` (Umlaute, §-Zeichen). |
| Gate in der CI | Eine Änderung, die die Qualität verschlechtert, kann nicht unbemerkt gemergt werden. |

## Grenzen und nächste Schritte

1. **Testset klein (43 Fragen) und selbst erstellt.** Der Schwellenwert für die Ablehnung wurde auf
   demselben Testset gewählt; sauberer wäre ein getrenntes Entwicklungs- und Testset.
2. **Die Prüfung versteht keine Verneinung.** Ein Satz mit den Wörtern des Gesetzes, aber umgekehrter
   Aussage, würde bestehen. Nächster Schritt: NLI-Modell oder LLM-as-Judge, kalibriert an menschlichen Bewertungen.
3. **Nur lexikalische Suche.** Hybride Suche (BM25 + Embeddings) für umformulierte Fragen.
4. **Weitere Regelwerke:** Prüfverfahrensvereinbarung (PrüfvV), KHEntgG, Deutsche Kodierrichtlinien –
   jeweils mit eigenen Testfragen.
5. **Datenschutz:** Die Wissensbasis enthält keine personenbezogenen Daten. Mit echten Fällen: Pseudonymisierung,
   Hosting in der EU oder im eigenen Rechenzentrum, Einbindung von Datenschutz und Informationssicherheit, Einordnung nach dem AI Act.

## Rechtliches

Gesetzestexte sind amtliche Werke (§ 5 UrhG). Dieses Projekt ist eine technische Demonstration und **keine Rechtsberatung**.

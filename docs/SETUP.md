# Einrichtung Schritt für Schritt

Von der ZIP-Datei bis zum grünen Build, zur SQL-Server-Datenbank und zur öffentlichen Demo.
Alle Befehle funktionieren in der **Google Cloud Shell** (kostenlos, Docker vorinstalliert) oder lokal mit Python 3.11.

---

## Teil A – Lokal starten (10 Minuten)

```bash
unzip regelwerk-rag.zip && cd regelwerk-rag
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
make ingest
make test
make eval
```

Erwartet: `72 passages from 2 laws stored`, `29 passed`, `GATE PASSED`.

Eine Frage stellen:

```bash
make ask Q="Darf ein Krankenhaus seine Abrechnung nach der Übermittlung noch korrigieren?"
```

Oberfläche (in der Cloud Shell danach oben rechts **Webvorschau → Port ändern → 8501**):

```bash
make app
```

---

## Teil B – Auf GitHub veröffentlichen

1. Auf github.com: **New repository** → Name `regelwerk-rag` → Public → *ohne* README → Create.
2. In der Shell (im Ordner `regelwerk-rag`):

```bash
git init -b main
git add .
git commit -m "Regelwerk-Assistent: RAG mit Evaluation und Quality Gate"
git remote add origin https://github.com/MohsenParizad/regelwerk-rag.git
git push -u origin main
```

Benutzername: `MohsenParizad`; Passwort: ein **Fine-grained Personal Access Token** mit
*Contents: Read and write* und *Workflows: Read and write* für dieses Repository
(Settings → Developer settings → Personal access tokens). Danach den Token wieder löschen.

3. Tab **Actions**: Der Workflow **CI** startet automatisch mit zwei Jobs:
   - `test-and-evaluate` – Tests, Evaluation, Gate, Bericht als Artefakt
   - `sql-server` – derselbe Ablauf gegen einen echten Microsoft SQL Server

Beide sollten grün werden. Den Bericht findest du im Lauf unter **Artifacts → evaluation-report**.

---

## Teil C – SQL Server selbst ausprobieren (Cloud Shell)

```bash
docker compose up -d mssql
sleep 20
docker compose logs mssql | grep -i "ready for client connections"

# ODBC-Treiber (einmalig)
curl -sSL https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc
curl -sSL https://packages.microsoft.com/config/debian/12/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update && sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
pip install -r requirements-mssql.txt

export DATABASE_URL="mssql+pyodbc://sa:YourStrong!Passw0rd@localhost:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
make ingest eval
```

> Falls die Cloud Shell kein Debian 12 ist: `cat /etc/os-release` zeigt die Version; den Pfad
> `debian/12` entsprechend anpassen (z. B. `ubuntu/24.04`).

In der Datenbank nachsehen (mit dem Kommandozeilenwerkzeug im Container):

```bash
docker compose exec mssql /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'YourStrong!Passw0rd' -C \
  -Q "SELECT TOP 5 id, LEN(text) AS zeichen FROM passages; SELECT generator, hit_at_k, faithfulness, gate_passed FROM eval_runs;"
```

Übungsfragen in SQL, die du im Gespräch zeigen kannst:

```sql
-- Welche Testfragen wurden im letzten Lauf falsch abgelehnt?
SELECT question_id FROM eval_results
WHERE run_id = (SELECT MAX(id) FROM eval_runs) AND answerable = 1 AND abstained = 1;

-- Wie hat sich die Qualität über die Läufe entwickelt?
SELECT id, created_at, generator, key_fact_recall, correct_abstention FROM eval_runs ORDER BY id;
```

---

## Teil D – Claude als Generator (optional, wenige Cent)

1. API-Schlüssel auf console.anthropic.com anlegen, **Ausgabenlimit setzen**.
2. Lokal: `cp .env.example .env`, Schlüssel eintragen, dann

```bash
export $(grep -v '^#' .env | xargs)
make eval-llm
```

3. Auf GitHub: Settings → Secrets and variables → Actions → **New repository secret** `ANTHROPIC_API_KEY`;
   dann Actions → **Evaluate LLM** → Run workflow.

Vergleiche `reports/eval_extractive.md` und `reports/eval_anthropic_*.md`: Wo ist das LLM besser
(Key-fact recall, umformulierte Fragen), wo schlechter (Faithfulness, Ablehnung)? Genau dieser Vergleich
ist die Antwort auf „Wie bewerten Sie die Qualität eines GenAI-Systems?“.

---

## Teil E – Öffentliche Demo (Streamlit Community Cloud, kostenlos)

1. share.streamlit.io → mit GitHub anmelden → **New app**.
2. Repository `MohsenParizad/regelwerk-rag`, Branch `main`, Main file `app.py` → Deploy.
3. Optional unter *Advanced settings → Secrets*: `ANTHROPIC_API_KEY = "..."` – nur mit Ausgabenlimit,
   da die Demo öffentlich ist. Ohne Schlüssel läuft die Offline-Variante.

Die App nutzt `data/passages.jsonl` aus dem Repository, braucht also keine Datenbank.

---

## Teil F – Das Projekt zu deinem machen

1. **Zehn eigene Testfragen** in `data/testset/testset.yaml` ergänzen: zuerst die Frage formulieren,
   dann die Antwort im Gesetz nachschlagen, dann `relevant` und `key_facts` eintragen.
   Mindestens zwei nicht beantwortbare „Fallen“.
2. `make eval` und die neuen Problemfälle im Bericht ansehen. Warum scheitert die Frage – Suche, Antwort oder Ablehnung?
3. Eine Verbesserung umsetzen und zeigen, dass die Kennzahl steigt, ohne eine andere zu verschlechtern.

Diese drei Schritte sind die Geschichte, die du im Vorstellungsgespräch erzählst.

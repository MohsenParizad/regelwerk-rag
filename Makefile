# Each target is one step of the BPMN process (docs/regelrag_process.bpmn).
PY = PYTHONPATH=src python3

.PHONY: all ingest ask eval eval-llm test app bpmn
all: ingest test eval

ingest:      ## Steps 1-3: download SGB V + KHG, split into Absätze, store (SQLite or SQL Server)
	$(PY) -m regelrag.ingest

ask:         ## Steps 5-7 for one question: make ask Q="Wie hoch ist die Aufwandspauschale?"
	$(PY) -m regelrag.pipeline "$(Q)"

eval:        ## Step 8: offline evaluation + quality gate (exit 1 if the gate fails)
	$(PY) -m regelrag.evaluate --generator extractive

eval-llm:    ## Step 8 with Claude (needs ANTHROPIC_API_KEY)
	$(PY) -m regelrag.evaluate --generator anthropic

test:        ## Unit, pipeline and quality tests
	python3 -m pytest -q

app:         ## Step 9: web interface on http://localhost:8501
	PYTHONPATH=src streamlit run app.py

bpmn:        ## Process model
	python3 scripts/make_bpmn.py

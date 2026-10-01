"""All settings in one place: corpus, paths, retrieval and quality thresholds."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
TESTSET = DATA / "testset" / "testset.yaml"
REPORTS = ROOT / "reports"

# Database: SQLite by default (no setup); SQL Server via environment variable, e.g.
# DATABASE_URL="mssql+pyodbc://sa:<pw>@localhost:1433/regelrag?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA / 'regelrag.db'}")

# Laws: official XML from gesetze-im-internet.de; daily GitHub mirror as fallback.
LAWS = {
    "SGB V": {
        "official": "https://www.gesetze-im-internet.de/sgb_5/xml.zip",
        "mirror": "https://raw.githubusercontent.com/QuantLaw/gesetze-im-internet/data/data/items/sgb_5/BJNR024820988.xml",
        "file": "sgb_5.xml",
        "norms": ["§ 39", "§ 40", "§ 107", "§ 108", "§ 109", "§ 111", "§ 112", "§ 275", "§ 275c", "§ 301"],
    },
    "KHG": {
        "official": "https://www.gesetze-im-internet.de/khg/xml.zip",
        "mirror": "https://raw.githubusercontent.com/QuantLaw/gesetze-im-internet/data/data/items/khg/BJNR010090972.xml",
        "file": "khg.xml",
        "norms": ["§ 17c"],
    },
}

# Retrieval
TOP_K = 5                 # passages given to the generator
MIN_SCORE = 0.5           # minimum coverage of the question by the best passage; below: "no basis found"
REF_BOOST = 4.0           # extra score if the question names the paragraph explicitly ("§ 275c")

# Generator: "extractive" (offline, deterministic, used in CI) or "anthropic" (needs ANTHROPIC_API_KEY)
GENERATOR = os.getenv("GENERATOR", "extractive")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

# Claim validation: share of a sentence's content words that must occur in the cited passages
SUPPORT_THRESHOLD = 0.6

# Evaluation gate: the build fails if any of these is violated
GATE = {
    "min_hit_at_k": 0.85,          # correct paragraph among the retrieved passages
    "min_faithfulness": 0.90,      # share of answer sentences supported by cited sources
    "min_key_fact_recall": 0.60,   # expected facts contained in the answer
    "min_correct_abstention": 0.75,  # out-of-scope questions answered with "no basis"
    "max_false_abstention": 0.15,    # answerable questions wrongly refused
}

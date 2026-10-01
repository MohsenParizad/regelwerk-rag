"""Storage with SQLAlchemy: the same code runs on SQLite (default) and Microsoft SQL Server.

Tables
  source_versions  which law file was loaded, from where, with which SHA-256 hash
  passages         one row per Absatz (the unit that is retrieved and cited)
  eval_runs        one row per evaluation run with all metrics and the gate result
  eval_results     one row per test question and run
"""
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String, UnicodeText,
                        create_engine, delete, select)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class SourceVersion(Base):
    __tablename__ = "source_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    law: Mapped[str] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64))
    loaded_at: Mapped[datetime] = mapped_column(DateTime)


class Passage(Base):
    __tablename__ = "passages"
    id: Mapped[str] = mapped_column(String(60), primary_key=True)   # e.g. "SGB V § 275c Abs. 1"
    law: Mapped[str] = mapped_column(String(20))
    paragraph: Mapped[str] = mapped_column(String(20))               # "§ 275c"
    absatz: Mapped[str] = mapped_column(String(10))                  # "1", "2a"
    position: Mapped[int] = mapped_column(Integer)                    # order within the paragraph
    title: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(UnicodeText)                    # NVARCHAR(max) on SQL Server


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    generator: Mapped[str] = mapped_column(String(40))
    n_questions: Mapped[int] = mapped_column(Integer)
    hit_at_k: Mapped[float] = mapped_column(Float)
    mrr: Mapped[float] = mapped_column(Float)
    faithfulness: Mapped[float] = mapped_column(Float)
    key_fact_recall: Mapped[float] = mapped_column(Float)
    correct_abstention: Mapped[float] = mapped_column(Float)
    false_abstention: Mapped[float] = mapped_column(Float)
    gate_passed: Mapped[bool] = mapped_column(Boolean)


class EvalResult(Base):
    __tablename__ = "eval_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("eval_runs.id"))
    question_id: Mapped[str] = mapped_column(String(20))
    answerable: Mapped[bool] = mapped_column(Boolean)
    abstained: Mapped[bool] = mapped_column(Boolean)
    hit: Mapped[bool] = mapped_column(Boolean)
    faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)  # None = abstained
    key_fact_recall: Mapped[float] = mapped_column(Float)
    answer: Mapped[str] = mapped_column(UnicodeText)


def get_engine(url: str = DATABASE_URL):
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine


def save_passages(engine, passages: list[dict], versions: list[dict]) -> None:
    """Replace all passages (full reload keeps the knowledge base consistent with one law version)."""
    with Session(engine) as s:
        s.execute(delete(Passage))
        s.add_all(Passage(**p) for p in passages)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        s.add_all(SourceVersion(loaded_at=now, **v) for v in versions)
        s.commit()


def load_passages(engine) -> list[dict]:
    with Session(engine) as s:
        rows = s.scalars(select(Passage).order_by(Passage.law, Passage.paragraph, Passage.position)).all()
        return [{"id": r.id, "law": r.law, "paragraph": r.paragraph, "absatz": r.absatz,
                 "position": r.position, "title": r.title, "text": r.text} for r in rows]


def save_eval(engine, generator: str, metrics: dict, per_question: list[dict], passed: bool) -> int:
    with Session(engine) as s:
        run = EvalRun(created_at=datetime.now(timezone.utc).replace(tzinfo=None), generator=generator,
                      n_questions=len(per_question), gate_passed=passed,
                      **{k: metrics[k] for k in ("hit_at_k", "mrr", "faithfulness", "key_fact_recall",
                                                 "correct_abstention", "false_abstention")})
        s.add(run)
        s.flush()
        s.add_all(EvalResult(run_id=run.id, **{k: q[k] for k in (
            "question_id", "answerable", "abstained", "hit", "faithfulness", "key_fact_recall", "answer")})
            for q in per_question)
        s.commit()
        return run.id

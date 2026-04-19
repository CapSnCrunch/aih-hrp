from __future__ import annotations

import json
import re
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras


@dataclass
class BenchmarkQuestion:
    id: int
    patient_id: int
    category: str
    num_notes: int
    clinician: str
    question: str
    choices: dict[str, str]  # {'A': ..., 'B': ..., 'C': ..., 'D': ..., 'E': ...}
    answer: str


@dataclass
class QuestionResult:
    question_id: int
    patient_id: int
    category: str
    predicted: str
    correct: str
    is_correct: bool
    raw_response: str


PROMPT_TEMPLATE = """\
You are a clinical reasoning assistant. Answer the following multiple choice \
question using only the patient context provided.

--- PATIENT CONTEXT ---
{context}

--- QUESTION ---
{question}

A) {A}
B) {B}
C) {C}
D) {D}
E) {E}

Respond with only the single letter of the correct answer (A, B, C, D, or E). \
Do not explain your reasoning."""


class BaseHarness(ABC):
    """
    Abstract base for all benchmark harnesses.

    Subclasses must implement `build_context(patient_id)` to supply the patient
    information the model will use when answering each question. Everything else
    — loading questions, calling Ollama, extracting the answer, scoring, and
    saving results — is handled here.
    """

    def __init__(
        self,
        model: str,
        db_config: Optional[dict] = None,
        ollama_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self._conn = psycopg2.connect(**(db_config or _default_db_config()))

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def build_context(self, patient_id: int) -> str:
        """Return a plain-text summary of the patient used as model context."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[QuestionResult]:
        """Run the benchmark and return per-question results."""
        questions = self._load_questions(category=category, limit=limit)
        results = []
        for q in questions:
            context = self.build_context(q.patient_id)
            raw = self._ask_ollama(self._format_prompt(q, context))
            predicted = self._extract_answer(raw)
            results.append(QuestionResult(
                question_id=q.id,
                patient_id=q.patient_id,
                category=q.category,
                predicted=predicted,
                correct=q.answer,
                is_correct=predicted == q.answer,
                raw_response=raw,
            ))
        return results

    def score(self, results: list[QuestionResult]) -> dict:
        """Return accuracy broken down by category and overall."""
        by_category: dict[str, list[bool]] = {}
        for r in results:
            by_category.setdefault(r.category, []).append(r.is_correct)

        breakdown = {
            cat: {
                "correct": sum(hits),
                "total": len(hits),
                "accuracy": sum(hits) / len(hits),
            }
            for cat, hits in by_category.items()
        }
        all_correct = sum(r.is_correct for r in results)
        return {
            "model": self.model,
            "harness": type(self).__name__,
            "total": len(results),
            "correct": all_correct,
            "accuracy": all_correct / len(results) if results else 0.0,
            "by_category": breakdown,
        }

    def save_results(self, results: list[QuestionResult], output_dir: str = "results") -> Path:
        """Write results + score summary to a timestamped JSON file."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out / f"{type(self).__name__}_{self.model.replace(':', '-')}_{ts}.json"
        payload = {
            "summary": self.score(results),
            "results": [asdict(r) for r in results],
        }
        path.write_text(json.dumps(payload, indent=2))
        return path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_questions(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[BenchmarkQuestion]:
        sql = """
            SELECT id, patient_id, category, num_notes, clinician,
                   question, choice_a, choice_b, choice_c, choice_d, choice_e, answer
            FROM ehrqa.questions
            WHERE (%s IS NULL OR category = %s)
            ORDER BY id
        """
        if limit:
            sql += f" LIMIT {int(limit)}"

        with self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, (category, category))
            rows = cur.fetchall()

        return [
            BenchmarkQuestion(
                id=row["id"],
                patient_id=row["patient_id"],
                category=row["category"],
                num_notes=row["num_notes"],
                clinician=row["clinician"],
                question=row["question"],
                choices={
                    "A": row["choice_a"],
                    "B": row["choice_b"],
                    "C": row["choice_c"],
                    "D": row["choice_d"],
                    "E": row["choice_e"],
                },
                answer=row["answer"].strip().upper(),
            )
            for row in rows
        ]

    def _format_prompt(self, q: BenchmarkQuestion, context: str) -> str:
        return PROMPT_TEMPLATE.format(
            context=context,
            question=q.question,
            **q.choices,
        )

    def _ask_ollama(self, prompt: str) -> str:
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }).encode()

        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["response"].strip()

    def _extract_answer(self, response: str) -> str:
        """Pull the first A–E letter from the model response."""
        match = re.search(r"\b([A-E])\b", response.upper())
        return match.group(1) if match else "?"

    def _query(self, sql: str, params=()) -> list[psycopg2.extras.DictRow]:
        with self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def _default_db_config() -> dict:
    return {
        "host": "localhost",
        "port": 5432,
        "user": "mimiciv",
        "password": "mimiciv",
        "dbname": "mimiciv",
    }

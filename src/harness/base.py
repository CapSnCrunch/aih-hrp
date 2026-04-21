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
    full_prompt: str = ""
    started_at: str = ""
    finished_at: str = ""
    wall_time_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_per_sec: float = 0.0
    llm_duration_s: float = 0.0
    sql_queries: list = None
    gather_summary: dict = None
    rag_metadata: dict = None

    def __post_init__(self):
        if self.sql_queries is None:
            self.sql_queries = []
        if self.gather_summary is None:
            self.gather_summary = {}
        if self.rag_metadata is None:
            self.rag_metadata = {}


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
    # Abstract interface — each harness implements this
    # ------------------------------------------------------------------

    @abstractmethod
    def answer_question(self, question: BenchmarkQuestion) -> QuestionResult:
        """Run a single benchmark question and return the result."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        verbose: bool = False,
    ) -> list[QuestionResult]:
        questions = self._load_questions(category=category, limit=limit)
        total = len(questions)
        results = []
        for i, q in enumerate(questions, 1):
            if verbose:
                print(f"\n[{i}/{total}] Q{q.id} patient={q.patient_id}")
                print(f"  Q: {q.question[:100]}")
            result = self.answer_question(q, verbose=verbose)
            results.append(result)
            running_acc = sum(r.is_correct for r in results) / i
            mark = "✓" if result.is_correct else "✗"
            print(
                f"[{i}/{total}] {mark} predicted={result.predicted} correct={result.correct}"
                f" | acc={running_acc:.1%}"
                f" | tokens={result.total_tokens} ({result.tokens_per_sec} tok/s)"
                f" | llm={result.llm_duration_s}s wall={result.wall_time_s}s"
            )
        return results

    def score(self, results: list[QuestionResult]) -> dict:
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
        total_llm_s = sum(r.llm_duration_s for r in results)
        total_wall_s = sum(r.wall_time_s for r in results)
        avg_tok_s = round(sum(r.tokens_per_sec for r in results) / len(results), 1) if results else 0
        return {
            "model": self.model,
            "harness": type(self).__name__,
            "total": len(results),
            "correct": all_correct,
            "accuracy": all_correct / len(results) if results else 0.0,
            "started_at": results[0].started_at if results else None,
            "finished_at": results[-1].finished_at if results else None,
            "by_category": breakdown,
            "token_usage": {
                "total_tokens": sum(r.total_tokens for r in results),
                "total_prompt_tokens": sum(r.prompt_tokens for r in results),
                "total_completion_tokens": sum(r.completion_tokens for r in results),
                "avg_tokens_per_sec": avg_tok_s,
                "total_llm_duration_s": round(total_llm_s, 2),
                "total_wall_time_s": round(total_wall_s, 2),
                "avg_wall_time_per_question_s": round(total_wall_s / len(results), 2) if results else 0,
            },
        }

    def save_results(self, results: list[QuestionResult], output_dir: str = "results") -> Path:
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
    # Shared helpers available to all subclasses
    # ------------------------------------------------------------------

    def _ask_ollama(self, prompt: str) -> tuple[str, dict]:
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
            data = json.loads(resp.read())

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        eval_duration_s = data.get("eval_duration", 0) / 1e9
        tokens_per_sec = completion_tokens / eval_duration_s if eval_duration_s > 0 else 0

        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "tokens_per_sec": round(tokens_per_sec, 1),
            "duration_s": round(data.get("total_duration", 0) / 1e9, 2),
        }
        return data["response"].strip(), usage

    def _extract_answer(self, response: str) -> str:
        match = re.search(r"\b([A-E])\b", response.upper())
        return match.group(1) if match else "?"

    def _format_prompt(self, q: BenchmarkQuestion, context: str) -> str:
        return PROMPT_TEMPLATE.format(
            context=context,
            question=q.question,
            **q.choices,
        )

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

    def _build_context(self, patient_id: int) -> str:
        sections = [
            self._demographics(patient_id),
            self._admissions(patient_id),
            self._diagnoses(patient_id),
            self._procedures(patient_id),
            self._prescriptions(patient_id),
            self._icu_stays(patient_id),
            self._discharge_notes(patient_id),
            self._radiology_notes(patient_id),
        ]
        return "\n\n".join(s for s in sections if s)

    def _demographics(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT gender, anchor_age, anchor_year_group, dod
            FROM mimiciv_hosp.patients
            WHERE subject_id = %s
        """, (patient_id,))
        if not rows:
            return ""
        r = rows[0]
        dod = f", deceased {r['dod']}" if r["dod"] else ""
        return (
            f"DEMOGRAPHICS\n"
            f"Gender: {r['gender']}, Age: {r['anchor_age']}, "
            f"Period: {r['anchor_year_group']}{dod}"
        )

    def _admissions(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT admittime, dischtime, admission_type, admission_location,
                   discharge_location, insurance, race, hospital_expire_flag
            FROM mimiciv_hosp.admissions
            WHERE subject_id = %s
            ORDER BY admittime
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["ADMISSIONS"]
        for r in rows:
            expired = " [expired]" if r["hospital_expire_flag"] else ""
            lines.append(
                f"  {r['admittime'].date()} – {r['dischtime'].date() if r['dischtime'] else '?'}"
                f" | {r['admission_type']} | from {r['admission_location']}"
                f" → {r['discharge_location']}{expired}"
            )
        return "\n".join(lines)

    def _diagnoses(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT d.long_title
            FROM mimiciv_hosp.diagnoses_icd di
            JOIN mimiciv_hosp.d_icd_diagnoses d
              ON d.icd_code = di.icd_code AND d.icd_version = di.icd_version
            WHERE di.subject_id = %s
            ORDER BY di.hadm_id, di.seq_num
            LIMIT 30
        """, (patient_id,))
        if not rows:
            return ""
        return "DIAGNOSES\n" + "\n".join(f"  - {r['long_title']}" for r in rows)

    def _procedures(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT p.chartdate, d.long_title
            FROM mimiciv_hosp.procedures_icd p
            JOIN mimiciv_hosp.d_icd_procedures d
              ON d.icd_code = p.icd_code AND d.icd_version = p.icd_version
            WHERE p.subject_id = %s
            ORDER BY p.chartdate
            LIMIT 20
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["PROCEDURES"]
        for r in rows:
            lines.append(f"  {r['chartdate'] or 'unknown date'}: {r['long_title']}")
        return "\n".join(lines)

    def _prescriptions(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT DISTINCT drug, dose_val_rx, dose_unit_rx, route, starttime
            FROM mimiciv_hosp.prescriptions
            WHERE subject_id = %s AND drug IS NOT NULL
            ORDER BY starttime
            LIMIT 30
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["PRESCRIPTIONS"]
        for r in rows:
            dose = f"{r['dose_val_rx']} {r['dose_unit_rx']}" if r["dose_val_rx"] else ""
            route = f"via {r['route']}" if r["route"] else ""
            lines.append(f"  - {r['drug']} {dose} {route}".strip())
        return "\n".join(lines)

    def _icu_stays(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT first_careunit, last_careunit, intime, outtime, los
            FROM mimiciv_icu.icustays
            WHERE subject_id = %s
            ORDER BY intime
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["ICU STAYS"]
        for r in rows:
            los = f"{r['los']:.1f} days" if r["los"] else "?"
            lines.append(
                f"  {r['intime'].date()} – {r['outtime'].date() if r['outtime'] else '?'}"
                f" | {r['first_careunit']} → {r['last_careunit']} | LOS: {los}"
            )
        return "\n".join(lines)

    def _discharge_notes(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT charttime, note_type, text
            FROM mimiciv_note.discharge
            WHERE subject_id = %s
            ORDER BY charttime
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["DISCHARGE NOTES"]
        for r in rows:
            date = r["charttime"].date() if r["charttime"] else "unknown date"
            lines.append(f"  [{date} | {r['note_type']}]\n{r['text']}")
        return "\n\n".join(lines)

    def _radiology_notes(self, patient_id: int) -> str:
        rows = self._query("""
            SELECT charttime, note_type, text
            FROM mimiciv_note.radiology
            WHERE subject_id = %s
            ORDER BY charttime
        """, (patient_id,))
        if not rows:
            return ""
        lines = ["RADIOLOGY REPORTS"]
        for r in rows:
            date = r["charttime"].date() if r["charttime"] else "unknown date"
            lines.append(f"  [{date} | {r['note_type']}]\n{r['text']}")
        return "\n\n".join(lines)

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

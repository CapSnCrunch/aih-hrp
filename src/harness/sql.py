import re
from datetime import datetime

import psycopg2.extras

from .base import BaseHarness, BenchmarkQuestion, QuestionResult, PROMPT_TEMPLATE

MAX_ITERATIONS = 8
MAX_ROWS = 10
MAX_CELL_CHARS = 500

GATHER_SYSTEM_PROMPT = """\
You are a data retrieval agent with access to a PostgreSQL database containing \
MIMIC-IV patient data. Your ONLY job is to gather relevant data for a clinical \
question by writing SQL queries. Do NOT answer the question — just retrieve data.

## Database schema

mimiciv_hosp.patients         — subject_id, gender, anchor_age, anchor_year_group, dod
mimiciv_hosp.admissions       — subject_id, hadm_id, admittime, dischtime, admission_type, admission_location, discharge_location, insurance, race, hospital_expire_flag
mimiciv_hosp.diagnoses_icd    — subject_id, hadm_id, seq_num, icd_code, icd_version
mimiciv_hosp.d_icd_diagnoses  — icd_code, icd_version, long_title
mimiciv_hosp.procedures_icd   — subject_id, hadm_id, seq_num, chartdate, icd_code, icd_version
mimiciv_hosp.d_icd_procedures — icd_code, icd_version, long_title
mimiciv_hosp.prescriptions    — subject_id, hadm_id, starttime, stoptime, drug, dose_val_rx, dose_unit_rx, route
mimiciv_hosp.transfers        — subject_id, hadm_id, transfer_id, eventtype, careunit, intime, outtime
mimiciv_hosp.services         — subject_id, hadm_id, transfertime, prev_service, curr_service
mimiciv_hosp.microbiologyevents — subject_id, hadm_id, charttime, spec_type_desc, test_name, org_name, interpretation
mimiciv_hosp.omr              — subject_id, chartdate, result_name, result_value
mimiciv_icu.icustays          — subject_id, hadm_id, stay_id, first_careunit, last_careunit, intime, outtime, los
mimiciv_icu.inputevents       — subject_id, hadm_id, stay_id, starttime, itemid, amount, amountuom, rate, rateuom
mimiciv_icu.outputevents      — subject_id, hadm_id, stay_id, charttime, itemid, value, valueuom
mimiciv_icu.datetimeevents    — subject_id, hadm_id, stay_id, charttime, itemid, value
mimiciv_icu.d_items           — itemid, label, category, unitname
mimiciv_note.discharge        — note_id, subject_id, hadm_id, note_type, charttime, text
mimiciv_note.radiology        — note_id, subject_id, hadm_id, note_type, charttime, text

## Rules — follow exactly

1. Each response must be exactly ONE of:

   A query:
   THOUGHT: <what data you need and why>
   SQL: <single plain SELECT statement, no markdown, no semicolons>

   Or when you have gathered enough data:
   DONE

2. Never write OBSERVATION: yourself — the system injects results.
3. No backticks or code fences around SQL.
4. One SELECT per response.
5. SELECT only — no INSERT, UPDATE, DELETE, etc.
6. Always filter by subject_id = {patient_id} unless querying a lookup table \
(d_icd_diagnoses, d_icd_procedures, d_items).
7. Use LIMIT to keep results small.
8. If a query returns (no results), do NOT query that same table again — move on.
9. Write DONE as soon as you have retrieved data from 3 or more successful queries.
"""

GATHER_USER_PROMPT = """\
Patient ID: {patient_id}

Question to gather data for (do NOT answer it — just retrieve relevant data):
{question}

Begin retrieving data now.
"""


class SQLHarness(BaseHarness):
    """
    Two-phase harness: an SQL agent gathers targeted data via a ReAct loop,
    then a clean reasoning call answers the question using the collected data
    as context — the same way NaiveHarness answers.
    """

    def answer_question(self, question: BenchmarkQuestion, verbose: bool = False) -> QuestionResult:
        started_at = datetime.now()
        context, gather_log, gather_usage, queries = self._gather_context(question, verbose=verbose)
        gather_summary = _build_gather_summary(queries)
        answer_prompt = self._format_prompt(question, context)
        raw, answer_usage = self._ask_ollama(answer_prompt)
        finished_at = datetime.now()
        usage = _merge_usage(gather_usage, answer_usage)
        predicted = self._extract_answer(raw)

        return QuestionResult(
            question_id=question.id,
            patient_id=question.patient_id,
            category=question.category,
            predicted=predicted,
            correct=question.answer,
            is_correct=predicted == question.answer,
            raw_response=gather_log + "\n\n--- ANSWER CALL ---\n" + raw,
            full_prompt=answer_prompt,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            wall_time_s=round((finished_at - started_at).total_seconds(), 2),
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            tokens_per_sec=usage["tokens_per_sec"],
            llm_duration_s=usage["duration_s"],
            sql_queries=queries,
            gather_summary=gather_summary,
        )

    def _gather_context(self, question: BenchmarkQuestion, verbose: bool = False) -> tuple[str, str, dict, list]:
        """Run the SQL ReAct loop and return (context_string, log, usage, queries)."""
        system = GATHER_SYSTEM_PROMPT.format(patient_id=question.patient_id)
        user = GATHER_USER_PROMPT.format(
            patient_id=question.patient_id,
            question=question.question,
        )
        conversation = f"{system}\n\n{user}\n"
        observations: list[str] = []
        queries: list[dict] = []
        cumulative_usage = {
            "prompt_tokens": 0, "completion_tokens": 0,
            "total_tokens": 0, "tokens_per_sec": 0.0, "duration_s": 0.0,
        }

        for _ in range(MAX_ITERATIONS):
            raw, usage = self._ask_ollama(conversation)
            _accumulate(cumulative_usage, usage)

            clean_raw = re.sub(
                r"OBSERVATION:.*?(?=THOUGHT:|DONE|SQL:|$)", "",
                raw, flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            conversation += clean_raw + "\n"

            sql_match = re.search(
                r"SQL:\s*(?:```(?:sql)?\s*)?(SELECT.*?)(?:```)?\s*(?=THOUGHT:|DONE|OBSERVATION:|\Z)",
                raw, re.IGNORECASE | re.DOTALL,
            )
            if sql_match:
                sql = re.split(r";", sql_match.group(1).strip())[0].strip()
                result = self._run_sql_safe(sql)
                success = not result.startswith("ERROR") and result != "(no results)"
                queries.append({"sql": sql, "result": result, "success": success})
                observations.append(result)
                conversation += f"\nOBSERVATION:\n{result}\n"
                if verbose:
                    if success:
                        status = "✓"
                    elif result == "(no results)":
                        status = "∅"
                    else:
                        status = "✗"
                    print(f"      {status} SQL: {sql[:120].replace(chr(10), ' ')}")
                    if result.startswith("ERROR"):
                        print(f"         → {result[:120]}")

            if re.search(r"\bDONE\b", raw, re.IGNORECASE):
                break

        cumulative_usage["duration_s"] = round(cumulative_usage["duration_s"], 2)
        context = _observations_to_context(observations)
        return context, conversation, cumulative_usage, queries

    def _run_sql_safe(self, sql: str) -> str:
        if not re.match(r"^\s*SELECT", sql, re.IGNORECASE):
            return "ERROR: Only SELECT statements are allowed."
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("SET LOCAL statement_timeout = '60s'")
                cur.execute(sql)
                rows = cur.fetchall()
            if not rows:
                return "(no results)"
            headers = list(rows[0].keys())
            lines = [", ".join(headers)]
            for row in rows[:MAX_ROWS]:
                cells = []
                for v in row.values():
                    s = str(v)
                    cells.append(s[:MAX_CELL_CHARS] + "..." if len(s) > MAX_CELL_CHARS else s)
                lines.append(", ".join(cells))
            if len(rows) > MAX_ROWS:
                lines.append(f"... ({len(rows) - MAX_ROWS} more rows truncated)")
            return "\n".join(lines)
        except Exception as e:
            self._conn.rollback()
            return f"ERROR: {e}"


def _classify_query(result: str) -> str:
    if result == "(no results)":
        return "no_results"
    if not result.startswith("ERROR"):
        return "success"
    if "column" in result and "does not exist" in result:
        return "column_error"
    if "does not exist" in result:
        return "schema_error"
    if "missing FROM-clause" in result:
        return "join_error"
    if "operator does not exist" in result:
        return "type_error"
    if "syntax error" in result:
        return "syntax_error"
    if "statement timeout" in result:
        return "timeout"
    if "Only SELECT" in result:
        return "not_select"
    return "unknown_error"


def _build_gather_summary(queries: list[dict]) -> dict:
    failure_reasons: dict[str, int] = {}
    successful = errors = no_results = 0
    for q in queries:
        reason = _classify_query(q["result"])
        q["failure_reason"] = reason
        if reason == "success":
            successful += 1
        elif reason == "no_results":
            no_results += 1
        else:
            errors += 1
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
    return {
        "total_queries": len(queries),
        "successful": successful,
        "no_results": no_results,
        "errors": errors,
        "failure_reasons": failure_reasons,
    }


def _observations_to_context(observations: list[str]) -> str:
    successful = [o for o in observations if not o.startswith("ERROR") and o != "(no results)"]
    if not successful:
        return "No data retrieved from the database."
    return "\n\n".join(f"[Query {i+1}]\n{obs}" for i, obs in enumerate(successful))


def _accumulate(cumulative: dict, usage: dict) -> None:
    for k in ("prompt_tokens", "completion_tokens", "total_tokens", "duration_s"):
        cumulative[k] += usage[k]
    cumulative["tokens_per_sec"] = round(
        cumulative["completion_tokens"] / cumulative["duration_s"], 1
    ) if cumulative["duration_s"] > 0 else 0.0


def _merge_usage(a: dict, b: dict) -> dict:
    merged = {k: a[k] + b[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens", "duration_s")}
    merged["duration_s"] = round(merged["duration_s"], 2)
    total_s = merged["duration_s"]
    merged["tokens_per_sec"] = round(merged["completion_tokens"] / total_s, 1) if total_s > 0 else 0.0
    return merged

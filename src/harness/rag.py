import json
import urllib.request
from datetime import datetime

from .base import BaseHarness, BenchmarkQuestion, QuestionResult

EMBED_MODEL = "mxbai-embed-large"
TOP_K = 10


class RAGHarness(BaseHarness):
    """
    Retrieves the top-k most semantically similar note chunks for the patient
    using pgvector cosine similarity, then answers using the same prompt
    pattern as NaiveHarness.
    """

    def answer_question(self, question: BenchmarkQuestion, verbose: bool = False) -> QuestionResult:
        started_at = datetime.now()

        t0 = datetime.now()
        query_vector = self._embed(question.question)
        embed_time_s = round((datetime.now() - t0).total_seconds(), 3)

        t0 = datetime.now()
        context, retrieved_sections, chunks_retrieved = self._retrieve(question.patient_id, query_vector, verbose=verbose)
        retrieve_time_s = round((datetime.now() - t0).total_seconds(), 3)

        prompt = self._format_prompt(question, context)
        raw, usage = self._ask_ollama(prompt)

        finished_at = datetime.now()
        predicted = self._extract_answer(raw)

        return QuestionResult(
            question_id=question.id,
            patient_id=question.patient_id,
            category=question.category,
            predicted=predicted,
            correct=question.answer,
            is_correct=predicted == question.answer,
            raw_response=raw,
            full_prompt=prompt,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            wall_time_s=round((finished_at - started_at).total_seconds(), 2),
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            tokens_per_sec=usage["tokens_per_sec"],
            llm_duration_s=usage["duration_s"],
            rag_metadata={
                "embed_time_s": embed_time_s,
                "retrieve_time_s": retrieve_time_s,
                "chunks_retrieved": chunks_retrieved,
                "retrieved_sections": retrieved_sections,
            },
        )

    def _embed(self, text: str) -> list[float]:
        payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
        req = urllib.request.Request(
            f"{self.ollama_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())["embedding"]

    def _retrieve(self, patient_id: int, query_vector: list[float], verbose: bool = False) -> tuple[str, list[str], int]:
        sql = """
            SELECT section_name, chunk_text
            FROM mimiciv_note.chunks
            WHERE subject_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        rows = self._query(sql, (patient_id, query_vector, TOP_K))

        if not rows:
            return "No relevant notes found for this patient.", [], 0

        chunks = []
        sections = []
        for row in rows:
            header = f"[{row['section_name']}]" if row['section_name'] else "[NOTE]"
            sections.append(row['section_name'] or "NOTE")
            chunks.append(f"{header}\n{row['chunk_text']}")
            if verbose:
                print(f"      Retrieved: {header} ({len(row['chunk_text'])} chars)")

        return "\n\n".join(chunks), sections, len(rows)

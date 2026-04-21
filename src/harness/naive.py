from datetime import datetime

from .base import BaseHarness, BenchmarkQuestion, QuestionResult


class NaiveHarness(BaseHarness):
    """
    Builds context by dumping structured patient records directly into the
    prompt. No retrieval, no tools — the model reasons from raw text alone.
    """

    def answer_question(self, question: BenchmarkQuestion, verbose: bool = False) -> QuestionResult:
        started_at = datetime.now()
        context = self._build_context(question.patient_id)
        prompt = self._format_prompt(question, context)
        raw, usage = self._ask_ollama(prompt)
        finished_at = datetime.now()

        return QuestionResult(
            question_id=question.id,
            patient_id=question.patient_id,
            category=question.category,
            predicted=self._extract_answer(raw),
            correct=question.answer,
            is_correct=self._extract_answer(raw) == question.answer,
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
        )

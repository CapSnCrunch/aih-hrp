from .base import BaseHarness, BenchmarkQuestion, QuestionResult


class CodeAgentHarness(BaseHarness):
    """
    Gives the model the ability to write and execute code (e.g. Python/SQL)
    to query and process patient data before answering the question.
    """

    def answer_question(self, question: BenchmarkQuestion) -> QuestionResult:
        raise NotImplementedError

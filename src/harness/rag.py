from .base import BaseHarness


class RAGHarness(BaseHarness):
    """
    Builds context via embedding-based retrieval over patient clinical notes.
    """

    def build_context(self, patient_id: int) -> str:
        raise NotImplementedError

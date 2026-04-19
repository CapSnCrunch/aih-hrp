from .base import BaseHarness


class SQLHarness(BaseHarness):
    """
    Gives the model access to SQL tools so it can query the DB directly
    rather than receiving pre-built context.
    """

    def build_context(self, patient_id: int) -> str:
        raise NotImplementedError

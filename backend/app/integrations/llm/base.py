"""LLM provider abstraction (CLAUDE.md 1, 2.4).

AI is an analysis layer, not the source of truth: every provider must
return the typed `AIAnalysisResult` contract, never raw free text, so the
backend can validate it before persisting anything.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.schemas import AIAnalysisResult


class LLMError(Exception):
    """A provider failure with a message that is safe to show to end users."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class LLMProvider(ABC):
    @abstractmethod
    def analyse_exam(
        self,
        extracted_text: str,
        total_marks: Optional[float],
        file_bytes: Optional[bytes] = None,
        media_type: Optional[str] = None,
    ) -> AIAnalysisResult:
        """Read the exam (file and/or user-supplied text) and return a validated result."""

    @abstractmethod
    def chat(self, context: str, message: str, history: Optional[list[dict]] = None) -> str:
        """Answer a self-assessment question, grounded in the given context."""

"""Tries several providers in order. If one fails with an LLMError (bad key,
quota, outage, unreadable output) the next one is tried. If all fail, the
LAST error is raised so the user sees a clear message."""
import logging
from typing import Optional

from app.integrations.llm.base import LLMError, LLMProvider
from app.schemas.schemas import AIAnalysisResult

logger = logging.getLogger(__name__)


class FallbackProvider(LLMProvider):
    def __init__(self, providers: list[tuple[str, LLMProvider]]):
        if not providers:
            raise ValueError("FallbackProvider needs at least one provider.")
        self.providers = providers

    def _run(self, method: str, *args, **kwargs):
        last: Optional[LLMError] = None
        for i, (name, provider) in enumerate(self.providers):
            try:
                return getattr(provider, method)(*args, **kwargs)
            except LLMError as exc:
                last = exc
                if i + 1 < len(self.providers):
                    logger.warning("Provider '%s' failed (%s); falling back to '%s'.",
                                   name, exc.user_message, self.providers[i + 1][0])
        assert last is not None
        raise last

    def analyse_exam(self, extracted_text, total_marks, file_bytes=None, media_type=None) -> AIAnalysisResult:
        return self._run("analyse_exam", extracted_text, total_marks, file_bytes, media_type)

    def chat(self, context: str, message: str, history: Optional[list[dict]] = None) -> str:
        return self._run("chat", context, message, history)
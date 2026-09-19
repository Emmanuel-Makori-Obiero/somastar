"""Selects the LLM provider(s) from settings. Call `factory.get_llm_provider()`
(module attribute access) so tests can monkeypatch it.

LLM_PROVIDER may be a single name ("gemini") or a fallback chain
("anthropic,gemini"): providers are tried left to right."""
from functools import lru_cache

from app.config import get_settings
from app.integrations.llm.base import LLMProvider


def _build(name: str, settings) -> LLMProvider:
    if name == "anthropic":
        from app.integrations.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    if name == "gemini":
        from app.integrations.llm.gemini_provider import GeminiProvider
        return GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    from app.integrations.llm.mock_provider import MockLLMProvider
    return MockLLMProvider()


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    chain = settings.provider_chain
    if len(chain) == 1:
        return _build(chain[0], settings)
    from app.integrations.llm.fallback_provider import FallbackProvider
    return FallbackProvider([(name, _build(name, settings)) for name in chain])
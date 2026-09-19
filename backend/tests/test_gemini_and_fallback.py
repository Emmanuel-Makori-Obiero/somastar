from types import SimpleNamespace

import pytest

from app.config import Settings
from app.integrations.llm.base import LLMError
from app.integrations.llm.fallback_provider import FallbackProvider
from app.integrations.llm.gemini_provider import GeminiProvider
from app.integrations.llm.mock_provider import MockLLMProvider
from tests.test_config_and_provider import GOOD, BAD
import json


def _settings(**over):
    s = Settings()
    for k, v in over.items():
        setattr(s, k, v)
    return s


class FakeModels:
    def __init__(self, *texts):
        self.calls, self._texts = [], list(texts)

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self._texts.pop(0))


def _gemini(*payloads):
    p = GeminiProvider.__new__(GeminiProvider)
    p.models = ["test-model"]
    p.model = "test-model"
    p.client = SimpleNamespace(models=FakeModels(*[t if isinstance(t, str) else json.dumps(t) for t in payloads]))
    return p


def test_provider_chain_parsing_and_validation():
    assert _settings(LLM_PROVIDER="anthropic, gemini").provider_chain == ["anthropic", "gemini"]
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        _settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="").validate()
    with pytest.raises(RuntimeError, match="unknown provider"):
        _settings(LLM_PROVIDER="gpt").validate()
    _settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="k").validate()


def test_gemini_parses_json_and_strips_fences():
    p = _gemini("```json\n" + json.dumps(GOOD) + "\n```")
    assert p.analyse_exam("", 10, b"%PDF-1.4 x", "application/pdf").questions[0].topic == "Algebra"


def test_gemini_retries_once_with_validation_feedback():
    p = _gemini(BAD, GOOD)
    assert p.analyse_exam("Q1 | Algebra | 10 | 7", 10).questions[0].student_score == 7
    assert len(p.client.models.calls) == 2


def test_gemini_gives_up_after_two_bad_answers():
    with pytest.raises(LLMError):
        _gemini(BAD, "not json").analyse_exam("Q1 | Algebra | 10 | 7", 10)


class Down(MockLLMProvider):
    def analyse_exam(self, *a, **k):
        raise LLMError("primary down")


def test_fallback_uses_next_provider_when_first_fails():
    fb = FallbackProvider([("anthropic", Down()), ("mock", MockLLMProvider())])
    assert fb.analyse_exam("Q1 | Algebra | 10 | 7", 10).questions


def test_fallback_raises_last_error_when_all_fail():
    fb = FallbackProvider([("a", Down()), ("b", Down())])
    with pytest.raises(LLMError, match="primary down"):
        fb.analyse_exam("Q1 | Algebra | 10 | 7", 10)


# ---- model fallback ----------------------------------------------------

from google.genai import errors as genai_errors


class ScriptedModels:
    """generate_content outcome per model name: an Exception to raise or text to return."""
    def __init__(self, script):
        self.script, self.tried = script, []

    def generate_content(self, model, **kwargs):
        self.tried.append(model)
        outcome = self.script[model]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


def _multi(script):
    p = GeminiProvider.__new__(GeminiProvider)
    p.models = list(script)
    p.model = p.models[0]
    p.client = SimpleNamespace(models=ScriptedModels(script))
    return p


def _overloaded():
    return genai_errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})


def test_model_list_is_parsed_from_comma_separated_setting():
    p = GeminiProvider(api_key="k", model=" a-model , b-model,, c-model ")
    assert p.models == ["a-model", "b-model", "c-model"] and p.model == "a-model"


def test_gemini_falls_back_to_next_model_when_first_overloaded():
    p = _multi({"m1": _overloaded(), "m2": json.dumps(GOOD)})
    assert p.analyse_exam("Q1 | Algebra | 10 | 7", 10).questions
    assert p.client.models.tried == ["m1", "m2"]


def test_gemini_walks_through_many_models():
    missing = genai_errors.ClientError(404, {"error": {"code": 404, "message": "not found", "status": "NOT_FOUND"}})
    limited = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    p = _multi({"m1": _overloaded(), "m2": missing, "m3": limited, "m4": json.dumps(GOOD)})
    assert p.analyse_exam("Q1 | Algebra | 10 | 7", 10).questions
    assert p.client.models.tried == ["m1", "m2", "m3", "m4"]


def test_gemini_bad_key_stops_chain_immediately():
    bad_key = genai_errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid", "status": "INVALID_ARGUMENT"}})
    p = _multi({"m1": bad_key, "m2": json.dumps(GOOD)})
    with pytest.raises(LLMError, match="API key"):
        p.analyse_exam("Q1 | Algebra | 10 | 7", 10)
    assert p.client.models.tried == ["m1"]


def test_gemini_raises_last_error_when_every_model_fails():
    p = _multi({"m1": _overloaded(), "m2": _overloaded()})
    with pytest.raises(LLMError, match="unavailable"):
        p.analyse_exam("Q1 | Algebra | 10 | 7", 10)
    assert p.client.models.tried == ["m1", "m2"]
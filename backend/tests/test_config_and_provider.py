import json
from types import SimpleNamespace

import pytest

from app.config import Settings, DEFAULT_DEV_SECRET
from app.integrations.llm.anthropic_provider import AnthropicProvider
from app.integrations.llm.base import LLMError
from app.services.exam_analysis.service import mark_interrupted_exams


def _settings(**over):
    s = Settings()
    for k, v in over.items():
        setattr(s, k, v)
    return s


def test_production_refuses_default_or_short_jwt_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _settings(ENV="production", JWT_SECRET=DEFAULT_DEV_SECRET).validate()
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _settings(ENV="production", JWT_SECRET="short").validate()
    _settings(ENV="production", JWT_SECRET="x" * 40, CORS_ORIGINS=["https://app.example.com"]).validate()


def test_production_refuses_wildcard_cors():
    with pytest.raises(RuntimeError, match="CORS"):
        _settings(ENV="production", JWT_SECRET="x" * 40, CORS_ORIGINS=["*"]).validate()


def test_anthropic_provider_needs_key():
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        _settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="").validate()


GOOD = {
    "questions": [{"question_number": "1", "topic": "Algebra", "max_marks": 10, "student_score": 7,
                   "correctness": "partially_correct", "difficulty": "medium", "skills": ["Mathematical reasoning"]}],
    "executive_summary": "Solid start.", "strengths": ["Algebra"], "weaknesses": [],
}
BAD = {**GOOD, "questions": [{**GOOD["questions"][0], "student_score": 99}]}  # score > max


class FakeClient:
    def __init__(self, *payloads):
        self.calls = []
        self._payloads = list(payloads)
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self._payloads.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=payload)])


def _provider(*payloads):
    p = AnthropicProvider.__new__(AnthropicProvider)
    p.model = "test-model"
    p.client = FakeClient(*payloads)
    return p


def test_provider_sends_pdf_as_document_and_forces_tool():
    p = _provider(GOOD)
    result = p.analyse_exam("", 10, b"%PDF-1.4 x", "application/pdf")
    assert result.questions[0].topic == "Algebra"
    call = p.client.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "record_exam_analysis"}
    assert call["messages"][0]["content"][0]["type"] == "document"


def test_provider_retries_once_with_validation_feedback():
    p = _provider(BAD, GOOD)
    assert p.analyse_exam("Q1 | Algebra | 10 | 7", 10).questions[0].student_score == 7
    assert len(p.client.calls) == 2
    retry_text = p.client.calls[1]["messages"][0]["content"][-1]["text"]
    assert "failed validation" in retry_text


def test_provider_gives_up_after_two_bad_answers():
    with pytest.raises(LLMError):
        _provider(BAD, BAD).analyse_exam("Q1 | Algebra | 10 | 7", 10)


def test_provider_requires_some_input():
    with pytest.raises(LLMError):
        _provider().analyse_exam("", None)


def test_interrupted_jobs_are_swept_at_startup(client, auth, upload):
    from app.db import SessionLocal
    from app.models.models import Exam, ExamStatus

    exam_id = upload().json()["id"]
    with SessionLocal() as db:
        db.get(Exam, exam_id).status = ExamStatus.analysing_questions
        db.commit()
    assert mark_interrupted_exams() == 1
    detail = client.get(f"/api/exams/{exam_id}", headers=auth).json()
    assert detail["status"] == "failed" and "interrupted" in detail["error_message"]

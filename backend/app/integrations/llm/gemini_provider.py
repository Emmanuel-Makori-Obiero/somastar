"""Gemini provider: Gemini reads the uploaded PDF/image directly (multimodal),
so no separate OCR step is needed.

Structured output uses Gemini's JSON mode with the Pydantic contract as the
response schema, then the result is re-validated locally. One retry is made
with the validation error fed back if the first answer doesn't validate.

Model fallback: GEMINI_MODEL may list several models separated by commas.
They are tried in order; if one is overloaded (503), rate-limited (429),
missing (404) or otherwise fails, the next model is tried. Only an invalid
API key stops the chain immediately (every model would fail the same way).
"""
import json
import logging
from typing import Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import ValidationError

from app.integrations.llm.anthropic_provider import ANALYSIS_SYSTEM, CHAT_SYSTEM, SUPPORTED_MEDIA
from app.integrations.llm.base import LLMError, LLMProvider
from app.schemas.schemas import AIAnalysisResult

logger = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


class _AuthError(LLMError):
    """Bad/forbidden API key: no other model will work either, so stop the chain."""


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        # `model` may be one name or a comma-separated fallback list.
        self.models = [m.strip() for m in (model or "").split(",") if m.strip()]
        if not self.models:
            raise ValueError("GEMINI_MODEL must name at least one model.")
        self.model = self.models[0]
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=180_000,
                # Gemini often returns temporary 503 "overloaded" errors: retry briefly with
                # backoff, then let the model chain move on to the next model.
                retry_options=types.HttpRetryOptions(
                    attempts=3 if len(self.models) == 1 else 2,
                    initial_delay=2.0, max_delay=15.0, exp_base=2.0,
                    http_status_codes=[429, 500, 502, 503, 504],
                ),
            ),
        )

    # ---- exam analysis -------------------------------------------------

    def analyse_exam(self, extracted_text, total_marks, file_bytes=None, media_type=None) -> AIAnalysisResult:
        if not file_bytes and not (extracted_text or "").strip():
            raise LLMError("Please upload the exam paper or paste a question breakdown so it can be analysed.")

        parts: list = []
        if file_bytes:
            if media_type not in SUPPORTED_MEDIA:
                raise LLMError("That file type isn't supported. Upload a PDF, PNG or JPG.")
            parts.append(types.Part.from_bytes(data=file_bytes, mime_type=media_type))

        prompt_parts = ["Analyse this exam and return the structured result."]
        if total_marks:
            prompt_parts.append(f"Total marks for the paper: {total_marks}.")
        if (extracted_text or "").strip():
            prompt_parts.append("Student-supplied question breakdown (one per line, "
                                "'Q | Topic | max_marks | student_score'):\n" + extracted_text.strip())
        base_prompt = "\n\n".join(prompt_parts)

        config = types.GenerateContentConfig(
            system_instruction=ANALYSIS_SYSTEM.replace(
                "by calling the record_exam_analysis tool", "as JSON matching the response schema"),
            response_mime_type="application/json",
            response_schema=AIAnalysisResult,
            max_output_tokens=16000,
            temperature=0.2,
        )

        feedback = ""
        for attempt in range(2):
            text = base_prompt + (f"\n\nYour previous answer failed validation:\n{feedback}\nFix these problems." if feedback else "")
            resp = self._generate(contents=parts + [types.Part.from_text(text=text)], config=config)
            raw = _strip_fences(getattr(resp, "text", None) or "")
            if not raw:
                feedback = "The response was empty."
                continue
            try:
                return AIAnalysisResult.model_validate_json(raw)
            except ValidationError as exc:
                feedback = json.dumps(exc.errors(include_url=False, include_context=False), default=str)[:1500]
                logger.warning("Gemini analysis failed validation (attempt %s): %s", attempt + 1, feedback)

        raise LLMError("The AI couldn't produce a readable analysis for this exam. Try a clearer scan or add a question breakdown.")

    # ---- chat ----------------------------------------------------------

    def chat(self, context: str, message: str, history: Optional[list[dict]] = None) -> str:
        contents: list = []
        for m in (history or [])[-10:]:
            if m.get("role") in {"user", "assistant"} and m.get("content"):
                role = "user" if m["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
        while contents and contents[0].role != "user":
            contents.pop(0)
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

        config = types.GenerateContentConfig(
            system_instruction=f"{CHAT_SYSTEM}\n\nStudent performance summary:\n{context}",
            max_output_tokens=2000,
            temperature=0.5,
        )
        resp = self._generate(contents=contents, config=config)
        text = (getattr(resp, "text", None) or "").strip()
        if not text:
            raise LLMError("The assistant didn't return an answer. Please try again.")
        return text

    # ---- transport -----------------------------------------------------

    def _generate(self, **kwargs):
        """Try each configured model in order; return the first successful response."""
        last: Optional[LLMError] = None
        for i, model in enumerate(self.models):
            try:
                resp = self._generate_with(model, **kwargs)
                if i > 0:
                    logger.info("Gemini answered using fallback model '%s'.", model)
                return resp
            except _AuthError:
                raise
            except LLMError as exc:
                last = exc
                if i + 1 < len(self.models):
                    logger.warning("Gemini model '%s' failed (%s); trying '%s'.",
                                   model, exc.user_message, self.models[i + 1])
        assert last is not None
        raise last

    def _generate_with(self, model: str, **kwargs):
        try:
            return self.client.models.generate_content(model=model, **kwargs)
        except genai_errors.ClientError as exc:
            code = getattr(exc, "code", None)
            msg = str(getattr(exc, "message", "") or exc)
            logger.error("Gemini client error (model %s) %s: %s", model, code, msg)
            low = msg.lower()
            if code in (401, 403) or "api key" in low:
                raise _AuthError("The AI service rejected the Gemini API key. Check GEMINI_API_KEY in backend/.env and restart.") from exc
            if code == 404:
                raise LLMError(f"The Gemini model '{model}' wasn't found. Check GEMINI_MODEL in backend/.env.") from exc
            if code == 429:
                raise LLMError("The Gemini quota or rate limit was reached. Please try again in a minute.") from exc
            raise LLMError("The AI service couldn't process this request. Try a smaller or clearer file.") from exc
        except genai_errors.ServerError as exc:
            logger.error("Gemini server error (model %s): %s", model, exc)
            raise LLMError("The AI service is unavailable right now. Please try again in a moment.") from exc
        except genai_errors.APIError as exc:
            logger.error("Gemini API error (model %s): %s", model, exc)
            raise LLMError("The AI service is unavailable right now. Please try again in a moment.") from exc
        except Exception as exc:  # noqa: BLE001 — network/timeouts from the underlying HTTP client
            logger.error("Could not reach Gemini (model %s): %s", model, exc)
            raise LLMError("Couldn't reach the AI service. Check your internet connection and try again.") from exc
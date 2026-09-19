"""
Mock LLM provider — offline, deterministic, no API key needed.

Parses simple structured input (one line per question:
"Q1 | Topic | max_marks | student_score") when supplied, otherwise derives a
clearly-mock breakdown from total_marks. It never reads the uploaded file.
Use LLM_PROVIDER=anthropic for real extraction.
"""
import re
from typing import Optional

from app.integrations.llm.base import LLMProvider, LLMError
from app.schemas.schemas import AIAnalysisResult, AIQuestionResult

TOPIC_POOL = ["Algebra", "Geometry", "Mechanics", "Organic Chemistry", "Cell Biology",
              "Essay Writing", "Data Interpretation", "Reading Comprehension"]
SKILL_POOL = ["Mathematical reasoning", "Graph reading", "Diagram interpretation",
              "Pattern recognition", "Written explanation", "Experimental reasoning"]


def _correctness(score: float, max_marks: float) -> str:
    if max_marks <= 0:
        return "unanswered"
    ratio = score / max_marks
    if ratio >= 0.95:
        return "correct"
    if ratio <= 0.05:
        return "incorrect"
    return "partially_correct"


class MockLLMProvider(LLMProvider):
    def analyse_exam(self, extracted_text, total_marks, file_bytes=None, media_type=None) -> AIAnalysisResult:
        lines = [l.strip() for l in (extracted_text or "").splitlines() if l.strip()]
        structured_lines = [l for l in lines if re.match(r"^Q?\d+\s*\|", l)]

        questions: list[AIQuestionResult] = []

        if structured_lines:
            for line in structured_lines:
                try:
                    parts = [p.strip() for p in line.split("|")]
                    qnum = parts[0].lstrip("Qq") or str(len(questions) + 1)
                    topic = parts[1] if len(parts) > 1 and parts[1] else "General"
                    max_marks = float(parts[2]) if len(parts) > 2 and parts[2] else 5.0
                    score = float(parts[3]) if len(parts) > 3 and parts[3] else None
                    skills = [s.strip() for s in parts[4].split(",") if s.strip()] if len(parts) > 4 and parts[4] else \
                        [SKILL_POOL[len(questions) % len(SKILL_POOL)]]
                    questions.append(AIQuestionResult(
                        question_number=qnum,
                        topic=topic,
                        max_marks=max_marks,
                        student_score=score,
                        error_type=None if score is None or score >= max_marks else "conceptual_error",
                        correctness=_correctness(score, max_marks) if score is not None else "unanswered",
                        difficulty=["easy", "medium", "hard"][len(questions) % 3],
                        skills=skills,
                    ))
                except ValueError as exc:  # bad number or score > max_marks
                    raise LLMError(
                        f"Couldn't read this line of your breakdown: \"{line}\". "
                        "Use the format: Q1 | Topic | max_marks | your_score (score can't exceed max marks)."
                    ) from exc
        else:
            marks_left = total_marks or 40.0
            n = max(4, min(10, int(marks_left // 5) or 4))
            per_q = round(marks_left / n, 1)
            for i in range(1, n + 1):
                score = round(per_q * (0.4 + 0.6 * ((i * 37) % 10) / 10), 1)
                score = min(score, per_q)
                questions.append(AIQuestionResult(
                    question_number=str(i),
                    topic=TOPIC_POOL[i % len(TOPIC_POOL)],
                    max_marks=per_q,
                    student_score=score,
                    error_type=None if score >= per_q * 0.9 else "conceptual_error",
                    correctness=_correctness(score, per_q),
                    difficulty=["easy", "medium", "hard"][i % 3],
                    skills=[SKILL_POOL[i % len(SKILL_POOL)]],
                ))

        if not questions:
            raise LLMError("No questions could be derived from this exam.")

        scored = [q for q in questions if q.student_score is not None]
        earned = sum(q.student_score for q in scored)
        max_total = sum(q.max_marks for q in scored) or 1
        pct = round(earned / max_total * 100, 1)

        strengths = sorted({q.topic for q in scored if q.max_marks and q.student_score / q.max_marks >= 0.75})
        weaknesses = sorted({q.topic for q in scored if q.max_marks and q.student_score / q.max_marks < 0.5})

        summary = (
            f"Scored {pct}% overall across {len(questions)} questions. "
            f"Strongest in {', '.join(strengths) if strengths else 'no single area yet'}; "
            f"needs attention in {', '.join(weaknesses) if weaknesses else 'no major gaps found'}. "
            "(Mock analysis — set LLM_PROVIDER=anthropic for real extraction.)"
        )

        return AIAnalysisResult(
            questions=questions,
            executive_summary=summary,
            strengths=strengths or ["Consistent attempt across most questions"],
            weaknesses=weaknesses or ["No significant weaknesses detected in this paper"],
        )

    def chat(self, context: str, message: str, history: Optional[list[dict]] = None) -> str:
        return (
            f"Here's where you stand: {context[:400]}\n\nRegarding \"{message}\" — keep reviewing your "
            "weaker topics and revisit flagged items in Revision. (Mock assistant — set "
            "LLM_PROVIDER=anthropic for grounded, conversational answers.)"
        )

"""Runs exam analysis end to end: read file -> AI analyse -> validate -> persist.

Runs as a background job (see routes/exams.py). Progress is real: the exam's
`status` moves through the pipeline and the frontend polls it. Any failure is
caught, logged, and turned into status=failed plus a user-safe error_message —
an exam can never be left stuck mid-pipeline (interrupted jobs are also swept
at startup by `mark_interrupted_exams`).

Per CLAUDE.md 2.4, AI output is a typed object before it ever reaches storage;
the providers validate it, and this module is the only place that persists it.
"""
import json
import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

import app.db as db_module
from app.core.clock import utcnow
from app.integrations.llm import factory
from app.integrations.llm.base import LLMError, LLMProvider
from app.integrations.storage.local import get_storage
from app.models.models import (
    Exam, ExamQuestion, ExamAnalysis, ExamStatus, Correctness, IN_PROGRESS_STATUSES,
    Skill, SkillEvidence, PerformanceSnapshot, RevisionItem,
)
from app.services.uploads import media_type_for_reference

logger = logging.getLogger(__name__)

REVISION_THRESHOLD = 0.6  # questions scored below 60% become revision items
MAX_REVISION_PER_EXAM = 8
GENERIC_ERROR = "Analysis failed. Please try again."


def normalise_skill_name(name: str) -> str:
    """Collapse whitespace and capitalise the first letter so 'graph  reading'
    and 'Graph reading' are one skill."""
    cleaned = " ".join((name or "").split())
    return cleaned[:1].upper() + cleaned[1:]


def _get_or_create_skill(db: Session, name: str) -> Skill:
    norm = normalise_skill_name(name)
    skill = db.query(Skill).filter(func.lower(Skill.name) == norm.lower()).first()
    if not skill:
        skill = Skill(name=norm, category="demonstrated")
        db.add(skill)
        db.flush()
    return skill


def delete_exam_derived(db: Session, exam_id: str) -> None:
    """Remove everything analysis produced for an exam (used by re-analyse and delete).
    Order matters: rows that reference questions go first."""
    db.query(SkillEvidence).filter(SkillEvidence.exam_id == exam_id).delete(synchronize_session=False)
    db.query(RevisionItem).filter(RevisionItem.source_exam_id == exam_id).delete(synchronize_session=False)
    db.query(PerformanceSnapshot).filter(PerformanceSnapshot.exam_id == exam_id).delete(synchronize_session=False)
    db.query(ExamAnalysis).filter(ExamAnalysis.exam_id == exam_id).delete(synchronize_session=False)
    db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).delete(synchronize_session=False)
    db.flush()


def _set_status(db: Session, exam: Exam, status: ExamStatus) -> None:
    exam.status = status
    db.commit()


def _run(db: Session, exam: Exam, provider: LLMProvider) -> None:
    file_bytes: Optional[bytes] = None
    media_type: Optional[str] = None

    _set_status(db, exam, ExamStatus.extracting)
    if exam.file_reference:
        file_bytes = get_storage().read(exam.file_reference)
        media_type = media_type_for_reference(exam.file_reference)

    _set_status(db, exam, ExamStatus.analysing_questions)
    result = provider.analyse_exam(exam.source_text or "", exam.total_marks, file_bytes, media_type)

    _set_status(db, exam, ExamStatus.generating_skills)
    delete_exam_derived(db, exam.id)
    db.expire_all()
    exam = db.get(Exam, exam.id)

    total_earned = 0.0
    total_scored_max = 0.0
    total_max = 0.0
    revision_candidates: list[tuple[ExamQuestion, Optional[str]]] = []

    for order, q in enumerate(result.questions):
        correctness = Correctness(q.correctness) if q.correctness in Correctness._value2member_map_ else None
        row = ExamQuestion(
            exam_id=exam.id,
            created_order=order,
            question_number=q.question_number,
            question_text=q.question_text,
            max_marks=q.max_marks,
            student_score=q.student_score,
            topic=q.topic,
            difficulty=q.difficulty,
            error_type=q.error_type,
            correctness=correctness,
        )
        db.add(row)
        db.flush()  # need row.id for evidence

        total_max += q.max_marks
        if q.student_score is not None:
            total_earned += q.student_score
            total_scored_max += q.max_marks
            if q.max_marks > 0 and q.student_score / q.max_marks < REVISION_THRESHOLD:
                revision_candidates.append((row, q.explanation))

        confidence = None
        if q.student_score is not None and q.max_marks > 0:
            confidence = round(q.student_score / q.max_marks, 2)

        seen: set[str] = set()
        for skill_name in q.skills:
            norm = normalise_skill_name(skill_name)
            if not norm or norm.lower() in seen:
                continue
            seen.add(norm.lower())
            skill = _get_or_create_skill(db, norm)
            db.add(SkillEvidence(
                user_id=exam.user_id,
                skill_id=skill.id,
                exam_id=exam.id,
                question_id=row.id,
                evidence_type="question_performance",
                confidence=confidence,
                score=q.student_score,
                explanation=f"Demonstrated on Q{q.question_number} ({q.topic})",
            ))

    _set_status(db, exam, ExamStatus.aggregating)

    # Percentage only over questions whose score is actually known.
    pct = round(total_earned / total_scored_max * 100, 1) if total_scored_max else None
    exam.total_marks = exam.total_marks or total_max or None

    db.add(ExamAnalysis(
        exam_id=exam.id,
        percentage_score=pct,
        executive_summary=result.executive_summary,
        overall_strengths=json.dumps(result.strengths),
        overall_weaknesses=json.dumps(result.weaknesses),
    ))

    if pct is not None:
        db.add(PerformanceSnapshot(
            user_id=exam.user_id,
            subject_id=exam.subject_id,
            exam_id=exam.id,
            score_percentage=pct,
            exam_date=exam.exam_date or exam.created_at or utcnow(),
        ))

    # Revision items: weakest first, capped.
    revision_candidates.sort(key=lambda rc: (rc[0].student_score or 0) / (rc[0].max_marks or 1))
    for row, explanation in revision_candidates[:MAX_REVISION_PER_EXAM]:
        db.add(RevisionItem(
            user_id=exam.user_id,
            source_exam_id=exam.id,
            source_question_id=row.id,
            topic=row.topic,
            question_text=row.question_text or f"Q{row.question_number}: revisit {row.topic or 'this topic'}",
            explanation=explanation or (
                f"You scored {row.student_score:g}/{row.max_marks:g} here"
                + (f" ({row.error_type.replace('_', ' ')})." if row.error_type else ".")
            ),
            difficulty=row.difficulty,
            status="pending",
        ))

    exam.error_message = None
    exam.status = ExamStatus.completed
    db.commit()


def process_exam(exam_id: str) -> None:
    """Background entry point. Owns its own DB session (the request's is closed by then)."""
    db = db_module.SessionLocal()
    try:
        exam = db.get(Exam, exam_id)
        if exam is None:
            return
        try:
            _run(db, exam, factory.get_llm_provider())
        except Exception as exc:  # noqa: BLE001 — anything must end in a clean failed state
            db.rollback()
            if isinstance(exc, LLMError):
                message = exc.user_message
                logger.warning("Exam %s analysis failed: %s", exam_id, message)
            else:
                message = GENERIC_ERROR
                logger.exception("Exam %s analysis crashed", exam_id)
            exam = db.get(Exam, exam_id)
            if exam is not None:
                exam.status = ExamStatus.failed
                exam.error_message = message
                db.commit()
    finally:
        db.close()


def mark_interrupted_exams() -> int:
    """Startup sweep: a job that was running when the server stopped will never finish."""
    db = db_module.SessionLocal()
    try:
        stuck = db.query(Exam).filter(Exam.status.in_(list(IN_PROGRESS_STATUSES))).all()
        for exam in stuck:
            exam.status = ExamStatus.failed
            exam.error_message = "Analysis was interrupted. Please retry."
        db.commit()
        return len(stuck)
    finally:
        db.close()

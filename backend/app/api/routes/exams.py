import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user
from app.config import get_settings
from app.core.errors import api_error
from app.db import get_db
from app.integrations.storage.local import get_storage
from app.models.models import User, Exam, Subject, ExamStatus, IN_PROGRESS_STATUSES
from app.schemas.schemas import ExamOut, ExamDetailOut, ExamAnalysisOut, ExamQuestionOut
from app.services.exam_analysis.service import process_exam, delete_exam_derived
from app.services.uploads import read_validated_upload, EXTENSION_FOR

router = APIRouter(prefix="/api/exams", tags=["exams"])


def _get_or_create_subject(db: Session, name: str) -> Subject:
    name = " ".join(name.split())
    subject = db.query(Subject).filter(func.lower(Subject.name) == name.lower()).first()
    if not subject:
        subject = Subject(name=name)
        db.add(subject)
        db.flush()
    return subject


def _owned_exam(db: Session, exam_id: str, user: User) -> Exam:
    exam = db.query(Exam).filter(Exam.id == exam_id, Exam.user_id == user.id).first()
    if not exam:
        raise api_error(404, "EXAM_NOT_FOUND", "Exam not found.")
    return exam


def _to_out(exam: Exam) -> ExamOut:
    out = ExamOut.model_validate(exam)
    out.status = exam.status.value
    out.percentage_score = exam.analysis.percentage_score if exam.analysis else None
    return out


@router.post("", response_model=ExamOut, status_code=202)
async def upload_exam(
    background: BackgroundTasks,
    title: str = Form(..., min_length=1, max_length=200),
    subject_name: str = Form(..., min_length=1, max_length=100),
    exam_round: str | None = Form(None, max_length=100),
    total_marks: float | None = Form(None, gt=0),
    extracted_text: str | None = Form(None, max_length=20000),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accepts the exam and returns immediately (202). Analysis runs in the
    background; poll GET /api/exams/{id} for status and results."""
    if file is None and not (extracted_text or "").strip():
        raise api_error(400, "NOTHING_TO_ANALYSE", "Upload the exam paper or paste a question breakdown.")

    file_reference = None
    if file is not None:
        max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
        content, media_type = await read_validated_upload(file, max_bytes)
        file_reference = get_storage().save(f"upload{EXTENSION_FOR[media_type]}", content)

    subject = _get_or_create_subject(db, subject_name)
    exam = Exam(
        user_id=current_user.id,
        subject_id=subject.id,
        title=title.strip(),
        exam_round=(exam_round or "").strip() or None,
        total_marks=total_marks,
        file_reference=file_reference,
        source_text=(extracted_text or "").strip() or None,
        status=ExamStatus.queued,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    background.add_task(process_exam, exam.id)
    return _to_out(exam)


@router.get("", response_model=list[ExamOut])
def list_exams(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exams = (
        db.query(Exam)
        .options(selectinload(Exam.analysis))
        .filter(Exam.user_id == current_user.id)
        .order_by(Exam.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [_to_out(e) for e in exams]


@router.get("/{exam_id}", response_model=ExamDetailOut)
def get_exam(exam_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exam = _owned_exam(db, exam_id, current_user)

    analysis_out = None
    if exam.analysis:
        analysis_out = ExamAnalysisOut(
            percentage_score=exam.analysis.percentage_score,
            executive_summary=exam.analysis.executive_summary,
            overall_strengths=json.loads(exam.analysis.overall_strengths or "[]"),
            overall_weaknesses=json.loads(exam.analysis.overall_weaknesses or "[]"),
        )

    base = _to_out(exam)
    return ExamDetailOut(
        **base.model_dump(),
        questions=[ExamQuestionOut.model_validate(q) for q in exam.questions],
        analysis=analysis_out,
    )


@router.post("/{exam_id}/reanalyze", response_model=ExamOut, status_code=202)
def reanalyze_exam(
    exam_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exam = _owned_exam(db, exam_id, current_user)
    if exam.status in IN_PROGRESS_STATUSES:
        raise api_error(409, "ALREADY_RUNNING", "This exam is already being analysed.")
    exam.status = ExamStatus.queued
    exam.error_message = None
    db.commit()
    db.refresh(exam)
    background.add_task(process_exam, exam.id)
    return _to_out(exam)


@router.delete("/{exam_id}", status_code=204)
def delete_exam(exam_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exam = _owned_exam(db, exam_id, current_user)
    if exam.status in IN_PROGRESS_STATUSES:
        raise api_error(409, "ALREADY_RUNNING", "Wait for the analysis to finish before deleting this exam.")

    file_reference = exam.file_reference
    delete_exam_derived(db, exam.id)
    db.expire_all()
    exam = _owned_exam(db, exam_id, current_user)
    db.delete(exam)
    db.commit()

    if file_reference:
        get_storage().delete(file_reference)
    return Response(status_code=204)

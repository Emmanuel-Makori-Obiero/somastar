from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.clock import utcnow
from app.core.errors import api_error
from app.db import get_db
from app.models.models import User, RevisionItem, Exam
from app.schemas.schemas import RevisionItemOut, RevisionItemUpdate

router = APIRouter(prefix="/api/revision", tags=["revision"])

# Simple spaced-repetition schedule; swap for a real algorithm later.
NEXT_REVIEW = {"pending": None, "reviewed": timedelta(days=3), "mastered": timedelta(days=30)}


def _out(item: RevisionItem, exam_title: str) -> RevisionItemOut:
    return RevisionItemOut(
        id=item.id,
        source_exam_id=item.source_exam_id,
        exam_title=exam_title,
        topic=item.topic,
        question_text=item.question_text,
        explanation=item.explanation,
        difficulty=item.difficulty,
        status=item.status,
        next_review_at=item.next_review_at,
    )


@router.get("", response_model=list[RevisionItemOut])
def list_revision_items(
    status: Optional[str] = Query(None, pattern="^(pending|reviewed|mastered)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(RevisionItem, Exam.title)
        .join(Exam, Exam.id == RevisionItem.source_exam_id)
        .filter(RevisionItem.user_id == current_user.id)
    )
    if status:
        q = q.filter(RevisionItem.status == status)
    rows = q.order_by(RevisionItem.created_at.desc()).limit(limit).offset(offset).all()
    return [_out(item, title) for item, title in rows]


@router.patch("/{item_id}", response_model=RevisionItemOut)
def update_revision_item(
    item_id: str,
    payload: RevisionItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(RevisionItem, Exam.title)
        .join(Exam, Exam.id == RevisionItem.source_exam_id)
        .filter(RevisionItem.id == item_id, RevisionItem.user_id == current_user.id)
        .first()
    )
    if not row:
        raise api_error(404, "REVISION_ITEM_NOT_FOUND", "Revision item not found.")
    item, title = row
    item.status = payload.status
    delta = NEXT_REVIEW[payload.status]
    item.next_review_at = utcnow() + delta if delta else None
    db.commit()
    db.refresh(item)
    return _out(item, title)

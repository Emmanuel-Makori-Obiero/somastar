from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.errors import api_error
from app.db import get_db
from app.integrations.llm import factory
from app.integrations.llm.base import LLMError
from app.models.models import User, AIConversation, AIMessage
from app.schemas.schemas import SelfAssessmentOut, AIChatMessageIn, AIChatMessageOut
from app.services.assessment.service import build_self_assessment

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.get("", response_model=SelfAssessmentOut)
def get_self_assessment(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return build_self_assessment(db, current_user.id)


@router.post("/chat", response_model=AIChatMessageOut)
def chat_with_assistant(
    payload: AIChatMessageIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convo = db.query(AIConversation).filter(AIConversation.user_id == current_user.id).first()
    if not convo:
        convo = AIConversation(user_id=current_user.id)
        db.add(convo)
        db.flush()

    history = [{"role": m.role, "content": m.content} for m in convo.messages[-10:]]

    assessment = build_self_assessment(db, current_user.id)
    context = (
        f"Overall average: {assessment.overall_average}%. Exams analysed: {assessment.exams_analysed}. "
        f"Strengths: {', '.join(s.skill for s in assessment.strengths) or 'none yet'}. "
        f"Weaknesses: {', '.join(w.skill for w in assessment.weaknesses) or 'none yet'}."
    )

    # Get the reply first so a provider failure doesn't leave an orphaned user message.
    try:
        reply = factory.get_llm_provider().chat(context, payload.message, history)
    except LLMError as exc:
        db.rollback()
        raise api_error(503, "ASSISTANT_UNAVAILABLE", exc.user_message)

    db.add(AIMessage(conversation_id=convo.id, role="user", content=payload.message))
    msg = AIMessage(conversation_id=convo.id, role="assistant", content=reply)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg

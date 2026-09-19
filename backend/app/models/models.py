"""
Core data model, per CLAUDE.md section 6.

P0 entities (User, Subject, Exam, ExamQuestion, ExamAnalysis, Skill,
SkillEvidence, PerformanceSnapshot), RevisionItem for P1, and
AIConversation/AIMessage for the self-assessment assistant.
"""
import enum
import uuid

from sqlalchemy import (
    Column, String, Float, ForeignKey, DateTime, Text, Enum
)
from sqlalchemy.orm import relationship

from app.core.clock import utcnow
from app.db import Base


def gen_id() -> str:
    return str(uuid.uuid4())


class ExamStatus(str, enum.Enum):
    uploaded = "uploaded"
    queued = "queued"
    extracting = "extracting"
    analysing_questions = "analysing_questions"
    generating_skills = "generating_skills"
    aggregating = "aggregating"
    completed = "completed"
    failed = "failed"


IN_PROGRESS_STATUSES = {
    ExamStatus.queued,
    ExamStatus.extracting,
    ExamStatus.analysing_questions,
    ExamStatus.generating_skills,
    ExamStatus.aggregating,
}


class Correctness(str, enum.Enum):
    correct = "correct"
    partially_correct = "partially_correct"
    incorrect = "incorrect"
    unanswered = "unanswered"


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    exams = relationship("Exam", back_populates="user")


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    description = Column(String, nullable=True)


class Exam(Base):
    __tablename__ = "exams"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    title = Column(String, nullable=False)
    exam_round = Column(String, nullable=True)
    exam_date = Column(DateTime, nullable=True)
    total_marks = Column(Float, nullable=True)
    file_reference = Column(String, nullable=True)
    source_text = Column(Text, nullable=True)  # optional user-supplied question breakdown
    status = Column(Enum(ExamStatus), default=ExamStatus.uploaded, nullable=False)
    error_message = Column(Text, nullable=True)  # user-safe reason when status == failed
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="exams")
    subject = relationship("Subject")
    questions = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan",
                             order_by="ExamQuestion.created_order")
    analysis = relationship("ExamAnalysis", back_populates="exam", uselist=False, cascade="all, delete-orphan")


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    id = Column(String, primary_key=True, default=gen_id)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False, index=True)
    created_order = Column(Float, nullable=False, default=0)  # preserves paper order
    question_number = Column(String, nullable=False)
    question_text = Column(Text, nullable=True)
    max_marks = Column(Float, nullable=False)
    student_score = Column(Float, nullable=True)  # null = unavailable, never fabricated
    topic = Column(String, nullable=True)
    subtopic = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)  # easy | medium | hard
    error_type = Column(String, nullable=True)
    correctness = Column(Enum(Correctness), nullable=True)
    question_type = Column(String, nullable=True)
    source_reference = Column(String, nullable=True)

    exam = relationship("Exam", back_populates="questions")


class ExamAnalysis(Base):
    __tablename__ = "exam_analyses"
    id = Column(String, primary_key=True, default=gen_id)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False, unique=True)
    percentage_score = Column(Float, nullable=True)
    executive_summary = Column(Text, nullable=True)
    overall_strengths = Column(Text, nullable=True)  # JSON-encoded list
    overall_weaknesses = Column(Text, nullable=True)  # JSON-encoded list
    analysis_version = Column(String, default="v1")
    created_at = Column(DateTime, default=utcnow)

    exam = relationship("Exam", back_populates="analysis")


class Skill(Base):
    __tablename__ = "skills"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=True)
    description = Column(String, nullable=True)


class SkillEvidence(Base):
    __tablename__ = "skill_evidence"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    skill_id = Column(String, ForeignKey("skills.id"), nullable=False)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False, index=True)
    question_id = Column(String, ForeignKey("exam_questions.id"), nullable=True)
    evidence_type = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    score = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    skill = relationship("Skill")


class RevisionItem(Base):
    __tablename__ = "revision_items"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    source_exam_id = Column(String, ForeignKey("exams.id"), nullable=False, index=True)
    source_question_id = Column(String, ForeignKey("exam_questions.id"), nullable=True)
    topic = Column(String, nullable=True)
    question_text = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    difficulty = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending | reviewed | mastered
    next_review_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False)
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False, index=True)
    score_percentage = Column(Float, nullable=False)
    exam_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    messages = relationship("AIMessage", back_populates="conversation", cascade="all, delete-orphan",
                            order_by="AIMessage.created_at")


class AIMessage(Base):
    __tablename__ = "ai_messages"
    id = Column(String, primary_key=True, default=gen_id)
    conversation_id = Column(String, ForeignKey("ai_conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    conversation = relationship("AIConversation", back_populates="messages")

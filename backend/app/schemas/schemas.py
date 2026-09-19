"""Typed API contracts. AI output is validated into these before storage/display
(CLAUDE.md 2.4) — never stored as raw text."""
import re
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator, model_validator


# --- Auth ---

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt ignores bytes past 72

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty.")
        return v

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Password must include at least one letter and one number.")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Exams ---

class ExamQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    question_number: str
    question_text: Optional[str] = None
    max_marks: float
    student_score: Optional[float] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    difficulty: Optional[str] = None
    error_type: Optional[str] = None
    correctness: Optional[str] = None
    question_type: Optional[str] = None


class ExamAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    percentage_score: Optional[float] = None
    executive_summary: Optional[str] = None
    overall_strengths: List[str] = []
    overall_weaknesses: List[str] = []


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    exam_round: Optional[str] = None
    exam_date: Optional[datetime] = None
    total_marks: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    percentage_score: Optional[float] = None


class ExamDetailOut(ExamOut):
    questions: List[ExamQuestionOut] = []
    analysis: Optional[ExamAnalysisOut] = None


# --- AI structured analysis contract (what the LLM layer must produce) ---

DifficultyLit = Literal["easy", "medium", "hard"]
CorrectnessLit = Literal["correct", "partially_correct", "incorrect", "unanswered"]


class AIQuestionResult(BaseModel):
    question_number: str = Field(min_length=1, max_length=20, description="Question label as printed, e.g. '1', '2a'.")
    question_text: Optional[str] = Field(default=None, description="Short paraphrase of what was asked, if readable.")
    topic: str = Field(min_length=1, max_length=120)
    max_marks: float = Field(ge=0, description="Marks available for this question.")
    student_score: Optional[float] = Field(
        default=None, ge=0,
        description="Marks the student earned. null if it cannot be read — never guess.",
    )
    error_type: Optional[str] = Field(default=None, description="e.g. conceptual_error, calculation_error, incomplete_answer. null if fully correct.")
    correctness: CorrectnessLit
    difficulty: DifficultyLit
    skills: List[str] = Field(default_factory=list, description="1-3 short skill names demonstrated or tested, e.g. 'Mathematical reasoning'.")
    explanation: Optional[str] = Field(default=None, description="One or two sentences on what went wrong and how to fix it. null if fully correct.")

    @model_validator(mode="after")
    def _score_within_max(self):
        if self.student_score is not None and self.student_score > self.max_marks:
            raise ValueError(f"Question {self.question_number}: student_score {self.student_score} exceeds max_marks {self.max_marks}.")
        return self


class AIAnalysisResult(BaseModel):
    questions: List[AIQuestionResult] = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    strengths: List[str]
    weaknesses: List[str]


# --- Self assessment ---

class SkillProfileItem(BaseModel):
    skill: str
    category: Optional[str] = None
    average_score: float
    evidence_count: int


class TrendPoint(BaseModel):
    exam_id: str
    exam_title: str
    subject: str
    exam_date: Optional[datetime] = None
    percentage: float


class SelfAssessmentOut(BaseModel):
    overall_average: Optional[float] = None
    exams_analysed: int
    strengths: List[SkillProfileItem]
    weaknesses: List[SkillProfileItem]
    profile: List[SkillProfileItem] = []  # every skill with evidence, best first
    trend: List[TrendPoint]
    career_suggestions: List[str]


class AIChatMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AIChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role: str
    content: str
    created_at: datetime


# --- Revision ---

class RevisionItemOut(BaseModel):
    id: str
    source_exam_id: str
    exam_title: str
    topic: Optional[str] = None
    question_text: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None
    status: str
    next_review_at: Optional[datetime] = None


class RevisionItemUpdate(BaseModel):
    status: Literal["pending", "reviewed", "mastered"]

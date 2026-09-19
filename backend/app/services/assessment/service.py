"""Aggregates intelligence from previous exam analyses (CLAUDE.md 1.2).

Uses joined queries (no per-row lookups) so cost stays flat as history grows.
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.models import PerformanceSnapshot, SkillEvidence, Skill, Exam, Subject
from app.schemas.schemas import SelfAssessmentOut, SkillProfileItem, TrendPoint

# Keys are lower-case; lookups are case-insensitive.
CAREER_MAP = {
    "mathematical reasoning": ["Engineering", "Data Science", "Actuarial Science"],
    "diagram interpretation": ["Architecture", "Engineering", "Medicine"],
    "graph reading": ["Economics", "Data Science", "Statistics"],
    "written explanation": ["Law", "Journalism", "Education"],
    "experimental reasoning": ["Medicine", "Biomedical Research", "Pharmacy"],
    "pattern recognition": ["Computer Science", "Software Engineering"],
}

STRENGTH_MIN = 70.0
WEAKNESS_MAX = 50.0


def build_self_assessment(db: Session, user_id: str) -> SelfAssessmentOut:
    trend_rows = (
        db.query(PerformanceSnapshot, Exam.title, Subject.name)
        .join(Exam, Exam.id == PerformanceSnapshot.exam_id)
        .join(Subject, Subject.id == PerformanceSnapshot.subject_id)
        .filter(PerformanceSnapshot.user_id == user_id)
        .order_by(PerformanceSnapshot.exam_date.asc())
        .all()
    )
    trend = [
        TrendPoint(
            exam_id=snap.exam_id,
            exam_title=title,
            subject=subject_name,
            exam_date=snap.exam_date,
            percentage=snap.score_percentage,
        )
        for snap, title, subject_name in trend_rows
    ]
    overall_avg = round(sum(t.percentage for t in trend) / len(trend), 1) if trend else None

    evidence_rows = (
        db.query(Skill.id, Skill.name, Skill.category, SkillEvidence.confidence)
        .join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
        .filter(SkillEvidence.user_id == user_id)
        .all()
    )
    by_skill: dict[str, dict] = defaultdict(lambda: {"name": "", "category": None, "scores": [], "count": 0})
    for skill_id, name, category, confidence in evidence_rows:
        entry = by_skill[skill_id]
        entry["name"], entry["category"] = name, category
        entry["count"] += 1
        if confidence is not None:
            entry["scores"].append(confidence)

    profile: list[SkillProfileItem] = []
    for entry in by_skill.values():
        if not entry["scores"]:
            continue
        profile.append(SkillProfileItem(
            skill=entry["name"],
            category=entry["category"],
            average_score=round(sum(entry["scores"]) / len(entry["scores"]) * 100, 1),
            evidence_count=entry["count"],
        ))
    profile.sort(key=lambda p: p.average_score, reverse=True)

    strengths = [p for p in profile if p.average_score >= STRENGTH_MIN][:5]
    weaknesses = sorted([p for p in profile if p.average_score < WEAKNESS_MAX], key=lambda p: p.average_score)[:5]

    careers: set[str] = set()
    for s in strengths:
        careers.update(CAREER_MAP.get(s.skill.lower(), []))

    return SelfAssessmentOut(
        overall_average=overall_avg,
        exams_analysed=len(trend),
        strengths=strengths,
        weaknesses=weaknesses,
        profile=profile,
        trend=trend,
        career_suggestions=sorted(careers) or ["Analyse more exams to unlock career suggestions"],
    )

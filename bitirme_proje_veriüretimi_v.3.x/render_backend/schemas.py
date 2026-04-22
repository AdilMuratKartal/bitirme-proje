"""
render_backend/schemas.py — Pydantic Response Modelleri

Her frontend sayfasına karşılık gelen JSON şemaları.
Bu modeller api.py response_model parametresinde kullanılır.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────
# GRADES PAGE
# ─────────────────────────────────────────────────────────────────

class OngoingCourseGrade(BaseModel):
    course_id: int
    course_name: str
    current_grade: Optional[float]           # mdl_grade_grades'den gerçek not
    risk_score: Optional[float]              # MIMO çıktısı (0.0–1.0)
    risk_level: Optional[str]               # "high" / "medium" / "low"
    predicted_grade: Optional[float]         # MIMO tahmin notu (0–100)
    failure_risk_percentage: Optional[float] # None eğer PENDING veya MIMO henüz yok
    freshness_status: str                    # "fresh" / "stale" / "pending"
    explanation_text: str                    # common_utils.get_risk_explanation()


class CompletedCourseDetail(BaseModel):
    course_id: int
    course_name: str
    quiz_avg: Optional[float]
    assign_avg: Optional[float]
    final_grade: Optional[float]
    grade_summary: str                       # "İyi performans, 85/100"
    mimo_risk_score: Optional[float]
    hkar_weak_topics: List[str]              # top-3 zayıf konu


class GradesPageResponse(BaseModel):
    ongoing_courses: List[OngoingCourseGrade]
    completed_courses: List[CompletedCourseDetail]
    user_id: int


# ─────────────────────────────────────────────────────────────────
# LEARNING PATH PAGE
# ─────────────────────────────────────────────────────────────────

class TimelineItem(BaseModel):
    timestamp: int
    date_str: str
    event_type: str             # "quiz" / "assignment" / "video" / "module" / "forum" / "other"
    course_id: int
    course_name: str
    grade: Optional[float]
    is_completed: Optional[bool]
    details: str


class ChartjsSeries(BaseModel):
    label: str
    data: List[float]
    borderColor: str
    backgroundColor: str


class LearningPathResponse(BaseModel):
    timeline: List[TimelineItem]
    chartjs_labels: List[str]           # tarih dizisi (son 30 gün, "DD Ay YYYY")
    chartjs_datasets: List[ChartjsSeries]
    user_id: int


# ─────────────────────────────────────────────────────────────────
# COMPETENCIES PAGE
# ─────────────────────────────────────────────────────────────────

class CompetencyItem(BaseModel):
    type: str                    # "OKUMA" / "FORUM" / "İZLEME" / "ÖDEV"
    total_activities: int
    completed: int
    percentage: float
    label: str                   # "Mükemmel" / "Yeterli" / "Geliştirilmeli" / "Düşük"
    explanation_text: str


class CompetenciesResponse(BaseModel):
    competencies: List[CompetencyItem]   # sabit 4 eleman
    predicted_class: Optional[str]       # HKAR'dan S1/S2/S3/S4
    overall_completion: float            # ortalama %
    user_id: int


# ─────────────────────────────────────────────────────────────────
# EVENTS PAGE
# ─────────────────────────────────────────────────────────────────

class EventItem(BaseModel):
    event_id: int
    event_type: str              # "quiz" / "assignment"
    course_id: int
    course_name: str
    title: str
    due_ts: int                  # Unix timestamp
    due_date_str: str            # "25 Nisan 2026, Cumartesi"
    is_submitted: bool
    days_until_due: Optional[int]  # None → geçmişte


class EventsResponse(BaseModel):
    past_events: List[EventItem]
    upcoming_events: List[EventItem]   # ref_date'e göre ≤7 gün içinde
    future_events: List[EventItem]     # >7 gün sonra
    reference_date_str: str
    user_id: int

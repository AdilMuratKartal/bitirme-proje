"""
render_backend/schemas.py — Pydantic Response Modelleri

Her frontend sayfasına karşılık gelen JSON şemaları.
Bu modeller api.py response_model parametresinde kullanılır.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────
# GRADES PAGE
# ─────────────────────────────────────────────────────────────────

class OngoingCourseGrade(BaseModel):
    course_id: int
    course_name: str
    current_grade: Optional[float]           # mdl_grade_grades'den gerçek not
    risk_score: Optional[float]              # risk_premodel çıktısı (0.0–1.0)
    risk_level: Optional[str]               # "high" / "medium" / "low"
    predicted_grade: Optional[float]         # geriye dönük uyumluluk (None)
    pass_probability: Optional[float] = None # risk_premodel geçme olasılığı (0.0–1.0)
    will_pass: Optional[int] = None          # risk_premodel: 1 = geçer, 0 = kalır
    failure_risk_percentage: Optional[float] # None eğer PENDING veya model henüz yok
    freshness_status: str                    # "fresh" / "stale" / "pending"
    explanation_text: str                    # common_utils.get_risk_explanation()
    completion_pct: Optional[float] = None           # dash_03: tamamlanma %
    total_visible_modules: Optional[int] = None      # dash_03: görünür modül sayısı
    completed_modules: Optional[int] = None          # dash_03: tamamlanan modül sayısı
    next_expected_date: Optional[str] = None         # dash_03: en yakın deadline


class CompletedCourseDetail(BaseModel):
    course_id: int
    course_name: str
    quiz_avg: Optional[float]
    assign_avg: Optional[float]
    final_grade: Optional[float]
    grade_summary: str
    risk_score: Optional[float]


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


class CourseCompletionItem(BaseModel):
    course: str
    completed: int
    total: int


class CompetenciesResponse(BaseModel):
    competencies: List[CompetencyItem]   # sabit 4 eleman
    predicted_class: Optional[str]       # risk_premodel: "Başarılı" / "Başarısız"
    overall_completion: float            # ortalama %
    completion_by_course: Optional[List[CourseCompletionItem]] = None
    user_id: int


# ─────────────────────────────────────────────────────────────────
# EVENTS PAGE  (düz dizi — sınıflandırma frontend'de yapılır)
# ─────────────────────────────────────────────────────────────────

class FlatEventItem(BaseModel):
    userid: int
    courseid: int
    cmid: int
    module_type: str            # "assign" / "quiz" / "workshop"
    display_name: str
    course_name: str
    course_short: str           # kısa kod (ör. "MATH201"), yoksa ""
    event_date: str             # "YYYY-MM-DD"
    timestart: int              # Unix timestamp (UTC gece yarısı)
    days_until: int             # negatif = geçmiş, pozitif = gelecek
    is_overdue: bool
    is_completed: bool


class EventsResponse(BaseModel):
    items: List[FlatEventItem]  # düz dizi — sıralama/sınıflandırma frontend'de
    user_id: int


# ─────────────────────────────────────────────────────────────────
# HOMEPAGE (ana sayfa özet kartı)
# ─────────────────────────────────────────────────────────────────

class HomepageCourse(BaseModel):
    course_id: int
    course_name: str
    current_grade: Optional[float] = None   # itemtype="course", None=henüz yok
    completion_pct: Optional[float] = None          # dash_03: tamamlanma %
    total_visible_modules: Optional[int] = None     # dash_03: görünür modül sayısı
    completed_modules: Optional[int] = None         # dash_03: tamamlanan modül sayısı


class HomepageGrade(BaseModel):
    item_name: str     # quiz/ödev adı (mdl_grade_items.itemname)
    grade: float
    date_str: str      # "25 Nis 2026" Türkçe kısa format


class HomepageEvent(BaseModel):
    title: str
    event_type: str    # "quiz" | "assignment"
    due_date_str: str  # "25 Nisan 2026, Cumartesi"


class HomepageResponse(BaseModel):
    user_name: str
    competency_pcts: Dict[str, float]     # {"OKUMA": 72.5, "FORUM": 45.0, ...}
    active_courses: List[HomepageCourse]  # max 6
    recent_grades: List[HomepageGrade]    # max 6, timemodified DESC
    upcoming_events: List[HomepageEvent]  # yaklaşan quiz+ödev
    recent_activities: List[str]          # son 30 günün benzersiz aktivite adları
    # KPI kartları — dash_02_user_stats (pre-compute yoksa None)
    focus_score: Optional[float] = None
    focus_score_delta_pct: Optional[float] = None
    avg_grade: Optional[float] = None
    avg_grade_delta: Optional[float] = None
    study_streak_days: Optional[int] = None
    streak_delta: Optional[int] = None
    late_assignment_count: Optional[int] = None
    total_study_minutes: Optional[float] = None
    avg_session_minutes: Optional[float] = None
    sessions_per_active_day: Optional[float] = None
    last_active_date: Optional[str] = None
    user_id: int


# ─────────────────────────────────────────────────────────────────
# HEATMAP PAGE (aktivite heatmap 7×24)
# ─────────────────────────────────────────────────────────────────

class HeatmapCell(BaseModel):
    weekday: int        # 0=Pazartesi, 6=Pazar
    hour: int           # 0-23
    event_count: int
    session_starts: int


class HeatmapResponse(BaseModel):
    data: List[HeatmapCell]   # 168 hücre (7×24)
    user_id: int


# ─────────────────────────────────────────────────────────────────
# COURSE ANALYTICS PAGE (dash_05)
# ─────────────────────────────────────────────────────────────────

class CourseAnalyticsItem(BaseModel):
    courseid: int
    assign_completion_rate: Optional[float] = None
    quiz_completion_rate: Optional[float] = None
    avg_daily_minutes: Optional[float] = None
    forum_total: Optional[int] = None
    forum_interactions: Optional[int] = None
    forum_interaction_rate: Optional[float] = None
    page_total: Optional[int] = None
    page_viewed: Optional[int] = None
    page_view_rate: Optional[float] = None


class CourseAnalyticsResponse(BaseModel):
    courses: List[CourseAnalyticsItem]
    user_id: int

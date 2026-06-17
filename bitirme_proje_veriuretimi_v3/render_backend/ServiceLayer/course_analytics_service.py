"""
render_backend/ServiceLayer/course_analytics_service.py — Kurs Analitiği Servisi

get_course_analytics(uid, dao) → CourseAnalyticsResponse

dash_05_course_analytics tablosundan per-course analitik verileri okur:
  assign/quiz tamamlama oranları, günlük ort. çalışma süresi, forum + page metrikleri.
Pre-compute yapılmamışsa boş liste döner.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import CourseAnalyticsItem, CourseAnalyticsResponse

_FLOAT_COLS = [
    "assign_completion_rate", "quiz_completion_rate", "avg_daily_minutes",
    "forum_interaction_rate", "page_view_rate",
]
_INT_COLS = ["forum_total", "forum_interactions", "page_total", "page_viewed"]


def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if pd.notna(val) else None
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    try:
        return int(val) if pd.notna(val) else None
    except (TypeError, ValueError):
        return None


def get_course_analytics(uid: int, dao: MoodleDAO) -> CourseAnalyticsResponse:
    df = dao.get_dash_course_analytics(uid)

    if df.empty:
        return CourseAnalyticsResponse(courses=[], user_id=uid)

    items: List[CourseAnalyticsItem] = [
        CourseAnalyticsItem(
            courseid=int(row["courseid"]),
            assign_completion_rate=_safe_float(row.get("assign_completion_rate")),
            quiz_completion_rate=_safe_float(row.get("quiz_completion_rate")),
            avg_daily_minutes=_safe_float(row.get("avg_daily_minutes")),
            forum_total=_safe_int(row.get("forum_total")),
            forum_interactions=_safe_int(row.get("forum_interactions")),
            forum_interaction_rate=_safe_float(row.get("forum_interaction_rate")),
            page_total=_safe_int(row.get("page_total")),
            page_viewed=_safe_int(row.get("page_viewed")),
            page_view_rate=_safe_float(row.get("page_view_rate")),
        )
        for _, row in df.iterrows()
    ]
    return CourseAnalyticsResponse(courses=items, user_id=uid)

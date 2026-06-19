"""
render_backend/ServiceLayer/grades_service.py — Notlar Sayfası Servisi

get_grades_page(uid, dao) → GradesPageResponse

dash-only: kurs ilerleme + not bilgileri dash_course_progress'ten gelir.
Risk değerleri (varsa) dash_risk precompute tablosundan okunur; yoksa PENDING.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import (
    CompletedCourseDetail,
    GradesPageResponse,
    OngoingCourseGrade,
)
from ServiceLayer.common_utils import (
    course_label,
    failure_risk_pct,
    format_grade_summary,
    get_risk_explanation,
    get_risk_explanation_pending,
)

# completion_pct bu eşiğin üstündeyse kurs "bitmiş" sayılır.
_COMPLETED_THRESHOLD = 99.5


def get_grades_page(uid: int, dao: MoodleDAO) -> GradesPageResponse:
    progress_df = dao.get_dash_course_progress(uid)
    risk = _user_risk(uid, dao)
    freshness = "fresh" if risk else "pending"

    ongoing: List[OngoingCourseGrade] = []
    completed: List[CompletedCourseDetail] = []

    if not progress_df.empty:
        for _, row in progress_df.iterrows():
            cid = int(row["courseid"])
            cname = course_label(cid, row.get("course_fullname"))
            comp_pct = float(row["completion_pct"]) if pd.notna(row.get("completion_pct")) else None
            avg_grade = float(row["avg_grade"]) if pd.notna(row.get("avg_grade")) else None

            if comp_pct is not None and comp_pct >= _COMPLETED_THRESHOLD:
                completed.append(_build_completed(cid, cname, avg_grade, risk))
            else:
                ongoing.append(_build_ongoing(cid, cname, avg_grade, comp_pct, row, risk, freshness))

    return GradesPageResponse(
        ongoing_courses=ongoing,
        completed_courses=completed,
        user_id=uid,
    )


def _user_risk(uid: int, dao: MoodleDAO) -> Optional[dict]:
    """dash_risk precompute (Faz 2) varsa öğrenci risk dict'ini döner; yoksa None."""
    getter = getattr(dao, "get_dash_risk", None)
    if getter is None:
        return None
    try:
        return getter(uid)
    except Exception:
        return None


def _build_ongoing(
    cid: int,
    cname: str,
    avg_grade: Optional[float],
    comp_pct: Optional[float],
    row: pd.Series,
    risk: Optional[dict],
    freshness: str,
) -> OngoingCourseGrade:
    risk = risk or {}
    risk_score = risk.get("risk_score")
    predicted_grade = risk.get("predicted_grade")

    if risk_score is not None and predicted_grade is not None:
        explanation = get_risk_explanation(risk_score, predicted_grade, cname)
    else:
        explanation = get_risk_explanation_pending(cname)

    total_vis = int(row["total_visible_modules"]) if pd.notna(row.get("total_visible_modules")) else None
    completed_mods = int(row["completed_modules"]) if pd.notna(row.get("completed_modules")) else None
    next_exp = str(row["next_expected_date"]) if pd.notna(row.get("next_expected_date")) else None

    return OngoingCourseGrade(
        course_id=cid,
        course_name=cname,
        current_grade=avg_grade,
        risk_score=risk_score,
        risk_level=risk.get("risk_level"),
        predicted_grade=predicted_grade,
        pass_probability=risk.get("pass_probability"),
        will_pass=risk.get("will_pass"),
        failure_risk_percentage=failure_risk_pct(risk_score) if risk_score is not None else None,
        freshness_status=freshness,
        explanation_text=explanation,
        completion_pct=comp_pct,
        total_visible_modules=total_vis,
        completed_modules=completed_mods,
        next_expected_date=next_exp,
    )


def _build_completed(
    cid: int,
    cname: str,
    avg_grade: Optional[float],
    risk: Optional[dict],
) -> CompletedCourseDetail:
    risk = risk or {}
    return CompletedCourseDetail(
        course_id=cid,
        course_name=cname,
        quiz_avg=None,
        assign_avg=None,
        final_grade=avg_grade,
        grade_summary=format_grade_summary(avg_grade, None, None),
        risk_score=risk.get("risk_score"),
    )

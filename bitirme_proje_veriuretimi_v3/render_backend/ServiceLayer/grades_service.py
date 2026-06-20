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
    GradeItemDetail,
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
    
    freshness = "fresh"
    if risk:
        computed_at_str = risk.get("computed_at")
        if computed_at_str:
            try:
                import datetime
                computed_at_dt = datetime.datetime.fromisoformat(computed_at_str)
                now_dt = datetime.datetime.now(datetime.timezone.utc)
                age_days = (now_dt - computed_at_dt).days
                if age_days >= 7:
                    freshness = "stale"
            except Exception:
                pass
    else:
        freshness = "pending"

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
        grade_items=_grade_items(uid, dao),
        recommendations=risk.get("recommendations", []) if risk else [],
        user_id=uid,
    )


def _f(v) -> Optional[float]:
    return float(v) if v is not None and pd.notna(v) else None


def _b(v) -> Optional[bool]:
    """dash_grade_items.passed → True/False/None (Postgres bool, sqlite int, ya da metin)."""
    if v is None or (not isinstance(v, bool) and pd.isna(v)):
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "t"):  return True
        if s in ("false", "0", "f"): return False
        return None
    return bool(v)


def _grade_items(uid: int, dao: MoodleDAO) -> List[GradeItemDetail]:
    """dash_grade_items'tan tek tek not kalemlerini GradeItemDetail listesine çevirir."""
    df = dao.get_dash_grade_items(uid)
    if df is None or df.empty:
        return []
    items: List[GradeItemDetail] = []
    for _, r in df.iterrows():
        items.append(GradeItemDetail(
            courseid=int(r["courseid"]),
            course_fullname=str(r["course_fullname"]),
            itemid=int(r["itemid"]),
            item_label=str(r["item_label"]),
            item_type=str(r["item_type"]),
            item_module=(None if pd.isna(r.get("item_module")) else str(r["item_module"])),
            grade=_f(r.get("grade")),
            grademax=_f(r.get("grademax")),
            norm_grade=_f(r.get("norm_grade")),
            gradepass=_f(r.get("gradepass")),
            norm_gradepass=_f(r.get("norm_gradepass")),
            passed=_b(r.get("passed")),
            graded_date=(None if pd.isna(r.get("graded_date")) else str(r["graded_date"])),
        ))
    return items


def _user_risk(uid: int, dao: MoodleDAO) -> Optional[dict]:
    """dash_risk precompute veya on-demand hesaplama."""
    from ServiceLayer.risk_service import get_or_calculate_user_risk
    try:
        return get_or_calculate_user_risk(uid, dao)
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

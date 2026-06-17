"""
render_backend/ServiceLayer/grades_service.py — Notlar Sayfası Servisi

get_grades_page(uid, dao, orchestrator) → GradesPageResponse

Devam eden kurslar: risk_premodel analizi + freshness.
Biten kurslar: arşiv notlar (quiz/ödev/final from grade_grades).
"""

from __future__ import annotations

import time
from typing import List, Optional

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from api_gateway_orchestration.orchestration.orchestration import BatchOrchestrator
from schemas import (
    CompletedCourseDetail,
    GradesPageResponse,
    OngoingCourseGrade,
)
from ServiceLayer.common_utils import (
    failure_risk_pct,
    format_grade_summary,
    get_risk_explanation,
    get_risk_explanation_pending,
)


def get_grades_page(
    uid: int,
    dao: MoodleDAO,
    orchestrator: BatchOrchestrator,
) -> GradesPageResponse:
    """
    Akış:
    1. Tüm kursları çek.
    2. Öğrencinin not detaylarını çek.
    3. Her kursu ongoing/completed olarak ayır (enddate < now → completed).
    4. Ongoing kurslar için orchestrator üzerinden risk_premodel analizi al.
    5. Completed kurslar için not ortalamalarını hesapla.
    6. GradesPageResponse döndür.
    """
    now_ts = int(time.time())

    courses_df  = dao.get_courses()
    grade_df    = dao.get_student_grade_details(uid)
    progress_df = dao.get_dash_course_progress(uid)

    # risk_premodel analizi — orchestrator hot-path (FRESH → cache, STALE/PENDING → predict)
    analysis            = orchestrator.get_student_analysis(uid, dao)
    risk_premodel_data  = analysis.get("data", {}).get("risk_premodel_analysis") or {}
    freshness = analysis.get("meta", {}).get("freshness", "pending")

    ongoing_courses: List[OngoingCourseGrade]    = []
    completed_courses: List[CompletedCourseDetail] = []

    for _, course in courses_df.iterrows():
        cid   = int(course["id"])
        cname = str(course["fullname"])
        end   = int(course["enddate"]) if pd.notna(course["enddate"]) else 0

        if end > 0 and end < now_ts:
            # ── Biten kurs ──────────────────────────────────────
            completed_courses.append(
                _build_completed(cid, cname, grade_df, risk_premodel_data)
            )
        else:
            # ── Devam eden kurs ─────────────────────────────────
            ongoing_courses.append(
                _build_ongoing(cid, cname, grade_df, risk_premodel_data, freshness, progress_df)
            )

    return GradesPageResponse(
        ongoing_courses=ongoing_courses,
        completed_courses=completed_courses,
        user_id=uid,
    )


# ─────────────────────────────────────────────────────────────────
# Yardımcı: devam eden kurs satırı
# ─────────────────────────────────────────────────────────────────

def _build_ongoing(
    cid: int,
    cname: str,
    grade_df: pd.DataFrame,
    risk_premodel_data: dict,
    freshness: str,
    progress_df: pd.DataFrame,
) -> OngoingCourseGrade:
    # Gerçek güncel not — grade_items.itemtype = "course" bu kurs için
    u_grades = grade_df[grade_df["courseid"] == cid] if not grade_df.empty else pd.DataFrame()
    course_row = (
        u_grades[u_grades["itemtype"] == "course"] if not u_grades.empty else pd.DataFrame()
    )
    current_grade: Optional[float] = (
        float(course_row.iloc[0]["finalgrade"])
        if not course_row.empty and pd.notna(course_row.iloc[0]["finalgrade"])
        else None
    )

    # risk_premodel alanları — PENDING ise None
    risk_score       = risk_premodel_data.get("risk_score")
    risk_level       = risk_premodel_data.get("risk_level")
    predicted_grade  = risk_premodel_data.get("predicted_grade")
    pass_probability = risk_premodel_data.get("pass_probability")
    will_pass        = risk_premodel_data.get("will_pass")

    frp: Optional[float] = (
        failure_risk_pct(risk_score) if risk_score is not None else None
    )

    if risk_score is not None and predicted_grade is not None:
        explanation = get_risk_explanation(risk_score, predicted_grade, cname)
    else:
        explanation = get_risk_explanation_pending(cname)

    # dash_03_course_progress — tamamlanma bilgileri
    prog = (
        progress_df[progress_df["courseid"] == cid]
        if not progress_df.empty else pd.DataFrame()
    )
    completion_pct: Optional[float] = (
        float(prog.iloc[0]["completion_pct"]) if not prog.empty and pd.notna(prog.iloc[0]["completion_pct"]) else None
    )
    total_visible: Optional[int] = (
        int(prog.iloc[0]["total_visible_modules"]) if not prog.empty and pd.notna(prog.iloc[0]["total_visible_modules"]) else None
    )
    completed_mods: Optional[int] = (
        int(prog.iloc[0]["completed_modules"]) if not prog.empty and pd.notna(prog.iloc[0]["completed_modules"]) else None
    )
    next_exp: Optional[str] = (
        str(prog.iloc[0]["next_expected_date"])
        if not prog.empty and pd.notna(prog.iloc[0]["next_expected_date"])
        else None
    )

    return OngoingCourseGrade(
        course_id=cid,
        course_name=cname,
        current_grade=current_grade,
        risk_score=risk_score,
        risk_level=risk_level,
        predicted_grade=predicted_grade,
        pass_probability=pass_probability,
        will_pass=will_pass,
        failure_risk_percentage=frp,
        freshness_status=freshness,
        explanation_text=explanation,
        completion_pct=completion_pct,
        total_visible_modules=total_visible,
        completed_modules=completed_mods,
        next_expected_date=next_exp,
    )


# ─────────────────────────────────────────────────────────────────
# Yardımcı: biten kurs satırı
# ─────────────────────────────────────────────────────────────────

def _build_completed(
    cid: int,
    cname: str,
    grade_df: pd.DataFrame,
    risk_premodel_data: dict,
) -> CompletedCourseDetail:
    u_grades = grade_df[grade_df["courseid"] == cid] if not grade_df.empty else pd.DataFrame()

    quiz_rows   = u_grades[u_grades["itemtype"] == "quiz"]   if not u_grades.empty else pd.DataFrame()
    assign_rows = u_grades[u_grades["itemtype"] == "assign"] if not u_grades.empty else pd.DataFrame()
    course_rows = u_grades[u_grades["itemtype"] == "course"] if not u_grades.empty else pd.DataFrame()

    quiz_avg: Optional[float] = (
        round(float(quiz_rows["finalgrade"].dropna().mean()), 1)
        if not quiz_rows.empty and quiz_rows["finalgrade"].notna().any()
        else None
    )
    assign_avg: Optional[float] = (
        round(float(assign_rows["finalgrade"].dropna().mean()), 1)
        if not assign_rows.empty and assign_rows["finalgrade"].notna().any()
        else None
    )
    final_grade: Optional[float] = (
        round(float(course_rows.iloc[0]["finalgrade"]), 1)
        if not course_rows.empty and pd.notna(course_rows.iloc[0]["finalgrade"])
        else None
    )

    return CompletedCourseDetail(
        course_id=cid,
        course_name=cname,
        quiz_avg=quiz_avg,
        assign_avg=assign_avg,
        final_grade=final_grade,
        grade_summary=format_grade_summary(final_grade, quiz_avg, assign_avg),
        risk_score=risk_premodel_data.get("risk_score"),
    )

"""
render_backend/ServiceLayer/competencies_service.py — Yetkinlikler Sayfası Servisi

get_competencies(uid, dao) → CompetenciesResponse

4 yetkinlik türü (OKUMA/FORUM/İZLEME/ÖDEV), dash_module_status tabanlı tamamlama oranları.
mdl_* yerine yalnızca dash precompute tabloları okunur.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import CompetenciesResponse, CompetencyItem, CourseCompletionItem
from ServiceLayer.common_utils import COMPETENCY_MODULE_TYPES, label_competency, course_label


def get_competencies(uid: int, dao: MoodleDAO) -> CompetenciesResponse:
    """
    Akış (dash-only):
    1. dash_module_status'tan öğrencinin tüm modüllerini çek.
    2. Her yetkinlik türü için (module_type eşlemesi) total + completed say.
    3. percentage = completed / total * 100.
    4. CompetenciesResponse döndür.
    """
    mod_df = dao.get_dash_module_status(uid)

    if not mod_df.empty:
        mod_df = mod_df.copy()
        mod_df["module_type"] = mod_df["module_type"].astype(str).str.strip().str.lower()
        mod_df["is_completed"] = mod_df["is_completed"].fillna(False).astype(bool)

    competencies: List[CompetencyItem] = []
    total_pct = 0.0

    for ctype_label, module_types in COMPETENCY_MODULE_TYPES.items():
        if mod_df.empty:
            type_rows = pd.DataFrame()
        else:
            type_rows = mod_df[mod_df["module_type"].isin(module_types)]

        total = int(len(type_rows))
        completed = int(type_rows["is_completed"].sum()) if total else 0
        pct = round(completed / total * 100, 1) if total else 0.0
        total_pct += pct

        label, explanation = label_competency(pct, ctype_label, total, completed)
        competencies.append(CompetencyItem(
            type=ctype_label,
            total_activities=total,
            completed=completed,
            percentage=pct,
            label=label,
            explanation_text=explanation,
        ))

    overall = round(total_pct / len(COMPETENCY_MODULE_TYPES), 1) if competencies else 0.0

    # 5. Kurs bazlı tamamlanan etkinlikler
    progress_df = dao.get_dash_course_progress(uid)
    completion_by_course: List[CourseCompletionItem] = []
    if not progress_df.empty:
        for _, row in progress_df.iterrows():
            cid = int(row["courseid"])
            cname = course_label(cid, row.get("course_fullname"))
            completed = int(row["completed_modules"]) if pd.notna(row.get("completed_modules")) else 0
            total = int(row["total_visible_modules"]) if pd.notna(row.get("total_visible_modules")) else 0
            completion_by_course.append(CourseCompletionItem(
                course=cname,
                completed=completed,
                total=total
            ))

    # predicted_class: risk precompute tablosundan (varsa); yoksa None.
    predicted_class: Optional[str] = _predicted_class(uid, dao)

    return CompetenciesResponse(
        competencies=competencies,
        predicted_class=predicted_class,
        overall_completion=overall,
        completion_by_course=completion_by_course,
        user_id=uid,
    )


def _predicted_class(uid: int, dao: MoodleDAO) -> Optional[str]:
    """Risk precompute varsa 'Başarılı'/'Başarısız' döner; yoksa None."""
    getter = getattr(dao, "get_dash_risk", None)
    if getter is None:
        return None
    try:
        risk = getter(uid)
    except Exception:
        return None
    if not risk:
        return None
    will_pass = risk.get("will_pass")
    if will_pass is None:
        return None
    return "Başarılı" if will_pass else "Başarısız"

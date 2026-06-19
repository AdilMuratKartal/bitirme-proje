"""
render_backend/ServiceLayer/homepage_service.py — Ana Sayfa Özet Servisi

get_homepage(uid, dao) → HomepageResponse

dash-only: tüm veriler dash precompute tablolarından gelir.
  - KPI'lar       → dash_user_stats
  - Kurslar/not   → dash_course_progress
  - Yetkinlik %   → dash_module_status (competencies ile aynı eşleme)
  - Yaklaşan/etkinlik + aktivite → dash_module_status
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import HomepageCourse, HomepageEvent, HomepageGrade, HomepageResponse
from ServiceLayer.common_utils import (
    COMPETENCY_MODULE_TYPES,
    course_label,
    format_date_short,
    format_date_tr,
)

# dash_module_status.module_type → kısa Türkçe etiket (aktivite isimleri için)
_MODULE_TR: Dict[str, str] = {
    "resource": "Kaynak", "assign": "Ödev", "quiz": "Quiz", "forum": "Forum",
    "page": "Sayfa", "url": "Bağlantı", "book": "Kitap", "folder": "Klasör",
    "label": "Etiket", "scorm": "İçerik", "lesson": "Ders", "wiki": "Wiki",
    "glossary": "Sözlük", "choice": "Anket", "questionnaire": "Anket",
    "workshop": "Atölye", "bigbluebuttonbn": "Canlı Ders", "chat": "Sohbet",
}
_EVENT_TYPES = {"assign": "assignment", "quiz": "quiz", "workshop": "assignment"}


def get_homepage(uid: int, dao: MoodleDAO) -> HomepageResponse:
    now_ts = int(time.time())

    stats = dao.get_dash_user_stats(uid)
    progress_df = dao.get_dash_course_progress(uid)
    mod_df = dao.get_dash_module_status(uid)

    # 1. Kullanıcı adı — anonim sette isim yok → placeholder
    user_name = f"Öğrenci {uid}"

    # 2. Yetkinlik yüzdeleri (competencies ile aynı eşleme)
    competency_pcts = _competency_pcts(mod_df)

    # 3. Aktif kurslar (max 6) + güncel not
    active_courses: List[HomepageCourse] = []
    recent_grades: List[HomepageGrade] = []
    if not progress_df.empty:
        for _, c in progress_df.head(6).iterrows():
            cid = int(c["courseid"])
            grade = float(c["avg_grade"]) if pd.notna(c.get("avg_grade")) else None
            comp_pct = float(c["completion_pct"]) if pd.notna(c.get("completion_pct")) else None
            total_vis = int(c["total_visible_modules"]) if pd.notna(c.get("total_visible_modules")) else None
            completed_mods = int(c["completed_modules"]) if pd.notna(c.get("completed_modules")) else None
            active_courses.append(HomepageCourse(
                course_id=cid,
                course_name=course_label(cid, c.get("course_fullname")),
                current_grade=grade,
                completion_pct=comp_pct,
                total_visible_modules=total_vis,
                completed_modules=completed_mods,
            ))
        # Son notlar: avg_grade'i olan kurslar (kurs-bazlı not)
        graded = progress_df[progress_df["avg_grade"].notna()]
        for _, c in graded.head(6).iterrows():
            cid = int(c["courseid"])
            date_str = _date_str(c.get("last_activity_date"))
            recent_grades.append(HomepageGrade(
                item_name=course_label(cid, c.get("course_fullname")),
                grade=round(float(c["avg_grade"]), 1),
                date_str=date_str,
            ))

    # 4. Yaklaşan etkinlikler + 5. son aktiviteler (dash_module_status)
    upcoming_events = _upcoming(mod_df, now_ts)
    recent_activities = _recent_activities(mod_df)

    # 6. KPI kartları
    kpi: dict = {}
    if stats:
        kpi = {
            "focus_score":           stats.get("focus_score"),
            "focus_score_delta_pct": stats.get("focus_score_delta_pct"),
            "avg_grade":             stats.get("avg_grade"),
            "avg_grade_delta":       stats.get("avg_grade_delta"),
            "study_streak_days":     stats.get("study_streak_days"),
            "streak_delta":          stats.get("streak_delta"),
            "late_assignment_count": stats.get("late_assignment_count"),
            "total_study_minutes":   stats.get("total_study_minutes"),
            "avg_session_minutes":   stats.get("avg_session_minutes"),
            "sessions_per_active_day": stats.get("sessions_per_active_day"),
            "last_active_date": (
                str(stats["last_active_date"]) if stats.get("last_active_date") else None
            ),
        }

    return HomepageResponse(
        user_name=user_name,
        competency_pcts=competency_pcts,
        active_courses=active_courses,
        recent_grades=recent_grades,
        upcoming_events=upcoming_events,
        recent_activities=recent_activities,
        user_id=uid,
        **kpi,
    )


def _competency_pcts(mod_df: pd.DataFrame) -> Dict[str, float]:
    if mod_df.empty:
        return {k: 0.0 for k in COMPETENCY_MODULE_TYPES}
    df = mod_df.copy()
    df["module_type"] = df["module_type"].astype(str).str.strip().str.lower()
    df["is_completed"] = df["is_completed"].fillna(False).astype(bool)
    out: Dict[str, float] = {}
    for label, types in COMPETENCY_MODULE_TYPES.items():
        rows = df[df["module_type"].isin(types)]
        total = len(rows)
        out[label] = round(int(rows["is_completed"].sum()) / total * 100, 1) if total else 0.0
    return out


def _upcoming(mod_df: pd.DataFrame, now_ts: int) -> List[HomepageEvent]:
    if mod_df.empty:
        return []
    items = []
    for _, row in mod_df.iterrows():
        mtype = str(row.get("module_type", "")).strip().lower()
        if mtype not in _EVENT_TYPES:
            continue
        ts_val = row.get("completion_time") or row.get("first_view_time")
        if pd.isna(ts_val) or not ts_val:
            continue
        due = int(ts_val)
        if due < now_ts:
            continue
        title = str(row.get("display_name") or "").strip()
        if not title or title.lower() in ("nombre", "none", "nan"):
            title = "Ödev" if mtype != "quiz" else "Quiz"
        items.append((due, HomepageEvent(
            title=title,
            event_type=_EVENT_TYPES[mtype],
            due_date_str=format_date_tr(due),
        )))
    items.sort(key=lambda x: x[0])
    return [ev for _, ev in items[:8]]


def _recent_activities(mod_df: pd.DataFrame) -> List[str]:
    if mod_df.empty:
        return []
    df = mod_df.copy()
    df["ts"] = df["completion_time"].fillna(df["first_view_time"])
    df = df[df["ts"].notna()].sort_values("ts", ascending=False)
    seen, names = set(), []
    for mt in df["module_type"]:
        label = _MODULE_TR.get(str(mt).strip().lower(), str(mt).capitalize())
        if label not in seen:
            seen.add(label)
            names.append(label)
        if len(names) >= 20:
            break
    return names


def _date_str(date_val) -> str:
    if not date_val:
        return "—"
    try:
        d = datetime.strptime(str(date_val)[:10], "%Y-%m-%d")
        ts = int(d.replace(tzinfo=timezone.utc).timestamp())
        return format_date_short(ts)
    except Exception:
        return "—"

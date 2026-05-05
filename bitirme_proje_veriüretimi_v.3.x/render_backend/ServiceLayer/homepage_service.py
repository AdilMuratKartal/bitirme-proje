"""
render_backend/ServiceLayer/homepage_service.py — Ana Sayfa Özet Servisi

get_homepage(uid, dao) → HomepageResponse

Tek endpoint'te toplanmış özet kart verisi:
  - Kullanıcı adı (mdl_user)
  - 4 yetkinlik yüzdesi (log-tabanlı, competencies_service ile aynı mantık)
  - Aktif 6 kurs + mevcut notları
  - Son 6 not (timemodified DESC)
  - Yaklaşan quiz + ödev adları
  - Son 30 günün aktivite adları (benzersiz, max 20)
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import HomepageCourse, HomepageEvent, HomepageGrade, HomepageResponse
from ServiceLayer.common_utils import format_date_short, format_date_tr

# ─── Sabitler ────────────────────────────────────────────────────

_COMP_MAP: Dict[str, List[str]] = {
    "OKUMA":  ["Okuma"],
    "FORUM":  ["Forum"],
    "İZLEME": ["Izleme"],
    "ÖDEV":   ["Odev"],
}

_COMPONENT_LABELS: Dict[str, str] = {
    "mod_quiz":        "Quiz",
    "mod_assign":      "Ödev",
    "mod_forum":       "Forum",
    "mod_resource":    "Kaynak",
    "mod_page":        "Sayfa",
    "mod_url":         "Bağlantı",
    "mod_videotime":   "Video",
    "mod_hvp":         "İnteraktif",
    "mod_lesson":      "Ders",
    "mod_book":        "Kitap",
    "mod_folder":      "Klasör",
    "mod_workshop":    "Atölye",
    "mod_glossary":    "Sözlük",
    "mod_survey":      "Anket",
    "mod_bigbluebuttonbn": "Canlı Ders",
}

# ─── Yardımcı fonksiyonlar ───────────────────────────────────────

def _calc_competency_pcts(modules_df: pd.DataFrame, logs_df: pd.DataFrame) -> Dict[str, float]:
    """4 yetkinlik türü için tamamlama yüzdesi hesapla."""
    viewed_ids: set = set()
    if not logs_df.empty:
        vl = logs_df[logs_df["action"].isin(["view", "viewed", "submitted", "completed"])]
        viewed_ids = {int(x) for x in vl["objectid"].dropna()}

    result: Dict[str, float] = {}
    for label, ctypes in _COMP_MAP.items():
        if modules_df.empty:
            result[label] = 0.0
            continue
        mods = modules_df[modules_df["content_type"].isin(ctypes)]
        total = len(mods)
        if total == 0:
            result[label] = 0.0
        else:
            done = len({int(x) for x in mods["id"]} & viewed_ids)
            result[label] = round(done / total * 100, 1)
    return result


def _component_names(logs_30d: pd.DataFrame) -> List[str]:
    """Son 30 günlük benzersiz aktivite adları, max 20."""
    if logs_30d.empty:
        return []
    seen, names = set(), []
    for comp in logs_30d["component"]:
        label = _COMPONENT_LABELS.get(comp, comp.replace("mod_", "").capitalize())
        if label not in seen:
            seen.add(label)
            names.append(label)
        if len(names) >= 20:
            break
    return names


def _upcoming_events(
    quiz_df: pd.DataFrame,
    assign_df: pd.DataFrame,
    now_ts: int,
) -> List[HomepageEvent]:
    """Yaklaşan quiz + ödev adlarını due_ts'e göre sıralı döner."""
    items: List[Tuple[int, HomepageEvent]] = []

    if not quiz_df.empty:
        future_q = quiz_df[quiz_df["timeclose"] > now_ts]
        for _, q in future_q.iterrows():
            due = int(q["timeclose"])
            items.append((due, HomepageEvent(
                title=str(q["name"]),
                event_type="quiz",
                due_date_str=format_date_tr(due),
            )))

    if not assign_df.empty:
        valid_a = assign_df[assign_df["duedate"].notna() & (assign_df["duedate"] > now_ts)]
        for _, a in valid_a.iterrows():
            due = int(a["duedate"])
            items.append((due, HomepageEvent(
                title=str(a["name"]),
                event_type="assignment",
                due_date_str=format_date_tr(due),
            )))

    items.sort(key=lambda x: x[0])
    return [ev for _, ev in items]


# ─── Ana fonksiyon ───────────────────────────────────────────────

def get_homepage(uid: int, dao: MoodleDAO) -> HomepageResponse:
    """
    Ana sayfa özet kartı.
    6 DAO çağrısı; log verisi iki amaç için reuse edilir (ekstra sorgu yok).
    """
    now_ts    = int(time.time())
    since_30d = now_ts - 30 * 86_400

    # 1. Kullanıcı adı
    user      = dao.get_user(uid)
    user_name = (
        f"{user['firstname']} {user['lastname']}" if user else f"Öğrenci {uid}"
    )

    # 2. Kurslar + notlar (tek çekimde iki ihtiyaç)
    courses_df = dao.get_courses()
    grades_df  = dao.get_student_grade_details(uid)

    # 2a. Aktif kurslar (enddate=0 veya >now), max 6
    if not courses_df.empty:
        active_c = courses_df[
            (courses_df["enddate"] == 0) | (courses_df["enddate"] > now_ts)
        ].head(6)
    else:
        active_c = pd.DataFrame()

    active_courses: List[HomepageCourse] = []
    for _, c in active_c.iterrows():
        c_id = int(c["id"])
        if not grades_df.empty:
            cg = grades_df[
                (grades_df["courseid"] == c_id) & (grades_df["itemtype"] == "course")
            ]["finalgrade"]
            current_grade = round(float(cg.mean()), 1) if not cg.empty else None
        else:
            current_grade = None
        active_courses.append(HomepageCourse(
            course_id=c_id,
            course_name=str(c["fullname"]),
            current_grade=current_grade,
        ))

    # 2b. Son 6 not (timemodified DESC, finalgrade dolu olanlar)
    if not grades_df.empty:
        recent_g = (
            grades_df[grades_df["finalgrade"].notna()]
            .sort_values("timemodified", ascending=False)
            .head(6)
        )
    else:
        recent_g = pd.DataFrame()

    recent_grades: List[HomepageGrade] = []
    for _, row in recent_g.iterrows():
        item_name = row.get("itemname") or str(row["itemtype"])
        recent_grades.append(HomepageGrade(
            item_name=str(item_name),
            grade=round(float(row["finalgrade"]), 1),
            date_str=format_date_short(int(row["timemodified"])),
        ))

    # 3. Log — yetkinlik % için tüm zamanlar, aktivite isimleri için 30 gün
    logs_all = dao.get_activity_logs_recent(uid, since_ts=0)
    logs_30d = logs_all[logs_all["timecreated"] >= since_30d] if not logs_all.empty else logs_all

    # 3a. Yetkinlik %
    modules_df      = dao.get_course_modules_all()
    competency_pcts = _calc_competency_pcts(modules_df, logs_all)

    # 3b. Aktivite isimleri (30 gün)
    recent_activities = _component_names(logs_30d)

    # 4. Etkinlik isimleri (takvim) — yaklaşan
    quiz_df   = dao.get_quiz_events(uid)
    assign_df = dao.get_assign_events(uid)
    upcoming_events = _upcoming_events(quiz_df, assign_df, now_ts)

    return HomepageResponse(
        user_name=user_name,
        competency_pcts=competency_pcts,
        active_courses=active_courses,
        recent_grades=recent_grades,
        upcoming_events=upcoming_events,
        recent_activities=recent_activities,
        user_id=uid,
    )

"""
render_backend/ServiceLayer/learning_path_service.py — Öğrenme Yolu Sayfası Servisi

get_learning_path(uid, dao, days=30) → LearningPathResponse

Son N günün aktivite günlüğünü timeline + Chart.js formatına dönüştürür.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import ChartjsSeries, LearningPathResponse, TimelineItem
from ServiceLayer.common_utils import CHART_COLORS, format_date_short, format_date_tr

# Log action + component → event_type eşlemeleri
_COMPONENT_TO_TYPE: Dict[str, str] = {
    "mod_quiz":    "quiz",
    "mod_assign":  "assignment",
    "mod_forum":   "forum",
    "mod_resource": "module",
    "mod_page":    "module",
    "mod_url":     "module",
    "mod_videotime": "video",
    "mod_hvp":     "video",
}


def get_learning_path(
    uid: int,
    dao: MoodleDAO,
    days: int = 30,
) -> LearningPathResponse:
    """
    Akış:
    1. Son `days` günün loglarını çek.
    2. Not detaylarını çek (quiz/ödev notları için).
    3. Tamamlama kayıtlarını çek (completion olayları için).
    4. Kurs isim haritasını oluştur.
    5. Timeline'ı birleştir ve timestamp sırala.
    6. Chart.js veri setini oluştur.
    """
    now_ts   = int(time.time())
    since_ts = now_ts - days * 86_400

    logs_df        = dao.get_activity_logs_recent(uid, since_ts)
    grade_df       = dao.get_student_grade_details(uid)
    courses_df     = dao.get_courses()
    modules_df     = dao.get_course_modules_all()

    # Kurs id → fullname haritası
    course_map: Dict[int, str] = {}
    if not courses_df.empty:
        for _, row in courses_df.iterrows():
            course_map[int(row["id"])] = str(row["fullname"])

    # Modül id → (content_type, course) haritası
    mod_map: Dict[int, Dict] = {}
    if not modules_df.empty:
        for _, row in modules_df.iterrows():
            mod_map[int(row["id"])] = {
                "content_type": str(row["content_type"]),
                "course":       int(row["course"]),
            }

    # Not zamanı haritası: (itemtype, courseid) → {timemodified: finalgrade}
    grade_time_map: Dict[tuple, float] = {}
    if not grade_df.empty:
        for _, row in grade_df.iterrows():
            if pd.notna(row["finalgrade"]) and pd.notna(row["timemodified"]):
                key = (str(row["itemtype"]), int(row["courseid"]))
                grade_time_map[key] = float(row["finalgrade"])

    timeline = _merge_timeline(uid, logs_df, grade_df, course_map, mod_map, since_ts)

    # Chart.js etiketleri: son `days` gün
    labels = _build_date_labels(since_ts, now_ts)
    datasets = _build_chartjs_data(timeline, labels, since_ts)

    return LearningPathResponse(
        timeline=timeline,
        chartjs_labels=labels,
        chartjs_datasets=datasets,
        user_id=uid,
    )


# ─────────────────────────────────────────────────────────────────
# Yardımcı: timeline birleştirme
# ─────────────────────────────────────────────────────────────────

def _merge_timeline(
    uid: int,
    logs_df: pd.DataFrame,
    grade_df: pd.DataFrame,
    course_map: Dict[int, str],
    mod_map: Dict[int, Dict],
    since_ts: int,
) -> List[TimelineItem]:
    items: List[TimelineItem] = []

    if not logs_df.empty:
        for _, row in logs_df.iterrows():
            ts          = int(row["timecreated"])
            component   = str(row.get("component", ""))
            action      = str(row.get("action", ""))
            course_id   = int(row["courseid"]) if pd.notna(row.get("courseid")) else 0
            objectid    = int(row["objectid"])  if pd.notna(row.get("objectid"))  else 0

            event_type = _resolve_event_type(component, action, objectid, mod_map)
            course_name = course_map.get(course_id, f"Kurs {course_id}")

            # Not: sadece submit/attempt eylemlerinde not bilgisi göster
            grade: float | None = None
            if action in ("submitted", "graded") and not grade_df.empty:
                itype = "quiz" if "quiz" in component else "assign" if "assign" in component else None
                if itype:
                    key = (itype, course_id)
                    grade = grade_df[
                        (grade_df["itemtype"] == itype) & (grade_df["courseid"] == course_id)
                    ]["finalgrade"].dropna().mean() if not grade_df.empty else None
                    if grade is not None:
                        grade = round(float(grade), 1)

            items.append(TimelineItem(
                timestamp=ts,
                date_str=format_date_tr(ts),
                event_type=event_type,
                course_id=course_id,
                course_name=course_name,
                grade=grade,
                is_completed=(action in ("completed", "submitted")),
                details=f"{component} — {action}",
            ))

    # Timestamp sırala (yeni → eski)
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items


def _resolve_event_type(
    component: str,
    action: str,
    objectid: int,
    mod_map: Dict[int, Dict],
) -> str:
    """component + action + modül content_type → event_type string."""
    mapped = _COMPONENT_TO_TYPE.get(component)
    if mapped:
        return mapped

    # Modül content_type'a göre
    if objectid and objectid in mod_map:
        ct = mod_map[objectid].get("content_type", "")
        if ct == "Izleme":
            return "video"
        if ct == "Forum":
            return "forum"
        if ct in ("Okuma", "Odev"):
            return "module"

    return "other"


# ─────────────────────────────────────────────────────────────────
# Yardımcı: Chart.js veri seti
# ─────────────────────────────────────────────────────────────────

def _build_date_labels(since_ts: int, now_ts: int) -> List[str]:
    """since_ts'den now_ts'e her gün için kısa Türkçe tarih etiketi."""
    labels = []
    day_ts = since_ts
    while day_ts <= now_ts:
        labels.append(format_date_short(day_ts))
        day_ts += 86_400
    return labels


def _build_chartjs_data(
    timeline: List[TimelineItem],
    labels: List[str],
    since_ts: int,
) -> List[ChartjsSeries]:
    """Her event_type için ayrı Chart.js serisi. Y = o gün aktivite sayısı."""
    type_day_count: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

    for item in timeline:
        day_idx = (item.timestamp - since_ts) // 86_400
        type_day_count[item.event_type][day_idx] += 1

    datasets: List[ChartjsSeries] = []
    for etype, day_counts in type_day_count.items():
        data = [float(day_counts.get(i, 0)) for i in range(len(labels))]
        color = CHART_COLORS.get(etype, "#999999")
        datasets.append(ChartjsSeries(
            label=etype.capitalize(),
            data=data,
            borderColor=color,
            backgroundColor=color + "33",  # %20 şeffaflık
        ))

    return datasets

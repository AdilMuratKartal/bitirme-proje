"""
render_backend/ServiceLayer/events_service.py — Etkinlikler Sayfası Servisi

get_events(uid, dao, reference_date=None) → EventsResponse

mdl_event tablosu yoktur — etkinlikler:
  - Quiz: mdl_quiz.timeclose → son gün
  - Ödev: mdl_assign.duedate → son gün

Kategori:
  past     → timeclose < ref_ts
  upcoming → ref_ts ≤ timeclose < ref_ts + 7 gün
  future   → timeclose ≥ ref_ts + 7 gün
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import EventItem, EventsResponse
from ServiceLayer.common_utils import days_until, format_date_tr

_7_DAYS = 7 * 86_400


def get_events(
    uid: int,
    dao: MoodleDAO,
    reference_date: Optional[datetime] = None,
) -> EventsResponse:
    """
    Akış:
    1. Quiz + ödev etkinliklerini çek.
    2. Kurs adı haritasını oluştur.
    3. ref_ts'e göre past/upcoming/future kategorile.
    4. EventsResponse döndür.
    """
    ref_ts = (
        int(reference_date.replace(tzinfo=timezone.utc).timestamp())
        if reference_date
        else int(time.time())
    )
    ref_dt = datetime.fromtimestamp(ref_ts, tz=timezone.utc)

    quiz_df   = dao.get_quiz_events(uid)
    assign_df = dao.get_assign_events(uid)
    courses_df = dao.get_courses()

    course_map: Dict[int, str] = {}
    if not courses_df.empty:
        for _, row in courses_df.iterrows():
            course_map[int(row["id"])] = str(row["fullname"])

    all_items: List[EventItem] = []

    # ── Quiz etkinlikleri ──────────────────────────────────────────
    if not quiz_df.empty:
        for _, row in quiz_df.iterrows():
            due_ts = int(row["timeclose"]) if pd.notna(row.get("timeclose")) else 0
            if due_ts == 0:
                continue
            is_submitted = (
                pd.notna(row.get("state")) and
                str(row["state"]) in ("finished", "submitted")
            )
            all_items.append(_make_event_item(
                event_id=int(row["id"]),
                event_type="quiz",
                course_id=int(row["course"]),
                title=str(row["name"]),
                due_ts=due_ts,
                is_submitted=is_submitted,
                course_map=course_map,
                ref_ts=ref_ts,
            ))

    # ── Ödev etkinlikleri ─────────────────────────────────────────
    if not assign_df.empty:
        for _, row in assign_df.iterrows():
            due_ts = int(row["duedate"]) if pd.notna(row.get("duedate")) else 0
            if due_ts == 0:
                continue
            is_submitted = (
                pd.notna(row.get("status")) and
                str(row["status"]) in ("submitted", "graded")
            )
            all_items.append(_make_event_item(
                event_id=int(row["id"]),
                event_type="assignment",
                course_id=int(row["course"]),
                title=str(row["name"]),
                due_ts=due_ts,
                is_submitted=is_submitted,
                course_map=course_map,
                ref_ts=ref_ts,
            ))

    # ── Kategorize ────────────────────────────────────────────────
    past_events:     List[EventItem] = []
    upcoming_events: List[EventItem] = []
    future_events:   List[EventItem] = []

    for item in all_items:
        if item.due_ts < ref_ts:
            past_events.append(item)
        elif item.due_ts < ref_ts + _7_DAYS:
            upcoming_events.append(item)
        else:
            future_events.append(item)

    # Sıralama: past → yeniden eskiye; upcoming/future → yakından uzağa
    past_events.sort(key=lambda x: x.due_ts, reverse=True)
    upcoming_events.sort(key=lambda x: x.due_ts)
    future_events.sort(key=lambda x: x.due_ts)

    return EventsResponse(
        past_events=past_events,
        upcoming_events=upcoming_events,
        future_events=future_events,
        reference_date_str=format_date_tr(ref_ts),
        user_id=uid,
    )


# ─────────────────────────────────────────────────────────────────
# Yardımcı: tek EventItem oluştur
# ─────────────────────────────────────────────────────────────────

def _make_event_item(
    event_id: int,
    event_type: str,
    course_id: int,
    title: str,
    due_ts: int,
    is_submitted: bool,
    course_map: Dict[int, str],
    ref_ts: int,
) -> EventItem:
    return EventItem(
        event_id=event_id,
        event_type=event_type,
        course_id=course_id,
        course_name=course_map.get(course_id, f"Kurs {course_id}"),
        title=title,
        due_ts=due_ts,
        due_date_str=format_date_tr(due_ts),
        is_submitted=is_submitted,
        days_until_due=days_until(due_ts, ref_ts),
    )

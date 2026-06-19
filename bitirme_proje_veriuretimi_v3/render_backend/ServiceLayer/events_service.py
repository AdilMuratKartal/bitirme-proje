"""
render_backend/ServiceLayer/events_service.py — Etkinlikler Sayfası Servisi

get_events(uid, dao, reference_date=None) → EventsResponse

dash-only: etkinlikler dash_module_status'taki assign + quiz modüllerinden türetilir
(dash_upcoming_events boş olduğu için). Son tarih sırası:
  expected_date (varsa) → completion_time (tamamlandıysa) → first_view_time.

Kategori (ref_ts'e göre): past / upcoming (≤7 gün) / future.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import EventItem, EventsResponse
from ServiceLayer.common_utils import course_label, days_until, format_date_tr

_7_DAYS = 7 * 86_400
_EVENT_TYPES = {"assign": "assignment", "quiz": "quiz", "workshop": "assignment"}


def _date_to_ts(date_val) -> Optional[int]:
    if date_val is None or (isinstance(date_val, float) and pd.isna(date_val)):
        return None
    try:
        if isinstance(date_val, str):
            d = datetime.strptime(date_val[:10], "%Y-%m-%d")
        else:
            d = datetime(date_val.year, date_val.month, date_val.day)
        return int(d.replace(tzinfo=timezone.utc).timestamp())
    except Exception:
        return None


def get_events(
    uid: int,
    dao: MoodleDAO,
    reference_date: Optional[datetime] = None,
) -> EventsResponse:
    ref_ts = (
        int(reference_date.replace(tzinfo=timezone.utc).timestamp())
        if reference_date
        else int(time.time())
    )

    mod_df = dao.get_dash_module_status(uid)
    all_items: List[EventItem] = []

    if not mod_df.empty:
        for _, row in mod_df.iterrows():
            mtype = str(row.get("module_type", "")).strip().lower()
            if mtype not in _EVENT_TYPES:
                continue

            due_ts = _date_to_ts(row.get("expected_date"))
            if due_ts is None and pd.notna(row.get("completion_time")) and row.get("completion_time"):
                due_ts = int(row["completion_time"])
            if due_ts is None and pd.notna(row.get("first_view_time")) and row.get("first_view_time"):
                due_ts = int(row["first_view_time"])
            if due_ts is None:
                continue

            cid = int(row["courseid"]) if pd.notna(row.get("courseid")) else 0
            title = str(row.get("display_name") or "").strip()
            if not title or title.lower() in ("nombre", "none", "nan"):
                title = "Ödev" if mtype != "quiz" else "Quiz"

            all_items.append(EventItem(
                event_id=int(row["cmid"]) if pd.notna(row.get("cmid")) else 0,
                event_type=_EVENT_TYPES[mtype],
                course_id=cid,
                course_name=course_label(cid, None),
                title=title,
                due_ts=due_ts,
                due_date_str=format_date_tr(due_ts),
                is_submitted=bool(row.get("is_completed")),
                days_until_due=days_until(due_ts, ref_ts),
            ))

    past, upcoming, future = [], [], []
    for item in all_items:
        if item.due_ts < ref_ts:
            past.append(item)
        elif item.due_ts < ref_ts + _7_DAYS:
            upcoming.append(item)
        else:
            future.append(item)

    past.sort(key=lambda x: x.due_ts, reverse=True)
    upcoming.sort(key=lambda x: x.due_ts)
    future.sort(key=lambda x: x.due_ts)

    return EventsResponse(
        past_events=past,
        upcoming_events=upcoming,
        future_events=future,
        reference_date_str=format_date_tr(ref_ts),
        user_id=uid,
    )

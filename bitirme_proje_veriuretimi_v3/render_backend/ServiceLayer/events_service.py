"""
render_backend/ServiceLayer/events_service.py — Etkinlikler Servisi (flat)

get_events(uid, dao) → EventsResponse

dash_module_status'tan assign/quiz/workshop modüllerini düz liste olarak döndürür.
Sınıflandırma (past/upcoming/future) frontend'de yapılır.

Tarih önceliği:  expected_date → completion_time → first_view_time
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import FlatEventItem, EventsResponse
from ServiceLayer.common_utils import course_label

_EVENT_TYPES = {"assign", "quiz", "workshop"}


def _date_to_ts(date_val) -> Optional[int]:
    """Tarih değerini Unix timestamp'e çevirir. None ise None döner."""
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


def _ts_to_date_str(ts: int) -> str:
    """Unix timestamp → 'YYYY-MM-DD' string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def get_events(
    uid: int,
    dao: MoodleDAO,
) -> EventsResponse:
    now_ts = int(time.time())
    mod_df = dao.get_dash_module_status(uid)
    items: List[FlatEventItem] = []

    if not mod_df.empty:
        for _, row in mod_df.iterrows():
            mtype = str(row.get("module_type", "")).strip().lower()
            if mtype not in _EVENT_TYPES:
                continue

            # Tarih çözümleme: expected_date → completion_time → first_view_time
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

            days_until = (due_ts - now_ts) // 86_400
            is_completed = bool(row.get("is_completed"))

            items.append(FlatEventItem(
                userid=uid,
                courseid=cid,
                cmid=int(row["cmid"]) if pd.notna(row.get("cmid")) else 0,
                module_type=mtype,
                display_name=title,
                course_name=course_label(cid, None),
                course_short="",
                event_date=_ts_to_date_str(due_ts),
                timestart=due_ts,
                days_until=days_until,
                is_overdue=(days_until < 0) and (not is_completed),
                is_completed=is_completed,
            ))

    # timestart'a göre sırala (en yakın deadline önce)
    items.sort(key=lambda x: x.timestart)

    return EventsResponse(items=items, user_id=uid)

"""
render_backend/ServiceLayer/learning_path_service.py — Öğrenme Yolu Sayfası Servisi

get_learning_path(uid, dao, days=30) → LearningPathResponse

dash-only: timeline → dash_module_status (tamamlama/ilk görüntüleme zamanları),
grafik → dash_daily_sessions. Anonim veri seti zaman ekseni gerçek "şimdi"den farklı
olduğu için son N gün penceresi verinin KENDİ en güncel tarihine göre hesaplanır.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import ChartjsSeries, LearningPathResponse, TimelineItem
from ServiceLayer.common_utils import (
    CHART_COLORS,
    course_label,
    event_type_for_module,
    format_date_short,
    format_date_tr,
)

_DAY = 86_400


def _date_to_ts(date_val) -> int:
    """'YYYY-MM-DD' (veya date) → UTC unix saniye."""
    if isinstance(date_val, str):
        d = datetime.strptime(date_val[:10], "%Y-%m-%d")
    else:
        d = datetime(date_val.year, date_val.month, date_val.day)
    return int(d.replace(tzinfo=timezone.utc).timestamp())


def get_learning_path(uid: int, dao: MoodleDAO, days: int = 30) -> LearningPathResponse:
    mod_df = dao.get_dash_module_status(uid)
    sess_df = dao.get_dash_daily_sessions(uid)

    timeline = _build_timeline(mod_df, limit=60)
    labels, datasets = _build_chart(sess_df, days)

    return LearningPathResponse(
        timeline=timeline,
        chartjs_labels=labels,
        chartjs_datasets=datasets,
        user_id=uid,
    )


def _build_timeline(mod_df: pd.DataFrame, limit: int) -> List[TimelineItem]:
    if mod_df.empty:
        return []

    items: List[TimelineItem] = []
    for _, row in mod_df.iterrows():
        completed = bool(row.get("is_completed"))
        ts_val = row.get("completion_time") if completed else row.get("first_view_time")
        if pd.isna(ts_val) or not ts_val:
            ts_val = row.get("first_view_time") or row.get("completion_time")
        if pd.isna(ts_val) or not ts_val:
            continue
        ts = int(ts_val)
        mtype = str(row.get("module_type", "")).strip().lower()
        cid = int(row["courseid"]) if pd.notna(row.get("courseid")) else 0
        items.append(TimelineItem(
            timestamp=ts,
            date_str=format_date_tr(ts),
            event_type=event_type_for_module(mtype),
            course_id=cid,
            course_name=course_label(cid, None),
            grade=None,
            is_completed=completed,
            details=f"{mtype or 'modül'} — {'tamamlandı' if completed else 'görüntülendi'}",
        ))

    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items[:limit]


def _build_chart(sess_df: pd.DataFrame, days: int):
    """dash_daily_sessions → son `days` günlük (verinin kendi penceresine göre) seri."""
    if sess_df.empty:
        return [], []

    sess = sess_df.copy()
    sess["ts"] = sess["activity_date"].map(_date_to_ts)
    sess = sess.sort_values("ts")

    max_ts = int(sess["ts"].max())
    since_ts = max_ts - days * _DAY
    window = sess[sess["ts"] >= since_ts]
    if window.empty:
        window = sess.tail(days)

    # Gün bazlı tek satıra indir (aynı gün birden çok satır olursa topla)
    by_day = (
        window.groupby("ts")[["session_count", "total_minutes", "page_views"]]
        .sum()
        .reset_index()
        .sort_values("ts")
    )

    labels = [format_date_short(int(t)) for t in by_day["ts"]]
    sessions_series = [float(x) for x in by_day["session_count"]]
    pageview_series = [float(x) for x in by_day["page_views"]]

    datasets = [
        ChartjsSeries(
            label="Oturum",
            data=sessions_series,
            borderColor=CHART_COLORS["module"],
            backgroundColor=CHART_COLORS["module"] + "33",
        ),
        ChartjsSeries(
            label="Sayfa Görüntüleme",
            data=pageview_series,
            borderColor=CHART_COLORS["quiz"],
            backgroundColor=CHART_COLORS["quiz"] + "33",
        ),
    ]
    return labels, datasets

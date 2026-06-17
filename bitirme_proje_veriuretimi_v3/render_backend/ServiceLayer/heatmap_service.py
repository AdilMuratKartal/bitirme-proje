"""
render_backend/ServiceLayer/heatmap_service.py — Aktivite Heatmap Servisi

get_heatmap(uid, dao) → HeatmapResponse

dash_06_activity_heatmap tablosundan 7×24 = 168 hücre okur.
Pre-compute yapılmamışsa boş liste döner (frontend graceful handle eder).
"""

from __future__ import annotations

from typing import List

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import HeatmapCell, HeatmapResponse


def get_heatmap(uid: int, dao: MoodleDAO) -> HeatmapResponse:
    df = dao.get_dash_activity_heatmap(uid)

    if df.empty:
        return HeatmapResponse(data=[], user_id=uid)

    cells: List[HeatmapCell] = [
        HeatmapCell(
            weekday=int(row["weekday"]),
            hour=int(row["hour"]),
            event_count=int(row["event_count"]),
            session_starts=int(row["session_starts"]),
        )
        for _, row in df.iterrows()
    ]
    return HeatmapResponse(data=cells, user_id=uid)

"""
render_backend/ServiceLayer/modules_service.py — Modül Durumları Servisi

get_modules(uid, dao) → ModuleStatusResponse
"""

from __future__ import annotations

from typing import List
import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import ModuleStatusItem, ModuleStatusResponse

def get_modules(uid: int, dao: MoodleDAO) -> ModuleStatusResponse:
    mod_df = dao.get_dash_module_status(uid)
    items: List[ModuleStatusItem] = []

    if not mod_df.empty:
        for _, row in mod_df.iterrows():
            cid = int(row["courseid"]) if pd.notna(row.get("courseid")) else 0
            cmid = int(row["cmid"]) if pd.notna(row.get("cmid")) else 0
            mtype = str(row.get("module_type", "")).strip().lower()
            title = str(row.get("display_name") or "").strip()
            is_completed = bool(row.get("is_completed"))
            
            completion_time = row.get("completion_time")
            completion_time = int(completion_time) if pd.notna(completion_time) and completion_time else None
                
            first_view_time = row.get("first_view_time")
            first_view_time = int(first_view_time) if pd.notna(first_view_time) and first_view_time else None
                
            expected_date = row.get("expected_date")
            expected_date = str(expected_date) if pd.notna(expected_date) and expected_date else None

            items.append(ModuleStatusItem(
                courseid=cid,
                cmid=cmid,
                module_type=mtype,
                display_name=title,
                is_completed=is_completed,
                completion_time=completion_time,
                first_view_time=first_view_time,
                expected_date=expected_date,
            ))

    return ModuleStatusResponse(items=items, user_id=uid)

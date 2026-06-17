"""
render_backend/orchestration/orchestration.py — BatchOrchestrator

İki mod:
  MOD A (Hot Path): get_student_analysis(uid, dao)
    → FRESH ise cache'den dön  (~50ms, predict() yok)
    → STALE/PENDING ise predict() çağır → yaz → dön  (~2-4s)

  MOD B (Cold Path): run_weekly_batch(week, dao)
    → Tüm aktif öğrenciler, 500'lük chunk, toplu predict() → yaz
"""

from __future__ import annotations

import gc
import time
import logging
from typing import Dict, List, Optional

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from api_gateway_orchestration.orchestration.check_freshness import freshness_status
from api_gateway_orchestration.orchestration.cache import get_cached_analysis, get_full_cached_result
from features.predict import predict_student_success

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
MAX_RETRIES = 3


def _chunks(lst: List, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _risk_premodel_to_db_row(result: Dict) -> Dict:
    """
    predict_student_success() çıktısını DB satır formatına dönüştürür.
    pass_probability + will_pass API'ye forward edilmek üzere eklenir;
    upsert SQL'i named-param kullandığından fazladan anahtarları yok sayar.
    """
    return {
        "user_id":          result["userid"],
        "risk_score":       result["risk_score"],
        "risk_level":       result["risk_level"],
        "predicted_grade":  None,
        "model_confidence": result["pass_probability"],
        "pass_probability": result["pass_probability"],
        "will_pass":        result["will_pass"],
    }


def _basic_from_result(result: Dict, tables: Dict) -> Dict:
    """risk_premodel sonucu + tablolardan temel öğrenci değerlerini hesaplar."""
    uid = result["userid"]
    import pandas as pd
    import numpy as np

    grd  = tables.get("mdl_grade_grades", pd.DataFrame())
    comp = tables.get("mdl_course_modules_completion", pd.DataFrame())
    logs = tables.get("mdl_logstore_standard_log", pd.DataFrame())

    u_grd  = grd[grd["userid"] == uid] if not grd.empty else pd.DataFrame()
    gpa    = float(u_grd["finalgrade"].mean()) if not u_grd.empty else 0.0

    u_comp    = comp[comp["userid"] == uid] if not comp.empty else pd.DataFrame()
    completed = int((u_comp["completionstate"] == 1).sum()) if not u_comp.empty else 0

    u_logs = logs[logs["userid"] == uid] if not logs.empty else pd.DataFrame()
    if not u_logs.empty:
        max_ts = int(u_logs["timecreated"].max())
        streak = int(len(u_logs[
            (u_logs["timecreated"] >= max_ts - 7 * 86_400) &
            (u_logs["action"] == "view")
        ]))
    else:
        streak = 0

    return {
        "user_id":           uid,
        "gpa":               round(gpa, 2),
        "total_courses":     int(tables.get("mdl_grade_items", pd.DataFrame())["courseid"].nunique()) or 3,
        "completed_credits": completed,
        "login_streak":      streak,
    }


class BatchOrchestrator:

    def __init__(self, dao: MoodleDAO, models=None):
        self.dao = dao

    # ─────────────────────────────────────────────────────────
    # MOD A — Hot Path: Tek Öğrenci (on-demand inference)
    # ─────────────────────────────────────────────────────────

    def get_student_analysis(self, uid: int, dao: MoodleDAO) -> Dict:
        """
        FRESH → DB'den dön (predict() çağrılmaz, ~50ms).
        STALE/PENDING → predict() çağır, yaz, dön (~2-4s).
        """
        cached, status = get_cached_analysis(uid, dao)

        if status == "FRESH":
            return {
                "data": get_full_cached_result(uid, dao),
                "meta": {"freshness": "fresh", "computed_at": str(cached["computed_at"])}
            }

        # STALE veya PENDING → on-demand inference
        tables = dao.get_batch_tables([uid])
        risk_premodel_raw = predict_student_success(uid, tables)

        risk_premodel_row = _risk_premodel_to_db_row(risk_premodel_raw)
        basic_row         = _basic_from_result(risk_premodel_raw, tables)

        with dao.transaction() as session:
            dao.upsert_mimo_analysis([risk_premodel_row], session)
            dao.upsert_basic_values([basic_row], session)

        return {
            "data": {
                "risk_premodel_analysis": risk_premodel_row,
                "basic_values":          basic_row,
            },
            "meta": {"freshness": "computed_now", "was": status.lower()}
        }

    # ─────────────────────────────────────────────────────────
    # MOD B — Cold Path: Haftalık Toplu Batch
    # ─────────────────────────────────────────────────────────

    def run_weekly_batch(self, week: int, dao: Optional[MoodleDAO] = None) -> Dict:
        """
        Tüm aktif öğrenciler için haftalık batch inference.
        500'lük chunk, her chunk tek transaction.
        Başarısız chunk loglanır, devam edilir.
        """
        _dao = dao or self.dao
        t_start = time.time()
        active_ids = _dao.get_active_student_ids(week=week)
        total = len(active_ids)
        processed = 0
        failed_ids: List[int] = []

        logger.info("weekly_batch_start", extra={"week": week, "total": total})

        for batch in _chunks(active_ids, BATCH_SIZE):
            success = False
            for attempt in range(MAX_RETRIES):
                try:
                    tables = _dao.get_batch_tables(batch)

                    risk_premodel_rows, basic_rows = [], []
                    for uid in batch:
                        raw = predict_student_success(uid, tables)
                        risk_premodel_rows.append(_risk_premodel_to_db_row(raw))
                        basic_rows.append(_basic_from_result(raw, tables))

                    with _dao.transaction() as session:
                        _dao.upsert_mimo_analysis(risk_premodel_rows, session)
                        _dao.upsert_basic_values(basic_rows, session)

                    gc.collect()
                    processed += len(batch)
                    success = True
                    break

                except Exception as exc:
                    logger.warning(
                        "batch_chunk_attempt_failed",
                        extra={"batch_start": batch[0], "attempt": attempt + 1, "error": str(exc)}
                    )
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(5 * (attempt + 1))

            if not success:
                failed_ids.extend(batch)
                logger.error("batch_chunk_permanent_fail",
                             extra={"batch_start": batch[0], "size": len(batch)})

        duration = round(time.time() - t_start, 1)
        summary = {
            "week":       week,
            "total":      total,
            "processed":  processed,
            "failed":     len(failed_ids),
            "duration_s": duration,
        }
        logger.info("weekly_batch_complete", extra=summary)
        return summary

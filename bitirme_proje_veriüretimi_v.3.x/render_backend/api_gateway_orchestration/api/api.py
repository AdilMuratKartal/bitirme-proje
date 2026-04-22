"""
render_backend/api/api.py — FastAPI Uygulaması

Web Service entrypoint. Sıfır iş mantığı, sıfır SQL, sıfır doğrudan model çağrısı.
Tüm iş mantığı Orchestration katmanına delege edilir.

Render startCommand:
    gunicorn api_gateway_orchestration.api.api:app \
      --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 60
"""

from __future__ import annotations

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse

# render_backend/ kökünü sys.path'e ekle
_HERE = os.path.dirname(os.path.abspath(__file__))
_RENDER_BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _RENDER_BACKEND)

from dependencies import get_dao
from Moodle_DAO.moodle_dao_schema import MoodleDAO
from api_gateway_orchestration.api.gateway import verify_firebase_token
from api_gateway_orchestration.api.middleware import register_middleware
from api_gateway_orchestration.orchestration.model_registry import ModelRegistry
from api_gateway_orchestration.orchestration.orchestration import BatchOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Singleton'lar (process boyunca bir kez yüklenir) ─────────────
_models: ModelRegistry | None = None
_orchestrator: BatchOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _models, _orchestrator
    logger.info("startup: modeller yükleniyor")
    _models = ModelRegistry.load_all()
    _orchestrator = BatchOrchestrator(dao=None, models=_models)  # dao inject point
    logger.info("startup: hazır")
    yield
    logger.info("shutdown: bağlantılar kapatılıyor")


app = FastAPI(
    title="Learning-Insight API",
    version="1.0.0",
    lifespan=lifespan,
)

register_middleware(app)


# ── Yardımcı ─────────────────────────────────────────────────────

def _get_orchestrator(dao: MoodleDAO) -> BatchOrchestrator:
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Servis başlatılıyor")
    _orchestrator.dao = dao
    return _orchestrator


# ── Endpoints ────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Render health check. Model yüklü ise ok."""
    return {"status": "ok", "models_loaded": _models is not None and _models.loaded}


@app.get("/api/student/{uid}/dashboard")
async def get_dashboard(
    uid: int,
    dao: Annotated[MoodleDAO, Depends(get_dao)],
    token: Annotated[dict, Depends(verify_firebase_token)],
):
    """
    Öğrenci özet dashboard'u.
    FRESH → cache'den (~50ms). STALE/PENDING → on-demand predict (~2-4s).
    """
    orch = _get_orchestrator(dao)
    result = orch.get_student_analysis(uid, dao)
    return result


@app.get("/api/student/{uid}/grades")
async def get_grades(
    uid: int,
    dao: Annotated[MoodleDAO, Depends(get_dao)],
    token: Annotated[dict, Depends(verify_firebase_token)],
):
    """MIMO analiz sonuçları (risk skoru, tahmini not)."""
    orch = _get_orchestrator(dao)
    cached = dao.get_mimo_analysis(uid)
    if cached is None:
        return JSONResponse(
            {"status": "pending", "message": "Analiz henüz hazır değil"},
            status_code=202
        )
    return cached


@app.get("/api/student/{uid}/competencies")
async def get_competencies(
    uid: int,
    dao: Annotated[MoodleDAO, Depends(get_dao)],
    token: Annotated[dict, Depends(verify_firebase_token)],
):
    """HKAR konu önerileri."""
    recs = dao.get_hkrt_analysis(uid)
    if not recs:
        return JSONResponse(
            {"status": "pending", "message": "Öneri analizi henüz hazır değil"},
            status_code=202
        )
    return {"recommendations": recs}


@app.get("/api/student/{uid}/basic")
async def get_basic_values(
    uid: int,
    dao: Annotated[MoodleDAO, Depends(get_dao)],
    token: Annotated[dict, Depends(verify_firebase_token)],
):
    """GPA, streak, tamamlanan ders sayısı."""
    values = dao.get_basic_values(uid)
    if values is None:
        return JSONResponse(
            {"status": "pending", "message": "Temel değerler henüz hazır değil"},
            status_code=202
        )
    return values


@app.post("/api/batch/run-weekly")
async def trigger_weekly_batch(
    dao: Annotated[MoodleDAO, Depends(get_dao)],
    token: Annotated[dict, Depends(verify_firebase_token)],
):
    """
    Manuel haftalık batch tetikleyici (test/admin).
    Production'da bu endpoint yerine Cron Job kullanılır.
    """
    import asyncio
    from datetime import datetime

    orch = _get_orchestrator(dao)
    week = datetime.utcnow().isocalendar()[1]

    # Background task olarak başlat — uzun süren işlemi bloklamaz
    asyncio.create_task(asyncio.to_thread(orch.run_weekly_batch, week, dao))
    return {"status": "started", "week": week}


@app.get("/api/batch/status")
async def batch_status(
    dao: Annotated[MoodleDAO, Depends(get_dao)],
    token: Annotated[dict, Depends(verify_firebase_token)],
):
    """Son batch durumu — şimdilik en son computed_at bazlı özet."""
    from sqlalchemy import text
    session = dao._session()
    try:
        result = session.execute(
            text("SELECT MAX(computed_at) as last_run, COUNT(*) as total_students "
                 "FROM mdl_mimo_analysis")
        ).fetchone()
        return {"last_run": str(result[0]), "total_students": result[1]}
    finally:
        session.close()

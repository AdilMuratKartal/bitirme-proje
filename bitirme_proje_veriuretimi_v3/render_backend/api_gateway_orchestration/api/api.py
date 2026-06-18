"""
render_backend/api/api.py — FastAPI Uygulaması

Web Service entrypoint. Sıfır iş mantığı, sıfır SQL, sıfır doğrudan model çağrısı.
Tüm iş mantığı Orchestration ve ServiceLayer katmanlarına delege edilir.

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
from sqlalchemy import text

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
from schemas import (
    CompetenciesResponse,
    CourseAnalyticsResponse,
    EventsResponse,
    GradesPageResponse,
    HeatmapResponse,
    HomepageResponse,
    LearningPathResponse,
)
from ServiceLayer.grades_service import get_grades_page
from ServiceLayer.homepage_service import get_homepage
from ServiceLayer.learning_path_service import get_learning_path
from ServiceLayer.competencies_service import get_competencies
from ServiceLayer.events_service import get_events
from ServiceLayer.heatmap_service import get_heatmap
from ServiceLayer.course_analytics_service import get_course_analytics

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
    _orchestrator = BatchOrchestrator(dao=None, models=_models)
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


def get_current_userid(
    token: Annotated[dict, Depends(verify_firebase_token)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
) -> int:
    """
    Doğrulanmış Firebase token'ından Moodle userid'sini çözer.
    Akış: Bearer token → verify_firebase_token → uid → student_registry lookup.
    Frontend kendi id'sini göndermez; userid daima sunucuda token'dan türetilir
    (IDOR koruması). Eşleme yoksa 403.
    """
    firebase_uid = token.get("uid", "")
    # Dev fallback: Firebase SDK kurulu değilse gateway "dev_user" döndürür.
    if firebase_uid == "dev_user":
        return int(os.environ.get("DEV_MOODLE_USERID", "2"))
    userid = dao.get_userid_by_firebase_uid(firebase_uid)
    if userid is None:
        raise HTTPException(status_code=403, detail="Kullanıcı Moodle'da bulunamadı")
    return userid


# ── Endpoints ────────────────────────────────────────────────────

@app.get("/health")
async def health(dao: Annotated[MoodleDAO, Depends(get_dao)]):
    """Render health check. DB ping + model yüklü kontrolü."""
    session = dao._session()
    try:
        session.execute(text("SELECT 1"))
    finally:
        session.close()
    return {"status": "ok", "models_loaded": _models is not None and _models.loaded}


@app.get("/api/student/me/home", response_model=HomepageResponse)
async def home(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Ana sayfa özet kartı: kullanıcı adı, yetkinlik %, kurslar, notlar, etkinlikler."""
    return get_homepage(userid, dao)


@app.get("/api/student/me/dashboard")
async def get_dashboard(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """
    Öğrenci özet dashboard'u.
    FRESH → cache'den (~50ms). STALE/PENDING → on-demand predict (~2-4s).
    """
    orch = _get_orchestrator(dao)
    return orch.get_student_analysis(userid, dao)


@app.get("/api/student/me/grades", response_model=GradesPageResponse)
async def grades(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Notlar sayfası: devam eden kurslar (risk_premodel + freshness) + biten kurslar (arşiv)."""
    orch = _get_orchestrator(dao)
    return get_grades_page(userid, dao, orch)


@app.get("/api/student/me/learning-path", response_model=LearningPathResponse)
async def learning_path(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Öğrenme yolu sayfası: son 30 günün aktivite timeline'ı + Chart.js veri seti."""
    return get_learning_path(userid, dao)


@app.get("/api/student/me/competencies", response_model=CompetenciesResponse)
async def competencies(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Yetkinlikler sayfası: 4 tür (OKUMA/FORUM/İZLEME/ÖDEV) log-tabanlı tamamlama oranları."""
    return get_competencies(userid, dao)


@app.get("/api/student/me/events", response_model=EventsResponse)
async def events(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Etkinlikler sayfası: quiz + ödev deadline'ları (geçmiş/yaklaşan/gelecek)."""
    return get_events(userid, dao)


@app.get("/api/student/me/basic")
async def get_basic_values(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """GPA, streak, tamamlanan ders sayısı."""
    values = dao.get_basic_values(userid)
    if values is None:
        return JSONResponse(
            {"status": "pending", "message": "Temel değerler henüz hazır değil"},
            status_code=202,
        )
    return values


@app.get("/api/student/me/heatmap", response_model=HeatmapResponse)
async def heatmap(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Aktivite heatmap: weekday × hour bazlı 7×24 = 168 hücre."""
    return get_heatmap(userid, dao)


@app.get("/api/student/me/course-analytics", response_model=CourseAnalyticsResponse)
async def course_analytics(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Kurs analitiği: assign/quiz tamamlama oranları + forum/page metrikleri."""
    return get_course_analytics(userid, dao)


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
    from datetime import datetime, timezone

    orch = _get_orchestrator(dao)
    week = datetime.now(timezone.utc).isocalendar()[1]
    asyncio.create_task(asyncio.to_thread(orch.run_weekly_batch, week, dao))
    return {"status": "started", "week": week}


@app.get("/api/batch/status")
async def batch_status(
    dao: Annotated[MoodleDAO, Depends(get_dao)],
    token: Annotated[dict, Depends(verify_firebase_token)],
):
    """Son batch durumu — en son computed_at bazlı özet."""
    session = dao._session()
    try:
        result = session.execute(
            text("SELECT MAX(computed_at) as last_run, COUNT(*) as total_students "
                 "FROM mdl_mimo_analysis")
        ).fetchone()
        return {"last_run": str(result[0]), "total_students": result[1]}
    finally:
        session.close()

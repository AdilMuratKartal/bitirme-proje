"""
render_backend/api/api.py — FastAPI Uygulaması (dash-only)

Web Service entrypoint. Sıfır iş mantığı, sıfır SQL, sıfır model çağrısı.
Tüm veriler dash_* precompute tablolarından okunur (mdl_* canlı sorgu YOK).
Risk değerleri offline hesaplanıp dash_risk tablosuna yazılır; burada yalnızca okunur.

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup: dash-only API hazır (model yüklemesi yok)")
    yield
    logger.info("shutdown: bağlantılar kapatılıyor")


app = FastAPI(
    title="Learning-Insight API",
    version="2.0.0",
    lifespan=lifespan,
)

register_middleware(app)


# ── Yardımcı ─────────────────────────────────────────────────────

def get_current_userid(
    token: Annotated[dict, Depends(verify_firebase_token)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
) -> int:
    """
    Doğrulanmış Firebase token'ından Moodle userid'sini çözer.
    Öncelikli akış: Token içindeki Custom Claims ('moodle_userid') doğrudan okunur (sıfır DB sorgusu).
    Yedek akış (fallback): firebase_uid -> student_registry lookup.
    """
    # 1. Öncelikli olarak Custom Claims kontrol edilir (sıfır DB sorgusu)
    moodle_userid = token.get("moodle_userid")
    if moodle_userid is not None:
        return int(moodle_userid)

    # 2. Yedek plan (Claims henüz yazılmamışsa veya dev modundaysa): DB sorgusu
    firebase_uid = token.get("uid", "")
    # Dev fallback: Firebase SDK kurulu değilse gateway "dev_user" döndürür.
    if firebase_uid == "dev_user":
        return int(os.environ.get("DEV_MOODLE_USERID", "2"))
    userid = dao.get_userid_by_firebase_uid(firebase_uid)
    if userid is None:
        raise HTTPException(status_code=403, detail="Kullanıcı Moodle'da bulunamadı")
    return userid



def _build_dashboard(userid: int, dao: MoodleDAO) -> dict:
    """Risk (dash_risk) + temel değerler (dash_user_stats) → dashboard yanıtı."""
    risk = dao.get_dash_risk(userid)
    stats = dao.get_dash_user_stats(userid) or {}

    if risk:
        risk_block = {
            "risk_score":       risk.get("risk_score"),
            "risk_level":       risk.get("risk_level"),
            "pass_probability": risk.get("pass_probability"),
            "will_pass":        risk.get("will_pass"),
            "predicted_grade":  risk.get("predicted_grade"),
        }
        freshness = "fresh"
    else:
        risk_block = {
            "risk_score": None, "risk_level": None,
            "pass_probability": None, "will_pass": None, "predicted_grade": None,
        }
        freshness = "pending"

    basic_values = {
        "gpa":              stats.get("avg_grade"),
        "streak":           stats.get("study_streak_days"),
        "late_assignments": stats.get("late_assignment_count"),
        "focus_score":      stats.get("focus_score"),
    }
    return {
        "risk_premodel_analysis": risk_block,
        "basic_values": basic_values,
        "freshness": freshness,
    }


# ── Endpoints ────────────────────────────────────────────────────

@app.get("/health")
async def health(dao: Annotated[MoodleDAO, Depends(get_dao)]):
    """Render health check. DB ping."""
    session = dao._session()
    try:
        session.execute(text("SELECT 1"))
    finally:
        session.close()
    return {"status": "ok", "mode": "dash-only"}


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
    """Öğrenci özet dashboard'u: risk (dash_risk precompute) + temel değerler (dash_user_stats)."""
    return _build_dashboard(userid, dao)


@app.get("/api/student/me/grades", response_model=GradesPageResponse)
async def grades(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Notlar sayfası: devam eden + biten kurslar (dash_course_progress + dash_risk)."""
    return get_grades_page(userid, dao)


@app.get("/api/student/me/learning-path", response_model=LearningPathResponse)
async def learning_path(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Öğrenme yolu sayfası: aktivite timeline'ı (dash_module_status) + Chart.js (dash_daily_sessions)."""
    return get_learning_path(userid, dao)


@app.get("/api/student/me/competencies", response_model=CompetenciesResponse)
async def competencies(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Yetkinlikler sayfası: 4 tür (OKUMA/FORUM/İZLEME/ÖDEV) dash_module_status tamamlama oranları."""
    return get_competencies(userid, dao)


@app.get("/api/student/me/events", response_model=EventsResponse)
async def events(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """Etkinlikler sayfası: quiz + ödev deadline'ları (dash_module_status)."""
    return get_events(userid, dao)


@app.get("/api/student/me/basic")
async def get_basic_values(
    userid: Annotated[int, Depends(get_current_userid)],
    dao: Annotated[MoodleDAO, Depends(get_dao)],
):
    """GPA, streak, odak skoru vb. — dash_user_stats'tan."""
    values = dao.get_dash_user_stats(userid)
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
    """Kurs analitiği: assign/quiz tamamlama oranları + forum/page metrikleri (dash_course_analytics)."""
    return get_course_analytics(userid, dao)

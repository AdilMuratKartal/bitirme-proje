"""
render_backend/dependencies.py — Tek DI Fabrikası

Her iki servis (Web Service + Cron Job) buradan MoodleDAO alır.
FastAPI: get_dao() → Depends() ile
Cron Job: build_dao() → doğrudan çağrı ile
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from Moodle_DAO.moodle_dao_schema import MoodleDAO

_engine = create_engine(
    os.environ["DATABASE_URL"],
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
    pool_recycle=1800,
    # sslmode URL'den gelir:
    #   internal URL (sslmode yok) → SSL'siz baglanir (Render internal SSL sunmaz)
    #   external URL (?sslmode=require) → SSL zorlanir
)

_SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_dao() -> MoodleDAO:
    """FastAPI Depends() ile kullanılır."""
    return MoodleDAO(session_factory=_SessionFactory)


def build_dao() -> MoodleDAO:
    """Cron Job ve non-FastAPI bağlamlarda doğrudan çağrılır."""
    return MoodleDAO(session_factory=_SessionFactory)

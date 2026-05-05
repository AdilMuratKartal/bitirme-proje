"""
render_backend/api/middleware.py — CORS + Logging Middleware

Render'a deploy edilen FastAPI uygulamasına bağlanır.
"""

from __future__ import annotations

import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def register_middleware(app: FastAPI) -> None:
    """CORS ve request logging middleware'lerini kaydet."""

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Production'da Firebase Hosting domain'i ile kısıtla
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        t = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - t) * 1000, 1)
        logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
        )
        return response

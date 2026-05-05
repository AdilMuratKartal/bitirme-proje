"""
render_backend/orchestration/check_freshness.py — Cache Freshness Kararları

"Cache" = mdl_mimo_analysis tablosundaki computed_at timestamp.
Ayrı Redis/Memcached kullanılmaz.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

STALENESS_THRESHOLD = timedelta(days=7)


def freshness_status(computed_at: Optional[datetime]) -> str:
    """
    FRESH   → computed_at 7 günden yeni — DB'den oku, predict() yok
    STALE   → computed_at 7 günden eski — on-demand predict(), güncelle
    PENDING → kayıt yok — ilk kez predict(), kayıt oluştur
    """
    if computed_at is None:
        return "PENDING"
    if (datetime.utcnow() - computed_at) < STALENESS_THRESHOLD:
        return "FRESH"
    return "STALE"


def is_fresh(computed_at: Optional[datetime]) -> bool:
    return freshness_status(computed_at) == "FRESH"

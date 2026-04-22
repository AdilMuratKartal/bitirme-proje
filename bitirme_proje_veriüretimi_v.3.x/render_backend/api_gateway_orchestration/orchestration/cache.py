"""
render_backend/orchestration/cache.py — DB Cache Sarmalayıcı

"Cache" katmanı: mdl_mimo_analysis ve mdl_hkrt_analysis tablolarına
erişimi saran yardımcı fonksiyonlar. DAO'yu bilir, orchestration'ı bilmez.
"""

from __future__ import annotations

from typing import Optional, Dict
from Moodle_DAO.moodle_dao_schema import MoodleDAO
from api_gateway_orchestration.orchestration.check_freshness import freshness_status


def get_cached_analysis(uid: int, dao: MoodleDAO) -> tuple[Optional[Dict], str]:
    """
    Öğrencinin analiz sonucunu ve freshness durumunu döner.
    Dönüş: (analiz_dict_or_None, "FRESH" | "STALE" | "PENDING")
    """
    cached = dao.get_mimo_analysis(uid)
    status = freshness_status(cached["computed_at"] if cached else None)
    return cached, status


def get_full_cached_result(uid: int, dao: MoodleDAO) -> Dict:
    """FRESH öğrenci için tüm analiz verilerini birleştirir."""
    mimo = dao.get_mimo_analysis(uid)
    hkrt = dao.get_hkrt_analysis(uid)
    basic = dao.get_basic_values(uid)
    return {
        "mimo_analysis": mimo,
        "hkrt_recommendations": hkrt,
        "basic_values": basic,
    }

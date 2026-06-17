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
    """
    FRESH öğrenci için tüm analiz verilerini birleştirir.
    DB satırında saklanan model_confidence (= pass_probability) üzerinden
    pass_probability + will_pass türetilir; böylece FRESH ve computed_now
    yolları aynı anahtar setini döner.
    """
    risk_premodel = dao.get_mimo_analysis(uid)
    basic         = dao.get_basic_values(uid)

    if risk_premodel is not None:
        conf = risk_premodel.get("model_confidence")
        if conf is not None:
            risk_premodel["pass_probability"] = float(conf)
            risk_premodel["will_pass"]        = int(float(conf) >= 0.5)

    return {
        "risk_premodel_analysis": risk_premodel,
        "basic_values":           basic,
    }

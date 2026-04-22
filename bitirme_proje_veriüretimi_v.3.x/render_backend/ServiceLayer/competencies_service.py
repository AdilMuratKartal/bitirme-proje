"""
render_backend/ServiceLayer/competencies_service.py — Yetkinlikler Sayfası Servisi

get_competencies(uid, dao) → CompetenciesResponse

4 yetkinlik türü (OKUMA/FORUM/İZLEME/ÖDEV), log-tabanlı tamamlama oranları.
HKAR önerileri yalnızca predicted_class için kullanılır; liste halinde dönmez.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from Moodle_DAO.moodle_dao_schema import MoodleDAO
from schemas import CompetenciesResponse, CompetencyItem
from ServiceLayer.common_utils import label_competency

# content_type sütunuyla eşleşen sabit konfigürasyon
COMPETENCY_CONFIG: Dict[str, List[str]] = {
    "OKUMA":  ["Okuma"],
    "FORUM":  ["Forum"],
    "İZLEME": ["Izleme"],
    "ÖDEV":   ["Odev"],
}


def get_competencies(uid: int, dao: MoodleDAO) -> CompetenciesResponse:
    """
    Akış:
    1. Tüm kurs modüllerini content_type'a göre grupla → total aktivite sayısı.
    2. Öğrencinin tüm loglarını çek.
    3. HKRT analiz sonucunu çek → predicted_class.
    4. Her COMPETENCY_CONFIG tipi için tamamlama oranını hesapla.
    5. CompetenciesResponse döndür.
    """
    modules_df = dao.get_course_modules_all()
    logs_df    = dao.get_activity_logs_recent(uid, since_ts=0)
    hkrt_rows  = dao.get_hkrt_analysis(uid)

    # predicted_class — HKRT analizi varsa ilk satırdan (tabloda saklanmıyor,
    # sadece mdl_hkrt_analysis'de bulunmuyor — orchestration sonucunda predict() verir).
    # Burada DB'den get_hkrt_analysis varsa predicted_class yok;
    # predicted_class bilgisi mdl_mimo_analysis.model_confidence yerine HKRT predict_class
    # olacak. Mevcut tabloda yok → None döner, frontend bunu handle eder.
    predicted_class: Optional[str] = None
    # mdl_hkrt_analysis tablosunda predicted_class sütunu yok.
    # İlerleyen sprint'te eklenebilir. Şimdilik None.

    # Log'lardan görüntülenen objectid seti
    viewed_ids: set[int] = set()
    if not logs_df.empty:
        view_logs = logs_df[logs_df["action"].isin(["view", "viewed", "submitted", "completed"])]
        viewed_ids = set(
            int(x) for x in view_logs["objectid"].dropna().tolist()
        )

    competencies: List[CompetencyItem] = []
    total_pct = 0.0

    for ctype_label, content_types in COMPETENCY_CONFIG.items():
        # Bu türe ait modüller
        if not modules_df.empty:
            type_mods = modules_df[modules_df["content_type"].isin(content_types)]
        else:
            type_mods = pd.DataFrame()

        total = len(type_mods)
        if total == 0:
            # Bu tür için modül yoksa %0
            label, explanation = label_competency(0.0, ctype_label, 0, 0)
            competencies.append(CompetencyItem(
                type=ctype_label,
                total_activities=0,
                completed=0,
                percentage=0.0,
                label=label,
                explanation_text=explanation,
            ))
            continue

        mod_ids = set(int(x) for x in type_mods["id"].tolist())
        completed = len(mod_ids & viewed_ids)
        pct = round(completed / total * 100, 1)
        total_pct += pct

        label, explanation = label_competency(pct, ctype_label, total, completed)
        competencies.append(CompetencyItem(
            type=ctype_label,
            total_activities=total,
            completed=completed,
            percentage=pct,
            label=label,
            explanation_text=explanation,
        ))

    overall = round(total_pct / len(COMPETENCY_CONFIG), 1) if competencies else 0.0

    return CompetenciesResponse(
        competencies=competencies,
        predicted_class=predicted_class,
        overall_completion=overall,
        user_id=uid,
    )

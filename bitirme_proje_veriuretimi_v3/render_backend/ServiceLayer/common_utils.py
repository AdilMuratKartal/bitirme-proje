"""
render_backend/ServiceLayer/common_utils.py — Paylaşılan Yardımcı Fonksiyonlar

Saf fonksiyonlar: DAO çağrısı yok, DB erişimi yok, model çağrısı yok.
Her ServiceLayer modülü bu dosyayı import edebilir.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

# ─────────────────────────────────────────────────────────────────
# Türkçe tarih için sabit listeler
# ─────────────────────────────────────────────────────────────────
_TR_MONTHS = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]
_TR_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# Chart.js renk paleti — event_type → hex
CHART_COLORS: dict[str, str] = {
    "quiz":       "#4F81BD",
    "assignment": "#C0504D",
    "video":      "#9BBB59",
    "module":     "#F79646",
    "forum":      "#8064A2",
    "other":      "#4BACC6",
}

# ─────────────────────────────────────────────────────────────────
# dash_* tabanlı eşlemeler (mdl_* yerine dash_module_status.module_type)
# ─────────────────────────────────────────────────────────────────

# 4 yetkinlik türü → dash_module_status.module_type değerleri
COMPETENCY_MODULE_TYPES: dict[str, list[str]] = {
    "OKUMA":  ["resource", "page", "book", "url", "folder", "label",
              "glossary", "wiki", "imscp", "data"],
    "FORUM":  ["forum", "oublog", "chat"],
    "İZLEME": ["scorm", "bigbluebuttonbn", "lesson", "pcast",
              "nanogong", "choice", "questionnaire"],
    "ÖDEV":   ["assign", "quiz", "workshop"],
}

# dash_module_status.module_type → timeline/learning-path event_type
MODULE_TYPE_TO_EVENT: dict[str, str] = {
    "assign": "assignment", "quiz": "quiz", "workshop": "assignment",
    "forum": "forum", "oublog": "forum", "chat": "forum",
    "scorm": "video", "bigbluebuttonbn": "video", "lesson": "video",
    "pcast": "video", "nanogong": "video",
    "resource": "module", "page": "module", "book": "module",
    "url": "module", "folder": "module", "label": "module",
    "glossary": "module", "wiki": "module", "imscp": "module", "data": "module",
}


def course_label(courseid: int, name: Optional[str]) -> str:
    """
    Anonim veri setinde kurs adları placeholder ('nombre') olabilir.
    Anlamlı ad yoksa "Kurs {id}" döner.
    """
    if name and str(name).strip().lower() not in ("", "nombre", "none", "nan"):
        return str(name).strip()
    return f"Kurs {courseid}"


def event_type_for_module(module_type: str) -> str:
    """dash_module_status.module_type → event_type string."""
    return MODULE_TYPE_TO_EVENT.get(str(module_type).strip().lower(), "other")


# ─────────────────────────────────────────────────────────────────
# Tarih formatı
# ─────────────────────────────────────────────────────────────────

def format_date_tr(ts: int) -> str:
    """Unix timestamp → "25 Nisan 2026, Cumartesi" (Türkçe, UTC)."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{dt.day} {_TR_MONTHS[dt.month]} {dt.year}, {_TR_DAYS[dt.weekday()]}"


def format_date_short(ts: int) -> str:
    """Unix timestamp → "25 Nis" (Chart.js ekseni için kısa format)."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{dt.day} {_TR_MONTHS[dt.month][:3]}"


# ─────────────────────────────────────────────────────────────────
# Risk hesaplamaları
# ─────────────────────────────────────────────────────────────────

def failure_risk_pct(risk_score: float) -> float:
    """risk_score (0.0–1.0) → yüzde (0.0–100.0), 1 ondalık."""
    return round(float(risk_score) * 100, 1)


def get_risk_explanation(
    risk_score: float,
    predicted_grade: float,
    course_name: str,
) -> str:
    """MIMO risk skoru → kullanıcıya gösterilecek Türkçe açıklama metni."""
    if risk_score >= 0.7:
        return (
            f"{course_name} dersinde başarısızlık riski yüksek "
            f"(tahmini not: {predicted_grade:.0f}/100). "
            "Hemen çalışmaya başlayın ve eksik konuları tamamlayın."
        )
    if risk_score >= 0.4:
        return (
            f"{course_name} dersinde orta düzeyde risk var "
            f"(tahmini not: {predicted_grade:.0f}/100). "
            "Çalışma düzeninizi artırmanız önerilir."
        )
    return (
        f"{course_name} dersinde düşük risk "
        f"(tahmini not: {predicted_grade:.0f}/100). "
        "Çalışma temponuzu koruyun."
    )


def get_risk_explanation_pending(course_name: str) -> str:
    """Freshness = PENDING durumlarda gösterilecek metin."""
    return f"{course_name} dersi için analiz hesaplanıyor. Kısa süre içinde hazır olacak."


# ─────────────────────────────────────────────────────────────────
# Yetkinlik etiketleri
# ─────────────────────────────────────────────────────────────────

def label_competency(
    pct: float,
    ctype: str,
    total: int,
    completed: int,
) -> Tuple[str, str]:
    """
    (label, explanation_text) döner.

    pct    : tamamlama yüzdesi (0–100)
    ctype  : "OKUMA" / "FORUM" / "İZLEME" / "ÖDEV"
    total  : bu türdeki toplam aktivite sayısı
    completed : görüntülenen/tamamlanan aktivite sayısı
    """
    if pct >= 80:
        label = "Mükemmel"
        text = (
            f"Toplam {total} {ctype.lower()} aktivitesinden {completed} tanesi tamamlandı. "
            "Mükemmel bir ilerleme!"
        )
    elif pct >= 60:
        label = "Yeterli"
        text = (
            f"Toplam {total} {ctype.lower()} aktivitesinden {completed} tanesi tamamlandı. "
            "Yeterli düzeyde, devam edin."
        )
    elif pct >= 40:
        label = "Geliştirilmeli"
        text = (
            f"Toplam {total} {ctype.lower()} aktivitesinden {completed} tanesi tamamlandı. "
            "Bu alanda daha fazla çalışmanız önerilir."
        )
    else:
        label = "Düşük"
        text = (
            f"Toplam {total} {ctype.lower()} aktivitesinden yalnızca {completed} tanesi tamamlandı. "
            "Bu alana öncelik vermeniz gerekiyor."
        )
    return label, text


# ─────────────────────────────────────────────────────────────────
# Not özeti (biten kurslar)
# ─────────────────────────────────────────────────────────────────

def format_grade_summary(
    final: Optional[float],
    quiz_avg: Optional[float],
    assign_avg: Optional[float],
) -> str:
    """Biten kurs için kısa not özeti metni."""
    if final is not None:
        grade = final
        if grade >= 85:
            verdict = "Çok iyi performans"
        elif grade >= 70:
            verdict = "İyi performans"
        elif grade >= 55:
            verdict = "Orta performans"
        else:
            verdict = "Düşük performans"
        return f"{verdict}, {grade:.0f}/100"

    parts = []
    if quiz_avg is not None:
        parts.append(f"Quiz ort: {quiz_avg:.0f}")
    if assign_avg is not None:
        parts.append(f"Ödev ort: {assign_avg:.0f}")
    if parts:
        return " | ".join(parts)
    return "Not verisi yok"


# ─────────────────────────────────────────────────────────────────
# Zaman farkı
# ─────────────────────────────────────────────────────────────────

def days_until(due_ts: int, ref_ts: int) -> Optional[int]:
    """
    due_ts ile ref_ts arasındaki tam gün farkı.
    Pozitif → gelecekte. 0 veya negatif → geçmişte (None döner).
    """
    diff = (due_ts - ref_ts) // 86_400
    return int(diff) if diff > 0 else None

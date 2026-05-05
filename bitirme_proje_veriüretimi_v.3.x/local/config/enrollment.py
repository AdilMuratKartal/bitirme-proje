"""
config/enrollment.py — Enrollment Dağıtım Parametreleri
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sadece PARAMETRELER burada durur. Algoritma enrollment_plan.py'dedir.

Farklı senaryo için (örn. tahmin verisi):
    config/enrollment.py içindeki sabitleri değiştir ya da
    enrollment_plan.build_enrollment_plan(..., config=my_config) şeklinde geç.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ─────────────────────────────────────────────────────────────────
# YÜK GRUPLARI
# L → hafif yük (5-6 ders)
# M → orta yük  (7-8 ders)
# H → ağır yük  (9-10 ders)
# ─────────────────────────────────────────────────────────────────
@dataclass
class LoadGroup:
    course_range: Tuple[int, int]   # (min_ders, max_ders)
    quota:        int               # kaç öğrenci bu grupta olacak


LOAD_GROUPS: Dict[str, LoadGroup] = {
    "L": LoadGroup(course_range=(5, 6),  quota=200),  #Ne kadar öğrenci ne kadar kurs alıcak dağılımları
    "M": LoadGroup(course_range=(7, 8),  quota=500),
    "H": LoadGroup(course_range=(9, 10), quota=300),
}


# ─────────────────────────────────────────────────────────────────
# SEGMENT → YÜK GRUBU AĞIRLIKLARI
# Her satır: [P(L), P(M), P(H)] — toplamı 1.0 olmalı
# ─────────────────────────────────────────────────────────────────
SEG_LOAD_WEIGHTS: Dict[str, List[float]] = {
    "S1": [0.00, 0.20, 0.80],   # Başarılı     → ağır yük tercih
    "S2": [0.10, 0.70, 0.20],   # Orta         → çoğunlukla M
    "S3": [0.40, 0.50, 0.10],   # İstikrarsız  → L/M dağılık
    "S4": [0.75, 0.25, 0.00],   # Terke meyilli → hafif yük
}


# ─────────────────────────────────────────────────────────────────
# MÜFREDAT KATMANLARİ (Curriculum Tiers)
# Kurs ID'leri: 1-15 arası, 3 katmana bölünmüş
# ─────────────────────────────────────────────────────────────────
@dataclass
class CourseTier:
    course_ids: List[int]
    weight:     float   # örnekleme ağırlığı (normalize edilmeden önce)


COURSE_TIERS: Dict[str, CourseTier] = {
    # Temel dersler: her öğrenci büyük olasılıkla buradan alır
    "foundation": CourseTier(
        course_ids=[1, 2, 3, 4, 5],    # Yazılım Tem., Veri Yapıları, NÖP, VDYS, Web
        weight=3.0,
    ),
    # Orta seviye: sık alınan zorunlu seçmeli benzeri
    "core": CourseTier(
        course_ids=[6, 7, 8, 9, 10],   # İşletim, Ağlar, Yazılım Müh., ML, YZ
        weight=2.0,
    ),
    # İleri: seçmeli / uzmanlık dersleri
    "advanced": CourseTier(
        course_ids=[11, 12, 13, 14, 15],  # Siber, Mobil, Bulut, Veri Analiti., İBE
        weight=1.0,
    ),
}

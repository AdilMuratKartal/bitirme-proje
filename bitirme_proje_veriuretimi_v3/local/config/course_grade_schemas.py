"""
config/course_grade_schemas.py — Kurs Başına Not Şemaları + Dönem Takvimi
aggregation: 10=WeightedMean | 11=SimpleWeightedMean | 13=Natural(Sum)
coef        : aggregationcoef — kurs başına toplam = 1.0
quiz_categories : her quiz hangi kategoriye düşer (3 giriş — quiz_index ile eşleşir)
assign_category : ödevler hangi kategoriye düşer (açık isim)
lesson/scorm/h5p/forum _category : None = notlandırılmaz

schedule:
    quiz_weeks       : [W1, W2, W3]  — 15 kurs 3 gruba bölünmüş, haftada max 5 kurs sınav
    assign_open_weeks: [A1, A2, A3]  — ödev açılış haftaları
    assign_durations : [d1, d2, d3]  — ödev açık kalma süresi (hafta)
    lecture_days     : [d, ...]      — haftanın hangi günleri ders var (0=Pzt..4=Cum)

Grup A (kurslar 1,4,7,10,13): quiz [4,7,12],  ödev [2,6,10]
Grup B (kurslar 2,5,8,11,14): quiz [5,8,13],  ödev [3,7,11]
Grup C (kurslar 3,6,9,12,15): quiz [6,9,14],  ödev [4,8,12]

Ders günleri (haftada max 3 kurs/gün):
    Pzt(0): 1,2,3  |  Sal(1): 4,5,6  |  Çar(2): 7,8,9
    Per(3): 10,11,12 | Cum(4): 13,14,15
"""

from typing import Dict


COURSE_GRADE_SCHEMAS: Dict[int, dict] = {
    1: {  # Yazılım Geliştirme Temelleri → Karma/Dengeli  [Grup A]
        "dominant": "lesson",
        "categories": [
            {"name": "Vize",          "aggregation": 10, "coef": 0.30, "grademax": 30},
            {"name": "Final",         "aggregation": 10, "coef": 0.35, "grademax": 35},
            {"name": "Ödevler",       "aggregation": 10, "coef": 0.20, "grademax": 20},
            {"name": "Derse Katılım", "aggregation": 13, "coef": 0.15, "grademax": 15},
        ],
        "quiz_grademax":    [15, 15, 35],
        "quiz_categories":  ["Vize", "Vize", "Final"],
        "assign_grademax":  10,
        "assign_category":  "Ödevler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  "Derse Katılım",
        "lesson_grademax":  15.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [4, 7, 12],
            "assign_open_weeks": [2, 6, 10],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [0],        # Pazartesi
        },
    },
    2: {  # Veri Yapıları ve Algoritmalar → Quiz-ağırlıklı  [Grup B]
        "dominant": "quiz",
        "categories": [
            {"name": "Vize",             "aggregation": 10, "coef": 0.30, "grademax": 30},
            {"name": "Final",            "aggregation": 10, "coef": 0.35, "grademax": 35},
            {"name": "Haftalık Testler", "aggregation": 10, "coef": 0.20, "grademax": 20},
            {"name": "Ödevler",          "aggregation": 10, "coef": 0.15, "grademax": 15},
        ],
        "quiz_grademax":    [30, 20, 35],
        "quiz_categories":  ["Vize", "Haftalık Testler", "Final"],
        "assign_grademax":  10,
        "assign_category":  "Ödevler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [5, 8, 13],
            "assign_open_weeks": [3, 7, 11],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [0],        # Pazartesi
        },
    },
    3: {  # Nesne Yönelimli Programlama → Assign-ağırlıklı  [Grup C]
        "dominant": "assign",
        "categories": [
            {"name": "Projeler",     "aggregation": 10, "coef": 0.50, "grademax": 50},
            {"name": "Vize",         "aggregation": 10, "coef": 0.20, "grademax": 20},
            {"name": "Final",        "aggregation": 10, "coef": 0.20, "grademax": 20},
            {"name": "Ders İçeriği", "aggregation": 13, "coef": 0.10, "grademax": 10},
        ],
        "quiz_grademax":    [10, 10, 20],
        "quiz_categories":  ["Vize", "Vize", "Final"],
        "assign_grademax":  15,
        "assign_category":  "Projeler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  "Ders İçeriği",
        "lesson_grademax":  10.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [6, 9, 14],
            "assign_open_weeks": [4, 8, 12],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [0],        # Pazartesi
        },
    },
    4: {  # Veritabanı Yönetim Sistemleri → SCORM-ağırlıklı  [Grup A]
        "dominant": "scorm",
        "categories": [
            {"name": "SCORM Modüller", "aggregation": 10, "coef": 0.40, "grademax": 40},
            {"name": "Vize",           "aggregation": 10, "coef": 0.25, "grademax": 25},
            {"name": "Final",          "aggregation": 10, "coef": 0.25, "grademax": 25},
            {"name": "Proje",          "aggregation": 10, "coef": 0.10, "grademax": 10},
        ],
        "quiz_grademax":    [12, 13, 25],
        "quiz_categories":  ["Vize", "Vize", "Final"],
        "assign_grademax":  100,
        "assign_category":  "Proje",
        "lesson_aggregationcoef": 0.0,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   "SCORM Modüller",
        "scorm_grademax":   40.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [4, 7, 12],
            "assign_open_weeks": [2, 6, 10],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [1],        # Salı
        },
    },
    5: {  # Web Teknolojileri → H5P + Assign  [Grup B]
        "dominant": "h5p",
        "categories": [
            {"name": "H5P Uygulamalar", "aggregation": 10, "coef": 0.35, "grademax": 35},
            {"name": "Ödevler",         "aggregation": 10, "coef": 0.35, "grademax": 35},
            {"name": "Final Sınavı",    "aggregation": 10, "coef": 0.30, "grademax": 30},
        ],
        "quiz_grademax":    [10, 10, 30],
        "quiz_categories":  ["Final Sınavı", "Final Sınavı", "Final Sınavı"],
        "assign_grademax":  15,
        "assign_category":  "Ödevler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     "H5P Uygulamalar",
        "h5p_grademax":     35.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [5, 8, 13],
            "assign_open_weeks": [3, 7, 11],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [1],        # Salı
        },
    },
    6: {  # İşletim Sistemleri → Quiz-ağırlıklı (lab)  [Grup C]
        "dominant": "quiz",
        "categories": [
            {"name": "Sınavlar",     "aggregation": 10, "coef": 0.60, "grademax": 60},
            {"name": "Lab Ödevleri", "aggregation": 10, "coef": 0.30, "grademax": 30},
            {"name": "Katılım",      "aggregation": 11, "coef": 0.10, "grademax": 10},
        ],
        "quiz_grademax":    [20, 20, 40],
        "quiz_categories":  ["Sınavlar", "Sınavlar", "Sınavlar"],
        "assign_grademax":  15,
        "assign_category":  "Lab Ödevleri",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  "Katılım",
        "lesson_grademax":  10.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [6, 9, 14],
            "assign_open_weeks": [4, 8, 12],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [1],        # Salı
        },
    },
    7: {  # Bilgisayar Ağları → Quiz-ağırlıklı  [Grup A]
        "dominant": "quiz",
        "categories": [
            {"name": "Vize",             "aggregation": 10, "coef": 0.25, "grademax": 25},
            {"name": "Final",            "aggregation": 10, "coef": 0.40, "grademax": 40},
            {"name": "Haftalık Testler", "aggregation": 10, "coef": 0.25, "grademax": 25},
            {"name": "Ödev",             "aggregation": 10, "coef": 0.10, "grademax": 10},
        ],
        "quiz_grademax":    [25, 25, 40],
        "quiz_categories":  ["Vize", "Haftalık Testler", "Final"],
        "assign_grademax":  10,
        "assign_category":  "Ödev",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [4, 7, 12],
            "assign_open_weeks": [2, 6, 10],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [2],        # Çarşamba
        },
    },
    8: {  # Yazılım Mühendisliği → Karma (Proje + Sınav + SCORM)  [Grup B]
        "dominant": "assign",
        "categories": [
            {"name": "Proje/Ödev", "aggregation": 10, "coef": 0.40, "grademax": 40},
            {"name": "Vize",       "aggregation": 10, "coef": 0.20, "grademax": 20},
            {"name": "Final",      "aggregation": 10, "coef": 0.25, "grademax": 25},
            {"name": "SCORM/Ders", "aggregation": 13, "coef": 0.15, "grademax": 15},
        ],
        "quiz_grademax":    [10, 10, 25],
        "quiz_categories":  ["Vize", "Vize", "Final"],
        "assign_grademax":  20,
        "assign_category":  "Proje/Ödev",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  "SCORM/Ders",
        "lesson_grademax":  15.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [5, 8, 13],
            "assign_open_weeks": [3, 7, 11],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [2],        # Çarşamba
        },
    },
    9: {  # Makine Öğrenmesi → Assign-ağırlıklı (notebook)  [Grup C]
        "dominant": "assign",
        "categories": [
            {"name": "Ödevler",  "aggregation": 10, "coef": 0.40, "grademax": 40},
            {"name": "Sınavlar", "aggregation": 10, "coef": 0.40, "grademax": 40},
            {"name": "H5P/Demo", "aggregation": 13, "coef": 0.20, "grademax": 20},
        ],
        "quiz_grademax":    [15, 15, 25],
        "quiz_categories":  ["Sınavlar", "Sınavlar", "Sınavlar"],
        "assign_grademax":  15,
        "assign_category":  "Ödevler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     "H5P/Demo",
        "h5p_grademax":     20.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [6, 9, 14],
            "assign_open_weeks": [4, 8, 12],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [2],        # Çarşamba
        },
    },
    10: {  # Yapay Zeka → Mixed  [Grup A]
        "dominant": "quiz",
        "categories": [
            {"name": "Sınavlar", "aggregation": 10, "coef": 0.50, "grademax": 50},
            {"name": "Ödevler",  "aggregation": 10, "coef": 0.30, "grademax": 30},
            {"name": "Katılım",  "aggregation": 11, "coef": 0.20, "grademax": 20},
        ],
        "quiz_grademax":    [15, 15, 30],
        "quiz_categories":  ["Sınavlar", "Sınavlar", "Sınavlar"],
        "assign_grademax":  15,
        "assign_category":  "Ödevler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  "Katılım",
        "lesson_grademax":  20.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [4, 7, 12],
            "assign_open_weeks": [2, 6, 10],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [3],        # Perşembe
        },
    },
    11: {  # Siber Güvenlik → Quiz-heavy (CTF tipi)  [Grup B]
        "dominant": "quiz",
        "categories": [
            {"name": "Vize",          "aggregation": 10, "coef": 0.30, "grademax": 30},
            {"name": "Final",         "aggregation": 10, "coef": 0.40, "grademax": 40},
            {"name": "Lab Sınavları", "aggregation": 10, "coef": 0.20, "grademax": 20},
            {"name": "Ödev",          "aggregation": 10, "coef": 0.10, "grademax": 10},
        ],
        "quiz_grademax":    [30, 20, 40],
        "quiz_categories":  ["Vize", "Lab Sınavları", "Final"],
        "assign_grademax":  10,
        "assign_category":  "Ödev",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [5, 8, 13],
            "assign_open_weeks": [3, 7, 11],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [3],        # Perşembe
        },
    },
    12: {  # Mobil Uygulama Geliştirme → Assign-heavy  [Grup C]
        "dominant": "assign",
        "categories": [
            {"name": "Projeler", "aggregation": 10, "coef": 0.55, "grademax": 55},
            {"name": "Sınavlar", "aggregation": 10, "coef": 0.35, "grademax": 35},
            {"name": "Katılım",  "aggregation": 11, "coef": 0.10, "grademax": 10},
        ],
        "quiz_grademax":    [15, 10, 20],
        "quiz_categories":  ["Sınavlar", "Sınavlar", "Sınavlar"],
        "assign_grademax":  20,
        "assign_category":  "Projeler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  "Katılım",
        "lesson_grademax":  10.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [6, 9, 14],
            "assign_open_weeks": [4, 8, 12],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [3],        # Perşembe
        },
    },
    13: {  # Bulut Bilişim → SCORM-heavy (sertifikasyon)  [Grup A]
        "dominant": "scorm",
        "categories": [
            {"name": "SCORM Sertifikasyon", "aggregation": 10, "coef": 0.45, "grademax": 45},
            {"name": "Sınavlar",            "aggregation": 10, "coef": 0.40, "grademax": 40},
            {"name": "Proje",               "aggregation": 10, "coef": 0.15, "grademax": 15},
        ],
        "quiz_grademax":    [15, 10, 25],
        "quiz_categories":  ["Sınavlar", "Sınavlar", "Sınavlar"],
        "assign_grademax":  15,
        "assign_category":  "Proje",
        "lesson_aggregationcoef": 0.0,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   "SCORM Sertifikasyon",
        "scorm_grademax":   45.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [4, 7, 12],
            "assign_open_weeks": [2, 6, 10],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [4],        # Cuma
        },
    },
    14: {  # Veri Analitiği → Assign + H5P  [Grup B]
        "dominant": "assign",
        "categories": [
            {"name": "Analizler",  "aggregation": 10, "coef": 0.45, "grademax": 45},
            {"name": "H5P Görsel", "aggregation": 13, "coef": 0.25, "grademax": 25},
            {"name": "Sınavlar",   "aggregation": 10, "coef": 0.30, "grademax": 30},
        ],
        "quiz_grademax":    [10, 10, 20],
        "quiz_categories":  ["Sınavlar", "Sınavlar", "Sınavlar"],
        "assign_grademax":  15,
        "assign_category":  "Analizler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     "H5P Görsel",
        "h5p_grademax":     25.0,
        "forum_category":   None,
        "forum_grademax":   0.0,
        "schedule": {
            "quiz_weeks":        [5, 8, 13],
            "assign_open_weeks": [3, 7, 11],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [4],        # Cuma
        },
    },
    15: {  # İnsan-Bilgisayar Etkileşimi → Forum + Assign + Quiz  [Grup C]
        "dominant": "assign",
        "categories": [
            {"name": "Projeler",       "aggregation": 10, "coef": 0.40, "grademax": 40},
            {"name": "Sınavlar",       "aggregation": 10, "coef": 0.30, "grademax": 30},
            {"name": "Forum Katılımı", "aggregation": 11, "coef": 0.20, "grademax": 20},
            {"name": "Derse Katılım",  "aggregation": 13, "coef": 0.10, "grademax": 10},
        ],
        "quiz_grademax":    [10, 10, 20],
        "quiz_categories":  ["Sınavlar", "Sınavlar", "Sınavlar"],
        "assign_grademax":  20,
        "assign_category":  "Projeler",
        "lesson_aggregationcoef": 0.03846,
        "lesson_category":  None,
        "lesson_grademax":  0.0,
        "scorm_category":   None,
        "scorm_grademax":   0.0,
        "h5p_category":     None,
        "h5p_grademax":     0.0,
        "forum_category":   "Forum Katılımı",
        "forum_grademax":   20.0,
        "schedule": {
            "quiz_weeks":        [6, 9, 14],
            "assign_open_weeks": [4, 8, 12],
            "assign_durations":  [2, 2, 3],
            "lecture_days":      [4],        # Cuma
        },
    },
}

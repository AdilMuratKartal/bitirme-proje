"""
config.py — Merkezi Konfigürasyon & Segment Profilleri (v4.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ölçek : 2000 Öğrenci | 15 Kurs | 15 Modül/Kurs | 14 Hafta
Mimari: İki Fazlı Üretim (Tarihsel + Canlı Simülasyon)

6 Temel Kural:
  [1] 2000 öğrenci, 15 kurs, 15 sıralı modül/kurs
  [2] Faz 1 = tarihsel 14 hafta | Faz 2 = cron/API ile haftalık ek
  [3] Quiz max 48h açık, giriş 18:00-20:00, attempt max 60 dk
  [4] Segment bazlı ödev teslimi (S1=erken, S2=son24h, S3=panik, S4=hiç/panik)
  [5] Dropout haftası sonrası hiç kayıt yok; modül hiyerarşisi zorunlu
  [6] Not girişi duedate + 3..10 gün (eğitmen gecikmesi)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import datetime


# ─────────────────────────────────────────────────────────────────
# GENEL PARAMETRELER
# ─────────────────────────────────────────────────────────────────
@dataclass
class GeneralConfig:
    seed:                  int  = 43
    n_students:            int  = 10000
    n_weeks:               int  = 14
    n_courses:             int  = 15
    n_modules_per_course:  int  = 15    # Kural 1
    n_quizzes_per_course:  int  = 3
    n_assignments_per_course: int = 5
    n_lookback:            int  = 3     # MIMO lookback penceresi
    output_dir:            str  = "output"
    db_path:               str  = "output/moodle_synthetic.db"
    locale:                str  = "tr_TR"
    semester_start: datetime.datetime = field(
        default_factory=lambda: datetime.datetime(2024, 2, 5, 8, 0, 0)
    )


# ─────────────────────────────────────────────────────────────────
# QUIZ ZAMANLAMA KURALLARI  (Kural 3)
# ─────────────────────────────────────────────────────────────────
@dataclass
class QuizConfig:
    max_open_hours:         int = 48   # timeopen → timeclose arası üst sınır
    entry_window_start_h:   int = 18   # Öğrenci giriş penceresi başı (18:00)
    entry_window_end_h:     int = 20   # Öğrenci giriş penceresi sonu (20:00)
    max_attempt_minutes:    int = 60   # Mutlak sınav süresi üst sınırı
    questions_per_quiz:     int = 10   # Her sınavda soru sayısı


# ─────────────────────────────────────────────────────────────────
# ÖDEV PENCERE KURALLARI  (Kural 4)
# ─────────────────────────────────────────────────────────────────
@dataclass
class AssignmentConfig:
    min_open_weeks: int = 1
    max_open_weeks: int = 3


# ─────────────────────────────────────────────────────────────────
# KURS VE KONU LİSTELERİ
# ─────────────────────────────────────────────────────────────────
COURSE_NAMES: List[str] = [
    "Yazılım Geliştirme Temelleri",
    "Veri Yapıları ve Algoritmalar",
    "Nesne Yönelimli Programlama",
    "Veritabanı Yönetim Sistemleri",
    "Web Teknolojileri",
    "İşletim Sistemleri",
    "Bilgisayar Ağları",
    "Yazılım Mühendisliği",
    "Makine Öğrenmesi",
    "Yapay Zeka",
    "Siber Güvenlik",
    "Mobil Uygulama Geliştirme",
    "Bulut Bilişim",
    "Veri Analitiği",
    "İnsan-Bilgisayar Etkileşimi",
]

# 15 modül sırası — course_modules.sequence ile birebir eşleşir
TOPICS: List[str] = [
    "Temel Kavramlar",
    "Değişkenler ve Veri Tipleri",
    "Kontrol Akışı",
    "Döngüler",
    "Fonksiyonlar",
    "Listeler ve Diziler",
    "Sözlükler ve Kümeler",
    "Nesne Yönelimli Programlama",
    "Hata Yönetimi",
    "Dosya İşlemleri",
    "Modüller ve Paketler",
    "Veritabanı Erişimi",
    "Web API Kullanımı",
    "Test ve Debugging",
    "Proje Uygulaması",
]

# ─────────────────────────────────────────────────────────────────
# SEGMENT TANIMLARI
# ─────────────────────────────────────────────────────────────────
SEGMENT_LABELS: Dict[str, str] = {
    "S1": "Başarılı",
    "S2": "Orta Başarılı",
    "S3": "İstikrarsız",
    "S4": "Terke Meyilli",
}

SEGMENT_RATIOS: Dict[str, float] = {
    "S1": 0.25,
    "S2": 0.35,
    "S3": 0.25,
    "S4": 0.15,
}


@dataclass
class SegmentProfile:
    """
    Bir segmentin tüm davranış parametrelerini tutar.
    Tuple = (ortalama, std_sapma) | float = olasılık
    """
    label: str

    # ── Dropout (Kural 5) ─────────────────────────────────────────
    dropout_prob:       float                    = 0.0
    dropout_week_range: Optional[Tuple[int,int]] = None  # (min_hafta, max_hafta)

    # ── mdl_logstore_standard_log ─────────────────────────────────
    weekly_clicks_base:   Tuple[float, float] = (15.0, 3.0)
    click_decay_per_week: float               = 0.00
    missing_week_prob:    float               = 0.02
    late_night_ratio:     float               = 0.05
    weekend_ratio:        float               = 0.20
    action_weights: Dict[str, float] = field(
        default_factory=lambda: {"view": 0.60, "submit": 0.25, "attempt": 0.15}
    )
    burst_activity: bool = False

    # ── mdl_user ──────────────────────────────────────────────────
    lastaccess_days_ago: Tuple[float, float] = (1.0, 5.0)

    # ── Notlandırma ───────────────────────────────────────────────
    base_grade:           Tuple[float, float] = (75.0, 8.0)
    grade_trend_per_week: Tuple[float, float] = (0.20, 1.0)
    grade_missing_prob:   float               = 0.02

    # ── Ödev teslimi (Kural 4) ────────────────────────────────────
    # Strateji: 'early' | 'last24h' | 'panic' | 'panic_or_miss'
    submit_strategy:      str   = "early"
    missing_submit_prob:  float = 0.03
    revision_prob:        float = 0.05

    # ── Quiz davranışı (Kural 3) ──────────────────────────────────
    quiz_score:           Tuple[float, float] = (70.0, 12.0)
    quiz_missing_prob:    float               = 0.02
    quiz_reattempt_prob:  float               = 0.05
    # Dakika cinsinden [lo, hi] — max_attempt_minutes ile kırpılır
    quiz_duration_range:  Tuple[int, int]     = (40, 60)

    # ── Modül tamamlama (Kural 5) ─────────────────────────────────
    completion_prob:      float               = 0.80
    module_gap_days:      Tuple[float, float] = (1.0, 3.0)

    # ── Soru denemesi ─────────────────────────────────────────────
    answered_ratio:       Tuple[float, float] = (0.85, 1.0)   # Soruyu boş bırakmama olasılığı
    correct_answer_prob:  Tuple[float, float] = (0.65, 0.85)
    topic_weakness_count: int                 = 1
    steps_per_question:   Tuple[int, int]     = (1, 4)


# ─────────────────────────────────────────────────────────────────
# SEGMENT PROFİLLERİ
# ─────────────────────────────────────────────────────────────────
SEGMENT_PROFILES: Dict[str, SegmentProfile] = {

    "S1": SegmentProfile(
        label                 = "Başarılı",
        dropout_prob          = 0.0,
        dropout_week_range    = None,              # Hiç dropout yok

        weekly_clicks_base    = (22.0, 3.0),
        click_decay_per_week  = 0.00,
        missing_week_prob     = 0.01,
        late_night_ratio      = 0.06,
        weekend_ratio         = 0.30,
        action_weights        = {"view": 0.45, "submit": 0.38, "attempt": 0.17},
        burst_activity        = False,
        lastaccess_days_ago   = (0.5, 1.0),

        base_grade            = (85.0, 6.0),
        grade_trend_per_week  = (0.40, 0.6),
        grade_missing_prob    = 0.01,

        submit_strategy       = "early",           # Günlerce önce teslim (Kural 4)
        missing_submit_prob   = 0.01,
        revision_prob         = 0.15,

        quiz_score            = (82.0, 9.0),
        quiz_missing_prob     = 0.01,
        quiz_reattempt_prob   = 0.03,
        quiz_duration_range   = (45, 60),

        completion_prob       = 1.0,    # S1 hiçbir modülü atlamaz (Kural 5)
        module_gap_days       = (0.5, 2.0),

        answered_ratio        = (0.92, 1.0),
        correct_answer_prob   = (0.82, 0.96),
        topic_weakness_count  = 0,
        steps_per_question    = (1, 2),
    ),

    "S2": SegmentProfile(
        label                 = "Orta Başarılı",
        dropout_prob          = 0.05,
        dropout_week_range    = (12, 14),

        weekly_clicks_base    = (14.0, 4.0),
        click_decay_per_week  = 0.01,
        missing_week_prob     = 0.05,
        late_night_ratio      = 0.12,
        weekend_ratio         = 0.18,
        action_weights        = {"view": 0.58, "submit": 0.27, "attempt": 0.15},
        burst_activity        = True,
        lastaccess_days_ago   = (2.0, 4.0),

        base_grade            = (65.0, 8.0),
        grade_trend_per_week  = (0.05, 1.8),
        grade_missing_prob    = 0.04,

        submit_strategy       = "last24h",         # Son 24 saate yığılır (Kural 4)
        missing_submit_prob   = 0.07,
        revision_prob         = 0.08,

        quiz_score            = (63.0, 13.0),
        quiz_missing_prob     = 0.06,
        quiz_reattempt_prob   = 0.12,
        quiz_duration_range   = (30, 58),

        completion_prob       = 0.75,
        module_gap_days       = (2.0, 5.0),

        answered_ratio        = (0.80, 0.95),
        correct_answer_prob   = (0.55, 0.75),
        topic_weakness_count  = 2,
        steps_per_question    = (1, 5),
    ),

    "S3": SegmentProfile(
        label                 = "İstikrarsız",
        dropout_prob          = 0.30,
        dropout_week_range    = (7, 13),

        weekly_clicks_base    = (9.0, 7.0),
        click_decay_per_week  = 0.02,
        missing_week_prob     = 0.20,
        late_night_ratio      = 0.30,
        weekend_ratio         = 0.12,
        action_weights        = {"view": 0.70, "submit": 0.18, "attempt": 0.12},
        burst_activity        = True,
        lastaccess_days_ago   = (5.0, 10.0),

        base_grade            = (52.0, 14.0),
        grade_trend_per_week  = (-0.30, 4.0),
        grade_missing_prob    = 0.12,

        submit_strategy       = "panic",           # Son 60 dk panik (Kural 4)
        missing_submit_prob   = 0.22,
        revision_prob         = 0.03,

        quiz_score            = (48.0, 20.0),
        quiz_missing_prob     = 0.20,
        quiz_reattempt_prob   = 0.18,
        quiz_duration_range   = (20, 55),

        completion_prob       = 0.50,
        module_gap_days       = (5.0, 14.0),

        answered_ratio        = (0.60, 0.85),
        correct_answer_prob   = (0.35, 0.60),
        topic_weakness_count  = 3,
        steps_per_question    = (2, 7),
    ),

    "S4": SegmentProfile(
        label                 = "Terke Meyilli",
        dropout_prob          = 0.70,
        dropout_week_range    = (3, 10),

        weekly_clicks_base    = (5.0, 4.0),
        click_decay_per_week  = 0.10,
        missing_week_prob     = 0.45,
        late_night_ratio      = 0.06,
        weekend_ratio         = 0.08,
        action_weights        = {"view": 0.85, "submit": 0.09, "attempt": 0.06},
        burst_activity        = False,
        lastaccess_days_ago   = (14.0, 30.0),

        base_grade            = (34.0, 10.0),
        grade_trend_per_week  = (-1.40, 2.2),
        grade_missing_prob    = 0.30,

        submit_strategy       = "panic_or_miss",   # Ya hiç ya son 5 dk (Kural 4)
        missing_submit_prob   = 0.50,
        revision_prob         = 0.01,

        quiz_score            = (24.0, 13.0),
        quiz_missing_prob     = 0.45,
        quiz_reattempt_prob   = 0.04,
        quiz_duration_range   = (10, 40),

        completion_prob       = 0.18,
        module_gap_days       = (10.0, 25.0),

        answered_ratio        = (0.30, 0.65),
        correct_answer_prob   = (0.18, 0.40),
        topic_weakness_count  = 5,
        steps_per_question    = (1, 3),
    ),
}


# ─────────────────────────────────────────────────────────────────
# TABLO ŞEMALARI  (ERD tam sütun listesi)
# ─────────────────────────────────────────────────────────────────
MDL_SCHEMA: Dict[str, List[str]] = {
    "mdl_user":                      ["id", "username", "firstname", "lastname",
                                      "email", "lastaccess", "timecreated"],
    "mdl_course":                    ["id", "shortname", "fullname", "startdate",
                                      "enddate", "timecreated"],
    "mdl_grade_items":               ["id", "courseid", "itemname", "itemtype",
                                      "grademax", "grademin", "timecreated"],
    "mdl_grade_grades":              ["id", "userid", "itemid", "finalgrade",
                                      "timemodified"],
    "mdl_grade_grades_history":      ["id", "userid", "itemid", "finalgrade",
                                      "timemodified", "source"],
    "mdl_assign":                    ["id", "course", "name", "duedate",
                                      "allowsubmissionsfromdate", "timeclose"],
    "mdl_assign_submission":         ["id", "userid", "assignment", "timemodified",
                                      "status", "delay_hours"],
    "mdl_logstore_standard_log":     ["id", "userid", "courseid", "component",
                                      "action", "objectid", "timecreated"],
    "mdl_quiz":                      ["id", "course", "name", "timeopen",
                                      "timeclose", "timelimit"],
    "mdl_quiz_attempts":             ["id", "quiz", "userid", "uniqueid",
                                      "timestart", "timefinish", "sumgrades",
                                      "state", "duration_minutes"],
    "mdl_course_modules":            ["id", "course", "module", "instance",
                                      "completion", "added", "sequence",
                                      "component", "content_type", "topic"],
    "mdl_course_modules_completion": ["id", "coursemoduleid", "userid",
                                      "completionstate", "timemodified"],
    "mdl_question_categories":       ["id", "name", "parent", "info"],
    "mdl_question":                  ["id", "category", "name", "qtype",
                                      "timecreated"],
    "mdl_question_attempts":         ["id", "questionusageid", "questionid",
                                      "userid", "responsesummary", "rightanswer",
                                      "fraction", "timecreated"],
    "mdl_question_attempt_steps":    ["id", "questionattemptid", "state",
                                      "timecreated"],
}

COMPONENT_TYPE_MAP: Dict[str, str] = {
    "mod_url":             "İzleme",
    "mod_lesson":          "İzleme",
    "mod_bigbluebuttonbn": "İzleme",
    "mod_resource":        "Okuma",
    "mod_page":            "Okuma",
    "mod_book":            "Okuma",
    "mod_folder":          "Okuma",
    "mod_assign":          "Ödev",
    "mod_quiz":            "Ödev",
    "mod_workshop":        "Ödev",
    "mod_forum":           "Forum",
}

QUESTION_STEP_STATES: List[str] = [
    "todo", "invalid", "complete", "needsgrading",
    "gradedwrong", "gradedright", "gradedpartial",
]

CONTENT_TYPE_THRESHOLDS: Dict[str, float] = {
    "İzleme": 0.70,
    "Okuma":  0.55,
    "Ödev":   0.40,
    "Forum":  0.30,
}


# ─────────────────────────────────────────────────────────────────
# ÇIKTI ŞEMALARI
# ─────────────────────────────────────────────────────────────────
@dataclass
class MIMOTargetSchema:
    risk_score_col:      str = "y_risk_score"
    predicted_grade_col: str = "y_predicted_grade"


@dataclass
class HKARTargetSchema:
    topic_status_col:        str = "topic_status"
    recommended_content_col: str = "recommended_content"


# ─────────────────────────────────────────────────────────────────
# ANA CONFIG
# ─────────────────────────────────────────────────────────────────
@dataclass
class MasterConfig:
    general:            GeneralConfig             = field(default_factory=GeneralConfig)
    quiz:               QuizConfig                = field(default_factory=QuizConfig)
    assignment:         AssignmentConfig          = field(default_factory=AssignmentConfig)
    mimo_target:        MIMOTargetSchema          = field(default_factory=MIMOTargetSchema)
    hkar_target:        HKARTargetSchema          = field(default_factory=HKARTargetSchema)
    schema:             Dict[str, List[str]]      = field(default_factory=lambda: MDL_SCHEMA)
    topics:             List[str]                 = field(default_factory=lambda: TOPICS)
    course_names:       List[str]                 = field(default_factory=lambda: COURSE_NAMES)
    component_map:      Dict[str, str]            = field(default_factory=lambda: COMPONENT_TYPE_MAP)
    content_thresholds: Dict[str, float]          = field(default_factory=lambda: CONTENT_TYPE_THRESHOLDS)
    segment_profiles:   Dict[str, SegmentProfile] = field(default_factory=lambda: SEGMENT_PROFILES)
    segment_ratios:     Dict[str, float]          = field(default_factory=lambda: SEGMENT_RATIOS)
    segment_labels:     Dict[str, str]            = field(default_factory=lambda: SEGMENT_LABELS)
    step_states:        List[str]                 = field(default_factory=lambda: QUESTION_STEP_STATES)


CFG = MasterConfig()

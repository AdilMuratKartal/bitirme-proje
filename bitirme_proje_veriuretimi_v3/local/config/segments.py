"""
config/segments.py — Segment Profilleri
4 öğrenci segmentinin davranış parametreleri.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


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
    answered_ratio:       Tuple[float, float] = (0.85, 1.0)
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
        dropout_week_range    = None,

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

        submit_strategy       = "early",
        missing_submit_prob   = 0.01,
        revision_prob         = 0.15,

        quiz_score            = (82.0, 9.0),
        quiz_missing_prob     = 0.01,
        quiz_reattempt_prob   = 0.03,
        quiz_duration_range   = (45, 60),

        completion_prob       = 1.0,
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

        submit_strategy       = "last24h",
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

        submit_strategy       = "panic",
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

        submit_strategy       = "panic_or_miss",
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

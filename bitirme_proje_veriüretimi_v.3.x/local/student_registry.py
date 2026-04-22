"""
student_registry.py — Öğrenci–Segment ve Dropout Atama Modülü (v4.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2000 öğrenci için segment ve dropout_week ataması tek noktada yapılır.

Kural 5 — Dropout Haftası:
  S1 → dropout_week = None   (hiç bırakmaz)
  S2 → %5 ihtimalle hafta 12-14
  S3 → %30 ihtimalle hafta 7-13
  S4 → %70 ihtimalle hafta 3-10
"""

import numpy as np
import pandas as pd
from typing import Optional

from config import CFG, SegmentProfile, SEGMENT_PROFILES, SEGMENT_RATIOS


def build_student_registry() -> pd.DataFrame:
    """
    Her öğrenci için segment ve dropout_week ataması.
    Sütunlar: userid | segment | label | dropout_week
    dropout_week = None → dönem sonuna kadar aktif
    """
    rng      = np.random.default_rng(CFG.general.seed)
    n        = CFG.general.n_students
    segments = list(SEGMENT_RATIOS.keys())
    probs    = [SEGMENT_RATIOS[s] for s in segments]
    assigned = rng.choice(segments, size=n, p=probs)

    rows = []
    for uid, seg in zip(range(1, n + 1), assigned):
        profile = SEGMENT_PROFILES[seg]

        # Kural 5: Dropout haftası belirle
        dropout_week: Optional[int] = None
        if profile.dropout_week_range is not None:
            if rng.random() < profile.dropout_prob:
                dw_min, dw_max = profile.dropout_week_range
                dropout_week = int(rng.integers(dw_min, dw_max + 1))

        rows.append({
            "userid":       uid,
            "segment":      seg,
            "label":        CFG.segment_labels[seg],
            "dropout_week": dropout_week,   # None = dönem sonuna kadar aktif
        })

    return pd.DataFrame(rows)


# ─── Singleton: bir kez üret, her yerden import et ───────────────
STUDENT_REGISTRY: pd.DataFrame = build_student_registry()

# Hızlı lookup dict'leri (O(1) erişim)
_SEG_MAP:     dict = dict(zip(STUDENT_REGISTRY["userid"], STUDENT_REGISTRY["segment"]))
_DROPOUT_MAP: dict = dict(zip(STUDENT_REGISTRY["userid"], STUDENT_REGISTRY["dropout_week"]))


def get_profile(userid: int) -> SegmentProfile:
    """Öğrencinin SegmentProfile nesnesini döner."""
    return SEGMENT_PROFILES[_SEG_MAP[userid]]


def get_segment(userid: int) -> str:
    """Öğrencinin segment kodunu döner (S1/S2/S3/S4)."""
    return _SEG_MAP[userid]


def get_dropout_week(userid: int) -> Optional[int]:
    """
    Öğrencinin dropout haftasını döner.
    None → dönem boyunca aktif.
    """
    return _DROPOUT_MAP[userid]


def is_active_in_week(userid: int, week: int) -> bool:
    """
    Kural 5: Öğrenci o haftada aktif mi?
    dropout_week = 6 ise hafta 7, 8, ... için False döner.
    """
    dw = _DROPOUT_MAP[userid]
    if dw is None:
        return True
    return week <= dw

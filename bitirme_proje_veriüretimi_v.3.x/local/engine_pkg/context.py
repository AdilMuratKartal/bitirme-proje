"""
engine_pkg/context.py — Paylaşılan simülasyon durumu (Context Object pattern).
Tüm handler/service sınıfları bu nesneyi constructor'da alır; böylece
SimulationEngine'in iç durumu tek yerde toplanır, handler'lar birbirinden bağımsız kalır.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from .store import DataStore


class SimContext:
    """
    Simülasyon boyunca değişen paylaşılan durum.
    Handler'lar bu nesneyi okur ve günceller.
    """
    __slots__ = (
        "store", "rng",
        "grade_cat_ids", "grade_cat_item_ids",
        "course_modules", "quiz_index",
        "assign_meta", "pending_grading",
        "completion_state", "s3_course_done",
    )

    def __init__(self, store: DataStore, rng: np.random.Generator) -> None:
        self.store: DataStore                           = store
        self.rng:   np.random.Generator                = rng

        # _setup_grade_categories tarafından doldurulur
        self.grade_cat_ids:      Dict[int, Dict[str, int]] = {}   # course_id → {cat_name: cat_id}
        self.grade_cat_item_ids: Dict[int, Dict[str, int]] = {}   # course_id → {cat_name: item_id}

        # _setup_course_modules tarafından doldurulur
        self.course_modules: Dict[int, List[dict]] = {}    # course_id → [modül satırları]

        # quiz sayacı: 0=vize, 1=haftalık test, 2=final
        self.quiz_index: Dict[int, int] = {}               # course_id → int

        # ödev meta verileri (GradingEvent için)
        self.assign_meta: Dict[int, dict] = {}             # assign_id → {item_id, due_dt}

        # bekleyen grading event'leri
        self.pending_grading: List[Any] = []

        # S2 modül completion takibi
        self.completion_state: Dict[Tuple[int, int], Dict] = {}  # (uid, course_id) → dict

        # S3 kurs başına tamamlama sayacı
        self.s3_course_done: Dict[Tuple[int, int], int] = {}     # (uid, course_id) → int

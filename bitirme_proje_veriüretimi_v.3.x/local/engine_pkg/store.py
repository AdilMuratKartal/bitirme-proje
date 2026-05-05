"""
engine_pkg/store.py — Tablo verisi ve ID yönetimi (DataStore).
Repository / DAO pattern: ham veri + add/next_id operasyonları tek yerde.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd


class DataStore:
    """
    Tüm Moodle tablo verilerini (_rows) ve ID sayaçlarını (_ids) tutar.
    SimulationEngine bileşenleri bu sınıftan veri okur/yazar.
    """

    TABLE_NAMES: List[str] = [
        "mdl_user", "mdl_course", "mdl_grade_categories", "mdl_grade_items",
        "mdl_enrol", "mdl_user_enrolments",
        "mdl_assign", "mdl_assign_submission",
        "mdl_quiz", "mdl_quiz_attempts",
        "mdl_course_modules", "mdl_course_modules_completion",
        "mdl_course_completions",
        "mdl_logstore_standard_log",
        "mdl_grade_grades", "mdl_grade_grades_history",
        "mdl_question_categories", "mdl_question",
        "mdl_question_attempts", "mdl_question_attempt_steps",
        "mdl_event",
        "mdl_forum", "mdl_forum_discussions", "mdl_forum_posts",
        "mdl_lesson", "mdl_lesson_attempts",
        "mdl_scorm", "mdl_h5pactivity",
        "mdl_badge", "mdl_badge_issued",
        "student_registry",
    ]

    def __init__(self) -> None:
        self._rows: Dict[str, List[dict]] = {t: [] for t in self.TABLE_NAMES}
        self._ids:  Dict[str, int]        = {t: 0  for t in self.TABLE_NAMES}
        # Özel sayaçlar (tablo adı dışında)
        self._ids["_quiz_uniqueid_counter"] = 0
        self._ids["_assign_counter"]        = 0
        self._ids["_quiz_counter"]          = 0

    # ── ID üretimi ────────────────────────────────────────────────────
    def next_id(self, table: str) -> int:
        self._ids[table] += 1
        return self._ids[table]

    def add(self, table: str, row: dict) -> None:
        row.setdefault("id", self.next_id(table))
        self._rows[table].append(row)

    # ── Çıktı ─────────────────────────────────────────────────────────
    def to_dataframes(self) -> Dict[str, pd.DataFrame]:
        frames: Dict[str, pd.DataFrame] = {}
        for name in self.TABLE_NAMES:
            rows = self._rows.get(name, [])
            if rows:
                df = pd.DataFrame(rows)
                if "id" in df.columns:
                    df = df[["id"] + [c for c in df.columns if c != "id"]]
                frames[name] = df
            else:
                frames[name] = pd.DataFrame()
        return frames

    def print_stats(self, tables: Dict[str, pd.DataFrame]) -> None:
        total = 0
        print(f"\n   {'Tablo':<48}  {'Satir':>10}")
        print(f"   {'-'*48}  {'-'*10}")
        for name in sorted(tables):
            n = len(tables[name])
            total += n
            print(f"   {name:<48}  {n:>10,}")
        print(f"   {'-'*48}  {'-'*10}")
        print(f"   {'TOPLAM':<48}  {total:>10,}")

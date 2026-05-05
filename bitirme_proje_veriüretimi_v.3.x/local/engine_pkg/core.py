"""
engine_pkg/core.py — Facade: SimulationEngine ince orkestratör.
Tüm iş mantığı handler/finalize/persistence sınıflarında; bu sınıf sadece koordine eder.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from config import CFG
from events import (
    AssignmentOpenEvent, DropoutCheckEvent,
    GradingEvent, QuizOpenEvent, WeeklyActivityEvent,
)

from .context import SimContext
from .finalize import BadgeIssuer, CourseCompletionFinalizer, GradeAggregator
from .handlers import (
    AssignmentHandler, DropoutCheckHandler, GradingHandler,
    QuizHandler, WeeklyActivityHandler,
)
from .persistence import StateManager
from .schedule import TimeCalc, build_semester_schedule
from .setup import ReferenceBuilder
from .store import DataStore


class SimulationEngine:
    """
    Event-tabanlı simülasyon motoru — ince Facade.

    Yerel kullanım:
        engine = SimulationEngine()
        tables = engine.simulate_full_semester(weeks=14)

    Cron kullanımı:
        engine = SimulationEngine()
        engine.load_state("output/engine_state.json")
        engine.load_rows_from_csv("output")
        engine.simulate_week(current_week)
        engine.save_state("output/engine_state.json")
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        rng   = np.random.default_rng(seed or CFG.general.seed)
        store = DataStore()
        self._ctx      = SimContext(store, rng)
        self._schedule = build_semester_schedule(CFG.general.n_courses)

        self._handlers: Dict[type, Any] = {
            WeeklyActivityEvent: WeeklyActivityHandler(self._ctx),
            QuizOpenEvent:       QuizHandler(self._ctx),
            AssignmentOpenEvent: AssignmentHandler(self._ctx),
            GradingEvent:        GradingHandler(self._ctx),
            DropoutCheckEvent:   DropoutCheckHandler(self._ctx),
        }
        ReferenceBuilder(self._ctx).build()

    # ─────────────────────────────────────────────────────────────
    # ANA SİMÜLASYON
    # ─────────────────────────────────────────────────────────────

    def simulate_full_semester(self, weeks: int = 14) -> Dict[str, pd.DataFrame]:
        print("=" * 68)
        print("  SimulationEngine -- Tam Donem Simulasyonu")
        print(f"  {CFG.general.n_students} ogrenci | "
              f"{CFG.general.n_courses} kurs | {weeks} hafta")
        print("=" * 68)

        for week in range(1, weeks + 1):
            print(f"\n  -- Hafta {week:02d} ----------------------------------")
            self.simulate_week(week)

        print("\n" + "=" * 68)
        print("  Simulasyon tamamlandi. Donem sonu tablolar uretiliyor...")

        CourseCompletionFinalizer().finalize(self._ctx)
        BadgeIssuer().issue(self._ctx)
        GradeAggregator().aggregate(self._ctx)

        tables = self._ctx.store.to_dataframes()
        self._ctx.store.print_stats(tables)
        print("=" * 68)
        return tables

    def simulate_week(self, week: int) -> None:
        ctx   = self._ctx
        store = ctx.store
        rng   = ctx.rng

        self._dispatch(WeeklyActivityEvent(week=week))

        for cs in self._schedule:
            if week in cs.quiz_weeks:
                store._ids["_quiz_counter"] += 1
                qid = store._ids["_quiz_counter"]
                open_dt, close_dt = TimeCalc.quiz_open_close(week, rng)
                self._dispatch(QuizOpenEvent(
                    week=week, course_id=cs.course_id,
                    quiz_id=qid, open_dt=open_dt, close_dt=close_dt,
                ))

            idx = cs.assign_weeks.index(week) if week in cs.assign_weeks else -1
            if idx >= 0:
                store._ids["_assign_counter"] += 1
                aid      = store._ids["_assign_counter"]
                dur      = cs.assign_durations[idx]
                open_dt  = TimeCalc.week_start(week)
                due_dt   = TimeCalc.week_start(week + dur) - timedelta(hours=1)
                self._dispatch(AssignmentOpenEvent(
                    week=week, course_id=cs.course_id,
                    assign_id=aid, open_weeks=dur,
                    open_dt=open_dt, due_dt=due_dt,
                ))

        due_now = [g for g in ctx.pending_grading if g.week == week]
        for g_evt in due_now:
            self._dispatch(g_evt)
            ctx.pending_grading.remove(g_evt)

    def dispatch(self, event: Any) -> None:
        self._dispatch(event)

    def _dispatch(self, event: Any) -> None:
        h = self._handlers.get(type(event))
        if h is None:
            raise ValueError(f"Bilinmeyen event tipi: {type(event)}")
        h.handle(event)

    # ─────────────────────────────────────────────────────────────
    # PERSISTENCE PROXY
    # ─────────────────────────────────────────────────────────────

    def save_state(self, path: str = "output/engine_state.json") -> None:
        StateManager().save(self._ctx, path)

    def load_state(self, path: str = "output/engine_state.json") -> None:
        StateManager().load(self._ctx, path)

    def load_rows_from_csv(self, out_dir: str = "output") -> None:
        StateManager().load_rows_from_csv(self._ctx, out_dir)

    # ─────────────────────────────────────────────────────────────
    # ÇIKTI (pipeline.py uyumluluğu)
    # ─────────────────────────────────────────────────────────────

    def to_dataframes(self) -> Dict[str, pd.DataFrame]:
        return self._ctx.store.to_dataframes()

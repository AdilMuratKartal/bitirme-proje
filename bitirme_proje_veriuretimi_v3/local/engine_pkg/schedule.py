"""
engine_pkg/schedule.py — Zaman hesaplamaları, segment davranışı, dönem takvimi.
Bağımsız yardımcı sınıflar: hiçbiri SimulationEngine'e bağımlı değil.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np

from config import CFG, COURSE_GRADE_SCHEMAS, SegmentProfile


# ─────────────────────────────────────────────────────────────────────
# ZAMAN YARDIMCISI
# ─────────────────────────────────────────────────────────────────────

class TimeCalc:
    """Statik zaman hesaplamalarını merkezileştirir. Test ve cron'a taşınabilir."""

    BASE = CFG.general.semester_start

    @staticmethod
    def week_start(week: int) -> datetime:
        return TimeCalc.BASE + timedelta(weeks=week - 1)

    @staticmethod
    def week_end(week: int) -> datetime:
        return TimeCalc.week_start(week) + timedelta(days=6, hours=23, minutes=59)

    @staticmethod
    def ts(dt: datetime) -> int:
        return int(dt.timestamp())

    @staticmethod
    def clamp(dt: datetime, lo: datetime, hi: datetime) -> datetime:
        return max(lo, min(dt, hi))

    # ── Kural 3: Quiz zamanlama ───────────────────────────────────────
    @staticmethod
    def quiz_open_close(week: int, rng: np.random.Generator) -> Tuple[datetime, datetime]:
        wstart     = TimeCalc.week_start(week)
        day_offset = rng.integers(1, 4)
        hour_open  = rng.integers(8, 16)
        open_dt    = wstart + timedelta(days=int(day_offset), hours=int(hour_open))
        open_hours = rng.integers(24, 49)
        close_dt   = open_dt + timedelta(hours=int(open_hours))
        return open_dt, close_dt

    @staticmethod
    def quiz_attempt_window(
        close_dt: datetime,
        profile:  SegmentProfile,
        rng:      np.random.Generator,
    ) -> Tuple[datetime, datetime, float]:
        """Kural 3: 18:00-20:00 giriş penceresi, max 60 dk attempt."""
        entry_day = close_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        win_start = entry_day + timedelta(hours=CFG.quiz.entry_window_start_h)
        win_end   = entry_day + timedelta(hours=CFG.quiz.entry_window_end_h)
        win_start = TimeCalc.clamp(win_start, close_dt - timedelta(hours=2),   close_dt - timedelta(minutes=5))
        win_end   = TimeCalc.clamp(win_end,   win_start + timedelta(minutes=1), close_dt - timedelta(minutes=1))

        start_dt    = datetime.fromtimestamp(float(rng.uniform(win_start.timestamp(), win_end.timestamp())))
        lo, hi      = profile.quiz_duration_range
        desired_min = float(rng.uniform(lo, hi))
        max_by_close = (close_dt - start_dt).total_seconds() / 60
        dur_min     = max(min(desired_min, max_by_close, CFG.quiz.max_attempt_minutes), 1.0)
        finish_dt   = start_dt + timedelta(minutes=dur_min)
        return start_dt, finish_dt, dur_min

    # ── Kural 4: Ödev teslim ─────────────────────────────────────────
    @staticmethod
    def submit_time(
        strategy: str,
        open_dt:  datetime,
        due_dt:   datetime,
        rng:      np.random.Generator,
    ) -> Optional[datetime]:
        if strategy == "early":
            dt = due_dt - timedelta(days=float(rng.uniform(3, 8)))
            return TimeCalc.clamp(dt, open_dt, due_dt)
        if strategy == "last24h":
            secs = float(rng.uniform(0, 7200) if rng.random() < 0.70 else rng.uniform(0, 86400))
            return TimeCalc.clamp(due_dt - timedelta(seconds=secs), open_dt, due_dt)
        if strategy == "panic":
            return TimeCalc.clamp(due_dt - timedelta(seconds=float(rng.uniform(60, 3600))), open_dt, due_dt)
        if strategy == "panic_or_miss":
            if rng.random() < 0.50:
                return None
            return TimeCalc.clamp(due_dt - timedelta(seconds=float(rng.uniform(0, 300))), open_dt, due_dt)
        return None

    # ── Kural 6: Not gecikme tarihi ──────────────────────────────────
    @staticmethod
    def grading_time(due_dt: datetime, rng: np.random.Generator) -> datetime:
        return due_dt + timedelta(days=int(rng.integers(3, 11)))

    @staticmethod
    def dirichlet_budget(n: int, total_seconds: float, rng: np.random.Generator) -> List[float]:
        fracs = rng.dirichlet(np.ones(n))
        return (fracs * total_seconds).tolist()

    @staticmethod
    def week_of(dt: datetime) -> int:
        diff = (dt - TimeCalc.BASE).days
        return max(1, min(int(diff // 7) + 1, CFG.general.n_weeks))


# ─────────────────────────────────────────────────────────────────────
# SEGMENT DAVRANIŞ KARAR NOKTASI
# ─────────────────────────────────────────────────────────────────────

class SegmentBehavior:
    """Segment profili + RNG → davranışsal kararlar. Test için bağımsız."""

    @staticmethod
    def should_skip_week(profile: SegmentProfile, rng: np.random.Generator) -> bool:
        return rng.random() < profile.missing_week_prob

    @staticmethod
    def weekly_click_count(profile: SegmentProfile, week: int, rng: np.random.Generator) -> int:
        mu, sigma = profile.weekly_clicks_base
        adjusted  = max(mu - profile.click_decay_per_week * (week - 1), 1.0)
        return max(int(rng.normal(adjusted, sigma)), 0)

    @staticmethod
    def random_action(profile: SegmentProfile, rng: np.random.Generator) -> str:
        actions = list(profile.action_weights.keys())
        weights = [profile.action_weights[a] for a in actions]
        return actions[int(rng.choice(len(actions), p=np.array(weights) / sum(weights)))]

    @staticmethod
    def random_component(rng: np.random.Generator) -> str:
        from config import COMPONENT_TYPE_MAP
        return str(rng.choice(list(COMPONENT_TYPE_MAP.keys())))

    @staticmethod
    def complete_module(profile: SegmentProfile, rng: np.random.Generator) -> bool:
        return rng.random() < profile.completion_prob

    @staticmethod
    def quiz_score(profile: SegmentProfile, rng: np.random.Generator) -> float:
        mu, sigma = profile.quiz_score
        return float(np.clip(rng.normal(mu, sigma), 0, 100))

    @staticmethod
    def grade_value(profile: SegmentProfile, week: int, rng: np.random.Generator) -> float:
        mu, sigma = profile.base_grade
        trend_mu, trend_sigma = profile.grade_trend_per_week
        trend = trend_mu + float(rng.normal(0, trend_sigma))
        return float(np.clip(rng.normal(mu + trend * (week - 1), sigma), 0, 100))


# ─────────────────────────────────────────────────────────────────────
# DÖNEM TAKVİMİ
# ─────────────────────────────────────────────────────────────────────

@dataclass
class CourseSchedule:
    """Bir kursun dönem boyunca quiz/ödev takvimi."""
    course_id:       int
    quiz_weeks:      List[int]
    assign_weeks:    List[int]
    assign_durations: List[int]


def build_semester_schedule(n_courses: int) -> List[CourseSchedule]:
    """
    COURSE_GRADE_SCHEMAS[cid]['schedule'] bloğundan kurs takvimlerini üretir.
    3 grup (A/B/C) ile haftada max 5 kurs sınav garantilenir.
    """
    schedules = []
    for cid in range(1, n_courses + 1):
        sched = COURSE_GRADE_SCHEMAS[cid]["schedule"]
        schedules.append(CourseSchedule(
            course_id        = cid,
            quiz_weeks       = list(sched["quiz_weeks"]),
            assign_weeks     = list(sched["assign_open_weeks"]),
            assign_durations = list(sched["assign_durations"]),
        ))
    return schedules

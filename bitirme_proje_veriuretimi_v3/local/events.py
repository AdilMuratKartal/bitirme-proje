"""
events.py — Simülasyon Olay Tipleri (v5.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Her event, SimulationEngine.dispatch() tarafından işlenir.
İleride cron job veya webhook ile doğrudan tetiklenebilir:
    engine.dispatch(QuizOpenEvent(week=8, course_id=3, quiz_id=12))
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────────────────────────
# TEMEL OLAY TİPLERİ
# ─────────────────────────────────────────────────────────────────

@dataclass
class WeeklyActivityEvent:
    """
    Her hafta tetiklenir.
    O haftanın modül completion kayıtlarını ve logstore girdilerini üretir.
    """
    week: int


@dataclass
class QuizOpenEvent:
    """
    Bir quiz açılır; öğrenci attempt'leri ve soru adımları üretilir.
    Quiz max 48 saat açık kalır (Kural 3).
    """
    week:        int
    course_id:   int
    quiz_id:     int
    open_dt:     datetime = field(default=None)   # None → engine hesaplar
    close_dt:    datetime = field(default=None)


@dataclass
class AssignmentOpenEvent:
    """
    Bir ödev açılır. Teslim kayıtları segment stratejisine göre üretilir (Kural 4).
    open_weeks sonra otomatik GradingEvent planlanır.
    """
    week:        int
    course_id:   int
    assign_id:   int
    open_weeks:  int = 2      # 1-3 hafta açık kalır
    open_dt:     datetime = field(default=None)
    due_dt:      datetime = field(default=None)


@dataclass
class GradingEvent:
    """
    Kapanmış ödevlerin notları toplu girilir (Kural 6: duedate + 3-10 gün).
    grading_dt: _handle_assignment_event'te tek seferlik hesaplanır (BUG-7).
    """
    week:        int
    assign_id:   int
    due_dt:      datetime   # Referans tarih (duedate)
    grading_dt:  datetime   # Gerçek not girme tarihi (due_dt + 3-10 gün)


@dataclass
class DropoutCheckEvent:
    """
    İsteğe bağlı: belirli bir haftada dropout olan öğrencileri raporlar.
    Canlı sistemde bildirim göndermek için kullanılabilir.
    """
    week: int

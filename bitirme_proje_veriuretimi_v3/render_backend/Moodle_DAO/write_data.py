"""
render_backend/Moodle_DAO/write_data.py — Tüm UPSERT Operasyonları

INSERT ON CONFLICT DO UPDATE kullanılır — idempotent (iki kez çalışsa zarar vermez).
Her write metodu session parametresi alır; commit Orchestrator'da yapılır.
"""

from __future__ import annotations

from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session


class WriteMixin:
    """WRITE metodları — MoodleDAO sınıfına mixin olarak bağlanır."""

    def upsert_mimo_analysis(self, results: List[Dict], session: Session) -> int:
        """
        MIMO analiz sonuçlarını yazar. Mevcut kayıt varsa günceller.
        results: [{"user_id": int, "risk_score": float, "risk_level": str,
                   "predicted_grade": float, "model_confidence": float}, ...]
        Dönüş: yazılan satır sayısı
        """
        if not results:
            return 0

        stmt = text("""
            INSERT INTO mdl_mimo_analysis
                (user_id, risk_score, risk_level, predicted_grade, model_confidence, computed_at)
            VALUES
                (:user_id, :risk_score, :risk_level, :predicted_grade, :model_confidence, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                risk_score       = EXCLUDED.risk_score,
                risk_level       = EXCLUDED.risk_level,
                predicted_grade  = EXCLUDED.predicted_grade,
                model_confidence = EXCLUDED.model_confidence,
                computed_at      = NOW()
        """)

        session.execute(stmt, results)
        return len(results)

    def upsert_hkrt_analysis(self, results: List[Dict], session: Session) -> int:
        """
        HKAR öneri sonuçlarını yazar. (user_id, topic_id) üzerine çakışma kontrolü.
        results: [{"user_id": int, "topic_id": str, "resource_type": str,
                   "priority": int, "reason_text": str}, ...]
        """
        if not results:
            return 0

        stmt = text("""
            INSERT INTO mdl_hkrt_analysis
                (user_id, topic_id, resource_type, priority, reason_text, computed_at)
            VALUES
                (:user_id, :topic_id, :resource_type, :priority, :reason_text, NOW())
            ON CONFLICT (user_id, topic_id) DO UPDATE SET
                resource_type = EXCLUDED.resource_type,
                priority      = EXCLUDED.priority,
                reason_text   = EXCLUDED.reason_text,
                computed_at   = NOW()
        """)

        session.execute(stmt, results)
        return len(results)

    def upsert_basic_values(self, results: List[Dict], session: Session) -> int:
        """
        Temel öğrenci değerlerini yazar (GPA, streak vb.).
        results: [{"user_id": int, "gpa": float, "total_courses": int,
                   "completed_credits": int, "login_streak": int}, ...]
        """
        if not results:
            return 0

        stmt = text("""
            INSERT INTO mdl_basic_values
                (user_id, gpa, total_courses, completed_credits, login_streak, updated_at)
            VALUES
                (:user_id, :gpa, :total_courses, :completed_credits, :login_streak, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                gpa               = EXCLUDED.gpa,
                total_courses     = EXCLUDED.total_courses,
                completed_credits = EXCLUDED.completed_credits,
                login_streak      = EXCLUDED.login_streak,
                updated_at        = NOW()
        """)

        session.execute(stmt, results)
        return len(results)

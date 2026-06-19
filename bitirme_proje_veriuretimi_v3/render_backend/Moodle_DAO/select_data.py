"""
render_backend/Moodle_DAO/select_data.py — SELECT Operasyonları (dash-only)

API yalnızca dash_* precompute tablolarından okur (mdl_* canlı sorgu YOK).
Auth eşlemesi student_registry.firebase_uid üzerinden çözülür.
Bu mixin MoodleDAO sınıfına dahil edilir — doğrudan kullanılmaz.
"""

from __future__ import annotations

from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import text


class SelectMixin:
    """READ metodları — MoodleDAO sınıfına mixin olarak bağlanır."""

    # ─────────────────────────────────────────────────────────────
    # Auth + öğrenci kayıt
    # ─────────────────────────────────────────────────────────────

    def get_userid_by_firebase_uid(self, firebase_uid: str) -> Optional[int]:
        """
        Firebase Auth uid'sinden Moodle userid'sini çözer.
        Eşleme student_registry.firebase_uid kolonunda tutulur.
        Kayıt yoksa None (= kullanıcı Firebase'de var ama Moodle'da yok).
        """
        session = self._session()
        try:
            row = session.execute(
                text("SELECT userid FROM student_registry WHERE firebase_uid = :uid"),
                {"uid": firebase_uid},
            ).fetchone()
            return row[0] if row else None
        finally:
            session.close()

    def get_active_student_ids(self, week: int, limit: Optional[int] = None) -> List[int]:
        """student_registry'den aktif öğrenci ID'leri (offline precompute araçları için)."""
        session = self._session()
        try:
            q = ("SELECT userid FROM student_registry "
                 "WHERE dropout_week IS NULL OR dropout_week > :week")
            if limit:
                q += f" LIMIT {limit}"
            result = session.execute(text(q), {"week": week})
            return [row[0] for row in result.fetchall()]
        finally:
            session.close()

    # ─────────────────────────────────────────────────────────────
    # Dashboard precompute tabloları (dash_*)
    # "Backend API'de JOIN yok; her tablo WHERE userid = ? ile okunur."
    # ─────────────────────────────────────────────────────────────

    def get_dash_user_stats(self, userid: int) -> Optional[Dict]:
        """dash_user_stats tablosundan tek satır döner. Pre-compute yoksa None."""
        session = self._session()
        try:
            row = session.execute(
                text("SELECT * FROM dash_user_stats WHERE userid = :uid"),
                {"uid": userid},
            ).fetchone()
            return dict(row._mapping) if row else None
        finally:
            session.close()

    def get_dash_course_progress(self, userid: int) -> pd.DataFrame:
        """dash_course_progress tablosundan kullanıcının tüm kurs satırları."""
        session = self._session()
        try:
            return pd.read_sql(
                text("SELECT courseid, course_fullname, course_shortname, "
                     "completion_pct, total_visible_modules, completed_modules, "
                     "avg_grade, next_expected_date, last_activity_date "
                     "FROM dash_course_progress WHERE userid = :uid"),
                session.bind,
                params={"uid": userid},
            )
        finally:
            session.close()

    def get_dash_activity_heatmap(self, userid: int) -> pd.DataFrame:
        """dash_activity_heatmap tablosundan 7×24 = 168 satır döner."""
        session = self._session()
        try:
            return pd.read_sql(
                text("SELECT weekday, hour, event_count, session_starts "
                     "FROM dash_activity_heatmap WHERE userid = :uid "
                     "ORDER BY weekday, hour"),
                session.bind,
                params={"uid": userid},
            )
        finally:
            session.close()

    def get_dash_course_analytics(self, userid: int) -> pd.DataFrame:
        """dash_course_analytics tablosundan kurs analitiği satırları."""
        session = self._session()
        try:
            return pd.read_sql(
                text("SELECT courseid, assign_completion_rate, quiz_completion_rate, "
                     "avg_daily_minutes, forum_total, forum_interactions, "
                     "forum_interaction_rate, page_total, page_viewed, page_view_rate "
                     "FROM dash_course_analytics WHERE userid = :uid"),
                session.bind,
                params={"uid": userid},
            )
        finally:
            session.close()

    def get_dash_upcoming_events(self, userid: int) -> pd.DataFrame:
        """dash_upcoming_events tablosundan modül bazlı deadline satırları."""
        session = self._session()
        try:
            return pd.read_sql(
                text("SELECT courseid, cmid, module_type, display_name, course_name, "
                     "event_date, timestart, days_until, is_overdue, is_completed "
                     "FROM dash_upcoming_events WHERE userid = :uid "
                     "ORDER BY timestart"),
                session.bind,
                params={"uid": userid},
            )
        finally:
            session.close()

    def get_dash_daily_sessions(self, userid: int) -> pd.DataFrame:
        """dash_daily_sessions tablosundan kullanıcının günlük oturum satırları."""
        session = self._session()
        try:
            return pd.read_sql(
                text("SELECT activity_date, day_of_week, session_count, "
                     "total_minutes, page_views "
                     "FROM dash_daily_sessions WHERE userid = :uid "
                     "ORDER BY activity_date"),
                session.bind,
                params={"uid": userid},
            )
        finally:
            session.close()

    def get_dash_module_status(self, userid: int) -> pd.DataFrame:
        """dash_module_status tablosundan kullanıcının modül bazlı durum satırları."""
        session = self._session()
        try:
            return pd.read_sql(
                text("SELECT courseid, cmid, module_type, display_name, "
                     "is_completed, completion_time, first_view_time, expected_date "
                     "FROM dash_module_status WHERE userid = :uid"),
                session.bind,
                params={"uid": userid},
            )
        finally:
            session.close()

    def get_dash_risk(self, userid: int) -> Optional[Dict]:
        """
        Öğrencinin precompute edilmiş risk sonucunu dash_risk tablosundan döner.
        Tablo henüz yoksa / kayıt yoksa None (frontend 'pending' gösterir).
        Risk değerleri offline (student_success modeli) hesaplanıp yazılır.
        """
        session = self._session()
        try:
            row = session.execute(
                text("SELECT user_id, risk_score, risk_level, predicted_grade, "
                     "pass_probability, will_pass, computed_at "
                     "FROM dash_risk WHERE user_id = :uid"),
                {"uid": userid},
            ).fetchone()
            return dict(row._mapping) if row else None
        except Exception:
            return None
        finally:
            session.close()

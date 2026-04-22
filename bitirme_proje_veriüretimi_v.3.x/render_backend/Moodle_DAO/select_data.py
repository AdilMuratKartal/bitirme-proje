"""
render_backend/Moodle_DAO/select_data.py — Tüm SELECT Operasyonları

Inference için gereken 7 kritik tablo + analiz tabloları okuma.
Bu mixin MoodleDAO sınıfına dahil edilir — doğrudan kullanılmaz.
"""

from __future__ import annotations

from typing import List, Dict, Optional
import pandas as pd
from sqlalchemy import text


class SelectMixin:
    """READ metodları — MoodleDAO sınıfına mixin olarak bağlanır."""

    def get_active_student_ids(self, week: int, limit: Optional[int] = None) -> List[int]:
        """
        student_registry tablosundan aktif öğrenci ID'lerini döner.
        Cron Job için: tüm aktif öğrenciler (limit=None).
        Test için: limit=N.
        """
        session = self._session()
        try:
            q = "SELECT userid FROM student_registry WHERE is_active = true"
            if limit:
                q += f" LIMIT {limit}"
            result = session.execute(text(q))
            return [row[0] for row in result.fetchall()]
        finally:
            session.close()

    def get_batch_tables(self, userids: List[int]) -> Dict[str, pd.DataFrame]:
        """
        Verilen öğrenci ID listesi için inference'ta gereken 7 tabloyu çeker.
        Hot path: tek öğrenci [uid] ile çağrılır.
        Cold path: 500'lük chunk ile çağrılır.
        """
        if not userids:
            return {}

        uid_list = ",".join(str(u) for u in userids)
        session = self._session()
        try:
            tables: Dict[str, pd.DataFrame] = {}

            tables["mdl_logstore_standard_log"] = pd.read_sql(
                text(f"SELECT userid, timecreated, component, action, contextlevel "
                     f"FROM mdl_logstore_standard_log WHERE userid IN ({uid_list})"),
                session.bind
            )
            tables["mdl_grade_grades"] = pd.read_sql(
                text(f"SELECT userid, itemid, finalgrade, timemodified "
                     f"FROM mdl_grade_grades WHERE userid IN ({uid_list})"),
                session.bind
            )
            tables["mdl_grade_items"] = pd.read_sql(
                text("SELECT id, courseid, itemtype, grademax FROM mdl_grade_items"),
                session.bind
            )
            tables["mdl_assign_submission"] = pd.read_sql(
                text(f"SELECT userid, assignment, timemodified, status, delay_hours "
                     f"FROM mdl_assign_submission WHERE userid IN ({uid_list})"),
                session.bind
            )
            tables["mdl_quiz_attempts"] = pd.read_sql(
                text(f"SELECT userid, quiz, timestart, timefinish, state, uniqueid, duration_minutes "
                     f"FROM mdl_quiz_attempts WHERE userid IN ({uid_list})"),
                session.bind
            )
            tables["mdl_course_modules"] = pd.read_sql(
                text("SELECT id, course, module, section, topic, content_type "
                     "FROM mdl_course_modules"),
                session.bind
            )
            tables["mdl_course_modules_completion"] = pd.read_sql(
                text(f"SELECT userid, coursemoduleid, completionstate "
                     f"FROM mdl_course_modules_completion WHERE userid IN ({uid_list})"),
                session.bind
            )
            tables["mdl_question_attempts"] = pd.read_sql(
                text(f"SELECT qa.id, qa.questionusageid, qa.questionid, qa.rightanswer, "
                     f"       qa.fraction "
                     f"FROM mdl_question_attempts qa "
                     f"INNER JOIN mdl_quiz_attempts qza ON qza.uniqueid = qa.questionusageid "
                     f"WHERE qza.userid IN ({uid_list})"),
                session.bind
            )
            tables["mdl_question_attempt_steps"] = pd.read_sql(
                text(f"SELECT qas.questionattemptid, qas.state, qas.timecreated "
                     f"FROM mdl_question_attempt_steps qas "
                     f"INNER JOIN mdl_question_attempts qa ON qa.id = qas.questionattemptid "
                     f"INNER JOIN mdl_quiz_attempts qza ON qza.uniqueid = qa.questionusageid "
                     f"WHERE qza.userid IN ({uid_list})"),
                session.bind
            )
            tables["mdl_question"] = pd.read_sql(
                text("SELECT id, category FROM mdl_question"),
                session.bind
            )
            tables["mdl_question_categories"] = pd.read_sql(
                text("SELECT id, name FROM mdl_question_categories"),
                session.bind
            )
            tables["student_registry"] = pd.read_sql(
                text(f"SELECT userid, segment, is_active "
                     f"FROM student_registry WHERE userid IN ({uid_list})"),
                session.bind
            )
            return tables
        finally:
            session.close()

    def get_mimo_analysis(self, userid: int) -> Optional[Dict]:
        """Tek öğrencinin MIMO analiz sonucunu döner. Yoksa None."""
        session = self._session()
        try:
            result = session.execute(
                text("SELECT user_id, risk_score, risk_level, predicted_grade, "
                     "model_confidence, computed_at "
                     "FROM mdl_mimo_analysis WHERE user_id = :uid"),
                {"uid": userid}
            ).fetchone()
            if result is None:
                return None
            return dict(result._mapping)
        finally:
            session.close()

    def get_hkrt_analysis(self, userid: int) -> List[Dict]:
        """Tek öğrencinin HKRT (HKAR) öneri listesini döner."""
        session = self._session()
        try:
            rows = session.execute(
                text("SELECT user_id, topic_id, resource_type, priority, reason_text, computed_at "
                     "FROM mdl_hkrt_analysis WHERE user_id = :uid ORDER BY priority"),
                {"uid": userid}
            ).fetchall()
            return [dict(r._mapping) for r in rows]
        finally:
            session.close()

    def get_basic_values(self, userid: int) -> Optional[Dict]:
        """Tek öğrencinin temel değer özetini döner. Yoksa None."""
        session = self._session()
        try:
            result = session.execute(
                text("SELECT user_id, gpa, total_courses, completed_credits, "
                     "login_streak, updated_at "
                     "FROM mdl_basic_values WHERE user_id = :uid"),
                {"uid": userid}
            ).fetchone()
            if result is None:
                return None
            return dict(result._mapping)
        finally:
            session.close()

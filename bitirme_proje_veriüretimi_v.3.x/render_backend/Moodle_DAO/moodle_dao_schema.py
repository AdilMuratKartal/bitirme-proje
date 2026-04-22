"""
render_backend/Moodle_DAO/moodle_dao_schema.py — MoodleDAO Ana Sınıfı

Sorumluluk: Tek SQL erişim noktası. Connection pool yönetimi.
Transaction lifecycle. Başka hiçbir dosya doğrudan SQL yazmaz.

SELECT → select_data.py
WRITE  → write_data.py
Her ikisi de bu sınıfa mixin olarak bağlanır.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, List, Dict
import pandas as pd
from sqlalchemy.orm import Session

from Moodle_DAO.select_data import SelectMixin
from Moodle_DAO.write_data import WriteMixin


class MoodleDAO(SelectMixin, WriteMixin):
    """
    Tek veritabanı erişim sınıfı.

    FK sırası (DAO garantisi — physical FK yok, logical FK burada enforce edilir):
    mdl_user → mdl_course → mdl_grade_items → mdl_course_modules
    → mdl_question_categories → mdl_question → mdl_quiz → mdl_assign
    → mdl_logstore_standard_log → mdl_grade_grades → mdl_grade_grades_history
    → mdl_quiz_attempts → mdl_question_attempts → mdl_question_attempt_steps
    → mdl_assign_submission → mdl_course_modules_completion → student_registry
    """

    def __init__(self, session_factory):
        self._sf = session_factory  # DI: dışarıdan enjekte edilir

    @contextmanager
    def transaction(self) -> Generator[Session, None, None]:
        """
        WRITE işlemleri için transaction context manager.
        Başarısızlıkta rollback, başarıda commit.
        READ işlemleri bu context'i KULLANMAZ (autocommit).
        """
        session: Session = self._sf()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _session(self) -> Session:
        """READ işlemleri için tek seferlik session (autocommit davranışı)."""
        return self._sf()

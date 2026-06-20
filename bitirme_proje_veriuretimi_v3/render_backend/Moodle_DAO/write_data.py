"""
render_backend/Moodle_DAO/write_data.py — WRITE Operasyonları (dash-only)

Dash-only mimaride API hiçbir şey YAZMAZ. Tüm precompute (dash_*, dash_risk)
offline araçlarla (localv2 pipeline + student_success modeli) hesaplanıp yüklenir.
Bu mixin geriye dönük uyumluluk için boş bırakılmıştır.
"""

from __future__ import annotations
from sqlalchemy import text


class WriteMixin:
    """WRITE metodları — dash-only mimaride API write yapmaz (boş mixin)."""
    
    def upsert_dash_risk(self, risk_data: dict) -> None:
        """Kullanıcının risk sonucunu dash_risk tablosuna yazar (varsa önce siler)."""
        with self.transaction() as session:
            session.execute(
                text("DELETE FROM dash_risk WHERE user_id = :user_id"),
                {"user_id": risk_data["user_id"]}
            )
            session.execute(
                text("INSERT INTO dash_risk (user_id, risk_score, risk_level, predicted_grade, pass_probability, will_pass, computed_at) "
                     "VALUES (:user_id, :risk_score, :risk_level, :predicted_grade, :pass_probability, :will_pass, :computed_at)"),
                risk_data
            )

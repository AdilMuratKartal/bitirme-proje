"""
render_backend/Moodle_DAO/write_data.py — WRITE Operasyonları (dash-only)

Dash-only mimaride API hiçbir şey YAZMAZ. Tüm precompute (dash_*, dash_risk)
offline araçlarla (localv2 pipeline + student_success modeli) hesaplanıp yüklenir.
Bu mixin geriye dönük uyumluluk için boş bırakılmıştır.
"""

from __future__ import annotations


class WriteMixin:
    """WRITE metodları — dash-only mimaride API write yapmaz (boş mixin)."""
    pass

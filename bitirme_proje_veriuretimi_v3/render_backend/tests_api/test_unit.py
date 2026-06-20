"""
Unit testleri — saf fonksiyonlar (DB/ag yok, milisaniye).

  - ServiceLayer/common_utils.py   : risk %, gun farki, modul->event, tarih, yetkinlik etiketi
  - 08_compute_risk._risk_level    : risk_score -> seviye esikleri (importlib ile yuklenir)
"""
import os
import importlib.util

from ServiceLayer.common_utils import (
    failure_risk_pct, days_until, event_type_for_module,
    format_date_short, label_competency,
)


# ── common_utils ─────────────────────────────────────────────────
def test_failure_risk_pct():
    assert failure_risk_pct(0.245) == 24.5
    assert failure_risk_pct(1.0) == 100.0
    assert failure_risk_pct(0.0) == 0.0


def test_days_until():
    assert days_until(1_000_000 + 5 * 86_400, 1_000_000) == 5   # gelecek -> 5 gun
    assert days_until(1_000_000, 1_000_000 + 86_400) is None    # gecmis -> None


def test_event_type_for_module():
    assert event_type_for_module("assign") == "assignment"
    assert event_type_for_module("quiz") == "quiz"
    assert event_type_for_module("forum") == "forum"
    assert event_type_for_module("bilinmeyen") == "other"


def test_format_date_short():
    # 1_750_000_000 -> 2025-06-15 (UTC) civari; "15 Haz" benzeri
    out = format_date_short(1_750_000_000)
    assert isinstance(out, str) and len(out) >= 4


def test_label_competency_esikleri():
    assert label_competency(85, "OKUMA", 10, 9)[0] == "Mükemmel"
    assert label_competency(65, "FORUM", 10, 7)[0] == "Yeterli"
    assert label_competency(45, "ÖDEV", 10, 5)[0] == "Geliştirilmeli"
    assert label_competency(20, "İZLEME", 10, 2)[0] == "Düşük"


# ── 08_compute_risk._risk_level (rakamla baslayan modul -> importlib) ──
def _load_risk_level():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))   # bitirme_proje_veriuretimi_v3/
    pipeline = os.path.join(root, "localv2", "pipeline")
    import sys
    if pipeline not in sys.path:
        sys.path.insert(0, pipeline)                # common importu icin
    path = os.path.join(pipeline, "06_dashboard_tables", "08_compute_risk.py")
    spec = importlib.util.spec_from_file_location("compute_risk_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._risk_level


def test_risk_level_esikleri():
    rl = _load_risk_level()
    assert rl(10.0) == "Düşük"     # < 40
    assert rl(39.9) == "Düşük"
    assert rl(40.0) == "Orta"      # 40-70
    assert rl(70.0) == "Orta"
    assert rl(70.1) == "Yüksek"    # > 70
    assert rl(96.0) == "Yüksek"

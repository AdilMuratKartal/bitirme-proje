"""
Canli SALT-OKUNUR entegrasyon testleri — gercek render.com servisi.

Yalnizca GET → production veriye SIFIR yazma.
/health token'siz; /api/student/me/* gercek Firebase token ister (LI_TOKEN).
"""
import pytest

from tests_api.conftest import requires_token


# ── Acik uc: servis ayakta mi (token'siz) ────────────────────────
def test_health(anon_client):
    r = anon_client.get("/health")
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "ok"


# ── Korumali uclar: 200 + beklenen ust-duzey anahtarlar ──────────
# (endpoint, beklenen anahtarlar) — yanit sema sagligi
_ENDPOINTS = [
    ("/api/student/me/home",             ["user_id", "active_courses"]),
    ("/api/student/me/dashboard",        ["risk_premodel_analysis", "basic_values"]),
    ("/api/student/me/grades",           ["ongoing_courses", "completed_courses"]),
    ("/api/student/me/learning-path",    ["timeline", "chartjs_labels", "chartjs_datasets"]),
    ("/api/student/me/competencies",     ["competencies"]),
    ("/api/student/me/events",           ["items"]),
    ("/api/student/me/basic",            []),   # dash_user_stats duz dict ya da 202 pending
    ("/api/student/me/heatmap",          ["data"]),
    ("/api/student/me/course-analytics", ["courses"]),
]


@requires_token
@pytest.mark.parametrize("endpoint,keys", _ENDPOINTS, ids=[e for e, _ in _ENDPOINTS])
def test_endpoint_donuyor_ve_sema(client, endpoint, keys):
    r = client.get(endpoint)
    # /basic pre-compute yoksa 202 dondurebilir — ikisi de gecerli
    assert r.status_code in (200, 202), f"{endpoint} -> {r.status_code}: {r.text[:200]}"
    body = r.json()
    if r.status_code == 200:
        for k in keys:
            assert k in body, f"{endpoint} yanitinda '{k}' yok"


# ── Veri sagligi: dashboard risk blogu mevcut (None/pending kabul) ─
@requires_token
def test_dashboard_risk_blogu_mevcut(client):
    r = client.get("/api/student/me/dashboard")
    assert r.status_code == 200, r.text
    blk = r.json()["risk_premodel_analysis"]
    for f in ("risk_score", "risk_level", "pass_probability", "will_pass"):
        assert f in blk          # alan var; degeri None olabilir (freshness=pending)

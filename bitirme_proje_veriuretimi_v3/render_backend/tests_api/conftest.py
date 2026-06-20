"""
render_backend/tests_api/conftest.py — CANLI render.com servisine SALT-OKUNUR test ortami

- Hicbir production verisi DEGISTIRILMEZ (yalnizca GET).
- Gercek deployed servise httpx ile baglanir (app import / SQLite YOK).
- /api/student/me/* uclari gercek Firebase token ister (LI_TOKEN env).

Env:
    LI_API_BASE  (varsayilan: https://learning-insight-api.onrender.com)
    LI_TOKEN     (Firebase ID token — DevTools'tan; ~1 saat gecerli)

Calistirma:
    $env:LI_TOKEN="<token>"
    .venv_gpu/Scripts/python -m pytest render_backend/tests_api -v
"""
import os
import sys

import httpx
import pytest

# render_backend kokunu path'e ekle (yalniz unit testlerin ServiceLayer importu icin;
# uygulama/DB import edilmez).
_RB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RB not in sys.path:
    sys.path.insert(0, _RB)

BASE_URL = os.environ.get("LI_API_BASE", "https://learning-insight-api.onrender.com").rstrip("/")
TOKEN = os.environ.get("LI_TOKEN", "").strip()

# Token gerektiren testleri token yoksa atla
requires_token = pytest.mark.skipif(
    not TOKEN, reason="LI_TOKEN ayarlanmamis — canli /api/* testleri atlandi (sadece /health kosar)"
)


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def anon_client():
    """Token'siz istemci (yalniz acik uclar: /health)."""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        yield c


@pytest.fixture
def client():
    """Firebase token'li istemci (korumali /api/* uclari icin)."""
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30.0) as c:
        yield c

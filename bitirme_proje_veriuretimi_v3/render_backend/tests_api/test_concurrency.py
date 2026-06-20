"""
Es-zamanlilik testi — CANLI render.com, SALT-OKUNUR.

Cok sayida kullanici ayni anda istek atinca servis tutarli/saglikli mi?
Yalnizca GET (prod'a yazma yok). Standard-tier'i yormamak icin dusuk worker (16).
Gercek olcekli yuk testi icin: tests/load/locustfile.py (Locust).
"""
import concurrent.futures as cf

import httpx
import pytest

from tests_api.conftest import requires_token, BASE_URL, TOKEN

_WORKERS = 16


def _get_dashboard():
    # Her worker KENDİ istemcisini kullanir (httpx.Client thread-paylasimi yok)
    with httpx.Client(base_url=BASE_URL,
                      headers={"Authorization": f"Bearer {TOKEN}"},
                      timeout=30.0) as c:
        r = c.get("/api/student/me/dashboard")
        return r.status_code, r.text


@requires_token
def test_eszamanli_istekler_tutarli():
    with cf.ThreadPoolExecutor(max_workers=_WORKERS) as ex:
        results = list(ex.map(lambda _: _get_dashboard(), range(_WORKERS)))

    # 1) Hepsi basarili
    codes = [sc for sc, _ in results]
    assert all(sc == 200 for sc in codes), f"Basarisiz kodlar: {[c for c in codes if c != 200]}"

    # 2) Es-zamanli kullanicida tutarlilik: ayni kullanici icin tum yanit govdeleri ozdes
    #    (snapshot okuma — cache/stale veya yarisma kaynakli sapma YOK)
    bodies = {txt for _, txt in results}
    assert len(bodies) == 1, "Es-zamanli yanitlar birbirinden farkli (tutarsizlik!)"


@requires_token
def test_eszamanli_health_yuksek_basari():
    # Acik uc uzerinde hafif eszamanli yuk — hata orani 0 olmali
    def _h():
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
            return c.get("/health").status_code
    with cf.ThreadPoolExecutor(max_workers=_WORKERS) as ex:
        codes = list(ex.map(lambda _: _h(), range(_WORKERS)))
    assert all(c == 200 for c in codes)

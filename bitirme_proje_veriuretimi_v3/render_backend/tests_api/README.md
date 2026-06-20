# API test süiti — CANLI render.com (salt-okunur) + unit

Bu klasör gerçek deployed servisi (**https://learning-insight-api.onrender.com**) **salt-okunur**
doğrular (yalnızca GET → production veriye **sıfır yazma**) + saf fonksiyon unit testleri içerir.

## Çalıştırma
```bash
# repo: bitirme_proje_veriuretimi_v3/
# 1) Token'ı al: frontend DevTools -> Network -> bir /api isteği -> Authorization: Bearer ...
$env:LI_TOKEN="<firebase_id_token>"            # PowerShell
# set LI_TOKEN=<...>                            # cmd

# 2) Çalıştır
.venv_gpu/Scripts/python -m pytest render_backend/tests_api -v
```
- **Token yoksa:** `/api/*` canlı testleri **atlanır (skip)**; `/health` ve unit testler yine koşar.
- **Farklı ortam:** `LI_API_BASE` ile URL değiştirilebilir (örn. yerel `http://localhost:8000`).
- Token ~1 saat geçerli; süresi dolarsa `/api/*` 401 verir → yeni token al.

## Kapsam
| Dosya | Katman | Ne |
|-------|--------|----|
| `test_live_readonly.py` | Canlı entegrasyon (GET) | `/health` + 9 `/api/student/me/*` ucu → 200 + şema (üst-düzey anahtarlar); dashboard risk bloğu mevcut |
| `test_concurrency.py` | Canlı eş-zamanlılık (GET) | 16 eş-zamanlı `/dashboard` → hepsi 200 + **tutarlı** (cache/stale yok); 16 eş-zamanlı `/health` |
| `test_unit.py` | Unit (offline) | `common_utils` + `08_compute_risk._risk_level` eşikleri |
| `conftest.py` | Altyapı | httpx client (token'lı/anon) + `requires_token` skip |

## Güvenlik
- **Sadece GET** → mevcut çalışan servise/veriye **dokunmaz**.
- Eş-zamanlılık düşük worker (16) → standard-tier'i yormaz.
- "DB değişince yanıt değişir" testi **bilerek yok** (prod'a yazmak gerekir). O doğrulama, offline
  upload sonrası elle/gözle yapılır.

## Yük testi (gerçek ölçek) — ayrı
20/50/100/1000 eş-zamanlı kullanıcı: [`../../tests/load/locustfile.py`](../../tests/load/locustfile.py)
```bash
.venv_gpu/Scripts/pip install locust
$env:LI_TOKEN="<token>"
locust -f tests/load/locustfile.py --host https://learning-insight-api.onrender.com \
       -u 100 -r 10 -t 2m --headless --csv=load_100
```
`--csv` çıktısı (p50/p95/RPS/hata oranı) tezde tabloya konur.
```

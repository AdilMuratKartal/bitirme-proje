"""
tests/load/locustfile.py — Learning-Insight API yuk testi (Locust)

Eszamanli 20 / 50 / 100 / 1000 aktif kullanici senaryolari icin.
Tum /api/student/me/* endpoint'leri Firebase Bearer token ister.

Kurulum:
    .venv_gpu/Scripts/pip install locust

Token (frontend DevTools -> Network -> bir /api istegi -> Authorization basligi):
    set  LI_TOKEN=eyJhbG...        (Windows cmd)
    $env:LI_TOKEN="eyJhbG..."      (PowerShell)

Calistirma (ornek: 100 kullanici, saniyede 10 rampa):
    locust -f tests/load/locustfile.py \
           --host https://learning-insight-api.onrender.com \
           -u 100 -r 10 -t 2m --headless --csv=load_100

  -u 1000 -r 50   -> 1000 kullanici
  -u 50  -r 10    -> 50 kullanici
  -u 20  -r 5     -> 20 kullanici
  (--csv cikti: load_*_stats.csv -> p50/p95/RPS/hata orani tabloya)

Web arayuzu icin --headless'i kaldir, http://localhost:8089 ac.
"""
import os
import random

from locust import HttpUser, task, between

_TOKEN = os.environ.get("LI_TOKEN", "")
_ENDPOINTS = [
    "/api/student/me/home",
    "/api/student/me/dashboard",
    "/api/student/me/grades",
    "/api/student/me/learning-path",
    "/api/student/me/competencies",
    "/api/student/me/events",
    "/api/student/me/basic",
    "/api/student/me/heatmap",
    "/api/student/me/course-analytics",
]


class OgrenciUser(HttpUser):
    # Gercekci kullanici: istekler arasi 1-3 sn dusunme suresi
    wait_time = between(1, 3)

    def on_start(self):
        if not _TOKEN:
            print("[UYARI] LI_TOKEN bos — istekler 401/403 donebilir.")
        self.client.headers.update({"Authorization": f"Bearer {_TOKEN}"})

    @task(3)
    def dashboard_acilisi(self):
        # Tipik acilis: home + dashboard birlikte yuklenir
        self.client.get("/api/student/me/home", name="home")
        self.client.get("/api/student/me/dashboard", name="dashboard")

    @task(1)
    def rastgele_sayfa(self):
        ep = random.choice(_ENDPOINTS)
        self.client.get(ep, name=ep)

    @task(1)
    def health(self):
        self.client.get("/health", name="health")

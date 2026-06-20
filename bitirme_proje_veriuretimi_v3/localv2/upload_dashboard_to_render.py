"""
localv2/upload_dashboard_to_render.py

Dashboard pre-compute CSV'lerini + golden kullanicilari render.com PostgreSQL'e yukler.
Mevcut yukleme desenini (DATABASE_URL + SQLAlchemy to_sql) tekrar kullanir.

.env icindeki DATABASE_URL kullanilir (external render URL, ?sslmode=require URL'de).

Calistirma (repo kokunden veya herhangi bir yerden):
    .venv_gpu/Scripts/python localv2/upload_dashboard_to_render.py
    .venv_gpu/Scripts/python localv2/upload_dashboard_to_render.py --yes   # onay sormadan

Yuklenen tablolar:
    9 dash tablosu (dash_risk + dash_features dahil) + golden_users + student_registry
    (hepsi if_exists="replace")
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect as sa_inspect, text

_HERE = os.path.dirname(os.path.abspath(__file__))          # localv2/
_ROOT = os.path.dirname(_HERE)                              # proje koku
_ENV  = os.path.join(_ROOT, ".env")

_DASH_DIR   = os.path.join(_HERE, "pipeline", "06_dashboard_tables", "cikti")
_GOLDEN_CSV = os.path.join(_HERE, "pipeline", "00_golden_users", "cikti", "golden_1000.csv")

_SEP = "=" * 64

# CSV dosya adi -> hedef tablo adi
_CSV_TO_TABLE = {
    "dash_01_daily_sessions.csv":   "dash_daily_sessions",
    "dash_02_user_stats.csv":       "dash_user_stats",
    "dash_03_course_progress.csv":  "dash_course_progress",
    "dash_04_module_status.csv":    "dash_module_status",
    "dash_05_course_analytics.csv": "dash_course_analytics",
    "dash_06_activity_heatmap.csv": "dash_activity_heatmap",
    "dash_07_upcoming_events.csv":  "dash_upcoming_events",
    "dash_08_risk.csv":             "dash_risk",
    "dash_09_features.csv":         "dash_features",
    "dash_09_grade_items.csv":      "dash_grade_items",
}

# Yukleme sonrasi olusturulacak index'ler (backend tum sorgularda WHERE userid = ?)
_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_dash_user_stats_uid       ON dash_user_stats(userid);",
    "CREATE INDEX IF NOT EXISTS idx_dash_course_progress_uid  ON dash_course_progress(userid);",
    "CREATE INDEX IF NOT EXISTS idx_dash_course_analytics_uid ON dash_course_analytics(userid);",
    "CREATE INDEX IF NOT EXISTS idx_dash_activity_heatmap_uid ON dash_activity_heatmap(userid);",
    "CREATE INDEX IF NOT EXISTS idx_dash_upcoming_events_uid  ON dash_upcoming_events(userid);",
    "CREATE INDEX IF NOT EXISTS idx_dash_daily_sessions_uid   ON dash_daily_sessions(userid);",
    "CREATE INDEX IF NOT EXISTS idx_dash_module_status_uid    ON dash_module_status(userid);",
    # Risk: backend get_dash_risk WHERE user_id = ?  (NOT: kolon adi user_id)
    "CREATE INDEX IF NOT EXISTS idx_dash_risk_uid             ON dash_risk(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_dash_features_uid         ON dash_features(userid);",
    "CREATE INDEX IF NOT EXISTS idx_dash_grade_items_uid      ON dash_grade_items(userid);",
    "CREATE INDEX IF NOT EXISTS idx_golden_users_uid          ON golden_users(userid);",
    "CREATE INDEX IF NOT EXISTS idx_student_registry_uid      ON student_registry(userid);",
    "CREATE INDEX IF NOT EXISTS idx_student_registry_dropout  ON student_registry(dropout_week);",
    # Auth: firebase_uid -> userid lookup (token dogrulama hot-path)
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_student_registry_firebase_uid ON student_registry(firebase_uid);",
]


def _ask_yes_no(soru: str) -> bool:
    """Evet/Hayir sorar. Varsayilan: Hayir."""
    while True:
        cevap = input(f"\n  {soru} [e/H]: ").strip().lower()
        if cevap in ("e", "evet", "y", "yes"):
            return True
        if cevap in ("", "h", "hayir", "hayır", "n", "no"):
            return False
        print("  Gecersiz giris — 'e' veya 'h' yazin.")


def _make_engine():
    load_dotenv(_ENV)
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit(f"[HATA] .env icinde DATABASE_URL yok. Beklenen: {_ENV}")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        # Hangi host'a yazildigini onayla (sifre gosterilmez)
        host = url.split("@")[-1].split("/")[0] if "@" in url else "?"
        print(f"  Baglanti basarili → {host}")
    except Exception as exc:
        sys.exit(f"[HATA] Baglanti kurulamadi: {exc}")
    return engine


def _safe_chunksize(n_cols: int) -> int:
    """
    method='multi' tek INSERT'te n_cols*chunksize parametre uretir; Postgres
    siniri 65535. Guvenli kalmak icin 60000 / n_cols (max 5000).
    """
    if n_cols <= 0:
        return 5000
    return max(1, min(5000, 60000 // n_cols))


def _upload(df: pd.DataFrame, table: str, engine) -> int:
    # Bos CSV (0 satir, basliklar var) → tablo yine de olusturulur ki backend
    # WHERE userid=? sorgusu "tablo yok" hatasi yerine bos sonuc dondursun.
    cs = _safe_chunksize(max(df.shape[1], 1))
    t0 = time.time()
    df.to_sql(table, engine, if_exists="replace", index=False,
              chunksize=cs, method="multi")
    note = "  (BOS tablo)" if df.empty else ""
    print(f"  {table:<26s} {len(df):>8,} satir  {df.shape[1]:>2d} sutun  "
          f"{time.time() - t0:>6.1f}s  OK{note}")
    return len(df)


def _build_student_registry(golden: pd.DataFrame, engine) -> pd.DataFrame:
    """
    golden_1000'den student_registry turet (hepsi aktif, dropout yok).
    KRITIK: Tablo REPLACE edildiginden, mevcut firebase_uid/firebase_email
    eslemelerini (seed_firebase_users + manuel demo eslemesi) DB'den okuyup
    userid uzerinden koruruz. Aksi halde her dash yuklemesinde auth eslemesi silinir.
    """
    reg = golden[["userid"]].copy()
    reg["segment"]      = "GOLDEN"
    reg["is_active"]    = True
    reg["dropout_week"] = pd.Series([pd.NA] * len(reg), dtype="Int64")  # NULL

    try:
        existing = pd.read_sql(
            "SELECT userid, firebase_uid, firebase_email FROM student_registry", engine
        )
        reg = reg.merge(existing, on="userid", how="left")
        kept = int(reg["firebase_uid"].notna().sum())
        print(f"  student_registry: {kept} firebase eslemesi korundu")
    except Exception as exc:
        # Tablo henuz yok (ilk yukleme) -> bos kolonlar
        reg["firebase_uid"] = None
        reg["firebase_email"] = None
        print(f"  student_registry: mevcut firebase eslemesi yok ({exc})")
    return reg


def main() -> None:
    parser = argparse.ArgumentParser(description="Dashboard CSV -> render PostgreSQL")
    parser.add_argument("--yes", action="store_true", help="Onay sormadan yukle")
    args = parser.parse_args()

    print(_SEP)
    print("  Dashboard + Golden Users -> render.com PostgreSQL")
    print(_SEP)

    # Kaynak dosyalari dogrula
    missing = [c for c in _CSV_TO_TABLE if not os.path.exists(os.path.join(_DASH_DIR, c))]
    if missing:
        sys.exit(f"[HATA] Eksik dash CSV: {missing}\n  Once dashboard pipeline'i calistirin.")
    if not os.path.exists(_GOLDEN_CSV):
        sys.exit(f"[HATA] golden_1000.csv yok: {_GOLDEN_CSV}")

    engine = _make_engine()

    if not args.yes:
        onay = _ask_yes_no(
            "Render DB'de bu tablolar SILINIP yeniden yazilacak (REPLACE):\n"
            "  9 dash tablosu (dash_risk + dash_features dahil) + golden_users + student_registry\n"
            "  Devam edilsin mi?"
        )
        if not onay:
            print("\n  Iptal edildi.")
            engine.dispose()
            return

    print(f"\n  [Yukleme] kaynak: {_DASH_DIR}")
    print(_SEP)
    total = 0

    # 1) 7 dash tablosu
    for csv_name, table in _CSV_TO_TABLE.items():
        df = pd.read_csv(os.path.join(_DASH_DIR, csv_name))
        total += _upload(df, table, engine)

    # 2) golden_users (ham liste)
    golden = pd.read_csv(_GOLDEN_CSV)
    total += _upload(golden, "golden_users", engine)

    # 3) student_registry (golden'dan turetilmis + firebase eslemeleri korunarak)
    total += _upload(_build_student_registry(golden, engine), "student_registry", engine)

    print(_SEP)
    print(f"  Toplam yazilan satir: {total:,}")

    # 4) Index'ler — her biri ayri commit (biri patlarsa digerleri kalir)
    print("\n  [Index] olusturuluyor ...")
    ok = 0
    for sql in _INDEXES:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
            ok += 1
        except Exception as exc:
            print(f"    [UYARI] index atlandi: {exc}")
    print(f"  {ok}/{len(_INDEXES)} index OK")

    # 5) Dogrulama ozeti — satir sayilari
    print("\n  [Dogrulama] tablo satir sayilari:")
    check_tables = list(_CSV_TO_TABLE.values()) + ["golden_users", "student_registry"]
    insp = sa_inspect(engine)
    with engine.connect() as conn:
        for t in check_tables:
            if insp.has_table(t):
                n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                print(f"    {t:<26s} {n:>8,}")

    engine.dispose()
    print(f"\n{_SEP}\n  Tamamlandi.\n{_SEP}")


if __name__ == "__main__":
    main()

"""
localv2/drop_render_mdl_tables.py

Render PostgreSQL'den ARTIK KULLANILMAYAN mdl_* tablolarini siler.

Gerekce: canli backend dash-only mimaride; yalnizca dash_* + student_registry okur.
mdl_* tablolari eski mimariden kalan artiklardir (canli API'de SIFIR mdl_ sorgusu).
Offline pipeline dash_*'i YEREL anon CSV'lerden uretir, render mdl_*'tan degil.

Guvenlik: silmeden ONCE her tabloyu CSV'ye yedekler (geri donulebilir).

Calistirma:
    .venv_gpu/Scripts/python localv2/drop_render_mdl_tables.py            # yedekle + onay sor
    .venv_gpu/Scripts/python localv2/drop_render_mdl_tables.py --yes      # onay sormadan
    .venv_gpu/Scripts/python localv2/drop_render_mdl_tables.py --no-backup --yes
"""
from __future__ import annotations

import argparse
import os
import sys
import datetime as _dt

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_ENV  = os.path.join(_ROOT, ".env")

_DEFAULT_BACKUP = os.path.join(
    r"C:\Users\2025\Documents\ML-Project",
    f"render_mdl_backup_{_dt.datetime.now():%Y%m%d_%H%M}",
)
_SEP = "=" * 64

# Korunacak (asla silinmeyecek) tablolar — guvenlik beyaz listesi
_PROTECTED_PREFIXES = ("dash_", "golden_users", "student_registry")


def _make_engine():
    load_dotenv(_ENV)
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit(f"[HATA] .env icinde DATABASE_URL yok: {_ENV}")
    eng = create_engine(url, pool_pre_ping=True)
    with eng.connect() as c:
        c.execute(text("SELECT 1"))
    host = url.split("@")[-1].split("/")[0] if "@" in url else "?"
    print(f"  Baglanti OK -> {host}")
    return eng


def _list_mdl_tables(engine) -> list[str]:
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND (tablename LIKE 'mdl\\_%' OR tablename LIKE 'anon\\_mdl\\_%') "
            "ORDER BY tablename"
        )).fetchall()
    tbls = [r[0] for r in rows]
    # Guvenlik: korunan prefiksleri ASLA dahil etme
    return [t for t in tbls if not t.startswith(_PROTECTED_PREFIXES)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="Onay sormadan sil")
    ap.add_argument("--no-backup", action="store_true", help="CSV yedegi alma")
    ap.add_argument("--backup-dir", default=_DEFAULT_BACKUP)
    args = ap.parse_args()

    print(_SEP); print("  Render mdl_* tablolarini SIL"); print(_SEP)
    engine = _make_engine()

    tables = _list_mdl_tables(engine)
    if not tables:
        print("  Silinecek mdl_* tablosu yok. Cikiliyor."); engine.dispose(); return

    print(f"\n  Bulunan mdl_* tablo: {len(tables)}")
    for t in tables:
        print(f"    - {t}")

    # 1) Yedek
    if not args.no_backup:
        os.makedirs(args.backup_dir, exist_ok=True)
        print(f"\n  [Yedek] -> {args.backup_dir}")
        for t in tables:
            try:
                df = pd.read_sql(f'SELECT * FROM "{t}"', engine)
                df.to_csv(os.path.join(args.backup_dir, f"{t}.csv"),
                          index=False, encoding="utf-8-sig")
                print(f"    {t:<34s} {len(df):>8,} satir yedeklendi")
            except Exception as exc:
                sys.exit(f"[HATA] {t} yedeklenemedi, SILME IPTAL: {exc}")
    else:
        print("\n  [Yedek] atlandi (--no-backup)")

    # 2) Onay
    if not args.yes:
        ans = input(f"\n  {len(tables)} mdl_* tablosu KALICI silinecek. Devam? [e/H]: ").strip().lower()
        if ans not in ("e", "evet", "y", "yes"):
            print("  Iptal edildi."); engine.dispose(); return

    # 3) DROP (tek transaction, CASCADE — aralarindaki FK'lari cozer)
    quoted = ", ".join(f'"{t}"' for t in tables)
    print("\n  [DROP] calistiriliyor ...")
    with engine.begin() as c:
        c.execute(text(f"DROP TABLE IF EXISTS {quoted} CASCADE"))
    print(f"  {len(tables)} tablo dusuruldu.")

    # 4) Dogrula
    with engine.connect() as c:
        remaining = [r[0] for r in c.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ))]
        still_mdl = [t for t in remaining if t.startswith(("mdl_", "anon_mdl_"))]
    print(f"\n  [Dogrulama] kalan tablo: {len(remaining)}")
    for t in remaining:
        print(f"    {t}")
    print(f"\n  Kalan mdl_*: {len(still_mdl)}  (beklenen: 0)")

    engine.dispose()
    print(f"\n{_SEP}\n  Tamamlandi.\n{_SEP}")


if __name__ == "__main__":
    main()

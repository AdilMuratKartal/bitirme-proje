"""
local/data_exporter.py — CSV → PostgreSQL Tek Seferlik Veri Aktarıcı
=====================================================================
SADECE lokal ortamda çalıştırılır. Render'a GİTMEZ.

Görev:
  local/csv_exports/ içindeki tüm Moodle CSV tablolarını
  Render PostgreSQL veritabanına yükler.

Çalıştırma (.venv_gpu aktifken):
    python local/data_exporter.py

Gereksinimler:
    pip install sqlalchemy psycopg2-binary python-dotenv
"""

from __future__ import annotations

import os
import sys
import time
import glob

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# ── Proje kökünü Python path'e ekle ──────────────────────────────
ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR     = os.path.join(ROOT, "local", "csv_exports")
ENV_PATH    = os.path.join(ROOT, ".env")

SEPARATOR = "=" * 62


def _load_db_url() -> str:
    load_dotenv(ENV_PATH)
    url = os.getenv("DATABASE_URL")
    if not url:
        print("[HATA] .env dosyasında DATABASE_URL bulunamadı.")
        print(f"       Beklenen konum: {ENV_PATH}")
        sys.exit(1)
    return url


def _get_csv_files() -> list[str]:
    pattern = os.path.join(CSV_DIR, "*.csv")
    files   = sorted(glob.glob(pattern))
    if not files:
        print(f"[HATA] {CSV_DIR} içinde CSV dosyası bulunamadı.")
        print("       Önce local/train_models.py çalıştırarak CSV'leri üretin.")
        sys.exit(1)
    return files


def export_all(if_exists: str = "replace", chunksize: int = 5000) -> None:
    print(SEPARATOR)
    print("  CSV → PostgreSQL Aktarıcı")
    print("  Hedef: Render.com Frankfurt PostgreSQL")
    print(SEPARATOR)

    # .env'den bağlantı URL'sini yükle
    db_url = _load_db_url()

    # SQLAlchemy engine — psycopg2 sürücüsü
    print("\n  [1/3] Veritabanına bağlanılıyor...")
    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  Bağlantı başarılı.")
    except Exception as exc:
        print(f"[HATA] Bağlantı kurulamadı: {exc}")
        sys.exit(1)

    # CSV dosyalarını bul
    csv_files = _get_csv_files()
    print(f"\n  [2/3] {len(csv_files)} tablo bulundu: {CSV_DIR}")
    print(SEPARATOR)

    toplam_satir = 0
    basarisiz    = []

    for idx, filepath in enumerate(csv_files, start=1):
        tablo_adi = os.path.splitext(os.path.basename(filepath))[0]
        t0 = time.time()

        try:
            df = pd.read_csv(filepath, low_memory=False)
            satir = len(df)

            df.to_sql(
                name      = tablo_adi,
                con       = engine,
                if_exists = if_exists,   # 'replace' → tabloyu silip yeniden yazar
                index     = False,
                chunksize = chunksize,
                method    = "multi",     # Toplu INSERT — tek tek INSERT'ten çok daha hızlı
            )

            sure = time.time() - t0
            toplam_satir += satir
            print(f"  [{idx:02d}/{len(csv_files)}] {tablo_adi:<45s} "
                  f"{satir:>9,} satır  {sure:>6.1f}s  OK")

        except Exception as exc:
            sure = time.time() - t0
            basarisiz.append(tablo_adi)
            print(f"  [{idx:02d}/{len(csv_files)}] {tablo_adi:<45s} "
                  f"{'HATA':>9s}         {sure:>6.1f}s  !! {exc}")

    # Özet
    print(SEPARATOR)
    print(f"\n  [3/3] Aktarım tamamlandı.")
    print(f"  Toplam tablo   : {len(csv_files)}")
    print(f"  Başarılı       : {len(csv_files) - len(basarisiz)}")
    print(f"  Başarısız      : {len(basarisiz)}" +
          (f" → {basarisiz}" if basarisiz else ""))
    print(f"  Toplam satır   : {toplam_satir:,}")
    print(SEPARATOR)

    engine.dispose()


if __name__ == "__main__":
    export_all()

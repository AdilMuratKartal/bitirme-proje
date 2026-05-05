"""
datafile_generator/postgresql/postgresql_data_generator.py — Simülasyon → PostgreSQL

Çalıştırma:
    python postgresql_data_generator.py              → 14 haftalık dönem → DB
    python postgresql_data_generator.py --weeks 8   → 8 hafta → DB
    python postgresql_data_generator.py --indexes   → yalnızca index oluştur (sim yok)

Gereksinimler:
    pip install sqlalchemy psycopg2-binary python-dotenv
.env içinde DATABASE_URL tanımlı olmalıdır.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Dict

import pandas as pd
from sqlalchemy import inspect as _sa_inspect

# local/ dizinini sys.path'e ekle (doğrudan çalıştırma için)
_PG_DIR  = os.path.dirname(os.path.abspath(__file__))
_DFG_DIR = os.path.dirname(_PG_DIR)
_LOCAL   = os.path.dirname(_DFG_DIR)
_ROOT    = os.path.dirname(_LOCAL)
for _p in (_LOCAL, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import CFG  # noqa: E402
from datafile_generator.base import run_simulation, save_meta  # noqa: E402

# Opsiyonel bağımlılıklar — import hatası durumunda kullanıcıya yönlendirme yap
try:
    from sqlalchemy import create_engine as _sa_create_engine, text as _sa_text
    from dotenv import load_dotenv as _load_dotenv
    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False

_SEP = "=" * 62
_ENV_PATH = os.path.join(_ROOT, ".env")


def _ask_yes_no(soru: str) -> bool:
    """Kullanıcıya evet/hayır sorar. Varsayılan: Hayır."""
    while True:
        cevap = input(f"\n  {soru} [e/H]: ").strip().lower()
        if cevap in ("e", "evet", "y", "yes"):
            return True
        if cevap in ("", "h", "hayir", "hayır", "n", "no"):
            return False
        print("  Geçersiz giriş — lütfen 'e' veya 'h' yazın.")

# CSV generator ile aynı tablo kategorileri
_STATIC_TABLES = frozenset({
    "mdl_user", "mdl_course", "mdl_course_modules", "mdl_quiz", "mdl_assign",
    "mdl_badge", "mdl_question", "mdl_question_categories", "mdl_grade_items",
    "mdl_grade_categories", "mdl_enrol", "mdl_user_enrolments", "mdl_forum",
})
_CUMULATIVE_TABLES = frozenset({
    "mdl_assign_submission",
    "mdl_course_modules_completion",
})


# ─────────────────────────────────────────────────────────────────
# VERİTABANI YARDIMCILARI
# ─────────────────────────────────────────────────────────────────

def _check_deps() -> None:
    if not _HAS_DEPS:
        print("[HATA] Eksik bagimliliklar. Lutfen calistirin:")
        print("       pip install sqlalchemy psycopg2-binary python-dotenv")
        sys.exit(1)


def _load_db_url() -> str:
    _load_dotenv(_ENV_PATH)
    url = os.getenv("DATABASE_URL")
    if not url:
        print("[HATA] .env dosyasinda DATABASE_URL bulunamadi.")
        print(f"       Beklenen konum: {_ENV_PATH}")
        sys.exit(1)
    return url


def _make_engine():
    url = _load_db_url()
    engine = _sa_create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(_sa_text("SELECT 1"))
        print("  Baglanti basarili.")
    except Exception as exc:
        print(f"[HATA] Baglanti kurulamadi: {exc}")
        sys.exit(1)
    return engine


def _table_exists(engine, table_name: str) -> bool:
    return _sa_inspect(engine).has_table(table_name)


# ─────────────────────────────────────────────────────────────────
# TABLOLARI VERİTABANINA YAZ
# ─────────────────────────────────────────────────────────────────

def write_tables_to_db(
    tables:    Dict[str, pd.DataFrame],
    engine,
    if_exists: str = "replace",
    chunksize: int = 5000,
) -> None:
    """
    Tüm DataFrame'leri PostgreSQL'e yazar.
    if_exists='replace' → tabloyu silip yeniden oluşturur (tam dönem yazımı).
    if_exists='append'  → mevcut tabloya ekler (artımlı yükleme).
    """
    print(_SEP)
    total_rows = 0
    failed     = []

    for idx, (tablo_adi, df) in enumerate(tables.items(), start=1):
        if df.empty:
            continue

        # 3-Tier append stratejisi
        if if_exists == "append":
            if tablo_adi in _STATIC_TABLES:
                if _table_exists(engine, tablo_adi):
                    print(f"  [{idx:02d}/{len(tables)}] {tablo_adi:<45s} {'ATLA':>9s}         (statik, mevcut)")
                    continue
                strategy = "replace"   # ilk çalışma — oluştur
            elif tablo_adi in _CUMULATIVE_TABLES:
                strategy = "replace"   # tam tablo yeniden yaz
            else:
                strategy = "append"    # transaction: sadece yeni satırlar
        else:
            strategy = if_exists       # "replace" — güvenli tam yazma

        t0 = time.time()
        try:
            df.to_sql(
                name      = tablo_adi,
                con       = engine,
                if_exists = strategy,
                index     = False,
                chunksize = chunksize,
                method    = "multi",
            )
            sure = time.time() - t0
            total_rows += len(df)
            print(f"  [{idx:02d}/{len(tables)}] {tablo_adi:<45s} "
                  f"{len(df):>9,} satir  {sure:>6.1f}s  OK")
        except Exception as exc:
            sure = time.time() - t0
            failed.append(tablo_adi)
            print(f"  [{idx:02d}/{len(tables)}] {tablo_adi:<45s} "
                  f"{'HATA':>9s}         {sure:>6.1f}s  !! {exc}")

    print(_SEP)
    print(f"  Toplam tablo   : {len(tables)}")
    print(f"  Basarili       : {len(tables) - len(failed)}")
    print(f"  Basarisiz      : {len(failed)}" + (f" -> {failed}" if failed else ""))
    print(f"  Toplam satir   : {total_rows:,}")
    print(_SEP)


# ─────────────────────────────────────────────────────────────────
# PERFORMANS INDEX'LERİ
# ─────────────────────────────────────────────────────────────────

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_log_userid      ON mdl_logstore_standard_log(userid);",
    "CREATE INDEX IF NOT EXISTS idx_log_course_time ON mdl_logstore_standard_log(courseid, timecreated);",
    "CREATE INDEX IF NOT EXISTS idx_grade_userid    ON mdl_grade_grades(userid, itemid);",
    "CREATE INDEX IF NOT EXISTS idx_qa_usage        ON mdl_question_attempts(questionusageid);",
    "CREATE INDEX IF NOT EXISTS idx_quizatt_user    ON mdl_quiz_attempts(userid, quiz);",
    "CREATE INDEX IF NOT EXISTS idx_completion_user ON mdl_course_modules_completion(userid, coursemoduleid);",
    "CREATE INDEX IF NOT EXISTS idx_assign_sub      ON mdl_assign_submission(userid, assignment);",
]

_INDEX_NAMES = [
    "idx_log_userid", "idx_log_course_time", "idx_grade_userid",
    "idx_qa_usage", "idx_quizatt_user", "idx_completion_user", "idx_assign_sub",
]


def drop_indexes(engine) -> None:
    """Yönetilen index'leri siler (DROP IF EXISTS — hata vermez)."""
    print("\n--- Mevcut index'ler siliniyor ---")
    with engine.connect() as conn:
        for name in _INDEX_NAMES:
            conn.execute(_sa_text(f"DROP INDEX IF EXISTS {name};"))
            print(f"  DROP  {name}")
        conn.commit()
    print("--- Index silme tamamlandi ---")


def create_indexes(engine) -> None:
    """Sorgulama performansını artıran index'leri oluşturur (idempotent)."""
    print("\n--- Index'ler olusturuluyor ---")
    with engine.connect() as conn:
        for sql in _INDEXES:
            conn.execute(_sa_text(sql))
            idx_name = sql.split("idx_")[1].split(" ")[0] if "idx_" in sql else sql[:40]
            print(f"  OK  idx_{idx_name}")
        conn.commit()
    print("--- Index'ler tamamlandi ---")


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    _check_deps()

    parser = argparse.ArgumentParser(
        description="Moodle Sentetik Veri Uretici — PostgreSQL Ciktisi",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Ornekler:
  python postgresql_data_generator.py              -> 14 haftalik donem -> DB
  python postgresql_data_generator.py --weeks 8   -> 8 hafta -> DB
  python postgresql_data_generator.py --indexes   -> yalnizca index olustur
""",
    )
    parser.add_argument("--weeks",   type=int, default=CFG.general.n_weeks,
                        help=f"Hafta sayisi (varsayilan: {CFG.general.n_weeks})")
    parser.add_argument("--output",  type=str, default="output",
                        help="Meta JSON dizini (varsayilan: output)")
    parser.add_argument("--indexes", action="store_true",
                        help="Simulasyon yapmadan sadece index'leri olustur/yenile")
    args = parser.parse_args()

    print(_SEP)
    print("  Simulasyon → PostgreSQL Veri Uretici")
    print(_SEP)

    engine = _make_engine()

    if args.indexes:
        yenile = _ask_yes_no("Mevcut index'ler önce silinsin mi? (DROP + CREATE)")
        if yenile:
            drop_indexes(engine)
        create_indexes(engine)
    else:
        eski_sil = _ask_yes_no(
            "Render DB'deki mevcut tablolar tamamen silinsin mi?\n"
            "  (Evet → REPLACE: eski veriler gider, yeni veri yazılır)\n"
            "  (Hayır → APPEND: mevcut veriler korunur, yeni satırlar eklenir)"
        )
        idx_yenile = _ask_yes_no(
            "Index'ler silinip yeniden oluşturulsun mu?\n"
            "  (Evet → DROP + CREATE  |  Hayır → CREATE IF NOT EXISTS)"
        )

        print()
        if_exists = "replace" if eski_sil else "append"
        print(f"  Strateji : {if_exists.upper()}")
        print(f"  Index    : {'DROP + CREATE' if idx_yenile else 'CREATE IF NOT EXISTS'}")
        print()

        tables = run_simulation(weeks=args.weeks)
        print(f"\n  [DB] Tablolar yaziliyor  (mod: {if_exists}) ...")
        write_tables_to_db(tables, engine, if_exists=if_exists)
        save_meta(tables, args.weeks, args.output)

        if idx_yenile:
            drop_indexes(engine)
        create_indexes(engine)

    engine.dispose()
    print("\n  Tamamlandi.")


if __name__ == "__main__":
    main()

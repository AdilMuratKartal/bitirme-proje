"""
datafile_generator/csv/csv_data_generator.py — Simülasyon → CSV

Kullanım:
    python csv_data_generator.py              → 14 haftalık dönem, output/raw_tables/
    python csv_data_generator.py --weeks 8
    python csv_data_generator.py --week 5     → cron modu (append)
    python csv_data_generator.py --view
    python csv_data_generator.py --view --table mdl_quiz_attempts --limit 20
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

# local/ dizinini sys.path'e ekle (doğrudan çalıştırma için)
_CSV_DIR = os.path.dirname(os.path.abspath(__file__))
_DFG_DIR = os.path.dirname(_CSV_DIR)
_LOCAL   = os.path.dirname(_DFG_DIR)
_ROOT    = os.path.dirname(_LOCAL)
for _p in (_LOCAL, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import CFG  # noqa: E402
from engine import SimulationEngine  # noqa: E402
from datafile_generator.base import run_simulation, save_meta  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# TABLO SINIFLANDIRMA (append modu için)
# ─────────────────────────────────────────────────────────────────
# Her engine başlatmada yeniden üretilen referans tablolar — append'de atlanır.
_STATIC_TABLES = frozenset({
    "mdl_user", "mdl_course", "mdl_course_modules",
    "mdl_question_categories", "mdl_question",
    "mdl_enrol", "mdl_user_enrolments",
    "mdl_forum", "mdl_lesson", "mdl_scorm", "mdl_h5pactivity", "mdl_badge",
    "student_registry",
})

# load_rows_from_csv ile tam geçmiş RAM'e yüklenen tablolar — append'de üzerine yaz.
_CUMULATIVE_TABLES = frozenset({
    "mdl_course_modules_completion",
    "mdl_assign_submission",
})

# Setup'ta oluşturulan mod grade_item'ları — cron append'de duplicate'i önle.
_SETUP_MODULES = frozenset({"lesson", "scorm", "h5pactivity", "forum"})


# ─────────────────────────────────────────────────────────────────
# KAYDETME
# ─────────────────────────────────────────────────────────────────

def save_tables(
    tables:  Dict[str, pd.DataFrame],
    out_dir: str  = "output",
    append:  bool = False,
) -> None:
    """
    DataFrameleri output/raw_tables/ altına CSV olarak yazar.

    append=False  → tam dönem yazımı (başlık dahil)
    append=True   → cron modu; static tablolar atlanır, kümülatif tablolar üzerine yazılır,
                    transaction tablolar gerçek append alır.
    """
    out = Path(out_dir) / "raw_tables"
    out.mkdir(parents=True, exist_ok=True)

    written = 0
    for name, df in tables.items():
        if df.empty:
            continue

        path = out / f"{name}.csv"

        if append and path.exists():
            # 1. Statik tablolar — her başlatmada yeniden üretiliyor; duplicate önlemi.
            if name in _STATIC_TABLES:
                continue

            # 2. Kümülatif tablolar — RAM'de tam geçmiş var, üzerine yaz.
            if name in _CUMULATIVE_TABLES:
                df.to_csv(path, index=False)
                written += 1
                continue

            # 3. mdl_grade_items özel kuralı — course/category + setup mod item'ları
            #    her başlatmada yeniden gelir; append'den hariç tut.
            if name == "mdl_grade_items" and "itemtype" in df.columns:
                static_type = df["itemtype"].isin(["course", "category"])
                setup_mod   = df["itemmodule"].isin(_SETUP_MODULES) if "itemmodule" in df.columns else (static_type & False)
                df = df[~(static_type | setup_mod)]
                if df.empty:
                    continue

            # 4. Geri kalan tablolar (log, quiz_attempts, notlar…) — gerçek append.
            df.to_csv(path, mode="a", header=False, index=False)
        else:
            df.to_csv(path, index=False)

        written += 1

    mode_label = "eklendi (append)" if append else "yazildi"
    print(f"\n   CSV'ler -> {out}  ({written} dosya {mode_label})")


# ─────────────────────────────────────────────────────────────────
# YÜKLEME
# ─────────────────────────────────────────────────────────────────

def load_tables(out_dir: str = "output") -> Dict[str, pd.DataFrame]:
    """
    {out_dir}/raw_tables/ altındaki tüm CSV dosyalarını okur ve
    {tablo_adı: DataFrame} sözlüğü olarak döner.
    """
    raw = Path(out_dir) / "raw_tables"
    if not raw.exists():
        raise FileNotFoundError(f"Veri dizini bulunamadi: {raw}")
    tables = {}
    for csv_file in sorted(raw.glob("*.csv")):
        tables[csv_file.stem] = pd.read_csv(csv_file)
    if not tables:
        raise FileNotFoundError(f"CSV dosyasi yok: {raw}")
    print(f"   CSV'ler <- {raw}  ({len(tables)} dosya yuklendi)")
    return tables


# ─────────────────────────────────────────────────────────────────
# GÖRÜNTÜLEME
# ─────────────────────────────────────────────────────────────────

def view_data(
    out_dir:    str           = "output",
    table_name: Optional[str] = None,
    limit:      int           = 10,
) -> None:
    """output/raw_tables/ içindeki CSV verilerini konsola yazdırır."""
    import json as _json
    raw = Path(out_dir) / "raw_tables"
    if not raw.exists():
        print("Veri bulunamadi. Once csv_data_generator.py calistirin.")
        return

    if table_name is None:
        print("\n" + "=" * 68)
        print("  VERI DURUMU")
        print("=" * 68)
        meta_path = Path(out_dir) / "simulation_meta.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = _json.load(f)
            print(f"\n  Simulate edilen hafta : {meta.get('n_weeks_simulated')}")
            print(f"  Ogrenci: {meta.get('n_students')} | "
                  f"Kurs: {meta.get('n_courses')} | "
                  f"Modul/Kurs: {meta.get('n_modules_per_course')}")

        print(f"\n  {'Tablo':<48}  {'Satir':>10}  {'Sutun':>6}")
        print(f"  {'-'*48}  {'-'*10}  {'-'*6}")
        total = 0
        for csv_path in sorted(raw.glob("*.csv")):
            try:
                df    = pd.read_csv(csv_path, nrows=0)
                n     = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1
                total += n
                print(f"  {csv_path.stem:<48}  {n:>10,}  {len(df.columns):>6}")
            except Exception as e:
                print(f"  {csv_path.stem:<48}  HATA: {e}")
        print(f"  {'-'*48}  {'-'*10}")
        print(f"  {'TOPLAM':<48}  {total:>10,}")
    else:
        csv_path = raw / f"{table_name}.csv"
        if not csv_path.exists():
            available = [p.stem for p in raw.glob("*.csv")]
            print(f"Tablo bulunamadi: {table_name}")
            print(f"Mevcut tablolar: {available}")
            return

        df         = pd.read_csv(csv_path, nrows=limit)
        total_rows = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1

        print(f"\n  Tablo        : {table_name}")
        print(f"  Toplam satir : {total_rows:,}  |  Gosterilen : {len(df)}")
        print(f"  Sutunlar     : {list(df.columns)}\n")

        with pd.option_context("display.max_columns", None, "display.width", 140,
                               "display.max_colwidth", 30):
            print(df.to_string(index=False))

        num_cols = df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            print("\n  Ozet istatistikler:")
            full = pd.read_csv(csv_path, usecols=num_cols)
            print(full.describe().round(2).to_string())


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Moodle Sentetik Veri Uretici — CSV Ciktisi",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Ornekler:
  python csv_data_generator.py                         -> 14 haftalik tam donem
  python csv_data_generator.py --weeks 8               -> sadece 8 hafta
  python csv_data_generator.py --week 5                -> cron: sadece hafta 5 (append)
  python csv_data_generator.py --view
  python csv_data_generator.py --view --table mdl_quiz_attempts --limit 25
""",
    )
    parser.add_argument("--weeks", type=int, default=CFG.general.n_weeks,
                        help=f"Hafta sayisi (varsayilan: {CFG.general.n_weeks})")
    parser.add_argument("--week",   type=int, default=None,
                        help="Cron modu: tek hafta simule et ve CSV'ye append et")
    parser.add_argument("--output", type=str, default="output",
                        help="Cikti dizini (varsayilan: output)")
    parser.add_argument("--view",   action="store_true",
                        help="Uretilmis verileri goruntule")
    parser.add_argument("--table",  type=str, default=None,
                        help="--view ile: belirli tabloyu onizle")
    parser.add_argument("--limit",  type=int, default=10,
                        help="--view --table ile: gosterilecek satir sayisi")
    args = parser.parse_args()

    if args.view:
        view_data(args.output, args.table, args.limit)

    elif args.week is not None:
        # Cron modu: state yükle, tek hafta çalıştır, append et
        state_path = f"{args.output}/engine_state.json"
        engine = SimulationEngine()
        engine.load_state(state_path)
        engine.load_rows_from_csv(args.output)
        engine.simulate_week(args.week)
        tables = engine.to_dataframes()
        engine.save_state(state_path)          # state önce (crash safety)
        save_tables(tables, args.output, append=True)
        save_meta(tables, args.week, args.output)

    else:
        tables = run_simulation(weeks=args.weeks)
        save_tables(tables, args.output)
        save_meta(tables, args.weeks, args.output)


if __name__ == "__main__":
    main()

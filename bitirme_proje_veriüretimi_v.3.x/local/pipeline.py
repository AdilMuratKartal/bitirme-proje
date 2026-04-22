"""
pipeline.py — Giriş Noktası v5.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lokal çalıştırma:
    python pipeline.py            → 14 haftalık tam dönem
    python pipeline.py --weeks 8  → sadece 8 hafta
    python pipeline.py --view     → üretilmiş verileri görüntüle
    python pipeline.py --view --table mdl_quiz_attempts --limit 20

Eski Faz 1/2 uyumluluğu kaldırıldı; SimulationEngine kullanılıyor.
"""

import sys
import os

# Repo root + local/ dizinini sys.path'e ekle (dosyalar local/ altına taşındı)
_LOCAL = os.path.dirname(os.path.abspath(__file__))
_ROOT  = os.path.dirname(_LOCAL)
sys.path.insert(0, _LOCAL)
sys.path.insert(0, _ROOT)

import argparse
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Optional

from engine import SimulationEngine
from config import CFG


# ─────────────────────────────────────────────────────────────────
# KAYDETME
# ─────────────────────────────────────────────────────────────────
# Referans tablolar her engine baslatmada _setup_reference_tables() tarafindan yeniden
# uretilir — cron modunda append edilmemeli, cunku duplicate satirlar olusur.
_STATIC_TABLES = frozenset({
    "mdl_user",
    "mdl_course",
    "mdl_course_modules",
    "mdl_question_categories",
    "mdl_question",
    "student_registry",
})

# load_rows_from_csv ile RAM'e tam gecmis yuklendiginden bu tablolar
# self._rows'da tum haftaları iceriyor. Append edilirse gecmis satirlar
# tekrar yazilir (duplicate). Cron modunda ustune yazilmali (overwrite).
# DIKKAT: Sadece load_rows_from_csv'de kalan tablolar buraya girmeli.
# (mdl_quiz_attempts, mdl_grade_grades vb. artik yuklenmediginden
#  onlar gercek append almali — yoksa CSV'deki gecmis veri silinir.)
_CUMULATIVE_TABLES = frozenset({
    "mdl_course_modules_completion",
    "mdl_assign_submission",
})


def save_tables(
    tables:  Dict[str, pd.DataFrame],
    out_dir: str  = "output",
    append:  bool = False,
) -> None:
    out = Path(out_dir) / "raw_tables"
    out.mkdir(parents=True, exist_ok=True)

    written = 0
    for name, df in tables.items():
        if df.empty:
            continue

        path = out / f"{name}.csv"

        if append and path.exists():
            # 1. Statik tablolar — her baslatmada yeniden uretiliyor, atla
            if name in _STATIC_TABLES:
                continue

            # 2. Kumulatif tablolar — RAM'de tam gecmis var, ustune yaz
            if name in _CUMULATIVE_TABLES:
                df.to_csv(path, index=False)
                written += 1
                continue

            # 3. mdl_grade_items ozel kurali — 'course' tipi satirlar her
            #    baslatmada yeniden geliyor; sadece quiz/assign satirlarini ekle
            if name == "mdl_grade_items" and "itemtype" in df.columns:
                df = df[df["itemtype"] != "course"]
                if df.empty:
                    continue

            # 4. Geri kalan tablolar (loglar, quiz_attempts, adimlar, notlar…)
            #    RAM'de yalnizca mevcut hafta var — gercek append
            df.to_csv(path, mode="a", header=False, index=False)
        else:
            df.to_csv(path, index=False)

        written += 1

    mode_label = "eklendi (append)" if append else "yazildi"
    print(f"\n   CSV'ler -> {out}  ({written} dosya {mode_label})")


def save_meta(tables: Dict[str, pd.DataFrame], weeks: int, out_dir: str = "output") -> None:
    meta = {
        "n_students":           CFG.general.n_students,
        "n_courses":            CFG.general.n_courses,
        "n_modules_per_course": CFG.general.n_modules_per_course,
        "n_weeks_simulated":    weeks,
        "semester_start":       str(CFG.general.semester_start),
        "table_row_counts":     {k: len(v) for k, v in tables.items() if not v.empty},
    }
    path = Path(out_dir) / "simulation_meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"   Meta → {path}")


# ─────────────────────────────────────────────────────────────────
# GÖRÜNTÜLEME  (Faz 3)
# ─────────────────────────────────────────────────────────────────
def view_data(
    out_dir:    str           = "output",
    table_name: Optional[str] = None,
    limit:      int           = 10,
) -> None:
    raw = Path(out_dir) / "raw_tables"
    if not raw.exists():
        print("Veri bulunamadi. Once pipeline.py'yi çalıştırın.")
        return

    if table_name is None:
        print("\n" + "=" * 68)
        print("  VERİ DURUMU")
        print("=" * 68)
        meta_path = Path(out_dir) / "simulation_meta.json"
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            print(f"\n  Simüle edilen hafta: {meta.get('n_weeks_simulated')}")
            print(f"  Öğrenci: {meta.get('n_students')} | "
                  f"Kurs: {meta.get('n_courses')} | "
                  f"Modül/Kurs: {meta.get('n_modules_per_course')}")

        print(f"\n  {'Tablo':<48}  {'Satır':>10}  {'Sütun':>6}")
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

        print(f"\n  Tablo : {table_name}")
        print(f"  Toplam satır : {total_rows:,}  |  Gösterilen : {len(df)}")
        print(f"  Sütunlar : {list(df.columns)}\n")

        with pd.option_context(
            "display.max_columns", None,
            "display.width", 140,
            "display.max_colwidth", 30,
        ):
            print(df.to_string(index=False))

        num_cols = df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            print(f"\n  Özet istatistikler:")
            full = pd.read_csv(csv_path, usecols=num_cols)
            print(full.describe().round(2).to_string())


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Moodle Sentetik Veri Uretici v5.0 -- SimulationEngine",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Ornekler:
  python pipeline.py                         -> 14 haftalik tam donem
  python pipeline.py --weeks 8              -> sadece 8 hafta
  python pipeline.py --week 5               -> cron modu: sadece hafta 5 (append)
  python pipeline.py --view
  python pipeline.py --view --table mdl_quiz_attempts --limit 25
""",
    )
    parser.add_argument(
        "--weeks", type=int, default=CFG.general.n_weeks,
        help=f"Simule edilecek hafta sayisi (varsayilan: {CFG.general.n_weeks})",
    )
    parser.add_argument(
        "--week", type=int, default=None,
        help="Cron modu: tek hafta simule et ve CSV'ye append et",
    )
    parser.add_argument(
        "--output", type=str, default="output",
        help="Cikti dizini (varsayilan: output)",
    )
    parser.add_argument(
        "--view", action="store_true",
        help="Uretilmis verileri goruntule",
    )
    parser.add_argument(
        "--table", type=str, default=None,
        help="--view ile: belirli tabloyu onizle",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="--view --table ile: gosterilecek satir sayisi",
    )

    args = parser.parse_args()

    if args.view:
        view_data(args.output, args.table, args.limit)
    elif args.week is not None:
        # Cron modu: state'i yukle, tek hafta calistir, CSV'ye append et
        state_path = f"{args.output}/engine_state.json"

        engine = SimulationEngine()
        engine.load_state(state_path)
        engine.load_rows_from_csv(args.output)

        engine.simulate_week(args.week)          # None doner
        tables = engine.to_dataframes()          # tablolari buradan al

        # BUG-2 FIX: State ÖNCE kaydedilir, CSV SONRA yazılır.
        # Crash Recovery garantisi: Render.com pod'u save_tables sırasında ölürse
        # state günceli → ID sayaçları doğru → Duplicate ID riski sıfır.
        # Worst-case: state yazıldı, CSV yazılmadı → sonraki çalışmada aynı hafta
        # yeniden simüle edilir (hafta verisi CSV'den eksik kalır), ama ID çakışması olmaz.
        # Tersi (CSV önce): CSV'de veri var, state eskide → ID'ler geri sarılır → Duplicate ID.
        engine.save_state(state_path)
        save_tables(tables, args.output, append=True)
        save_meta(tables, args.week, args.output)
    else:
        engine = SimulationEngine()
        tables = engine.simulate_full_semester(weeks=args.weeks)
        save_tables(tables, args.output)
        save_meta(tables, args.weeks, args.output)

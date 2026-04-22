"""
pipeline.py — İki Fazlı Orkestrasyon & Lokal Veri Görüntüleme (v4.0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Faz 1 — Tarihsel eğitim seti (tüm dönem):
    python pipeline.py --phase 1

Faz 2 — Canlı simülasyon (tek hafta ekleme):
    python pipeline.py --phase 2 --week 8

Faz 3 — Lokal veri görüntüleme:
    python pipeline.py --view
    python pipeline.py --view --table mdl_quiz_attempts --limit 20
"""

import argparse
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional

from config import CFG
from raw_tables import load_all_tables
from student_registry import STUDENT_REGISTRY


# ─────────────────────────────────────────────────────────────────
# KAYDETME YARDIMCILARI
# ─────────────────────────────────────────────────────────────────
# Faz 2'de sadece işlem tabloları CSV'ye eklenir; referans tabloları dokunulmaz.
_REFERENCE_TABLES = frozenset({
    "mdl_course", "mdl_grade_items", "mdl_assign", "mdl_quiz",
    "mdl_question_categories", "mdl_question", "mdl_course_modules",
    "student_registry", "mdl_user",
})


def _save_df(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def save_tables(
    tables:  Dict[str, pd.DataFrame],
    out:     Path,
    mode:    str = "write",   # "write" | "append"
) -> None:
    """
    mode='write'  → Faz 1: tüm tablolar sıfırdan yazılır.
    mode='append' → Faz 2: referans tabloları atlanır, işlem tabloları
                    mevcut CSV'ye eklenir ve id sütunu yeniden sıralanır.
    """
    d = out / "raw_tables"
    d.mkdir(parents=True, exist_ok=True)

    for name, df in tables.items():
        path = d / f"{name}.csv"

        if mode == "append" and name not in _REFERENCE_TABLES and path.exists():
            existing = pd.read_csv(path)
            combined = pd.concat([existing, df], ignore_index=True)
            # id çakışması varsa yeniden sırala
            if "id" in combined.columns:
                combined["id"] = range(1, len(combined) + 1)
            combined.to_csv(path, index=False)
        else:
            _save_df(df, path)

    print(f"   Tablolar → {d}  ({len(tables)} CSV)")


def save_segment_report(out: Path) -> None:
    d = out / "segment_report"
    d.mkdir(parents=True, exist_ok=True)

    # Segment dağılımı
    dist = (
        STUDENT_REGISTRY.groupby(["segment", "label"])
        .size().reset_index(name="count")
    )
    dist["ratio"] = (dist["count"] / len(STUDENT_REGISTRY)).round(3)
    _save_df(dist, d / "segment_distribution.csv")

    print("\n   Segment Dağılımı:")
    for _, row in dist.iterrows():
        bar = "█" * int(row["ratio"] * 40)
        print(f"      {row['segment']}  {row['label']:<20}  n={row['count']:>4}  {bar}")

    # Dropout raporu
    dropout = STUDENT_REGISTRY.groupby("segment").agg(
        toplam        = ("userid", "count"),
        dropout_sayisi = ("dropout_week", lambda x: x.notna().sum()),
    ).reset_index()
    dropout["dropout_orani"] = (
        dropout["dropout_sayisi"] / dropout["toplam"]
    ).round(3)
    _save_df(dropout, d / "dropout_report.csv")

    print("\n   Dropout Dağılımı:")
    for _, row in dropout.iterrows():
        print(f"      {row['segment']}  dropout={row['dropout_sayisi']:>3}/"
              f"{row['toplam']}  ({row['dropout_orani']:.0%})")


def _print_table_stats(tables: Dict[str, pd.DataFrame]) -> None:
    total = sum(len(df) for df in tables.values())
    print(f"\n   {'Tablo':<48}  {'Satır':>10}")
    print(f"   {'-'*48}  {'-'*10}")
    for name in sorted(tables):
        print(f"   {name:<48}  {len(tables[name]):>10,}")
    print(f"   {'-'*48}  {'-'*10}")
    print(f"   {'TOPLAM':<48}  {total:>10,}")


# ─────────────────────────────────────────────────────────────────
# FAZ 1 — Tarihsel Eğitim Seti
# ─────────────────────────────────────────────────────────────────
def run_phase1(out_dir: str = "output") -> Dict[str, Any]:
    """
    Tüm dönem (14 hafta) için tarihsel veri üretir.
    Çıktı: output/raw_tables/*.csv + output/phase1_meta.json
    """
    print("=" * 72)
    print("  FAZ 1 — Tarihsel Eğitim Seti Üretimi")
    print(f"  {CFG.general.n_students} Öğrenci | "
          f"{CFG.general.n_courses} Kurs | "
          f"{CFG.general.n_modules_per_course} Modül/Kurs | "
          f"{CFG.general.n_weeks} Hafta")
    print("=" * 72)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    tables = load_all_tables(phase_week=None)

    print("\n  Kaydediliyor...")
    save_tables(tables, out, mode="write")
    save_segment_report(out)

    meta = {
        "phase":                  1,
        "n_students":             CFG.general.n_students,
        "n_courses":              CFG.general.n_courses,
        "n_modules_per_course":   CFG.general.n_modules_per_course,
        "n_weeks":                CFG.general.n_weeks,
        "semester_start":         str(CFG.general.semester_start),
        "table_row_counts":       {k: len(v) for k, v in tables.items()},
        "segment_ratios":         CFG.segment_ratios,
    }
    meta_path = out / "phase1_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"\n   Meta → {meta_path}")

    print("\n" + "=" * 72)
    print("  FAZ 1 tamamlandi!")
    _print_table_stats(tables)
    print("=" * 72)

    return {"tables": tables, "meta": meta}


# ─────────────────────────────────────────────────────────────────
# FAZ 2 — Canlı Simülasyon (Tek Hafta)
# ─────────────────────────────────────────────────────────────────
def run_phase2(week: int, out_dir: str = "output") -> Dict[str, Any]:
    """
    Belirtilen haftanın canlı simülasyonunu çalıştırır.
    Sadece o hafta aktif olan öğrencilerin kayıtlarını mevcut CSV'ye ekler.
    Faz 1 tamamlanmadan çalışmaz.
    """
    out         = Path(out_dir)
    phase1_meta = out / "phase1_meta.json"

    if not phase1_meta.exists():
        raise FileNotFoundError(
            "Faz 1 tamamlanmamis! Once python pipeline.py --phase 1 calistirin."
        )

    print("=" * 72)
    print(f"  FAZ 2 — Canli Simulasyon  (Hafta {week})")
    print("=" * 72)

    tables = load_all_tables(phase_week=week)

    print("\n  Mevcut CSV'lere ekleniyor...")
    save_tables(tables, out, mode="append")

    meta = {
        "phase":            2,
        "simulated_week":   week,
        "table_row_counts": {k: len(v) for k, v in tables.items()},
    }
    meta_path = out / f"phase2_week{week:02d}_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n  FAZ 2 — Hafta {week} tamamlandi!")
    _print_table_stats(tables)
    print("=" * 72)

    return {"tables": tables, "meta": meta}


# ─────────────────────────────────────────────────────────────────
# FAZ 3 — Lokal Veri Görüntüleme
# ─────────────────────────────────────────────────────────────────
def view_data(
    out_dir:    str           = "output",
    table_name: Optional[str] = None,
    limit:      int           = 10,
) -> None:
    """
    Üretilmiş verinin özetini lokal terminalde gösterir.
    --table ile belirli bir tabloyu, --limit ile satır sayısını ayarla.
    """
    out = Path(out_dir)
    raw = out / "raw_tables"

    if not raw.exists():
        print("Veri bulunamadi. Once --phase 1 ile veri uretiniz.")
        return

    # ── Genel durum ───────────────────────────────────────────────
    if table_name is None:
        print("\n" + "=" * 68)
        print("  LOKAL VERİ DURUMU")
        print("=" * 68)

        phase1_done = (out / "phase1_meta.json").exists()
        print(f"\n  Faz 1 tamamlandi : {'Evet' if phase1_done else 'Hayir'}")

        simulated = sorted(out.glob("phase2_week*_meta.json"))
        if simulated:
            weeks = [int(p.stem.split("week")[1].split("_")[0]) for p in simulated]
            print(f"  Simulasyon haftalari : {weeks}")
        else:
            print("  Simulasyon haftalari : Henuz yok")

        print(f"\n  {'Tablo':<48}  {'Satir':>10}  {'Sutun':>6}")
        print(f"  {'-'*48}  {'-'*10}  {'-'*6}")
        total_rows = 0
        for csv_path in sorted(raw.glob("*.csv")):
            try:
                df = pd.read_csv(csv_path, nrows=0)   # sadece baslik
                n_rows = sum(1 for _ in open(csv_path)) - 1
                total_rows += n_rows
                print(f"  {csv_path.stem:<48}  {n_rows:>10,}  {len(df.columns):>6}")
            except Exception as e:
                print(f"  {csv_path.stem:<48}  HATA: {e}")

        print(f"  {'-'*48}  {'-'*10}")
        print(f"  {'TOPLAM':<48}  {total_rows:>10,}")

        # Segment & dropout ozet
        seg_path = out / "segment_report" / "segment_distribution.csv"
        if seg_path.exists():
            print("\n  Segment Dagilimi:")
            seg_df = pd.read_csv(seg_path)
            for _, row in seg_df.iterrows():
                bar = "█" * int(row["ratio"] * 30)
                print(f"    {row['segment']}  {row['label']:<20}  "
                      f"n={row['count']:>4}  ({row['ratio']:.0%})  {bar}")

    # ── Belirli tablo önizlemesi ──────────────────────────────────
    else:
        csv_path = raw / f"{table_name}.csv"
        if not csv_path.exists():
            available = [p.stem for p in raw.glob("*.csv")]
            print(f"Tablo bulunamadi: {table_name}")
            print(f"Mevcut tablolar: {available}")
            return

        df = pd.read_csv(csv_path, nrows=limit)
        total_rows = sum(1 for _ in open(csv_path)) - 1

        print(f"\n  Tablo : {table_name}")
        print(f"  Toplam satir : {total_rows:,}  |  Gosterilen : {len(df)}")
        print(f"  Sutunlar : {list(df.columns)}\n")

        with pd.option_context(
            "display.max_columns", None,
            "display.width", 140,
            "display.max_colwidth", 30,
        ):
            print(df.to_string(index=False))

        # Numerik ozet istatistikleri
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            print(f"\n  Ozet istatistikler (numerik):")
            full_df = pd.read_csv(csv_path, usecols=num_cols)
            print(full_df.describe().round(2).to_string())


# ─────────────────────────────────────────────────────────────────
# CLI GIRIŞ NOKTASI
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Moodle Sentetik Veri Uretici v4.0",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Ornekler:
  python pipeline.py --phase 1
  python pipeline.py --phase 2 --week 8
  python pipeline.py --view
  python pipeline.py --view --table mdl_quiz_attempts --limit 25
""",
    )
    parser.add_argument(
        "--phase", type=int, choices=[1, 2], default=None,
        help="1 = Tarihsel (tum donem) | 2 = Canli simulasyon (tek hafta)",
    )
    parser.add_argument(
        "--week", type=int, default=None,
        help="Faz 2: simulasyon haftasi (1-14)",
    )
    parser.add_argument(
        "--output", type=str, default="output",
        help="Cikti dizini (varsayilan: output)",
    )
    parser.add_argument(
        "--view", action="store_true",
        help="Uretilmis verilerin ozetini goster (Faz 3)",
    )
    parser.add_argument(
        "--table", type=str, default=None,
        help="--view ile kullan: belirli tabloyu on izle",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="--view --table ile kullan: gosterilecek satir sayisi",
    )

    args = parser.parse_args()

    if args.view:
        view_data(args.output, args.table, args.limit)

    elif args.phase == 1:
        run_phase1(args.output)

    elif args.phase == 2:
        if args.week is None:
            parser.error("Faz 2 icin --week parametresi gereklidir!")
        if not (1 <= args.week <= CFG.general.n_weeks):
            parser.error(f"--week 1 ile {CFG.general.n_weeks} arasinda olmalidir!")
        run_phase2(args.week, args.output)

    else:
        parser.print_help()

"""
local/run_full_pipeline.py — Tam Entegre Pipeline
==================================================
Simulasyonu TEK SEFER calistirir; ayni tabloları hem DB'ye hem
model egitimi icin kullanir. Boylesece DB ve model kesinlikle
ayni veriyle uyumlu olur.

  Adim 1: Simulasyon -> output/train/ (CSV yedek)
  Adim 2: Ayni tables dict -> PostgreSQL (replace)
  Adim 3: Ayni tables dict -> MIMO + HKAR egitimi (.keras + .pkl)
  Adim 4: .keras -> .onnx + .pkl -> .json (render_backend/saved_models/)

Calistirma (.venv_gpu aktifken, .env icinde DATABASE_URL tanimli):
    python local/run_full_pipeline.py
    python local/run_full_pipeline.py --weeks 8
    python local/run_full_pipeline.py --skip-db      (DB yazimini atla)
    python local/run_full_pipeline.py --skip-train   (egitimi atla)
    python local/run_full_pipeline.py --skip-onnx    (ONNX donusumunu atla)
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# ── Path kurulumu ─────────────────────────────────────────────────
_LOCAL = os.path.dirname(os.path.abspath(__file__))
_ROOT  = os.path.dirname(_LOCAL)
for _p in (_LOCAL, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
from config import CFG

_SEP = "=" * 65
_TRAIN_CUTOFFS = [4, 6, 8, 10, 12]


def _banner(step: int, label: str) -> None:
    print(f"\n{_SEP}")
    print(f"  ADIM {step}: {label}")
    print(_SEP)


# =================================================================
# Adim 1: Simulasyon + CSV yedek
# =================================================================
def step_simulate(weeks: int, out_dir: str) -> dict:
    from datafile_generator.base import run_simulation, save_meta
    from datafile_generator.csv.csv_data_generator import save_tables

    print(f"  {weeks} haftalik simulasyon baslatiliyor...")
    tables = run_simulation(weeks=weeks)
    save_tables(tables, out_dir)
    save_meta(tables, weeks, out_dir)
    print(f"  [OK] {len(tables)} tablo uretildi -> {out_dir}/raw_tables/")
    return tables


# =================================================================
# Adim 2: PostgreSQL'e yaz
# =================================================================
def step_write_db(tables: dict) -> None:
    from datafile_generator.postgresql.postgresql_data_generator import (
        _make_engine,
        write_tables_to_db,
        drop_indexes,
        create_indexes,
    )

    engine = _make_engine()
    write_tables_to_db(tables, engine, if_exists="replace")
    drop_indexes(engine)
    create_indexes(engine)
    engine.dispose()
    print("  [OK] Tablolar PostgreSQL'e yazildi, indexler olusturuldu.")


# =================================================================
# Adim 3: Model egitimi (ayni tables dict)
# =================================================================
def step_train(tables: dict) -> None:
    try:
        import tensorflow as tf
        tf.random.set_seed(42)
        np.random.seed(42)
        print(f"  TensorFlow: {tf.__version__}")
    except ImportError:
        print("[HATA] TensorFlow bulunamadi. .venv_gpu ortaminda calistirin:")
        print("       .venv_gpu\\Scripts\\activate")
        sys.exit(1)

    from feature_mimo import build_mimo_dataset
    from feature_hkar import build_hkar_dataset
    from train_models import train_mimo, train_hkar, _ensure_dirs

    _ensure_dirs()

    # ── MIMO: cok kesimli egitim ──────────────────────────────
    print(f"\n  [MIMO] Multi-cutoff egitim: {_TRAIN_CUTOFFS}")
    all_x_time, all_x_static               = [], []
    all_y_risk, all_y_grade, all_y_seg     = [], [], []
    for cw in _TRAIN_CUTOFFS:
        ds = build_mimo_dataset(tables, cutoff_week=cw)
        all_x_time.append(ds["X_Time"])
        all_x_static.append(ds["X_Static"])
        all_y_risk.append(ds["y_risk"])
        all_y_grade.append(ds["y_grade"])
        all_y_seg.append(ds["y_segment"])

    mimo_ds = {
        "X_Time":    np.concatenate(all_x_time),
        "X_Static":  np.concatenate(all_x_static),
        "y_risk":    np.concatenate(all_y_risk),
        "y_grade":   np.concatenate(all_y_grade),
        "y_segment": np.concatenate(all_y_seg),
    }
    print(f"  X_Time   : {mimo_ds['X_Time'].shape}")
    print(f"  X_Static : {mimo_ds['X_Static'].shape}")
    train_mimo(mimo_ds)
    print("  [OK] MIMO modeli saved_models/ altina kaydedildi.")

    # ── HKAR ─────────────────────────────────────────────────
    print("\n  [HKAR] Dataset olusturuluyor...")
    hkar_ds = build_hkar_dataset(tables)
    print(f"  X_Sequence  : {hkar_ds['X_Sequence'].shape}")
    print(f"  X_UserHabit : {hkar_ds['X_UserHabit'].shape}")
    train_hkar(hkar_ds)
    print("  [OK] HKAR modeli saved_models/ altina kaydedildi.")


# =================================================================
# Adim 4: ONNX donusumu
# =================================================================
def step_onnx() -> None:
    try:
        import tensorflow as tf     # noqa: F401 — tf2onnx icin gerekli
        import tf2onnx              # noqa: F401
        import onnxruntime          # noqa: F401
    except ImportError as e:
        print(f"  [HATA] Eksik bagimlilik: {e}")
        print("  pip install tf2onnx onnxruntime")
        sys.exit(1)

    from convert_to_onnx import convert_keras_to_onnx

    dst = os.path.join(_ROOT, "render_backend", "saved_models")
    os.makedirs(dst, exist_ok=True)

    convert_keras_to_onnx("mimo")
    convert_keras_to_onnx("hkar")
    print(f"  [OK] ONNX dosyalari -> {dst}/")


# =================================================================
# Ana akis
# =================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulasyon -> PostgreSQL -> Egitim -> ONNX (tek komut)",
    )
    parser.add_argument("--weeks",      type=int, default=CFG.general.n_weeks,
                        help=f"Hafta sayisi (varsayilan: {CFG.general.n_weeks})")
    parser.add_argument("--output",     type=str,
                        default=os.path.join(_ROOT, "output", "train"),
                        help="CSV yedek dizini")
    parser.add_argument("--skip-db",    action="store_true",
                        help="PostgreSQL yazimini atla (DB'siz test)")
    parser.add_argument("--skip-train", action="store_true",
                        help="Model egitimini atla (sadece veri)")
    parser.add_argument("--skip-onnx",  action="store_true",
                        help="ONNX donusumunu atla")
    args = parser.parse_args()

    t_start = time.time()
    print(_SEP)
    print("  TAM ENTEGRE PIPELINE")
    print(f"  Hafta         : {args.weeks}")
    print(f"  CSV yedek     : {args.output}/")
    print(f"  Skip DB       : {args.skip_db}")
    print(f"  Skip Egitim   : {args.skip_train}")
    print(f"  Skip ONNX     : {args.skip_onnx}")
    print(_SEP)

    # 1. Simulasyon + CSV
    _banner(1, "Simulasyon + CSV Yedek")
    tables = step_simulate(args.weeks, args.output)

    # 2. PostgreSQL
    if not args.skip_db:
        _banner(2, "PostgreSQL'e Yaz")
        step_write_db(tables)
    else:
        print("\n  [ATLANDI] PostgreSQL yazimi.")

    # 3. Egitim
    if not args.skip_train:
        _banner(3, "Model Egitimi (MIMO + HKAR)")
        step_train(tables)
    else:
        print("\n  [ATLANDI] Model egitimi.")

    # 4. ONNX
    if not args.skip_onnx:
        _banner(4, "ONNX Donusumu")
        step_onnx()
    else:
        print("\n  [ATLANDI] ONNX donusumu.")

    # Ozet
    elapsed = time.time() - t_start
    print(f"\n{_SEP}")
    print(f"  PIPELINE TAMAMLANDI  ({elapsed:.1f}s)")
    print(_SEP)

    if not args.skip_onnx:
        print("\n  Sonraki adim — modelleri commit et ve push et:")
        print("    git add render_backend/saved_models/")
        print("    git commit -m \"models: yeni ONNX agirliklar\"")
        print("    git push origin main")
        print("    -> Render otomatik deploy eder.")
    elif not args.skip_train:
        print("\n  Sonraki adim:")
        print("    python local/convert_to_onnx.py   (ONNX donusumu icin)")


if __name__ == "__main__":
    main()

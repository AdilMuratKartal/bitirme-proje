"""
datafile_generator/predict/predict_data_generator.py — Predict Veri Üreticisi

Çalıştırma:
    python predict_data_generator.py             → 14 haftalık sim, cutoff=8
    python predict_data_generator.py --seed 42   → farklı rastgele dağılım

Strateji:
  1. Yeni öğrenci kaydı (userid 10001–11000, rastgele segment dağılımı)
  2. 14 haftalık tam dönem simülasyonu (H9+ gerçek not etiketi için)
  3. cutoff_week=8 ile özellik çıkarımı (erken uyarı kesiti)
  4. CSV kaydı → output/predict/raw_tables/

FUTURE_CUTOFF_WEEK override:
  Monkey-patch çalışmaz (yerel binding). Bunun yerine build_mimo_dataset'e
  cutoff_week=8 parametresi geçirilir.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, Any

import numpy as np
import pandas as pd

# sys.path kurulumu (doğrudan çalıştırma için)
_PRED_DIR = os.path.dirname(os.path.abspath(__file__))
_DFG_DIR  = os.path.dirname(_PRED_DIR)
_LOCAL    = os.path.dirname(_DFG_DIR)
_ROOT     = os.path.dirname(_LOCAL)
for _p in (_LOCAL, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config.predict_config import (          # noqa: E402
    PREDICT_SEED, PREDICT_CUTOFF, PREDICT_OUT_DIR,
)
from datafile_generator.predict.predict_registry import build_predict_registry  # noqa: E402
from datafile_generator.base import save_meta                                    # noqa: E402
from datafile_generator.csv.csv_data_generator import save_tables                # noqa: E402

_SEP = "=" * 62


def run_predict_simulation(
    seed:        int = PREDICT_SEED,
    cutoff_week: int = PREDICT_CUTOFF,
    out_dir:     str = PREDICT_OUT_DIR,
) -> Dict[str, Any]:
    """
    Predict verisi üretir ve CSV olarak kaydeder.

    1. STUDENT_REGISTRY'yi predict registry ile geçici olarak değiştirir.
    2. 14 haftalık tam dönem simülasyonu yapar.
    3. cutoff_week kesitinde özellik çıkarımı yapar.
    4. Tabloları out_dir'e kaydeder.
    5. STUDENT_REGISTRY'yi geri yükler.

    Returns:
        mimo_ds: build_mimo_dataset() çıktısı (X_Time, X_Static, y_risk, vb.)
    """
    import student_registry as _sr
    from engine import SimulationEngine
    from feature_mimo import build_mimo_dataset

    # 1. Predict registry'yi oluştur ve modülü override et
    pred_registry = build_predict_registry(seed=seed)
    original_registry = _sr.STUDENT_REGISTRY.copy()
    _sr.set_registry(pred_registry)

    print(_SEP)
    print(f"  Predict Veri Üretici")
    print(f"  Seed: {seed}  |  Cutoff: H{cutoff_week}  |  Çıktı: {out_dir}")
    print(_SEP)

    try:
        # 2. 14 haftalık tam simülasyon (H9+ gerçek notlar için gerekli)
        print("\n[1/3] Simülasyon başlatılıyor (14 hafta)...")
        tables = SimulationEngine(seed=seed).simulate_full_semester(weeks=14)
        print(f"  Üretilen tablo sayısı: {len(tables)}")

        # 3. cutoff_week kesitinde özellik çıkarımı
        print(f"\n[2/3] MIMO özellikleri çıkarılıyor (cutoff=H{cutoff_week})...")
        mimo_ds = build_mimo_dataset(tables, cutoff_week=cutoff_week)
        print(f"  X_Time   : {mimo_ds['X_Time'].shape}")
        print(f"  X_Static : {mimo_ds['X_Static'].shape}")
        print(f"  current_week column (ortalama): {mimo_ds['X_Static'][:, 5].mean():.1f}")

        # 4. CSV'ye kaydet
        print(f"\n[3/3] CSV'ye yaziliyor: {out_dir}/")
        save_tables(tables, out_dir)
        save_meta(tables, 14, out_dir)

        print(f"\n  Predict userid aralığı: "
              f"{pred_registry['userid'].min()} – {pred_registry['userid'].max()}")
        print(f"  Toplam örnek: {len(pred_registry)}")
        print(_SEP)

    finally:
        # 5. STUDENT_REGISTRY'yi her durumda geri yükle
        _sr.set_registry(original_registry)

    return mimo_ds


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Predict Veri Üreticisi — erken uyarı kesiti",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Örnekler:
  python predict_data_generator.py               → seed=999, cutoff=8
  python predict_data_generator.py --seed 42     → farklı segment dağılımı
  python predict_data_generator.py --cutoff 6    → 6. hafta kesiti
  python predict_data_generator.py --output output/pred_v2
""",
    )
    parser.add_argument("--seed",   type=int, default=PREDICT_SEED,
                        help=f"Rastgele tohum (varsayılan: {PREDICT_SEED})")
    parser.add_argument("--cutoff", type=int, default=PREDICT_CUTOFF,
                        help=f"Gözlem penceresi kesit haftası (varsayılan: {PREDICT_CUTOFF})")
    parser.add_argument("--output", type=str, default=PREDICT_OUT_DIR,
                        help=f"Çıktı dizini (varsayılan: {PREDICT_OUT_DIR})")
    args = parser.parse_args()

    mimo_ds = run_predict_simulation(
        seed=args.seed,
        cutoff_week=args.cutoff,
        out_dir=args.output,
    )

    print("\n  Tamamlandı.")
    print(f"  X_Time shape  : {mimo_ds['X_Time'].shape}")
    print(f"  X_Static shape: {mimo_ds['X_Static'].shape}")


if __name__ == "__main__":
    main()

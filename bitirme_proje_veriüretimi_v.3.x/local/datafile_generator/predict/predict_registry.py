"""
datafile_generator/predict/predict_registry.py
Predict modu için bağımsız öğrenci kaydı üretir:
  - userid = 10001 – 11000  (train seti ile çakışmaz)
  - Segment dağılımı: Dirichlet ile rastgele (train sabit 25/35/25/15'ten farklı)
  - Her öğrenciye 3–7 kurs (max 7 kısıtı korunur)
  - S4 öğrencileri için rastgele dropout_week (2–8 arası)
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import numpy as np
import pandas as pd

# sys.path ayarları (doğrudan çalıştırma için)
_PRED_DIR = os.path.dirname(os.path.abspath(__file__))
_DFG_DIR  = os.path.dirname(_PRED_DIR)
_LOCAL    = os.path.dirname(_DFG_DIR)
_ROOT     = os.path.dirname(_LOCAL)
for _p in (_LOCAL, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import CFG                           # noqa: E402
from config.predict_config import (             # noqa: E402
    PREDICT_N_STUDENTS, PREDICT_ID_OFFSET, PREDICT_SEED,
)


def build_predict_registry(
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """
    Rastgele segment dağılımlı öğrenci kaydı üretir.
    Returns: STUDENT_REGISTRY uyumlu DataFrame
    """
    rng = np.random.default_rng(seed if seed is not None else PREDICT_SEED)

    # Rastgele segment dağılımı (uniform Dirichlet prior)
    raw    = rng.dirichlet([1.0, 1.0, 1.0, 1.0])
    counts = (raw * PREDICT_N_STUDENTS).astype(int)
    counts[0] += PREDICT_N_STUDENTS - counts.sum()   # toplam = N garantisi

    seg_labels = (
        ["S1"] * counts[0]
        + ["S2"] * counts[1]
        + ["S3"] * counts[2]
        + ["S4"] * counts[3]
    )
    rng.shuffle(seg_labels)

    n        = PREDICT_N_STUDENTS
    n_courses = CFG.general.n_courses

    _LABELS = {
        "S1": "Başarılı",
        "S2": "Orta Başarılı",
        "S3": "İstikrarsız",
        "S4": "Terke Meyilli",
    }

    userids      = list(range(PREDICT_ID_OFFSET + 1, PREDICT_ID_OFFSET + n + 1))
    dropout_week = []

    for seg in seg_labels:
        # Dropout haftası: yalnızca S4, gözlem penceresi içinde (2–8)
        dw = int(rng.integers(2, 9)) if seg == "S4" else None
        dropout_week.append(dw)

    print(f"[PredictRegistry] Segment dağılımı: "
          f"S1={counts[0]} S2={counts[1]} S3={counts[2]} S4={counts[3]}")

    return pd.DataFrame({
        "userid":        userids,
        "segment":       seg_labels,
        "label":         [_LABELS[s] for s in seg_labels],
        "dropout_week":  dropout_week,
    })

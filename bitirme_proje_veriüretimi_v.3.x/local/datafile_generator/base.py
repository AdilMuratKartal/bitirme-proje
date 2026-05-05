"""
datafile_generator/base.py — İki üretici (CSV + PostgreSQL) tarafından paylaşılan kod.
- run_simulation() : SimulationEngine'i başlatır ve tabloları döndürür
- save_meta()      : JSON metadata dosyasını yazar
- sadece veri üretme kisimini kendi baslarina calistirabilmek icin bu gerekiyor.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

# local/ dizinini path'e ekle (doğrudan çalıştırma senaryosu için)
_DFG_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCAL   = os.path.dirname(_DFG_DIR)
_ROOT    = os.path.dirname(_LOCAL)
for _p in (_LOCAL, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import CFG  # noqa: E402 — path setup yukarıda yapılıyor
from engine import SimulationEngine  # noqa: E402


def run_simulation(
    weeks: int = 14,
    seed:  Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    """
    SimulationEngine'i çalıştırır ve tüm tabloları DataFrame sözlüğü olarak döndürür.
    Her iki üretici (CSV ve PostgreSQL) bu fonksiyonu çağırır.
    """
    engine = SimulationEngine(seed=seed)
    return engine.simulate_full_semester(weeks=weeks)


def save_meta(
    tables:  Dict[str, pd.DataFrame],
    weeks:   int,
    out_dir: str = "output",
) -> None:
    """Simülasyon metadata bilgilerini JSON olarak kaydeder."""
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
    print(f"   Meta -> {path}")

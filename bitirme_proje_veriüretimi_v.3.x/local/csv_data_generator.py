"""
local/csv_data_generator.py — Sentetik Tablo CSV Dışa Aktarıcı
===============================================================
SADECE lokal ortamda kullanılır. Render.com'a GİTMEZ.

Görev:
  SimulationEngine'den gelen 17 adet Moodle tablosunu
  (Dict[str, pd.DataFrame]) local/csv_exports/ klasörüne
  her biri kendi adıyla CSV olarak kaydeder.

Kullanım:
  from local.csv_data_generator import export_tables_to_csv
  export_tables_to_csv(tables)
"""

from __future__ import annotations

import os
import pandas as pd
from typing import Dict

# CSV dosyaları bu klasöre yazılır
CSV_EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "csv_exports")


def export_tables_to_csv(
    tables: Dict[str, pd.DataFrame],
    output_dir: str = CSV_EXPORT_DIR,
    encoding: str = "utf-8-sig",   # Excel'de Türkçe karakterler için BOM'lu UTF-8
) -> None:
    """
    17 Moodle tablosunu CSV olarak diske yazar.

    Parametreler
    ------------
    tables     : simulate_full_semester() çıktısı — {tablo_adı: DataFrame}
    output_dir : Hedef klasör (varsayılan: local/csv_exports/)
    encoding   : Dosya kodlaması (varsayılan: utf-8-sig)
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n  [CSV] Dışa aktarma başlıyor → {output_dir}")
    print(f"  [CSV] Tablo sayısı: {len(tables)}")

    toplam_satir = 0
    for tablo_adi, df in tables.items():
        if not isinstance(df, pd.DataFrame):
            print(f"  [CSV] ATLANDI (DataFrame değil): {tablo_adi}")
            continue

        dosya_yolu = os.path.join(output_dir, f"{tablo_adi}.csv")
        df.to_csv(dosya_yolu, index=False, encoding=encoding)

        boyut_kb   = os.path.getsize(dosya_yolu) / 1024
        toplam_satir += len(df)
        print(f"  [CSV]   {tablo_adi:<45s} {len(df):>8,} satır  {boyut_kb:>8.1f} KB")

    print(f"  [CSV] Toplam satır : {toplam_satir:,}")
    print(f"  [CSV] Tamamlandı   : {output_dir}")

# -*- coding: utf-8 -*-
"""Tum analizleri sirayla calistirir.
Kullanim:  python run_all.py ["VERI_KLASORU_YOLU"]
Yol verilmezse common.py icindeki DATA_DIR kullanilir.
"""
import subprocess, sys, os

here = os.path.dirname(os.path.abspath(__file__))
scripts = [
    "01_sentetiklik.py",
    "02_kronoloji.py",
    "03_altin_ogrenci.py",
    "04_kurs_log_penceresi.py",
    "05_hayalet_kayip_not.py",
    "06_not_zaman_kumelenme.py",
    "07_fk_ve_features.py",
]
hata = []
for s in scripts:
    print("\n" + "#"*70 + f"\n# {s}\n" + "#"*70)
    r = subprocess.run([sys.executable, os.path.join(here, s)] + sys.argv[1:])
    if r.returncode != 0:
        hata.append(s)
        print(f"!! {s} hata verdi (devam ediliyor)")

print("\n" + "="*70)
print("BITTI. Tum raporlar ve CSV'ler 'cikti' klasorunde.")
if hata:
    print("Hata veren scriptler:", hata)
    print("-> Ilgili ekran ciktisini inceleyip kolon adlarini kontrol edin.")
else:
    print("Tum scriptler basariyla tamamlandi.")

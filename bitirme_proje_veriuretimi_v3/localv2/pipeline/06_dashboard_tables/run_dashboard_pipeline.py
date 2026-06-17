# -*- coding: utf-8 -*-
"""Dashboard Pipeline Runner

Bagimlilik sirasiyla tum dashboard tablo script'lerini calistirir:

  [00] select_golden_users.py       -> golden_1000.csv + config.json
  [04] compute_module_status.py     -> dash_04_module_status.csv  (agir, once calisir)
  [01] compute_daily_sessions.py    -> dash_01_daily_sessions.csv
  [02] compute_user_stats.py        -> dash_02_user_stats.csv     (01 ve 04'e bagimli)
  [03] compute_course_progress.py   -> dash_03_course_progress.csv (04'e bagimli)
  [05] compute_course_analytics.py  -> dash_05_course_analytics.csv (04'e bagimli)
  [06] compute_activity_heatmap.py  -> dash_06_activity_heatmap.csv (gün x saat heatmap)
  [07] compute_upcoming_events.py   -> dash_07_upcoming_events.csv  (04'e bagimli)

Kullanim:
  python run_dashboard_pipeline.py
  python run_dashboard_pipeline.py --skip-golden   # golden_1000.csv zaten varsa
  python run_dashboard_pipeline.py --only 03 05    # sadece belirli adimlari calistir
"""

import sys, os, subprocess, argparse, time

THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(THIS_DIR, "../00_golden_users")
GOLDEN_CSV = os.path.join(GOLDEN_DIR, "cikti/golden_1000.csv")

STEPS = [
    ("00", os.path.join(GOLDEN_DIR, "select_golden_users.py"),      "Altin kullanici secimi"),
    ("04", os.path.join(THIS_DIR,   "04_compute_module_status.py"), "Modul tamamlanma durumu"),
    ("01", os.path.join(THIS_DIR,   "01_compute_daily_sessions.py"),"Gunluk oturum hesaplama"),
    ("02", os.path.join(THIS_DIR,   "02_compute_user_stats.py"),    "Kullanici istatistikleri"),
    ("03", os.path.join(THIS_DIR,   "03_compute_course_progress.py"),"Kurs ilerleme ozeti"),
    ("05", os.path.join(THIS_DIR,   "05_compute_course_analytics.py"),"Kurs analitigi"),
    ("06", os.path.join(THIS_DIR,   "06_compute_activity_heatmap.py"),"Aktivite heatmap (gun x saat)"),
    ("07", os.path.join(THIS_DIR,   "07_compute_upcoming_events.py"), "Upcoming events (per-user deadline tablosu)"),
]

def run_step(label, script_path, description):
    print(f"\n{'='*60}")
    print(f"ADIM [{label}]: {description}")
    print(f"Script: {script_path}")
    print("="*60)
    t0 = time.time()
    result = subprocess.run([sys.executable, script_path], check=False)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n[HATA] Adim {label} basarisiz (returncode={result.returncode}). Pipeline durduruluyor.")
        sys.exit(result.returncode)
    print(f"\n[OK] Adim {label} tamamlandi ({elapsed:.1f}s)")
    return elapsed


def main():
    parser = argparse.ArgumentParser(description="Dashboard pipeline runner")
    parser.add_argument("--skip-golden", action="store_true",
                        help="golden_1000.csv zaten varsa adim 00'i atla")
    parser.add_argument("--only", nargs="*", metavar="STEP",
                        help="Sadece verilen adim numaralarini calistir (örn: --only 03 05)")
    args = parser.parse_args()

    only_set = set(args.only) if args.only else None
    total_start = time.time()
    elapsed_map = {}

    for label, script_path, description in STEPS:
        # --only filtresi
        if only_set and label not in only_set:
            print(f"[ATLA] Adim {label} ({description})")
            continue

        # --skip-golden: adim 00 ve golden_1000.csv varsa atla
        if label == "00" and args.skip_golden:
            if os.path.exists(GOLDEN_CSV):
                print(f"[ATLA] Adim 00 — golden_1000.csv mevcut, yeniden hesaplanmiyor.")
                continue
            else:
                print(f"[UYARI] --skip-golden verildi ama golden_1000.csv bulunamadi, calistiriliyor.")

        elapsed_map[label] = run_step(label, script_path, description)

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print("TUM ADIMLAR TAMAMLANDI")
    for label, elapsed in elapsed_map.items():
        print(f"  [{label}] {elapsed:.1f}s")
    print(f"  Toplam: {total_elapsed:.1f}s")
    print("="*60)

    # Cikti dosyalarini listele
    print("\nCikti dosyalari:")
    cikti_dirs = [
        os.path.join(GOLDEN_DIR, "cikti"),
        os.path.join(THIS_DIR,   "cikti"),
    ]
    for d in cikti_dirs:
        if os.path.exists(d):
            for fname in sorted(os.listdir(d)):
                fpath = os.path.join(d, fname)
                size_kb = os.path.getsize(fpath) / 1024
                print(f"  {fpath}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()

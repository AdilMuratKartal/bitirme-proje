# -*- coding: utf-8 -*-
"""DASHBOARD TABLO 6 — dash_06_activity_heatmap

Kullanicinin Moodle'i hangi gun ve saatte kullandigini gosteren
haftalik aktivite haritasi (gün x saat heatmap).

RPubs ilhamli: Braden Baker "When Are Students Using Moodle?"
Kaynak analiz: 13 sinif, Spring/Fall 2021

Cikti: cikti/dash_06_activity_heatmap.csv
  userid | weekday | hour | event_count | session_starts

weekday: 0=Pazartesi ... 6=Pazar (Python dt.dayofweek)
hour: 0-23
event_count: o gün+saatte toplam log event sayisi
session_starts: o gün+saatte yeni oturum baslangic sayisi (30 dk bosluk = yeni oturum)
"""

import sys, os, json
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import num, kaydet, load_monthly_logs

GOLDEN_CSV  = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/golden_1000.csv")
CONFIG_JSON = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/config.json")
CIKTI_DIR   = os.path.join(os.path.dirname(__file__), "cikti")

print("=== DASHBOARD 06: AKTIVITE HEATMAP ===\n")

with open(CONFIG_JSON, encoding="utf-8") as f:
    cfg = json.load(f)

# 1. Golden users
golden = pd.read_csv(GOLDEN_CSV, usecols=["userid"])
golden_users = set(golden["userid"].astype(int))
print(f"  Golden users: {len(golden_users):,}")

# 2. Tum aylarin log kayitlari (sadece golden users)
print("\n[1/3] Loglar yukleniyor...")
log_df = load_monthly_logs(
    usecols=["time", "userid"],
    filtered_users=golden_users,
)
log_df["userid"] = num(log_df["userid"]).astype(int)
log_df["time"]   = num(log_df["time"]).astype(float)

log_df = log_df[
    (log_df["userid"].isin(golden_users)) &
    (log_df["time"] > 1_000_000_000)
].copy()
print(f"  Toplam log kaydi: {len(log_df):,}")

# 3. Saat ve weekday türet
print("\n[2/3] Saat ve gün hesaplaniyor...")
ts = pd.to_datetime(log_df["time"], unit="s", utc=True)
log_df["hour"]    = ts.dt.hour          # 0-23
log_df["weekday"] = ts.dt.dayofweek    # 0=Pazartesi, 6=Pazar

# Oturum baslangici: ayni kullanici icin 30 dk+ bosluk = yeni oturum
log_df = log_df.sort_values(["userid", "time"])
log_df["prev_time"] = log_df.groupby("userid")["time"].shift(1)
log_df["gap_s"]     = log_df["time"] - log_df["prev_time"]
log_df["new_session"] = log_df["gap_s"].isna() | (log_df["gap_s"] > 1800)

# 4. Gün x saat agregasyonu
print("[3/3] Heatmap agregasyonu yapiliyor...")
heatmap = (
    log_df
    .groupby(["userid", "weekday", "hour"])
    .agg(
        event_count=("time", "count"),
        session_starts=("new_session", "sum"),
    )
    .reset_index()
)
heatmap["session_starts"] = heatmap["session_starts"].astype(int)

# Tum kullanicilar icin eksik (weekday, hour) kombinasyonlarini 0 ile doldur
# (frontend haritasi icin tam 7x24 = 168 hücre beklenir)
all_users   = list(golden_users)
all_weekdays = list(range(7))
all_hours    = list(range(24))

full_index = pd.MultiIndex.from_product(
    [all_users, all_weekdays, all_hours],
    names=["userid", "weekday", "hour"]
)
full_df = pd.DataFrame(index=full_index).reset_index()
heatmap = full_df.merge(heatmap, on=["userid", "weekday", "hour"], how="left")
heatmap["event_count"]    = heatmap["event_count"].fillna(0).astype(int)
heatmap["session_starts"] = heatmap["session_starts"].fillna(0).astype(int)

heatmap = heatmap.sort_values(["userid", "weekday", "hour"])

print(f"\n  Toplam satir: {len(heatmap):,}  (beklenen: {len(golden_users)*7*24:,})")
print(f"  Ort. event/hücre: {heatmap['event_count'].mean():.2f}")
print(f"  En aktif saat: {heatmap.groupby('hour')['event_count'].sum().idxmax():.0f}:00")
print(f"  En aktif gun (0=Pzt): {heatmap.groupby('weekday')['event_count'].sum().idxmax()}")

kaydet(CIKTI_DIR, "dash_06_activity_heatmap.csv", heatmap)
print("\n=== TAMAMLANDI ===")

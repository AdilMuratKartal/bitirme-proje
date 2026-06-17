# -*- coding: utf-8 -*-
"""DASHBOARD TABLO 1 — dash_daily_sessions

Kaynak: aylik mdl_log dosyalari (golden users icin)
Oturum tanimi: 30 dakikadan kisa araliklarla devam eden aktivite = ayni oturum.

Cikti: cikti/dash_01_daily_sessions.csv
  userid | activity_date | day_of_week | session_count | total_minutes | page_views
"""

import sys, os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import num, kaydet, load_monthly_logs

GOLDEN_CSV = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/golden_1000.csv")
CIKTI_DIR  = os.path.join(os.path.dirname(__file__), "cikti")
SESSION_GAP_S = 1800  # 30 dakika = oturum kopma esigi

print("=== DASHBOARD 01: GUNLUK OTURUM HESAPLAMA ===\n")

# 1. Golden users
golden = pd.read_csv(GOLDEN_CSV, usecols=["userid"])
golden_users = set(golden["userid"].astype(int))
print(f"  Golden users: {len(golden_users):,}")

# 2. Loglar (sadece golden users, time+userid+action)
print("\n[1/3] Aylik loglar yukleniyor...")
log_df = load_monthly_logs(
    usecols=["time", "userid", "action"],
    filtered_users=golden_users,
)
if len(log_df) == 0:
    raise SystemExit("HATA: Log kaydi bulunamadi.")

log_df["userid"] = num(log_df["userid"]).astype(int)
log_df["time"]   = num(log_df["time"])
log_df["action"] = log_df["action"].fillna("").str.lower()

# Gecersiz timestamp'leri at
log_df = log_df[log_df["time"] > 1_000_000_000].copy()
log_df = log_df.sort_values(["userid", "time"]).reset_index(drop=True)
print(f"  Toplam gecerli log satiri: {len(log_df):,}")

# 3. Oturum hesaplama (vectorized)
print("\n[2/3] Oturum hesaplaniyor...")

# Her kullanici icin onceki event'in zamani
log_df["prev_time"] = log_df.groupby("userid")["time"].shift(1)
log_df["gap_s"]     = log_df["time"] - log_df["prev_time"]

# Yeni oturum: kullanici degisti (gap NaN) veya gecikme > 30 dk
log_df["new_session"] = log_df["gap_s"].isna() | (log_df["gap_s"] > SESSION_GAP_S)

# Global oturum ID (her new_session = 1 bir oturumu baslatir)
log_df["session_id"] = log_df["new_session"].cumsum()

# Oturum suresi: gap'i oturuma ata (max SESSION_GAP_S; NaN = 0)
log_df["session_min"] = log_df["gap_s"].clip(upper=SESSION_GAP_S).fillna(0) / 60.0

# Tarih ve haftanin gunu
log_df["activity_date"] = pd.to_datetime(log_df["time"], unit="s", utc=True).dt.date
log_df["day_of_week"]   = pd.to_datetime(log_df["time"], unit="s", utc=True).dt.dayofweek  # 0=Pzt

# page_views: action'i "view" iceriyorsa
log_df["is_view"] = log_df["action"].str.contains("view", na=False).astype(int)

# 4. Gunluk aggregate
print("[3/3] Gunluk aggregation...")
daily = (
    log_df.groupby(["userid", "activity_date", "day_of_week"])
    .agg(
        session_count=("session_id",  "nunique"),
        total_minutes=("session_min", "sum"),
        page_views=   ("is_view",     "sum"),
    )
    .reset_index()
)

daily["total_minutes"] = daily["total_minutes"].round(2)
daily["page_views"]    = daily["page_views"].astype(int)
daily["session_count"] = daily["session_count"].astype(int)

print(f"\n  Gunluk satir sayisi: {len(daily):,}")
print(f"  Kullanic sayisi    : {daily['userid'].nunique():,}")
print(f"  Tarih araligi      : {daily['activity_date'].min()} — {daily['activity_date'].max()}")
print(f"  Ort. günlük süre   : {daily['total_minutes'].mean():.1f} dk")

kaydet(CIKTI_DIR, "dash_01_daily_sessions.csv", daily)
print("\n=== TAMAMLANDI ===")

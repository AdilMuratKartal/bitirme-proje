# -*- coding: utf-8 -*-
"""DASHBOARD TABLO 5 — dash_course_analytics

Kurs detay sayfasi analitik bolumu icin per-user per-course ozet.
  - En cok etkilesilen modul tipi
  - Assign / quiz / resource tamamlanma oranlari
  - Gunluk ortalama calisma suresi (bu kurs icin)
  - Toplam aktif gun sayisi

Bagimliliklar:
  - cikti/dash_04_module_status.csv  (completion rates)
  - aylik mdl_log (kurs bazi aktivite suresi)

Cikti: cikti/dash_05_course_analytics.csv
  userid | courseid | most_common_module_type
         | assign_total | assign_completed | assign_completion_rate
         | quiz_total   | quiz_completed   | quiz_completion_rate
         | resource_total | resource_viewed | resource_view_rate
         | forum_total | forum_interactions | forum_interaction_rate
         | page_total  | page_viewed        | page_view_rate
         | avg_daily_minutes | total_active_days | total_events | last_activity_date
"""

import sys, os, json
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import num, kaydet, load_monthly_logs

GOLDEN_CSV  = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/golden_1000.csv")
CONFIG_JSON = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/config.json")
MODULE_CSV  = os.path.join(os.path.dirname(__file__), "cikti/dash_04_module_status.csv")
CIKTI_DIR   = os.path.join(os.path.dirname(__file__), "cikti")

# resource grubu: insan okunur olmayan tum dokuman/icerik tipleri
RESOURCE_TYPES = {"resource", "url", "page", "folder", "label", "book"}

print("=== DASHBOARD 05: KURS ANALITIGI ===\n")

with open(CONFIG_JSON, encoding="utf-8") as f:
    cfg = json.load(f)
    data_end_ts = cfg["data_end_ts"]

# 1. Golden users
golden = pd.read_csv(GOLDEN_CSV, usecols=["userid"])
golden_users = set(golden["userid"].astype(int))
print(f"  Golden users: {len(golden_users):,}")

# 2. Module status: tamamlanma oranlari
print("\n[1/3] Modul durumu yukleniyor...")
mod = pd.read_csv(MODULE_CSV, usecols=[
    "userid", "courseid", "module_type", "is_visible", "is_completed"
])
mod["userid"]       = mod["userid"].astype(int)
mod["courseid"]     = mod["courseid"].astype(int)
mod["is_visible"]   = mod["is_visible"].astype(bool)
mod["is_completed"] = mod["is_completed"].astype(bool)
mod["module_type"]  = mod["module_type"].fillna("other").str.lower()

visible_mod = mod[mod["is_visible"]].copy()

# assign completion
assign_stats = (
    visible_mod[visible_mod["module_type"] == "assign"]
    .groupby(["userid", "courseid"])
    .agg(assign_total=("is_visible", "count"), assign_completed=("is_completed", "sum"))
    .reset_index()
)
assign_stats["assign_completion_rate"] = (
    assign_stats["assign_completed"] / assign_stats["assign_total"].clip(lower=1) * 100
).round(2)

# quiz completion
quiz_stats = (
    visible_mod[visible_mod["module_type"] == "quiz"]
    .groupby(["userid", "courseid"])
    .agg(quiz_total=("is_visible", "count"), quiz_completed=("is_completed", "sum"))
    .reset_index()
)
quiz_stats["quiz_completion_rate"] = (
    quiz_stats["quiz_completed"] / quiz_stats["quiz_total"].clip(lower=1) * 100
).round(2)

# resource/url/page/folder view rate
res_stats = (
    visible_mod[visible_mod["module_type"].isin(RESOURCE_TYPES)]
    .groupby(["userid", "courseid"])
    .agg(resource_total=("is_visible", "count"), resource_viewed=("is_completed", "sum"))
    .reset_index()
)
res_stats["resource_view_rate"] = (
    res_stats["resource_viewed"] / res_stats["resource_total"].clip(lower=1) * 100
).round(2)

# forum interactions (add discussion, reply → is_completed=True)
forum_stats = (
    visible_mod[visible_mod["module_type"] == "forum"]
    .groupby(["userid", "courseid"])
    .agg(forum_total=("is_visible", "count"), forum_interactions=("is_completed", "sum"))
    .reset_index()
)
forum_stats["forum_interaction_rate"] = (
    forum_stats["forum_interactions"] / forum_stats["forum_total"].clip(lower=1) * 100
).round(2)

# page views (sadece 'page' tipi; resource grubundan ayri olarak detayli)
page_stats = (
    visible_mod[visible_mod["module_type"] == "page"]
    .groupby(["userid", "courseid"])
    .agg(page_total=("is_visible", "count"), page_viewed=("is_completed", "sum"))
    .reset_index()
)
page_stats["page_view_rate"] = (
    page_stats["page_viewed"] / page_stats["page_total"].clip(lower=1) * 100
).round(2)

# 3. Log'dan kurs bazi aktivite suresi + en cok modul tipi
print("[2/3] Kurs bazi log analizi yukleniyor...")
enrolled_courses = set(mod["courseid"])
log_df = load_monthly_logs(
    usecols=["time", "userid", "course", "module", "action"],
    filtered_users=golden_users,
    filtered_courses=enrolled_courses,
)
log_df["userid"]   = num(log_df["userid"]).astype(int)
log_df["courseid"] = num(log_df.get("courseid", log_df.get("course", pd.Series()))).astype(int)
log_df["time"]     = num(log_df["time"]).astype(float)
log_df["module"]   = log_df["module"].fillna("other").str.strip().str.lower()

log_df = log_df[log_df["time"] > 1_000_000_000].sort_values(["userid", "courseid", "time"])

# Oturum suresi hesabi (kurs icinde 30 dk bosluk = yeni oturum)
log_df["prev_time"]   = log_df.groupby(["userid", "courseid"])["time"].shift(1)
log_df["gap_s"]       = log_df["time"] - log_df["prev_time"]
log_df["session_min"] = log_df["gap_s"].clip(upper=1800).fillna(0) / 60.0

log_df["activity_date"] = pd.to_datetime(log_df["time"], unit="s", utc=True).dt.date

# Gunluk toplam dakika ve toplam event
log_activity = log_df.groupby(["userid", "courseid", "activity_date"]).agg(
    daily_minutes=("session_min", "sum"),
    events=("time", "count"),
).reset_index()

course_time = log_activity.groupby(["userid", "courseid"]).agg(
    avg_daily_minutes=("daily_minutes", "mean"),
    total_active_days=("activity_date", "nunique"),
    total_events=("events", "sum"),
    last_activity_date=("activity_date", "max"),
).reset_index()
course_time["avg_daily_minutes"] = course_time["avg_daily_minutes"].round(2)

# En cok etkilesilen modul tipi per (userid, courseid)
mod_type_counts = (
    log_df.groupby(["userid", "courseid", "module"]).size()
    .reset_index(name="event_count")
)
most_common = (
    mod_type_counts.sort_values("event_count", ascending=False)
    .drop_duplicates(subset=["userid", "courseid"])
    [["userid", "courseid", "module"]]
    .rename(columns={"module": "most_common_module_type"})
)

# 4. Birlestir
print("[3/3] Birlestiriliyor...")

# Base: tum (userid, courseid) cifte sahip olabilmek icin
# mod'dan benzersiz (userid, courseid) ciftlerini al
base = visible_mod[["userid", "courseid"]].drop_duplicates().copy()

result = base.merge(assign_stats, on=["userid", "courseid"], how="left")
result = result.merge(quiz_stats,  on=["userid", "courseid"], how="left")
result = result.merge(res_stats,   on=["userid", "courseid"], how="left")
result = result.merge(course_time, on=["userid", "courseid"], how="left")
result = result.merge(most_common,  on=["userid", "courseid"], how="left")
result = result.merge(forum_stats,  on=["userid", "courseid"], how="left")
result = result.merge(page_stats,   on=["userid", "courseid"], how="left")

# Eksik degerleri doldur
for col in ["assign_total", "assign_completed", "quiz_total", "quiz_completed",
            "resource_total", "resource_viewed",
            "forum_total", "forum_interactions", "page_total", "page_viewed"]:
    result[col] = result[col].fillna(0).astype(int)

for col in ["assign_completion_rate", "quiz_completion_rate", "resource_view_rate",
            "forum_interaction_rate", "page_view_rate", "avg_daily_minutes"]:
    result[col] = result[col].fillna(0.0).round(2)

result["total_active_days"]        = result["total_active_days"].fillna(0).astype(int)
result["total_events"]             = result["total_events"].fillna(0).astype(int)
result["most_common_module_type"]  = result["most_common_module_type"].fillna("unknown")

cols = [
    "userid", "courseid", "most_common_module_type",
    "assign_total", "assign_completed", "assign_completion_rate",
    "quiz_total", "quiz_completed", "quiz_completion_rate",
    "resource_total", "resource_viewed", "resource_view_rate",
    "forum_total", "forum_interactions", "forum_interaction_rate",
    "page_total", "page_viewed", "page_view_rate",
    "avg_daily_minutes", "total_active_days", "total_events", "last_activity_date"
]
result = result[cols].sort_values(["userid", "courseid"])

print(f"\n  Toplam satir (user x kurs): {len(result):,}")
print(f"  En yakin modul tipi dagilimi:")
print(result["most_common_module_type"].value_counts().head(8).to_string())

kaydet(CIKTI_DIR, "dash_05_course_analytics.csv", result)
print("\n=== TAMAMLANDI ===")

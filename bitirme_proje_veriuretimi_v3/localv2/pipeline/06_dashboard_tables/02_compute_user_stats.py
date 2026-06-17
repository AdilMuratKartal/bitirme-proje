# -*- coding: utf-8 -*-
"""DASHBOARD TABLO 2 — dash_user_stats

Ana sayfa kart kutulari icin per-user ozet istatistikler.

Bagimliliklar:
  - cikti/dash_01_daily_sessions.csv  (focus_score, streak, total_minutes)
  - cikti/dash_04_module_status.csv   (late_assignment_count)
  - anon_mdl_grade_grades + grade_items (avg_grade)

Cikti: cikti/dash_02_user_stats.csv
  userid | focus_score | focus_score_delta_pct | avg_grade | avg_grade_delta
         | study_streak_days | streak_delta | late_assignment_count
         | late_assignment_delta | total_courses_active | total_study_minutes
         | last_active_date | computed_at
"""

import sys, os, json, datetime
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import load, num, kaydet

GOLDEN_CSV   = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/golden_1000.csv")
CONFIG_JSON  = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/config.json")
SESSIONS_CSV = os.path.join(os.path.dirname(__file__), "cikti/dash_01_daily_sessions.csv")
MODULE_CSV   = os.path.join(os.path.dirname(__file__), "cikti/dash_04_module_status.csv")
CIKTI_DIR    = os.path.join(os.path.dirname(__file__), "cikti")

print("=== DASHBOARD 02: KULLANICI ISTATISTIKLERI ===\n")

# data_end_ts
with open(CONFIG_JSON, encoding="utf-8") as f:
    data_end_ts = json.load(f)["data_end_ts"]

# 1. Golden users
golden = pd.read_csv(GOLDEN_CSV, usecols=["userid", "n_courses"])
golden["userid"] = golden["userid"].astype(int)
print(f"  Golden users: {len(golden):,}")

# 2. Daily sessions
print("\n[1/4] Gunluk oturumlar yukleniyor...")
sessions = pd.read_csv(SESSIONS_CSV, parse_dates=["activity_date"])
sessions["userid"]        = sessions["userid"].astype(int)
sessions["activity_date"] = pd.to_datetime(sessions["activity_date"]).dt.date
sessions["total_minutes"] = sessions["total_minutes"].astype(float)
sessions["page_views"]    = sessions["page_views"].astype(int)

# Referans tarih: veri bitis tarihi (suanki zaman degil, tarihsel veri icin)
import datetime as dt
ref_date = dt.datetime.fromtimestamp(data_end_ts).date()
ref_ts = pd.Timestamp(ref_date)
week_ago = ref_date - dt.timedelta(days=7)
two_weeks_ago = ref_date - dt.timedelta(days=14)

# focus_score: son 7 gunun dakikasi / haftalik ortalama * 100
total_per_user = sessions.groupby("userid")["total_minutes"].sum().rename("total_study_minutes")
n_weeks_per_user = sessions.groupby("userid")["activity_date"].apply(
    lambda dates: max(1, (dates.max() - dates.min()).days // 7 + 1)
).rename("n_weeks")
avg_weekly = (total_per_user / n_weeks_per_user).rename("avg_weekly_minutes")

last_7d = sessions[sessions["activity_date"] >= week_ago].groupby("userid")["total_minutes"].sum()
prev_7d = sessions[
    (sessions["activity_date"] >= two_weeks_ago) & (sessions["activity_date"] < week_ago)
].groupby("userid")["total_minutes"].sum()

focus_df = pd.DataFrame({
    "total_study_minutes": total_per_user,
    "avg_weekly_minutes": avg_weekly,
    "last_7d_minutes": last_7d,
    "prev_7d_minutes": prev_7d,
}).reset_index()
focus_df = focus_df.rename(columns={"index": "userid"})

focus_df["focus_score"] = (
    focus_df["last_7d_minutes"] /
    focus_df["avg_weekly_minutes"].clip(lower=1)
    * 100
).clip(upper=100).round(2)

focus_df["prev_focus"] = (
    focus_df["prev_7d_minutes"] /
    focus_df["avg_weekly_minutes"].clip(lower=1)
    * 100
).clip(upper=100)

focus_df["focus_score_delta_pct"] = (focus_df["focus_score"] - focus_df["prev_focus"]).round(2)

# last_active_date
last_active = sessions.groupby("userid")["activity_date"].max().rename("last_active_date")

# avg_session_minutes: toplam dakika / toplam oturum sayisi
total_sessions = sessions.groupby("userid")["session_count"].sum()
avg_session_minutes = (
    total_per_user / total_sessions.clip(lower=1)
).round(2).rename("avg_session_minutes")

# sessions_per_active_day: aktif gunlerde gunluk ortalama oturum sayisi
sessions_per_active_day = (
    sessions.groupby("userid")["session_count"].mean()
).round(2).rename("sessions_per_active_day")

# 3. Study streak (bugune kadar ardasik aktif gunler, ref_date baz alinarak)
print("[2/4] Calisma serisi (streak) hesaplaniyor...")

def compute_streak(dates_series):
    """Verilen tarih listesinden ardisik gun sayisini hesaplar (ref_date'ten geriye)."""
    dates = sorted(set(dates_series), reverse=True)
    if not dates:
        return 0
    streak = 0
    expected = ref_date
    for d in dates:
        if d == expected:
            streak += 1
            expected -= dt.timedelta(days=1)
        elif d < expected:
            break
    return streak

streak_series = sessions.groupby("userid")["activity_date"].apply(compute_streak).rename("study_streak_days")

# streak_delta: bugun ile dun karsilastirmasi anlamsiz tarihsel veri icin,
# basitce ref_date-1 olan tarihte log olup olmadigini kontrol ediyoruz
yesterday = ref_date - dt.timedelta(days=1)
had_activity_yesterday = (
    sessions[sessions["activity_date"] == yesterday]
    .groupby("userid")["page_views"].sum()
    .gt(0)
    .astype(int)
    .rename("streak_delta")
)

# 4. Module status: late assignments ve aktif kurs sayisi
print("[3/4] Modul durumu yukleniyor...")
mod = pd.read_csv(MODULE_CSV, usecols=[
    "userid", "courseid", "module_type", "is_visible", "is_completed",
    "expected_date", "completion_required"
])
mod["userid"]              = mod["userid"].astype(int)
mod["is_visible"]          = mod["is_visible"].astype(bool)
mod["is_completed"]        = mod["is_completed"].astype(bool)
mod["completion_required"] = mod["completion_required"].fillna(0).astype(int)

# expected_date'i date'e cevir
mod["expected_date"] = pd.to_datetime(mod["expected_date"], errors="coerce")

# Late assignment: assign, gorunen, tamamlanmamis, expected gecmis
late_mask = (
    (mod["module_type"] == "assign") &
    (mod["is_visible"]) &
    (~mod["is_completed"]) &
    (mod["expected_date"].notna()) &
    (mod["expected_date"] < ref_ts)
)
late_counts = mod[late_mask].groupby("userid").size().rename("late_assignment_count")

# Aktif kurs sayisi (kullanicinin gorununur modulü olan kurs sayisi)
active_courses = mod[mod["is_visible"]].groupby("userid")["courseid"].nunique().rename("total_courses_active")

# 5. Grade: normalise avg
print("[4/4] Grade bilgileri yukleniyor...")
gg = load("grade_grades", usecols=["userid", "itemid", "finalgrade", "hidden"])
gi = load("grade_items", usecols=["id", "courseid", "itemtype", "grademax", "grademin", "hidden"])

if gg is not None and gi is not None:
    gg["userid"]     = num(gg["userid"]).astype(int)
    gg["itemid"]     = num(gg["itemid"]).astype("Int64")
    gg["finalgrade"] = num(gg["finalgrade"])
    gg["hidden"]     = num(gg["hidden"]).fillna(0).astype(int)

    gi["id"]        = num(gi["id"]).astype("Int64")
    gi["grademax"]  = num(gi["grademax"]).fillna(100)
    gi["grademin"]  = num(gi["grademin"]).fillna(0)
    gi["hidden"]    = num(gi["hidden"]).fillna(0).astype(int)

    # Sadece gorunen, kurs-seviyeli grade itemlar
    gi_course = gi[(gi["itemtype"] == "course") & (gi["hidden"] == 0)][["id", "grademax", "grademin"]]

    grade_joined = gg[(gg["hidden"] == 0) & gg["finalgrade"].notna()].merge(
        gi_course, left_on="itemid", right_on="id", how="inner"
    )
    # Normalise: (finalgrade - grademin) / (grademax - grademin) * 100
    range_val = (grade_joined["grademax"] - grade_joined["grademin"]).clip(lower=1)
    grade_joined["norm_grade"] = (
        (grade_joined["finalgrade"] - grade_joined["grademin"]) / range_val * 100
    ).clip(0, 100)

    avg_grade = grade_joined.groupby("userid")["norm_grade"].mean().round(2).rename("avg_grade")
else:
    avg_grade = pd.Series(dtype=float, name="avg_grade")

# 6. Birlestir
print("\n[Birlestirme]...")
stats = golden[["userid", "n_courses"]].copy()
stats = stats.merge(focus_df[["userid", "focus_score", "focus_score_delta_pct",
                               "total_study_minutes"]], on="userid", how="left")
stats = stats.merge(last_active.reset_index(), on="userid", how="left")
stats = stats.merge(streak_series.reset_index(), on="userid", how="left")
stats = stats.merge(had_activity_yesterday.reset_index(), on="userid", how="left")
stats = stats.merge(late_counts.reset_index(), on="userid", how="left")
stats = stats.merge(active_courses.reset_index(), on="userid", how="left")
stats = stats.merge(avg_grade.reset_index(), on="userid", how="left")
stats = stats.merge(avg_session_minutes.reset_index(), on="userid", how="left")
stats = stats.merge(sessions_per_active_day.reset_index(), on="userid", how="left")

# Eksik degerleri doldur
stats["focus_score"]           = stats["focus_score"].fillna(0).round(2)
stats["focus_score_delta_pct"] = stats["focus_score_delta_pct"].fillna(0).round(2)
stats["avg_grade"]             = stats["avg_grade"].fillna(pd.NA)
stats["avg_grade_delta"]       = 0.0  # iki olcum arasi delta; ilk versiyon icin 0
stats["study_streak_days"]     = stats["study_streak_days"].fillna(0).astype(int)
stats["streak_delta"]          = stats["streak_delta"].fillna(0).astype(int)
stats["late_assignment_count"] = stats["late_assignment_count"].fillna(0).astype(int)
stats["late_assignment_delta"] = 0    # ilk versiyon icin 0
stats["total_courses_active"]  = stats["total_courses_active"].fillna(stats["n_courses"]).astype(int)
stats["total_study_minutes"]     = stats["total_study_minutes"].fillna(0).round(2)
stats["avg_session_minutes"]     = stats["avg_session_minutes"].fillna(0).round(2)
stats["sessions_per_active_day"] = stats["sessions_per_active_day"].fillna(0).round(2)
stats["computed_at"]             = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

cols = [
    "userid", "focus_score", "focus_score_delta_pct",
    "avg_grade", "avg_grade_delta",
    "study_streak_days", "streak_delta",
    "late_assignment_count", "late_assignment_delta",
    "total_courses_active", "total_study_minutes",
    "avg_session_minutes", "sessions_per_active_day",
    "last_active_date", "computed_at"
]
stats = stats[cols]

print(f"\n  Kullanici sayisi      : {len(stats):,}")
print(f"  Ort. focus score      : {stats['focus_score'].mean():.1f}")
print(f"  Ort. study streak     : {stats['study_streak_days'].mean():.1f} gün")
print(f"  Ort. late assignments : {stats['late_assignment_count'].mean():.1f}")
print(f"  Avg grade mevcut      : {stats['avg_grade'].notna().sum():,} kullanici")

kaydet(CIKTI_DIR, "dash_02_user_stats.csv", stats)
print("\n=== TAMAMLANDI ===")

# -*- coding: utf-8 -*-
"""DASHBOARD TABLO 3 — dash_course_progress

Kurslarim sayfasi kurs kartlari icin per-user per-course ozet.
Tamamlanma orani: sadece gorunen (visible=1) moduller hesaba katilir.

Bagimliliklar:
  - cikti/dash_04_module_status.csv
  - anon_mdl_course, anon_mdl_user_enrolments, anon_mdl_enrol
  - anon_mdl_grade_grades + grade_items (kurs notu)

Cikti: cikti/dash_03_course_progress.csv
  userid | courseid | course_fullname | course_shortname | course_visible
         | enrollment_status | total_visible_modules | completed_modules
         | completion_pct | avg_grade | next_expected_date
         | last_activity_date | computed_at
"""

import sys, os, json, datetime
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import load, num, kaydet, load_monthly_logs

GOLDEN_CSV   = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/golden_1000.csv")
CONFIG_JSON  = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/config.json")
MODULE_CSV   = os.path.join(os.path.dirname(__file__), "cikti/dash_04_module_status.csv")
CIKTI_DIR    = os.path.join(os.path.dirname(__file__), "cikti")

print("=== DASHBOARD 03: KURS ILERLEME OZETI ===\n")

with open(CONFIG_JSON, encoding="utf-8") as f:
    data_end_ts = json.load(f)["data_end_ts"]

import datetime as dt
ref_date = dt.datetime.fromtimestamp(data_end_ts).date()
ref_ts = pd.Timestamp(ref_date)

# 1. Golden users
golden = pd.read_csv(GOLDEN_CSV, usecols=["userid"])
golden_users = set(golden["userid"].astype(int))
print(f"  Golden users: {len(golden_users):,}")

# 2. Module status
print("\n[1/5] Modul durumu yukleniyor...")
mod = pd.read_csv(MODULE_CSV, usecols=[
    "userid", "courseid", "is_visible", "is_completed", "expected_date"
])
mod["userid"]       = mod["userid"].astype(int)
mod["courseid"]     = mod["courseid"].astype(int)
mod["is_visible"]   = mod["is_visible"].astype(bool)
mod["is_completed"] = mod["is_completed"].astype(bool)
mod["expected_date"] = pd.to_datetime(mod["expected_date"], errors="coerce")

# Tamamlanma orani per (userid, courseid) — sadece gorunen moduller
visible_mod = mod[mod["is_visible"]].copy()

module_counts = visible_mod.groupby(["userid", "courseid"]).agg(
    total_visible_modules=("is_visible", "count"),
    completed_modules=("is_completed", "sum"),
).reset_index()

module_counts["completion_pct"] = (
    module_counts["completed_modules"] / module_counts["total_visible_modules"] * 100
).where(module_counts["total_visible_modules"] > 0).round(2)

# next_expected_date: en yakin tamamlanmamis, gorunen, tarihi gecmemis modul
upcoming = visible_mod[
    (~mod["is_completed"]) &
    (mod["expected_date"].notna()) &
    (mod["expected_date"] >= ref_ts)
]
next_exp = (
    upcoming.groupby(["userid", "courseid"])["expected_date"]
    .min()
    .reset_index(name="next_expected_date")
)

# 3. Son aktivite tarihi (log'dan)
print("[2/5] Son aktivite tarihleri icin loglar yukleniyor...")
enrolled_courses = set(mod["courseid"])
log_df = load_monthly_logs(
    usecols=["time", "userid", "course"],
    filtered_users=golden_users,
    filtered_courses=enrolled_courses,
)
log_df["userid"]   = num(log_df["userid"]).astype(int)
log_df["courseid"] = num(log_df.get("courseid", log_df.get("course", pd.Series()))).astype(int)
log_df["time"]     = num(log_df["time"])
log_df = log_df[log_df["time"] > 1_000_000_000]
log_df["activity_date"] = pd.to_datetime(log_df["time"], unit="s", utc=True).dt.date

last_activity = (
    log_df.groupby(["userid", "courseid"])["activity_date"]
    .max()
    .reset_index(name="last_activity_date")
)

# 4. Kurs meta: fullname, shortname, visible
print("[3/5] Kurs meta bilgileri yukleniyor...")
course = load("course", usecols=["id", "fullname", "shortname", "visible"])
course["id"]      = num(course["id"]).astype(int)
course["visible"] = num(course["visible"]).fillna(0).astype(int)
course["fullname"]  = course["fullname"].fillna("").str.strip()
course["shortname"] = course["shortname"].fillna("").str.strip()

# 5. Enrollment durumu per (userid, courseid)
print("[4/5] Kayit durumu yukleniyor...")
ue    = load("user_enrolments", usecols=["status", "enrolid", "userid"])
enrol = load("enrol", usecols=["id", "status", "courseid"])

ue["status"]    = num(ue["status"]).astype(int)
ue["enrolid"]   = num(ue["enrolid"]).astype("Int64")
ue["userid"]    = num(ue["userid"]).astype(int)
enrol["id"]       = num(enrol["id"]).astype("Int64")
enrol["status"]   = num(enrol["status"]).astype(int)
enrol["courseid"] = num(enrol["courseid"]).astype(int)

enrol_status = (
    ue.merge(enrol[["id", "status", "courseid"]], left_on="enrolid", right_on="id")
    [["userid", "courseid", "status_x"]]
    .rename(columns={"status_x": "enrollment_status"})
    .drop_duplicates(subset=["userid", "courseid"])
)
enrol_status = enrol_status[enrol_status["userid"].isin(golden_users)]

# 6. Grade: kurs-seviyeli normalise not
print("[5/5] Kurs notlari yukleniyor...")
gg = load("grade_grades", usecols=["userid", "itemid", "finalgrade", "hidden"])
gi = load("grade_items", usecols=["id", "courseid", "itemtype", "grademax", "grademin", "hidden"])

if gg is not None and gi is not None:
    gg["userid"]     = num(gg["userid"]).astype(int)
    gg["itemid"]     = num(gg["itemid"]).astype("Int64")
    gg["finalgrade"] = num(gg["finalgrade"])
    gg["hidden"]     = num(gg["hidden"]).fillna(0).astype(int)

    gi["id"]       = num(gi["id"]).astype("Int64")
    gi["courseid"] = num(gi["courseid"]).astype(int)
    gi["grademax"] = num(gi["grademax"]).fillna(100)
    gi["grademin"] = num(gi["grademin"]).fillna(0)
    gi["hidden"]   = num(gi["hidden"]).fillna(0).astype(int)

    # Kurs seviyeli grade item (itemtype='course')
    gi_course = gi[(gi["itemtype"] == "course") & (gi["hidden"] == 0)]
    grade_j = gg[(gg["hidden"] == 0) & gg["finalgrade"].notna()].merge(
        gi_course[["id", "courseid", "grademax", "grademin"]],
        left_on="itemid", right_on="id", how="inner"
    )
    rng = (grade_j["grademax"] - grade_j["grademin"]).clip(lower=1)
    grade_j["norm_grade"] = (
        (grade_j["finalgrade"] - grade_j["grademin"]) / rng * 100
    ).clip(0, 100)

    course_avg_grade = (
        grade_j[grade_j["userid"].isin(golden_users)]
        .groupby(["userid", "courseid"])["norm_grade"]
        .mean().round(2)
        .reset_index(name="avg_grade")
    )
else:
    course_avg_grade = pd.DataFrame(columns=["userid", "courseid", "avg_grade"])

# 7. Birlestir
print("\nBirlestiriliyor...")
result = module_counts.copy()
result = result.merge(next_exp, on=["userid", "courseid"], how="left")
result = result.merge(last_activity, on=["userid", "courseid"], how="left")
result = result.merge(
    course[["id", "fullname", "shortname", "visible"]].rename(columns={"id": "courseid"}),
    on="courseid", how="left"
)
result = result.merge(enrol_status, on=["userid", "courseid"], how="left")
result = result.merge(course_avg_grade, on=["userid", "courseid"], how="left")

result = result.rename(columns={
    "fullname": "course_fullname",
    "shortname": "course_shortname",
    "visible": "course_visible",
})
result["course_visible"]    = result["course_visible"].fillna(1).astype(int)
result["enrollment_status"] = result["enrollment_status"].fillna(0).astype(int)
result["computed_at"]       = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

cols = [
    "userid", "courseid", "course_fullname", "course_shortname", "course_visible",
    "enrollment_status", "total_visible_modules", "completed_modules",
    "completion_pct", "avg_grade", "next_expected_date",
    "last_activity_date", "computed_at"
]
result = result[cols].sort_values(["userid", "courseid"])

print(f"\n  Toplam satir (user x kurs): {len(result):,}")
print(f"  Kullanici: {result['userid'].nunique():,}")
print(f"  Kurs: {result['courseid'].nunique():,}")
print(f"  Ort. completion_pct: {result['completion_pct'].mean():.1f}%")
print(f"  Avg grade mevcut: {result['avg_grade'].notna().sum():,}")

kaydet(CIKTI_DIR, "dash_03_course_progress.csv", result)
print("\n=== TAMAMLANDI ===")

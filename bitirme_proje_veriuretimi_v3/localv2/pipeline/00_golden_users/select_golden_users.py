# -*- coding: utf-8 -*-
"""ASAMA 00 — Altin Kullanici Secimi (Golden Users)

1000 en kaliteli ogrenci secilir:
  - En az 2 gorununur kursa aktif kayitli (status=0, roleid=5, contextlevel=50)
  - En az 1 log kaydi var
  - Skor = n_log_events*0.4 + n_inferred_completions*0.4 + n_courses*5*0.2
  - Esdeger skorda grade kaydi olanlar once

Cikti:
  cikti/golden_1000.csv  — userid | n_courses | n_log_events | n_inferred_completions
                                  | has_grades | selection_score | selected_at
  cikti/config.json      — data_end_ts (log'daki max timestamp)
  cikti/golden_selection_rapor.txt
"""

import sys, os, datetime, json
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import load, num, kaydet, rapor, yuzde, load_monthly_logs

CIKTI_DIR   = os.path.join(os.path.dirname(__file__), "cikti")
N_GOLDEN    = 1000
MIN_COURSES = 2
MOODLE_CONTEXT_COURSE = 50
STUDENT_ROLE_ID       = 5

# Modül tipine göre "tamamlanma" aksiyonları
COMPLETION_ACTIONS = {
    "assign":   {"submit"},
    "quiz":     {"close attempt", "submit"},
    "resource": {"view"},
    "url":      {"view"},
    "page":     {"view"},
    "folder":   {"view"},
    "forum":    {"add discussion", "reply"},
    "feedback": {"submit"},
    "choice":   {"choose"},
    "lesson":   {"view"},
    "survey":   {"submit"},
    "wiki":     {"view"},
    "scorm":    {"view"},
    "workshop": {"submit"},
}

print("=== ASAMA 00: ALTIN KULLANICI SECIMI ===\n")

# ------------------------------------------------------------------ #
# 1. Aktif kurslar (visible=1)
# ------------------------------------------------------------------ #
print("[1/7] Aktif kurslar yukleniyor...")
course = load("course", usecols=["id", "visible"])
if course is None:
    raise SystemExit("HATA: anon_mdl_course.csv bulunamadi.")
course["id"]      = num(course["id"])
course["visible"] = num(course["visible"])
active_courses = set(course[course["visible"] == 1]["id"].dropna().astype(int))
print(f"  Aktif kurs: {len(active_courses):,}")

# ------------------------------------------------------------------ #
# 2. Aktif kayitlar: user_enrolments ∩ enrol (her ikisi de status=0)
# ------------------------------------------------------------------ #
print("\n[2/7] Kayit tablolari yukleniyor...")
ue    = load("user_enrolments", usecols=["status", "enrolid", "userid"])
enrol = load("enrol", usecols=["id", "status", "courseid"])
if ue is None or enrol is None:
    raise SystemExit("HATA: user_enrolments veya enrol tablosu bulunamadi.")

ue["status"]    = num(ue["status"])
ue["enrolid"]   = num(ue["enrolid"]).astype("Int64")
ue["userid"]    = num(ue["userid"]).astype("Int64")
enrol["id"]       = num(enrol["id"]).astype("Int64")
enrol["status"]   = num(enrol["status"])
enrol["courseid"] = num(enrol["courseid"]).astype("Int64")

enrolled = (
    ue[ue["status"] == 0]
    .merge(enrol[enrol["status"] == 0][["id", "courseid"]],
           left_on="enrolid", right_on="id")
)[["userid", "courseid"]].drop_duplicates()
enrolled = enrolled[enrolled["courseid"].isin(active_courses)].copy()
print(f"  Aktif kayit (ue+enrol status=0, visible kurs): {len(enrolled):,} "
      f"({enrolled['userid'].nunique():,} kullanici)")

# ------------------------------------------------------------------ #
# 3. Ogrenci rolu (roleid=5, contextlevel=50)
# ------------------------------------------------------------------ #
print("\n[3/7] Rol atamalari kontrol ediliyor...")
ra  = load("role_assignments", usecols=["roleid", "contextid", "userid"])
ctx = load("context", usecols=["id", "contextlevel", "instanceid"])
if ra is None or ctx is None:
    raise SystemExit("HATA: role_assignments veya context tablosu bulunamadi.")

ra["roleid"]    = num(ra["roleid"])
ra["contextid"] = num(ra["contextid"]).astype("Int64")
ra["userid"]    = num(ra["userid"]).astype("Int64")
ctx["id"]           = num(ctx["id"]).astype("Int64")
ctx["contextlevel"] = num(ctx["contextlevel"])
ctx["instanceid"]   = num(ctx["instanceid"]).astype("Int64")

course_ctx = (
    ctx[ctx["contextlevel"] == MOODLE_CONTEXT_COURSE][["id", "instanceid"]]
    .rename(columns={"id": "contextid", "instanceid": "courseid"})
)
student_course_idx = (
    ra[ra["roleid"] == STUDENT_ROLE_ID][["userid", "contextid"]]
    .merge(course_ctx, on="contextid")
    [["userid", "courseid"]]
    .drop_duplicates()
    .set_index(["userid", "courseid"])
    .index
)

enrolled["userid"]   = enrolled["userid"].astype("Int64")
enrolled["courseid"] = enrolled["courseid"].astype("Int64")
enrolled = enrolled[
    enrolled.set_index(["userid", "courseid"]).index.isin(student_course_idx)
].copy()
enrolled["userid"]   = enrolled["userid"].astype(int)
enrolled["courseid"] = enrolled["courseid"].astype(int)

# n_courses per user → filtre: >= MIN_COURSES
user_courses = (
    enrolled.groupby("userid")["courseid"].nunique()
    .reset_index(name="n_courses")
)
eligible_users   = set(user_courses[user_courses["n_courses"] >= MIN_COURSES]["userid"])
eligible_courses = set(enrolled[enrolled["userid"].isin(eligible_users)]["courseid"])
print(f"  Ogrenci rolü + n_courses>={MIN_COURSES}: {len(eligible_users):,} kullanici")

# ------------------------------------------------------------------ #
# 4. Aylik loglar (sadece uygun kullanicilar)
# ------------------------------------------------------------------ #
print("\n[4/7] Aylik loglar yukleniyor...")
log_df = load_monthly_logs(
    usecols=["time", "userid", "course", "module", "cmid", "action"],
    filtered_users=eligible_users,
    filtered_courses=eligible_courses,
)
if len(log_df) == 0:
    raise SystemExit("HATA: Hicbir log kaydi bulunamadi. DATA_DIR ve log-olarak-aylar kontrolu.")

log_df["userid"] = num(log_df["userid"]).astype("Int64")
log_df["time"]   = num(log_df["time"])
log_df["cmid"]   = num(log_df.get("cmid", pd.Series(0, index=log_df.index))).fillna(0).astype(int)
log_df["module"] = log_df["module"].fillna("").str.strip().str.lower()
log_df["action"] = log_df["action"].fillna("").str.strip().str.lower()

data_end_ts = int(log_df["time"].dropna().max())
print(f"  Veri bitis zamani (data_end_ts): {datetime.datetime.fromtimestamp(data_end_ts):%Y-%m-%d}")

# n_log_events per user
log_counts = (
    log_df.groupby("userid").size()
    .reset_index(name="n_log_events")
)
log_counts["userid"] = log_counts["userid"].astype(int)
users_with_log = set(log_counts[log_counts["n_log_events"] >= 1]["userid"])
print(f"  Log kaydi olan kullanici: {len(users_with_log):,}")

# ------------------------------------------------------------------ #
# 5. Tamamlanma cikarimi (inferred completions)
# ------------------------------------------------------------------ #
print("\n[5/7] Tamamlanma cikarimi (log → completion inference)...")
cm  = load("course_modules", usecols=["id", "module", "visible"])
mod = load("modules", usecols=["id", "name"])
if cm is None or mod is None:
    raise SystemExit("HATA: course_modules veya modules tablosu bulunamadi.")

cm["id"]      = num(cm["id"]).astype("Int64")
cm["visible"] = num(cm["visible"])
mod["id"]   = num(mod["id"]).astype("Int64")
mod["name"] = mod["name"].str.strip().str.lower()

visible_cmids = set(
    cm[cm["visible"] == 1]
    .merge(mod, left_on="module", right_on="id", how="left")[["id_x"]]
    .rename(columns={"id_x": "cmid"})["cmid"]
    .dropna().astype("Int64")
)

# Completion olaylarini topla (vectorized, modül tipine göre)
parts = []
for mod_type, actions in COMPLETION_ACTIONS.items():
    mask = (log_df["module"] == mod_type) & (log_df["action"].isin(actions)) & (log_df["cmid"] > 0)
    subset = log_df[mask][["userid", "cmid"]].copy()
    subset["cmid"] = subset["cmid"].astype("Int64")
    parts.append(subset)

if parts:
    comp_df = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["userid", "cmid"])
    comp_df = comp_df[comp_df["cmid"].isin(visible_cmids)]
else:
    comp_df = pd.DataFrame(columns=["userid", "cmid"])

inferred = (
    comp_df.groupby("userid").size()
    .reset_index(name="n_inferred_completions")
)
inferred["userid"] = inferred["userid"].astype(int)
print(f"  Benzersiz (userid, cmid) tamamlama: {len(comp_df):,}")

# ------------------------------------------------------------------ #
# 6. Grade kaydi kontrolu
# ------------------------------------------------------------------ #
print("\n[6/7] Grade kaydi kontrolu...")
gg = load("grade_grades", usecols=["userid", "finalgrade"])
if gg is not None:
    gg["userid"]     = num(gg["userid"]).astype("Int64")
    gg["finalgrade"] = num(gg["finalgrade"])
    users_with_grades = set(gg[gg["finalgrade"].notna()]["userid"].astype(int))
else:
    users_with_grades = set()
print(f"  Grade kaydi olan kullanici: {len(users_with_grades):,}")

# ------------------------------------------------------------------ #
# 7. Skor hesapla + Sec
# ------------------------------------------------------------------ #
print("\n[7/7] Skorlama ve secim...")
base = user_courses[user_courses["userid"].isin(users_with_log)].copy()
base = base.merge(log_counts, on="userid", how="left")
base = base.merge(inferred, on="userid", how="left")
base["n_log_events"]           = base["n_log_events"].fillna(0).astype(int)
base["n_inferred_completions"] = base["n_inferred_completions"].fillna(0).astype(int)
base["has_grades"]             = base["userid"].isin(users_with_grades)

base["selection_score"] = (
    base["n_log_events"]           * 0.4 +
    base["n_inferred_completions"] * 0.4 +
    base["n_courses"] * 5          * 0.2
)

# Birincil: selection_score (büyükten küçük), ikincil: has_grades (True önce)
base = base.sort_values(
    ["selection_score", "has_grades"],
    ascending=[False, False]
).reset_index(drop=True)

n_available = len(base)
golden = base.head(N_GOLDEN).copy()
golden["selected_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print(f"\n  Uygun havuz: {n_available:,} | Secilen: {len(golden):,}")
print(f"  n_courses: min={golden['n_courses'].min()}, max={golden['n_courses'].max()}, "
      f"ort={golden['n_courses'].mean():.1f}")
print(f"  n_log_events: ort={golden['n_log_events'].mean():.0f}, "
      f"max={golden['n_log_events'].max():,}")
print(f"  n_inferred_completions: ort={golden['n_inferred_completions'].mean():.1f}")
print(f"  has_grades: {golden['has_grades'].sum()} "
      f"(%{yuzde(golden['has_grades'].sum(), len(golden)):.1f})")

if len(golden) < N_GOLDEN:
    print(f"\n  UYARI: Uygun kullanici {N_GOLDEN}'den az ({len(golden)}), tüm havuz secildi.")

# ------------------------------------------------------------------ #
# Kaydet
# ------------------------------------------------------------------ #
kaydet(CIKTI_DIR, "golden_1000.csv", golden)

os.makedirs(CIKTI_DIR, exist_ok=True)
config = {"data_end_ts": data_end_ts, "n_golden": len(golden)}
with open(os.path.join(CIKTI_DIR, "config.json"), "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)
print(f">>> Config: {os.path.join(CIKTI_DIR, 'config.json')}")

lines = [
    "=== ASAMA 00: ALTIN KULLANICI SECIMI RAPORU ===",
    f"Secim tarihi: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
    f"Veri bitis ts: {data_end_ts} ({datetime.datetime.fromtimestamp(data_end_ts):%Y-%m-%d})",
    "",
    f"Uygun havuz (n_courses>={MIN_COURSES}, log>=1): {n_available:,}",
    f"Secilen (N_GOLDEN={N_GOLDEN}):                 {len(golden):,}",
    "",
    "--- Istatistikler ---",
    f"n_courses              : min={golden['n_courses'].min()}, "
    f"max={golden['n_courses'].max()}, ort={golden['n_courses'].mean():.1f}",
    f"n_log_events           : min={golden['n_log_events'].min()}, "
    f"max={golden['n_log_events'].max()}, ort={golden['n_log_events'].mean():.0f}",
    f"n_inferred_completions : min={golden['n_inferred_completions'].min()}, "
    f"max={golden['n_inferred_completions'].max()}, ort={golden['n_inferred_completions'].mean():.1f}",
    f"has_grades             : {golden['has_grades'].sum()} / {len(golden)} "
    f"(%{yuzde(golden['has_grades'].sum(), len(golden)):.1f})",
    "",
    "Skor formulü: n_log_events*0.4 + n_inferred_completions*0.4 + n_courses*5*0.2",
    "Esdeger skorda has_grades=True önce.",
]
rapor(CIKTI_DIR, "golden_selection_rapor.txt", lines)

print("\n=== TAMAMLANDI ===")

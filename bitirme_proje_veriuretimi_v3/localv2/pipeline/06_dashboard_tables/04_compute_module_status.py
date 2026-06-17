# -*- coding: utf-8 -*-
"""DASHBOARD TABLO 4 — dash_module_status

Her (golden_user, gorunen_course_module) cifti icin tamamlanma durumu.
Tamamlanma: mdl_log'daki modul tipine ozgu aksiyonlarla cikarilir.

Not: mdl_course_modules_completion tablosu bu veri setinde yok,
     bu yüzden log'dan inference yapiyoruz.

Cikti: cikti/dash_04_module_status.csv
  userid | courseid | cmid | module_type | display_name | section_order
       | is_visible | is_available | completion_required
       | is_completed | completion_action | completion_time
       | first_view_time | view_to_complete_hours
       | expected_date | added_date
"""

import sys, os, json
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import load, num, kaydet, load_monthly_logs, TIME_OFFSET_S

GOLDEN_CSV = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/golden_1000.csv")
CONFIG_JSON= os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/config.json")
CIKTI_DIR  = os.path.join(os.path.dirname(__file__), "cikti")

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

print("=== DASHBOARD 04: MODULE TAMAMLANMA DURUMU ===\n")

# data_end_ts: availability hesabi icin veri bitis zamani
data_end_ts = None
if os.path.exists(CONFIG_JSON):
    with open(CONFIG_JSON, encoding="utf-8") as f:
        data_end_ts = json.load(f).get("data_end_ts")
if data_end_ts is None:
    raise SystemExit("HATA: config.json bulunamadi. Once select_golden_users.py calistirin.")

print(f"  data_end_ts: {data_end_ts}")

# 1. Golden users + kayitlari
golden = pd.read_csv(GOLDEN_CSV, usecols=["userid"])
golden_users = set(golden["userid"].astype(int))
print(f"  Golden users: {len(golden_users):,}")

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
    .merge(enrol[enrol["status"] == 0][["id", "courseid"]], left_on="enrolid", right_on="id")
)[["userid", "courseid"]].drop_duplicates()
enrolled["userid"]   = enrolled["userid"].astype(int)
enrolled["courseid"] = enrolled["courseid"].astype(int)
enrolled = enrolled[enrolled["userid"].isin(golden_users)]
golden_courses = set(enrolled["courseid"])
print(f"  Golden users kurs sayisi: {len(golden_courses):,}")

# 2. Course modules + module tipi + kurs bilgisi
print("\n[1/5] Course modules yukleniyor...")
cm = load("course_modules", usecols=[
    "id", "course", "module", "instance", "section",
    "visible", "visibleold", "completion",
    "completionexpected", "availablefrom", "availableuntil", "added"
])
mod_tbl = load("modules", usecols=["id", "name"])
if cm is None or mod_tbl is None:
    raise SystemExit("HATA: course_modules veya modules tablosu bulunamadi.")

cm["id"]                  = num(cm["id"]).astype("Int64")
cm["course"]              = num(cm["course"]).astype("Int64")
cm["module"]              = num(cm["module"]).astype("Int64")
cm["instance"]            = num(cm["instance"]).astype("Int64")
cm["section"]             = num(cm["section"]).fillna(0).astype(int)
cm["visible"]             = num(cm["visible"]).fillna(0).astype(int)
cm["completion"]          = num(cm["completion"]).fillna(0).astype(int)
cm["completionexpected"]  = num(cm["completionexpected"]).fillna(0).astype(int)
cm["availablefrom"]       = num(cm["availablefrom"]).fillna(0).astype(int)
cm["availableuntil"]      = num(cm["availableuntil"]).fillna(0).astype(int)
cm["added"]               = num(cm["added"]).fillna(0).astype(int)

# Zaman kaydirma: 0 = "belirsiz/yok", dokunulmuyor
for _col in ["completionexpected", "availablefrom", "availableuntil", "added"]:
    _m = cm[_col] > 0
    cm.loc[_m, _col] = cm.loc[_m, _col] + TIME_OFFSET_S

mod_tbl["id"]   = num(mod_tbl["id"]).astype("Int64")
mod_tbl["name"] = mod_tbl["name"].str.strip().str.lower()

# Sadece golden users'in kurslarindaki modüller
cm = cm[cm["course"].isin(golden_courses)].copy()

# module_type join
cm_typed = cm.merge(mod_tbl, left_on="module", right_on="id", suffixes=("", "_mod"))
cm_typed = cm_typed.rename(columns={"id": "cmid", "course": "courseid", "name": "module_type"})
cm_typed = cm_typed[["cmid", "courseid", "instance", "module_type", "section",
                      "visible", "completion", "completionexpected",
                      "availablefrom", "availableuntil", "added"]]
print(f"  Course modules (golden kurslar): {len(cm_typed):,}")

# 3. display_name: grade_items'tan
print("\n[2/5] Display name (grade_items)...")
gi = load("grade_items", usecols=["id", "courseid", "itemname", "itemmodule", "iteminstance", "itemtype"])
if gi is not None:
    gi["iteminstance"] = num(gi["iteminstance"]).astype("Int64")
    gi["courseid"]     = num(gi["courseid"]).astype("Int64")
    gi["itemmodule"]   = gi["itemmodule"].fillna("").str.strip().str.lower()
    gi["itemname"]     = gi["itemname"].fillna("").str.strip()
    # itemtype='mod' olan öğeler (modüle bağlı grade item)
    gi_mod = gi[gi["itemtype"] == "mod"][["courseid", "itemmodule", "iteminstance", "itemname"]].copy()
    gi_mod = gi_mod.rename(columns={"iteminstance": "instance", "itemmodule": "module_type"})
    cm_typed = cm_typed.merge(
        gi_mod[["courseid", "module_type", "instance", "itemname"]],
        on=["courseid", "module_type", "instance"],
        how="left"
    )
    cm_typed["display_name"] = cm_typed["itemname"].where(
        cm_typed["itemname"].notna() & (cm_typed["itemname"] != ""),
        other=cm_typed["module_type"].str.capitalize() + " (section " + cm_typed["section"].astype(str) + ")"
    )
    cm_typed = cm_typed.drop(columns=["itemname", "instance"])
else:
    cm_typed["display_name"] = (
        cm_typed["module_type"].str.capitalize()
        + " (section "
        + cm_typed["section"].astype(str)
        + ")"
    )
    cm_typed = cm_typed.drop(columns=["instance"])

# 4. Availability hesabi (data_end_ts referansiyla)
cm_typed["is_visible"]   = cm_typed["visible"] == 1
cm_typed["is_available"] = (
    cm_typed["is_visible"] &
    ((cm_typed["availablefrom"] == 0) | (cm_typed["availablefrom"] <= data_end_ts)) &
    ((cm_typed["availableuntil"] == 0) | (cm_typed["availableuntil"] >= data_end_ts))
)

# Tarih sütunlari
def ts_to_date(series):
    return pd.to_datetime(
        series.where(series > 0, other=pd.NA),
        unit="s", utc=True, errors="coerce"
    ).dt.date

cm_typed["expected_date"] = ts_to_date(cm_typed["completionexpected"])
cm_typed["added_date"]    = ts_to_date(cm_typed["added"])

# 5. Loglardan completion inference
print("\n[3/5] Tamamlanma cikarimi icin loglar yukleniyor...")
log_df = load_monthly_logs(
    usecols=["time", "userid", "module", "cmid", "action"],
    filtered_users=golden_users,
    filtered_courses=golden_courses,
)
log_df["userid"] = num(log_df["userid"]).astype(int)
log_df["time"]   = num(log_df["time"]).astype(float)
log_df["cmid"]   = num(log_df.get("cmid", pd.Series(0, index=log_df.index))).fillna(0).astype(int)
log_df["module"] = log_df["module"].fillna("").str.strip().str.lower()
log_df["action"] = log_df["action"].fillna("").str.strip().str.lower()

log_df = log_df[(log_df["cmid"] > 0) & (log_df["time"] > 1_000_000_000)].copy()

# Completion action maskesi
print("[4/5] Completion olaylari filtreleniyor...")
valid_cmids = set(cm_typed["cmid"].astype(int))
parts = []
for mod_type, actions in COMPLETION_ACTIONS.items():
    mask = (
        (log_df["module"] == mod_type) &
        (log_df["action"].isin(actions)) &
        (log_df["cmid"].isin(valid_cmids))
    )
    subset = log_df[mask][["userid", "cmid", "time", "action"]].copy()
    if len(subset):
        parts.append(subset)

if parts:
    comp_log = pd.concat(parts, ignore_index=True)
    # Her (userid, cmid) icin en erken tamamlanma zamani ve hangi action
    first_comp = (
        comp_log.sort_values("time")
        .groupby(["userid", "cmid"])
        .first()
        .reset_index()
    )
    first_comp = first_comp.rename(columns={"action": "completion_action", "time": "completion_time"})
    first_comp["completion_time"] = first_comp["completion_time"].astype("Int64")
    first_comp["is_completed"]    = True
else:
    first_comp = pd.DataFrame(columns=["userid", "cmid", "completion_action", "completion_time", "is_completed"])

print(f"  Tamamlanan (userid, cmid) cift: {len(first_comp):,}")

# First view: log'da her (userid, cmid) icin action='view' olan ilk zaman
print("\n[4.5/5] Ilk goruntulenme zamani hesaplaniyor...")
_view_log = log_df[log_df["action"] == "view"]
first_view = (
    _view_log[_view_log["cmid"].isin(valid_cmids)]
    .groupby(["userid", "cmid"])["time"]
    .min()
    .reset_index()
    .rename(columns={"time": "first_view_time"})
)
first_view["first_view_time"] = first_view["first_view_time"].astype("Int64")
print(f"  Ilk goruntulenme kaydi: {len(first_view):,}")

# 6. Cross join: her golden_user x kayitli_oldugu_kurslardaki_moduller
print("\n[5/5] Cross join ve final tablo olusturuluyor...")
user_module = enrolled.merge(
    cm_typed[["cmid", "courseid", "module_type", "display_name", "section",
              "is_visible", "is_available", "completion", "expected_date", "added_date"]],
    on="courseid"
)
user_module = user_module.rename(columns={
    "section": "section_order",
    "completion": "completion_required"
})

# Completion bilgisi ekle
user_module = user_module.merge(
    first_comp[["userid", "cmid", "completion_action", "completion_time", "is_completed"]],
    on=["userid", "cmid"],
    how="left"
)
user_module["is_completed"]      = user_module["is_completed"].fillna(False)
user_module["completion_action"] = user_module["completion_action"].fillna(pd.NA)
user_module["completion_time"]   = user_module["completion_time"].fillna(pd.NA)

# First view time + view-to-complete lag
user_module = user_module.merge(
    first_view[["userid", "cmid", "first_view_time"]],
    on=["userid", "cmid"],
    how="left"
)
user_module["first_view_time"] = user_module["first_view_time"].fillna(pd.NA)

user_module["view_to_complete_hours"] = pd.NA
_assign_done = (
    (user_module["module_type"] == "assign") &
    (user_module["is_completed"]) &
    user_module["first_view_time"].notna() &
    user_module["completion_time"].notna()
)
if _assign_done.any():
    user_module.loc[_assign_done, "view_to_complete_hours"] = (
        (user_module.loc[_assign_done, "completion_time"].astype(float) -
         user_module.loc[_assign_done, "first_view_time"].astype(float)) / 3600
    ).round(2)

# Sütun sirasi
cols = [
    "userid", "courseid", "cmid", "module_type", "display_name", "section_order",
    "is_visible", "is_available", "completion_required",
    "is_completed", "completion_action", "completion_time",
    "first_view_time", "view_to_complete_hours",
    "expected_date", "added_date"
]
user_module = user_module[cols].sort_values(["userid", "courseid", "section_order", "cmid"])

print(f"\n  Toplam satir: {len(user_module):,}")
print(f"  Tamamlanan modüller: {user_module['is_completed'].sum():,} "
      f"(%{100 * user_module['is_completed'].mean():.1f})")
print(f"  Gorunen modüller: {user_module['is_visible'].sum():,}")

kaydet(CIKTI_DIR, "dash_04_module_status.csv", user_module)
print("\n=== TAMAMLANDI ===")

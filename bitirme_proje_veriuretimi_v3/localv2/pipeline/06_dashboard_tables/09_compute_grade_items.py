# -*- coding: utf-8 -*-
"""DASHBOARD TABLO 9 — dash_grade_items

Notlar sayfasi icin ogrencinin HESAPLANABILIR tum grade_grades kalemleri
(kurs-seviyesi avg_grade'in aksine: tek tek odev/quiz/manuel/kategori notlari).

Filtreler (hesaplanabilir not):
  - grade_grades.finalgrade NOT NULL
  - grade_grades.hidden = 0
  - grade_grades.excluded = 0
  - grade_items.hidden = 0
  - grade_items.gradetype = 1   (sayisal/value not)

Gecti/gecmedi (gradepass):
  - gradepass NOT NULL & gradepass > 0  -> esik var
  - norm_gradepass = ((gradepass-grademin)/(grademax-grademin))*100  (olcek farkini hizalar)
  - passed = norm_grade >= norm_gradepass ; esik yoksa passed = NA (belirsiz)

Kaynak: anon_mdl_grade_grades + anon_mdl_grade_items + anon_mdl_course (BASLIKLI kanonik veri)
Cikti : cikti/dash_09_grade_items.csv
  userid | courseid | course_fullname | itemid | item_label | item_type | item_module
         | grade | grademax | grademin | norm_grade | gradepass | norm_gradepass
         | passed | graded_date
"""
import sys, os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import load, num, kaydet, TIME_OFFSET_S

GOLDEN_CSV = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/golden_1000.csv")
CIKTI_DIR  = os.path.join(os.path.dirname(__file__), "cikti")

# itemmodule -> kisa Turkce etiket (itemname anonim 'nombre' oldugu icin turden uretilir)
_MOD_TR = {
    "assign": "Ödev", "quiz": "Quiz", "workshop": "Atölye", "lesson": "Ders",
    "scorm": "İçerik", "forum": "Forum", "choice": "Anket", "data": "Veritabanı",
    "glossary": "Sözlük", "wiki": "Wiki",
}
_PLACEHOLDER = {"", "nombre", "none", "nan"}


def _item_label(itemname, itemtype, itemmodule) -> str:
    name = str(itemname).strip()
    if name and name.lower() not in _PLACEHOLDER:
        return name
    t = str(itemtype).strip().lower()
    if t == "course":   return "Kurs Genel Notu"
    if t == "manual":   return "Manuel Not"
    if t == "category": return "Kategori Toplamı"
    if t == "mod":
        m = str(itemmodule).strip().lower()
        return _MOD_TR.get(m, (m.capitalize() if m and m not in _PLACEHOLDER else "Etkinlik"))
    return t.capitalize() if t else "Not"


print("=== DASHBOARD 09: ITEM-SEVIYESI NOTLAR ===\n")

# 1. Golden users
golden = pd.read_csv(GOLDEN_CSV, usecols=["userid"])
golden_users = set(golden["userid"].astype(int))
print(f"  Golden users: {len(golden_users):,}")

# 2. grade_grades + grade_items
print("\n[1/4] grade_grades / grade_items yukleniyor...")
gg = load("grade_grades", usecols=["itemid", "userid", "finalgrade", "hidden", "excluded", "timemodified"])
gi = load("grade_items", usecols=["id", "courseid", "itemname", "itemtype", "itemmodule",
                                  "gradetype", "grademax", "grademin", "gradepass", "hidden"])
if gg is None or gi is None:
    raise SystemExit("HATA: anon_mdl_grade_grades / grade_items bulunamadi (DATA_DIR?).")

gg["userid"]     = num(gg["userid"]).astype("Int64")
gg["itemid"]     = num(gg["itemid"]).astype("Int64")
gg["finalgrade"] = num(gg["finalgrade"])
gg["hidden"]     = num(gg["hidden"]).fillna(0).astype(int)
gg["excluded"]   = num(gg["excluded"]).fillna(0).astype(int)
gg["timemodified"] = num(gg["timemodified"])

# Filtre: hesaplanabilir + gizli/haric degil + golden
gg = gg[
    gg["finalgrade"].notna() &
    (gg["hidden"] == 0) &
    (gg["excluded"] == 0) &
    gg["userid"].isin(golden_users)
].copy()
print(f"  grade_grades (filtreli, golden): {len(gg):,}")

gi["id"]        = num(gi["id"]).astype("Int64")
gi["courseid"]  = num(gi["courseid"]).astype("Int64")
gi["gradetype"] = num(gi["gradetype"]).fillna(0).astype(int)
gi["grademax"]  = num(gi["grademax"])
gi["grademin"]  = num(gi["grademin"]).fillna(0)
gi["gradepass"] = num(gi["gradepass"])
gi["hidden"]    = num(gi["hidden"]).fillna(0).astype(int)

# Filtre: sayisal (gradetype=1) + gizli degil
gi = gi[(gi["gradetype"] == 1) & (gi["hidden"] == 0)].copy()
print(f"  grade_items (gradetype=1, not-hidden): {len(gi):,}")

# 3. Join + normalize
print("\n[2/4] Birlestirme + normalize...")
df = gg.merge(
    gi[["id", "courseid", "itemname", "itemtype", "itemmodule", "grademax", "grademin", "gradepass"]],
    left_on="itemid", right_on="id", how="inner",
)
print(f"  Birlesmis kalem: {len(df):,}")

rng = (df["grademax"] - df["grademin"]).clip(lower=1)
df["norm_grade"] = (((df["finalgrade"] - df["grademin"]) / rng) * 100).clip(0, 100).round(1)

# 4. Gecti/gecmedi — gradepass>0 olan kalemlerde
print("[3/4] Gecti/gecmedi (gradepass) hesaplaniyor...")
has_thr = df["gradepass"].notna() & (df["gradepass"] > 0)
df["norm_gradepass"] = pd.NA
df.loc[has_thr, "norm_gradepass"] = (
    ((df.loc[has_thr, "gradepass"] - df.loc[has_thr, "grademin"]) / rng[has_thr]) * 100
).clip(0, 100).round(1)
df["norm_gradepass"] = num(df["norm_gradepass"])

df["passed"] = pd.NA
df.loc[has_thr, "passed"] = df.loc[has_thr, "norm_grade"] >= df.loc[has_thr, "norm_gradepass"]
df["passed"] = df["passed"].astype("boolean")

# 5. Etiket + kurs adi + tarih
print("[4/4] Etiket, kurs adi, tarih...")
df["item_label"] = [
    _item_label(n, t, m) for n, t, m in zip(df["itemname"], df["itemtype"], df["itemmodule"])
]
df = df.rename(columns={"itemtype": "item_type", "itemmodule": "item_module"})

course = load("course", usecols=["id", "fullname"])
if course is not None:
    course["id"] = num(course["id"]).astype("Int64")
    course["fullname"] = course["fullname"].fillna("").astype(str).str.strip()
    df = df.merge(course.rename(columns={"id": "courseid", "fullname": "course_fullname"}),
                  on="courseid", how="left")
else:
    df["course_fullname"] = ""

def _coursename(cid, name):
    n = str(name).strip()
    return n if n and n.lower() not in _PLACEHOLDER else f"Kurs {int(cid)}"
df["course_fullname"] = [_coursename(c, n) for c, n in zip(df["courseid"], df["course_fullname"])]

# graded_date: timemodified + 12y offset (diger dash tablolariyla tutarli)
tm = df["timemodified"]
ts = (tm.where(tm.notna() & (tm > 0)) + TIME_OFFSET_S)
graded = pd.to_datetime(ts, unit="s", utc=True, errors="coerce")
df["graded_date"] = graded.dt.strftime("%Y-%m-%d")
df["graded_date"] = df["graded_date"].where(df["graded_date"].notna(), None)

# 6. Cikti
df["grade"] = df["finalgrade"].round(2)
df["userid"] = df["userid"].astype(int)
df["courseid"] = df["courseid"].astype(int)
df["itemid"] = df["itemid"].astype(int)

cols = [
    "userid", "courseid", "course_fullname", "itemid", "item_label",
    "item_type", "item_module", "grade", "grademax", "grademin",
    "norm_grade", "gradepass", "norm_gradepass", "passed", "graded_date",
]
result = df[cols].sort_values(["userid", "courseid", "itemid"]).reset_index(drop=True)

print(f"\n  Toplam kalem: {len(result):,}")
print(f"  Kullanici: {result['userid'].nunique():,}  |  Kurs: {result['courseid'].nunique():,}")
print(f"  item_type dagilimi:\n{result['item_type'].value_counts().to_string()}")
n_thr = int(result['passed'].notna().sum())
n_pass = int((result['passed'] == True).sum())
print(f"  Esikli (gradepass>0) kalem: {n_thr:,}  |  passed=True: {n_pass:,}  passed=False: {n_thr - n_pass:,}")

kaydet(CIKTI_DIR, "dash_09_grade_items.csv", result)
print("\n=== TAMAMLANDI ===")

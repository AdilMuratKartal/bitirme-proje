# -*- coding: utf-8 -*-
"""DASHBOARD TABLO 7 — dash_07_upcoming_events

Kullanicinin tum gorunen modullerinden deadline (completionexpected) olan
etkinlikleri listeler. mdl_event tablosunun onon-hesaplanmis, per-user karsiligi.

Bagimliliklar:
  - cikti/dash_04_module_status.csv  (expected_date, is_visible, is_completed,
                                      module_type, display_name, userid, courseid, cmid)
  - cikti/config.json                (data_end_ts — zaman kaydirmali referans)

Cikti: cikti/dash_07_upcoming_events.csv
  userid | courseid | cmid | module_type | display_name
       | event_date | timestart | days_until | is_overdue | is_completed

Notlar:
  - event_date: completionexpected tarihi (zaman kaydirmali, 2026-2027 araliginda)
  - days_until: event_date - ref_date; negatif = gecmis deadline
  - is_overdue: deadline gecmis VE tamamlanmamis
  - Tum moduller dahil (sadece is_visible=True, expected_date IS NOT NULL)
  - Frontend istedigi araliga filtreleyebilir (orn: days_until BETWEEN -7 AND 30)
"""

import sys, os, json
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import load, num, TIME_OFFSET_S

MODULE_CSV  = os.path.join(os.path.dirname(__file__), "cikti/dash_04_module_status.csv")
CONFIG_JSON = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/config.json")
GOLDEN_CSV  = os.path.join(os.path.dirname(__file__), "../00_golden_users/cikti/golden_1000.csv")
CIKTI_DIR   = os.path.join(os.path.dirname(__file__), "cikti")

print("=== DASHBOARD 07: UPCOMING EVENTS ===\n")

# 1. Referans tarihi (zaman kaydirmali data_end_ts'den)
with open(CONFIG_JSON, encoding="utf-8") as f:
    data_end_ts = json.load(f)["data_end_ts"]

import datetime as dt
ref_date = dt.datetime.fromtimestamp(data_end_ts, tz=dt.timezone.utc).date()
print(f"  Referans tarihi (data_end_ts): {ref_date}")

# 2. Module status yukle
print("\n[1/3] Modul durumu yukleniyor...")
mod = pd.read_csv(MODULE_CSV, usecols=[
    "userid", "courseid", "cmid", "module_type", "display_name",
    "is_visible", "is_completed", "expected_date"
])
mod["userid"]       = mod["userid"].astype(int)
mod["courseid"]     = mod["courseid"].astype(int)
mod["cmid"]         = mod["cmid"].astype(int)
mod["is_visible"]   = mod["is_visible"].astype(bool)
mod["is_completed"] = mod["is_completed"].astype(bool)
mod["expected_date"] = pd.to_datetime(mod["expected_date"], errors="coerce")

print(f"  Toplam modul satiri: {len(mod):,}")

# 3. Filtre: gorunen + deadline olan moduller
events = mod[
    mod["is_visible"] &
    mod["expected_date"].notna()
].copy()
print(f"  Deadline olan gorunen modul: {len(events):,}")

# 4. Hesaplamalar
events["days_until"] = (
    pd.to_datetime(events["expected_date"]) - pd.Timestamp(ref_date)
).dt.days.astype(int)

events["is_overdue"] = (events["days_until"] < 0) & (~events["is_completed"])

# timestart: event_date → Unix timestamp (UTC gece yarisi)
events["timestart"] = (
    pd.to_datetime(events["expected_date"])
    .astype("int64") // 10**9
).astype(int)

# 5. Kurs adi ekle (opsiyonel zenginlestirme)
course = load("course", usecols=["id", "fullname", "shortname"])
if course is not None:
    course["id"] = num(course["id"]).astype(int)
    course["fullname"]  = course["fullname"].fillna("").str.strip()
    course["shortname"] = course["shortname"].fillna("").str.strip()
    events = events.merge(
        course.rename(columns={"id": "courseid", "fullname": "course_name",
                               "shortname": "course_short"}),
        on="courseid", how="left"
    )
    events["course_name"]  = events["course_name"].fillna("")
    events["course_short"] = events["course_short"].fillna("")
else:
    events["course_name"]  = ""
    events["course_short"] = ""

# 6. Sirala: kullanici → deadline yakini once
events = events.sort_values(["userid", "days_until"])

cols = [
    "userid", "courseid", "cmid", "module_type", "display_name",
    "course_name", "course_short",
    "event_date", "timestart", "days_until", "is_overdue", "is_completed"
]
# event_date sutununu string'e cevir (CSV uyumlulugu)
events["event_date"] = events["expected_date"].dt.strftime("%Y-%m-%d")
events = events[cols]

# Ozet istatistikler
n_overdue   = events[events["is_overdue"]].shape[0]
n_upcoming  = events[events["days_until"] >= 0].shape[0]
n_completed = events[events["is_completed"]].shape[0]

print(f"\n  Toplam event satiri   : {len(events):,}")
print(f"  Gecmis deadline (tamamlanmamis): {n_overdue:,}")
print(f"  Yaklasan (days_until >= 0)     : {n_upcoming:,}")
print(f"  Tamamlanmis           : {n_completed:,}")
print(f"  Kullanici sayisi       : {events['userid'].nunique():,}")

if len(events):
    earliest = events["event_date"].min()
    latest   = events["event_date"].max()
    print(f"  Tarih araligi         : {earliest} → {latest}")

from common import kaydet
kaydet(CIKTI_DIR, "dash_07_upcoming_events.csv", events)
print("\n=== TAMAMLANDI ===")

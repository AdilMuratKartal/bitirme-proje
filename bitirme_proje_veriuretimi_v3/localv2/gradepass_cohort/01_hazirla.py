# -*- coding: utf-8 -*-
"""Kesin Esikli Kohort — Hazirlik + Oznitelik Cikarma

Kohort kriteri:
  - finalgrade IS NOT NULL          (gercek not var)
  - gradepass > 0                   (ogretmen esigi belirlenmis)
  - grademax > 0                    (gecerli maksimum)
  - grademin IS NOT NULL
  - grade_grades.hidden = 0
  - grade_items.hidden = 0
  - itemtype = 'course'

Etiket: finalgrade >= gradepass -> 1 (Gecti), < gradepass -> 0 (Kaldi)
Normalize gerekmez: ikisi de ayni Moodle skalasinda.

Cikti: cikti/01_cohort_dataset.csv
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from common import (load, num, kaydet, rapor, yuzde,
                    MONTHLY_LOG_FILES, DATA_DIR, TS_LO, NOW)

import pandas as pd
import numpy as np

CIKTI_DIR = os.path.join(os.path.dirname(__file__), "cikti")
FILTERED_CSV = os.path.join(
    os.path.dirname(__file__), "..", "pipeline",
    "01_student_filter", "cikti", "01_filtered_students.csv"
)
CHUNK_SIZE = 500_000

print("=== GRADEPASS COHORT: 01_hazirla.py ===\n")

# --------------------------------------------------------------------------- #
# 1. Filtreli ogrenci listesi (student_filter degistirilmez)
# --------------------------------------------------------------------------- #
print("[1/7] Filtreli ogrenci listesi yukleniyor...")
if not os.path.exists(FILTERED_CSV):
    raise SystemExit(
        f"HATA: 01_filtered_students.csv bulunamadi.\n"
        f"  Beklenen: {FILTERED_CSV}\n"
        f"  Once pipeline/01_student_filter/filter_students.py calistirin."
    )
fs = pd.read_csv(FILTERED_CSV)
fs["userid"]   = num(fs["userid"]).astype("Int64")
fs["courseid"] = num(fs["courseid"]).astype("Int64")
filtered_users   = set(fs["userid"].dropna().astype(int))
filtered_courses = set(fs["courseid"].dropna().astype(int))
valid_pairs      = set(zip(fs["userid"].dropna().astype(int),
                           fs["courseid"].dropna().astype(int)))
print(f"  {len(filtered_users):,} kullanici  |  {len(filtered_courses):,} kurs")

# --------------------------------------------------------------------------- #
# 2. grade_items — sadece itemtype='course', gradepass>0, grademax>0
# --------------------------------------------------------------------------- #
print("\n[2/7] grade_items yukleniyor...")
_gi_base = ["id", "courseid", "itemtype", "grademax", "grademin", "gradepass", "hidden"]
try:
    gi = load("grade_items", usecols=_gi_base + ["gradetype", "needsupdate"])
    _gi_quality_cols = True
except Exception:
    gi = load("grade_items", usecols=_gi_base)
    _gi_quality_cols = False
    print("  NOT: gradetype/needsupdate kolonlari CSV'de yok, kontrol atlanidi.")
if gi is None:
    raise SystemExit("HATA: anon_mdl_grade_items.csv bulunamadi.")

gi["id"]       = num(gi["id"]).astype("Int64")
gi["courseid"] = num(gi["courseid"]).astype("Int64")
gi["grademax"] = num(gi["grademax"])
gi["grademin"] = num(gi["grademin"])
gi["gradepass"] = num(gi["gradepass"])
gi["hidden"]   = num(gi["hidden"]).fillna(0).astype(int)

gi_raw = len(gi)
# itemtype = 'course' (kurs seviyesi notu)
gi = gi[gi["itemtype"] == "course"].copy()
print(f"  itemtype=course: {len(gi):,}  (ham: {gi_raw:,})")

# Kohort filtreleme
gi = gi[
    (gi["hidden"] == 0) &
    (gi["gradepass"].notna()) & (gi["gradepass"] > 0) &
    (gi["grademax"].notna())  & (gi["grademax"] > 0) &
    (gi["grademin"].notna())
].copy()
print(f"  gradepass>0 + grademax>0 + not-hidden: {len(gi):,} item")

# Sadece filtreli kurslardaki item'lar
gi = gi[gi["courseid"].isin(filtered_courses)].copy()
print(f"  Filtreli kurslarla kesisim: {len(gi):,} item")

# Kontrol: gradetype = 1 (sayisal) — 0=None, 3=Text sayisal islenemez
if _gi_quality_cols and "gradetype" in gi.columns:
    gi["gradetype"] = num(gi["gradetype"]).fillna(1).astype(int)
    _n_nongr = (gi["gradetype"] != 1).sum()
    if _n_nongr:
        print(f"  KONTROL gradetype: {_n_nongr} sayisal-olmayan item cikarildi (gradetype!=1)")
    gi = gi[gi["gradetype"] == 1].copy()
    print(f"  gradetype=1 (sayisal): {len(gi):,} item")

# Kontrol: needsupdate = 0 — 1 ise cron bekleniyor, finalgrade guncel degil
if _gi_quality_cols and "needsupdate" in gi.columns:
    gi["needsupdate"] = num(gi["needsupdate"]).fillna(0).astype(int)
    _n_stale = (gi["needsupdate"] != 0).sum()
    if _n_stale:
        print(f"  KONTROL needsupdate: {_n_stale} item cikarildi (cron bekliyor, not guncel degil)")
    gi = gi[gi["needsupdate"] == 0].copy()
    print(f"  needsupdate=0: {len(gi):,} item")

valid_itemids = set(gi["id"].dropna().astype(int))

# --------------------------------------------------------------------------- #
# 2b. Kayit Kontrolu (mdl_enrol + mdl_user_enrolments)                      #
# --------------------------------------------------------------------------- #
print("\n[2b] Kayit kontrolu (mdl_enrol + mdl_user_enrolments)...")
_enrol_ok_pairs = None  # None => tablo yok, kontrol raporda uyari olarak gosterilir

_enrol_tbl  = load("enrol",            usecols=["id", "courseid", "status"])
_uenrol_tbl = load("user_enrolments",  usecols=["enrolid", "userid", "status", "timeend"])

if _enrol_tbl is not None and _uenrol_tbl is not None:
    _enrol_tbl["id"]       = num(_enrol_tbl["id"]).astype("Int64")
    _enrol_tbl["courseid"] = num(_enrol_tbl["courseid"]).astype("Int64")
    _enrol_tbl["status"]   = num(_enrol_tbl["status"]).fillna(0).astype(int)

    _uenrol_tbl["enrolid"]  = num(_uenrol_tbl["enrolid"]).astype("Int64")
    _uenrol_tbl["userid"]   = num(_uenrol_tbl["userid"]).astype("Int64")
    _uenrol_tbl["status"]   = num(_uenrol_tbl["status"]).fillna(0).astype(int)
    _uenrol_tbl["timeend"]  = num(_uenrol_tbl["timeend"]).fillna(0).astype("int64")

    # mdl_enrol.status = 0 → aktif kayit yontemi
    _valid_enrolids = set(
        _enrol_tbl[_enrol_tbl["status"] == 0]["id"].dropna().astype(int)
    )
    # mdl_user_enrolments: enrolid gecerli + status=0 + timeend=0 veya >NOW
    _ue = _uenrol_tbl[
        _uenrol_tbl["enrolid"].isin(_valid_enrolids) &
        (_uenrol_tbl["status"] == 0) &
        ((_uenrol_tbl["timeend"] == 0) | (_uenrol_tbl["timeend"] > int(NOW)))
    ].copy()
    _ue = _ue.merge(
        _enrol_tbl[["id", "courseid"]].rename(columns={"id": "enrolid"}),
        on="enrolid", how="left"
    ).dropna(subset=["userid", "courseid"])
    _ue["userid"]   = _ue["userid"].astype(int)
    _ue["courseid"] = _ue["courseid"].astype(int)
    _enrol_ok_pairs = set(zip(_ue["userid"], _ue["courseid"]))
    print(f"  Aktif kayitli (userid,courseid): {len(_enrol_ok_pairs):,} cift")
else:
    print("  UYARI: mdl_enrol / mdl_user_enrolments CSV'de bulunamadi, kayit kontrolu atlanidi.")

# --------------------------------------------------------------------------- #
# 2c. Not Kategorisi Kontrolu (mdl_grade_categories)                         #
# --------------------------------------------------------------------------- #
print("\n[2c] Not kategorisi kontrolu (mdl_grade_categories)...")
_gc_tbl = load("grade_categories", usecols=["id", "courseid", "depth", "aggregation"])
_gc_ok_courses = set()

if _gc_tbl is not None:
    _gc_tbl["courseid"]    = num(_gc_tbl["courseid"]).astype("Int64")
    _gc_tbl["depth"]       = num(_gc_tbl["depth"]).fillna(0).astype(int)
    _gc_tbl["aggregation"] = num(_gc_tbl["aggregation"])

    # Kok kategori: depth=1 ve aggregation NOT NULL (hesaplama yontemi tanimli)
    _gc_root = _gc_tbl[
        (_gc_tbl["depth"] == 1) & (_gc_tbl["aggregation"].notna())
    ].copy()
    _gc_ok_courses = set(_gc_root["courseid"].dropna().astype(int))

    _n_total_gc = _gc_tbl["courseid"].nunique()
    print(f"  Kok not kategorisi (depth=1 + aggregation): {len(_gc_ok_courses)}/{_n_total_gc} kurs")

    _missing_gc = filtered_courses - _gc_ok_courses
    if _missing_gc:
        print(f"  UYARI: {len(_missing_gc)} filtreli kursta kok kategori eksik: "
              f"{sorted(_missing_gc)[:5]}{'...' if len(_missing_gc) > 5 else ''}")
    else:
        print(f"  Tum filtreli kurslar icin kok kategori mevcut.")
else:
    print("  UYARI: mdl_grade_categories CSV'de bulunamadi, kategori kontrolu atlanidi.")

# --------------------------------------------------------------------------- #
# 3. grade_grades — finalgrade NOT NULL, gizli degil
# --------------------------------------------------------------------------- #
print("\n[3/7] grade_grades yukleniyor...")
gg = load("grade_grades",
          usecols=["itemid", "userid", "finalgrade", "hidden"])
if gg is None:
    raise SystemExit("HATA: anon_mdl_grade_grades.csv bulunamadi.")

gg["itemid"]     = num(gg["itemid"]).astype("Int64")
gg["userid"]     = num(gg["userid"]).astype("Int64")
gg["finalgrade"] = num(gg["finalgrade"])
gg["hidden"]     = num(gg["hidden"]).fillna(0).astype(int)

gg_raw = len(gg)
gg = gg[
    (gg["hidden"] == 0) &
    (gg["finalgrade"].notna()) &
    (gg["itemid"].isin(valid_itemids)) &
    (gg["userid"].isin(filtered_users))
].copy()
print(f"  Filtreden gelen: {len(gg):,}  (ham: {gg_raw:,})")

# --------------------------------------------------------------------------- #
# 4. JOIN: grade_grades + grade_items
# --------------------------------------------------------------------------- #
print("\n[4/7] JOIN yapiliyor...")
cohort = gg.merge(
    gi[["id", "courseid", "grademax", "grademin", "gradepass"]].rename(
        columns={"id": "itemid"}
    ),
    on="itemid", how="inner"
)
print(f"  JOIN sonrasi: {len(cohort):,} satir")

# (userid, courseid) geçerli cift filtresi
pair_mask = pd.Series(
    list(zip(cohort["userid"].astype(int), cohort["courseid"].astype(int)))
).isin(valid_pairs).values
cohort = cohort[pair_mask].copy()
print(f"  Gecerli (userid,courseid) cifti: {len(cohort):,} satir")

# Bir (userid, courseid) icin birden fazla course-level item varsa en yuksek finalgrade'i al
cohort["userid"]   = cohort["userid"].astype(int)
cohort["courseid"] = cohort["courseid"].astype(int)
n_before_dedup = len(cohort)
cohort = (cohort.sort_values("finalgrade", ascending=False)
                .drop_duplicates(subset=["userid", "courseid"], keep="first")
                .reset_index(drop=True))
if n_before_dedup != len(cohort):
    print(f"  Duplicate (userid,courseid) temizlendi: "
          f"{n_before_dedup - len(cohort):,} satir kaldirildi")

# Kayit kontrolu raporu (enrol tablolari varsa)
if _enrol_ok_pairs is not None:
    _cohort_pairs = set(zip(cohort["userid"].astype(int), cohort["courseid"].astype(int)))
    _n_enrol_ok  = sum(1 for p in _cohort_pairs if p in _enrol_ok_pairs)
    _n_enrol_bad = len(_cohort_pairs) - _n_enrol_ok
    if _n_enrol_bad:
        print(f"  KONTROL kayit: {_n_enrol_bad} cohort cifti aktif kayit bulunamadi "
              f"(mdl_user_enrolments'ta eksik veya suresi dolmus)")
    print(f"  Kayit kontrolu: {_n_enrol_ok}/{len(_cohort_pairs)} aktif kayitli")

# --------------------------------------------------------------------------- #
# 5. Etiket + Not oznitelikleri
# --------------------------------------------------------------------------- #
print(f"\n[5/7] Etiket + not oznitelikleri hesaplaniyor...")

cohort["label"] = (cohort["finalgrade"] >= cohort["gradepass"]).astype(int)

# Normalize edilmis not: (finalgrade - grademin) / (grademax - grademin)
denom = cohort["grademax"] - cohort["grademin"]
denom = denom.replace(0, np.nan)  # grademax == grademin durumu
cohort["norm_pct"] = ((cohort["finalgrade"] - cohort["grademin"]) / denom).round(4)

# grade_margin: pozitif -> gecti, negatif -> kaldi
cohort["grade_margin"] = (cohort["finalgrade"] - cohort["gradepass"]).round(4)
cohort["grade_margin_pct"] = (cohort["grade_margin"] / denom).round(4)

n1 = (cohort["label"] == 1).sum()
n0 = (cohort["label"] == 0).sum()
print(f"  label=1 (Gecti): {n1:,}  (%{yuzde(n1, len(cohort)):.1f})")
print(f"  label=0 (Kaldi): {n0:,}  (%{yuzde(n0, len(cohort)):.1f})")

cohort_users   = set(cohort["userid"].astype(int))
cohort_courses = set(cohort["courseid"].astype(int))

# --------------------------------------------------------------------------- #
# 6. Log oznitelikleri (12 aylik CSV)
# --------------------------------------------------------------------------- #
print("\n[6/7] Log oznitelikleri hesaplaniyor...")

LOG_COLS = ["time", "userid", "course", "module", "cmid", "action"]

def _load_log_chunk(fpath, u_set, c_set, chunk_size=CHUNK_SIZE):
    parts = []
    for chunk in pd.read_csv(
        fpath, sep=",", low_memory=False, encoding="utf-8-sig",
        encoding_errors="replace", on_bad_lines="skip",
        usecols=LOG_COLS, chunksize=chunk_size
    ):
        chunk.columns = [str(c).strip().lower() for c in chunk.columns]
        if "course" in chunk.columns and "courseid" not in chunk.columns:
            chunk = chunk.rename(columns={"course": "courseid"})
        chunk["userid"]   = num(chunk["userid"]).astype("Int64")
        chunk["courseid"] = num(chunk["courseid"]).astype("Int64")
        chunk["time"]     = num(chunk["time"])
        chunk = chunk[chunk["userid"].isin(u_set) & chunk["courseid"].isin(c_set)]
        if len(chunk):
            parts.append(chunk[["userid", "courseid", "time", "module", "action"]].copy())
    return parts

all_log_parts = []
for fpath in MONTHLY_LOG_FILES:
    month = os.path.basename(fpath).replace("anon_", "").replace(".csv", "")
    print(f"  {month:12s} ...", end=" ", flush=True)
    parts = _load_log_chunk(fpath, cohort_users, cohort_courses)
    n = sum(len(p) for p in parts)
    all_log_parts.extend(parts)
    print(f"{n:,} satir")

# anon_mdl_log.csv (eger varsa)
full_log_path = os.path.join(DATA_DIR, "anon_mdl_log.csv")
if os.path.exists(full_log_path):
    print(f"  anon_mdl_log.csv ...", end=" ", flush=True)
    parts = _load_log_chunk(full_log_path, cohort_users, cohort_courses)
    n = sum(len(p) for p in parts)
    all_log_parts.extend(parts)
    print(f"{n:,} satir")

# Ek log feature map'leri — log yoksa bos kalir, _get(default=0) ile 0 doner
forum_submit_map  = {}
forum_view_map    = {}
modul_cesit_map   = {}
resource_view_map = {}
quiz_act_map      = {}
night_ratio_map   = {}
weekend_ratio_map = {}
n_sessions_map    = {}
cps_map           = {}
max_hissiz_map    = {}

log_summary = None
if all_log_parts:
    log_df = pd.concat(all_log_parts, ignore_index=True)
    # Timestamp gecerlilik
    ts_mask = (log_df["time"] >= TS_LO) & (log_df["time"] <= NOW)
    log_df = log_df[ts_mask].copy()
    # Duplicate temizle
    log_df = log_df.drop_duplicates(
        subset=["userid", "courseid", "time", "action"]
    )
    log_df["userid"]   = log_df["userid"].astype(int)
    log_df["courseid"] = log_df["courseid"].astype(int)
    log_df["time"]     = log_df["time"].astype("Int64")

    print(f"  Temiz log: {len(log_df):,} satir  |  "
          f"{log_df['userid'].nunique():,} kullanici  |  "
          f"{log_df['courseid'].nunique():,} kurs")

    grp = log_df.groupby(["userid", "courseid"])
    log_summary = pd.DataFrame({
        "n_log"      : grp["time"].count(),
        "ilk_log"    : grp["time"].min(),
        "son_log"    : grp["time"].max(),
        "n_aktif_gun": grp["time"].apply(
                          lambda x: x.map(lambda t: int(t) // 86400).nunique()),#öğrenci toplam kaç gün logu var
        "n_view"     : grp["action"].apply(
                          lambda x: x.str.contains("view", case=False, na=False).sum()),
        "n_pure_log" : grp.apply(
                          lambda g: (~((g["module"] == "resource") &
                                      g["action"].str.contains("view", case=False, na=False))
                                    ).sum(), include_groups=False),
        "n_perf_log" : grp.apply(
                          lambda g: g["module"].isin(
                              ["assign", "quiz", "workshop", "lesson"]).sum(),
                          include_groups=False),
    }).reset_index()

    log_summary["aktif_sure_gun"] = (
        (log_summary["son_log"] - log_summary["ilk_log"]) / 86400
    ).round(2)
    log_summary["log_per_gun"] = (
        log_summary["n_log"] / log_summary["n_aktif_gun"].replace(0, np.nan)
    ).round(4)

    log_summary["userid"]   = log_summary["userid"].astype(int)
    log_summary["courseid"] = log_summary["courseid"].astype(int)

    # ----------------------------------------------------------------------- #
    # BLOK 1: Gelismis log oznitelikleri
    # ----------------------------------------------------------------------- #
    print("  [Blok1] Gelismis log oznitelikleri hesaplaniyor...")

    # Forum katilimi
    forum_submit_map = (
        log_df[(log_df["module"] == "forum") &
               (log_df["action"].str.contains(
                   "post|reply|add|submit", case=False, na=False))]
        .groupby(["userid", "courseid"]).size().to_dict()
    )
    forum_view_map = (
        log_df[(log_df["module"] == "forum") &
               (log_df["action"].str.contains("view", case=False, na=False))]
        .groupby(["userid", "courseid"]).size().to_dict()
    )

    # Modul cesitliligi
    modul_cesit_map = (
        log_df.groupby(["userid", "courseid"])["module"].nunique().to_dict()
    )

    # Resource / Quiz ham etkileşim sayilari (oran hesabi icin)
    resource_view_map = (
        log_df[(log_df["module"] == "resource") &
               (log_df["action"].str.contains("view", case=False, na=False))]
        .groupby(["userid", "courseid"]).size().to_dict()
    )
    quiz_act_map = (
        log_df[log_df["module"] == "quiz"]
        .groupby(["userid", "courseid"]).size().to_dict()
    )

    # Gece (22:00-23:59 ve 00:00-05:59) ve hafta sonu orani
    # epoch % 86400 // 3600 -> UTC saat; (epoch // 86400 + 4) % 7 -> weekday (0=Pzt)
    _hour    = (log_df["time"].astype("int64") % 86400 // 3600)
    _weekday = (log_df["time"].astype("int64") // 86400 + 4) % 7
    night_mask   = (_hour >= 22) | (_hour <= 5)
    weekend_mask = _weekday.isin([5, 6])

    _den = log_df.groupby(["userid", "courseid"]).size()
    night_ratio_map = (
        (log_df[night_mask].groupby(["userid", "courseid"]).size() / _den)
        .fillna(0).round(4).to_dict()
    )
    weekend_ratio_map = (
        (log_df[weekend_mask].groupby(["userid", "courseid"]).size() / _den)
        .fillna(0).round(4).to_dict()
    )

    # Oturum sayisi + oturum basina tiklanma (30-dk kesme: 1800 sn)
    log_sorted = log_df.sort_values(["userid", "courseid", "time"])

    def _session_stats(g):
        times = g["time"].values.astype("int64")
        if len(times) == 0:
            return pd.Series({"n_sessions": 0, "clicks_per_session": 0.0})
        n_ses = int(1 + (np.diff(times) > 1800).sum())
        return pd.Series({"n_sessions": n_ses,
                          "clicks_per_session": round(len(times) / n_ses, 4)})

    session_df = (log_sorted.groupby(["userid", "courseid"])
                  .apply(_session_stats, include_groups=False)
                  .reset_index())
    session_df["userid"]   = session_df["userid"].astype(int)
    session_df["courseid"] = session_df["courseid"].astype(int)
    n_sessions_map = session_df.set_index(["userid", "courseid"])["n_sessions"].to_dict()
    cps_map        = session_df.set_index(["userid", "courseid"])["clicks_per_session"].to_dict()

    # En uzun erişimsizlik suresi (gun — en guclu dropout gostergesi)
    def _max_hissizlik(g):
        days = sorted(set(int(t) // 86400 for t in g["time"].values.astype("int64")))
        if len(days) < 2:
            return 0
        return int(max(np.diff(days)))

    max_hissiz_map = (log_sorted.groupby(["userid", "courseid"])
                     .apply(_max_hissizlik, include_groups=False)
                     .to_dict())

    print(f"  [Blok1] Tamamlandi: "
          f"forum={len(forum_submit_map)} | "
          f"modul_cesit={len(modul_cesit_map)} | "
          f"session={len(n_sessions_map)}")

else:
    print("  UYARI: Hic log satiri yuklenemedi; log oznitelikleri 0 olacak.")

# --------------------------------------------------------------------------- #
# Teslim + Quiz
# --------------------------------------------------------------------------- #
# assign_submission -> n_teslim
assign_sub = load("assign_submission", usecols=["assignment", "userid", "status"])
assign_tbl = load("assign", usecols=["id", "course"])

n_teslim_map = {}
if assign_sub is not None and assign_tbl is not None:
    assign_sub["userid"]     = num(assign_sub["userid"]).astype("Int64")
    assign_sub["assignment"] = num(assign_sub["assignment"]).astype("Int64")
    assign_tbl["id"]         = num(assign_tbl["id"]).astype("Int64")
    assign_tbl["course"]     = num(assign_tbl["course"]).astype("Int64")

    valid_status = ["submitted", "new", "reopened"]
    if "status" in assign_sub.columns:
        asub = assign_sub[assign_sub["status"].isin(valid_status)].copy()
    else:
        asub = assign_sub.copy()

    asub = asub.merge(
        assign_tbl.rename(columns={"id": "assignment", "course": "courseid"}),
        on="assignment", how="left"
    )
    asub = asub.dropna(subset=["userid", "courseid"])
    asub["userid"]   = asub["userid"].astype(int)
    asub["courseid"] = asub["courseid"].astype(int)
    # Sadece cohort kullanicilari
    asub = asub[asub["userid"].isin(cohort_users) & asub["courseid"].isin(cohort_courses)]
    n_teslim_map = asub.groupby(["userid", "courseid"]).size().to_dict()
    print(f"  assign_submission: {len(asub):,} gecerli teslim")
else:
    print("  UYARI: assign tablolari bulunamadi, n_teslim=0.")

# quiz_attempts -> n_quiz_deneme
quiz_att = load("quiz_attempts", usecols=["quiz", "userid", "timefinish"])
quiz_tbl = load("quiz", usecols=["id", "course"])

n_quiz_map = {}
if quiz_att is not None and quiz_tbl is not None:
    quiz_att["userid"]     = num(quiz_att["userid"]).astype("Int64")
    quiz_att["quiz"]       = num(quiz_att["quiz"]).astype("Int64")
    quiz_att["timefinish"] = num(quiz_att["timefinish"])
    quiz_tbl["id"]         = num(quiz_tbl["id"]).astype("Int64")
    quiz_tbl["course"]     = num(quiz_tbl["course"]).astype("Int64")

    qatt = quiz_att[quiz_att["timefinish"] > 0].copy()
    qatt = qatt.merge(
        quiz_tbl.rename(columns={"id": "quiz", "course": "courseid"}),
        on="quiz", how="left"
    )
    qatt = qatt.dropna(subset=["userid", "courseid"])
    qatt["userid"]   = qatt["userid"].astype(int)
    qatt["courseid"] = qatt["courseid"].astype(int)
    qatt = qatt[qatt["userid"].isin(cohort_users) & qatt["courseid"].isin(cohort_courses)]
    n_quiz_map = qatt.groupby(["userid", "courseid"]).size().to_dict()
    print(f"  quiz_attempts (tamamlanan): {len(qatt):,} deneme")
else:
    print("  UYARI: quiz tablolari bulunamadi, n_quiz_deneme=0.")

# --------------------------------------------------------------------------- #
# 7. Ozellikleri birlestir + imputation
# --------------------------------------------------------------------------- #
print("\n[7/7] Oznitelik matrisi olusturuluyor...")

df = cohort[["userid", "courseid", "label",
             "finalgrade", "gradepass", "grademax", "grademin",
             "norm_pct", "grade_margin", "grade_margin_pct"]].copy()

# Log ozeti
if log_summary is not None:
    df = df.merge(
        log_summary[["userid", "courseid", "n_log", "n_aktif_gun",
                     "log_per_gun", "aktif_sure_gun", "n_view",
                     "n_pure_log", "n_perf_log"]],
        on=["userid", "courseid"], how="left"
    )
else:
    for c in ["n_log", "n_aktif_gun", "log_per_gun", "aktif_sure_gun",
              "n_view", "n_pure_log", "n_perf_log"]:
        df[c] = 0

# log sayilari -> fillna(0)
log_count_cols = ["n_log", "n_aktif_gun", "n_view", "n_pure_log",
                  "n_perf_log", "aktif_sure_gun", "log_per_gun"]
for c in log_count_cols:
    if c in df.columns:
        df[c] = df[c].fillna(0)

# n_teslim, n_quiz_deneme
df["n_teslim"] = df.apply(
    lambda r: n_teslim_map.get((int(r["userid"]), int(r["courseid"])), 0), axis=1
)
df["n_quiz_deneme"] = df.apply(
    lambda r: n_quiz_map.get((int(r["userid"]), int(r["courseid"])), 0), axis=1
)

# performans_skoru
df["performans_skoru"] = (df["n_teslim"] * 2.0 + df["n_quiz_deneme"] * 1.5).round(4)

# MNAR bayraklari
df["log_var"]    = (df["n_log"] > 0).astype(int)
df["teslim_var"] = (df["n_teslim"] > 0).astype(int)

# ----------------------------------------------------------------------- #
# BLOK 2: Gelismis oznitelikler
# ----------------------------------------------------------------------- #
def _get(mapping, uid, cid, default=0):
    return mapping.get((int(uid), int(cid)), default)

# Forum + Modul
df["forum_submit"]    = df.apply(lambda r: _get(forum_submit_map,  r.userid, r.courseid), axis=1)
df["forum_view"]      = df.apply(lambda r: _get(forum_view_map,    r.userid, r.courseid), axis=1)
df["n_modul_cesit"]   = df.apply(lambda r: _get(modul_cesit_map,   r.userid, r.courseid), axis=1)
df["resource_view"]   = df.apply(lambda r: _get(resource_view_map, r.userid, r.courseid), axis=1)
df["quiz_act"]        = df.apply(lambda r: _get(quiz_act_map,      r.userid, r.courseid), axis=1)

# Temporal / Session
df["night_ratio"]        = df.apply(lambda r: _get(night_ratio_map,   r.userid, r.courseid, 0.0), axis=1)
df["weekend_ratio"]      = df.apply(lambda r: _get(weekend_ratio_map, r.userid, r.courseid, 0.0), axis=1)
df["n_sessions"]         = df.apply(lambda r: _get(n_sessions_map,    r.userid, r.courseid), axis=1)
df["clicks_per_session"] = df.apply(lambda r: _get(cps_map,           r.userid, r.courseid, 0.0), axis=1)
df["max_hissizlik"]      = df.apply(lambda r: _get(max_hissiz_map,    r.userid, r.courseid), axis=1)

# Hamle A: log1p donusumleri (saga carpik count verisi)
for _col in ["n_log", "n_aktif_gun", "n_view", "n_perf_log", "n_teslim", "n_quiz_deneme"]:
    df[f"{_col}_log1p"] = np.log1p(df[_col])

# Hamle B: Kurs bazli z-score (38 farkli kurs -> kurs-bagimsiz model)
_eps = 1e-5
for _col in ["n_log", "n_aktif_gun", "n_perf_log", "aktif_sure_gun"]:
    df[f"{_col}_course_z"] = df.groupby("courseid")[_col].transform(
        lambda x: (x - x.mean()) / (x.std() + _eps)
    ).round(4)

# Hamle C: Oran oznitelikleri (nitelik / nicelik sinyali)
_denom = df["n_log"] + _eps
df["perf_ratio"]        = (df["n_perf_log"]    / _denom).round(4)
df["view_ratio"]        = (df["n_view"]         / _denom).round(4)
df["resource_view_pct"] = (df["resource_view"]  / _denom).round(4)
df["quiz_act_pct"]      = (df["quiz_act"]       / _denom).round(4)
df["teslim_per_gun"]    = (df["n_teslim"] / (df["n_aktif_gun"] + _eps)).round(4)

# Hamle D: Kurs icinde percentile rank (dagilim-bagimsiz, carpik count verileri icin z-score'dan guclu)
_pctile_cols = ["n_log", "n_aktif_gun", "n_sessions", "n_perf_log", "n_modul_cesit"]
for _col in _pctile_cols:
    df[f"{_col}_pctile"] = df.groupby("courseid")[_col].rank(pct=True).round(4)

# Kurs tier: ekstrem (0%/100% gecme) vs anlamli vs kucuk
_ks = df.groupby("courseid").agg(
    _n=("userid", "nunique"), _p=("label", "mean")).reset_index()

def _kurs_tier(row):
    p, n = row["_p"], row["_n"]
    if p <= 0.05 or p >= 0.95: return 0  # ekstrem
    if n >= 50 and 0.10 < p < 0.90: return 1  # anlamli buyuk
    if n >= 10: return 2  # anlamli kucuk
    return 3  # cok kucuk

_ks["kurs_tier"] = _ks.apply(_kurs_tier, axis=1)
df = df.merge(_ks[["courseid", "kurs_tier"]], on="courseid", how="left")
df["kurs_tier"] = df["kurs_tier"].fillna(3).astype(int)

# z-score NaN temizle (tek elemanli kurslar std=NaN -> 0)
_z_cols = [c for c in df.columns if c.endswith("_course_z")]
df[_z_cols] = df[_z_cols].fillna(0.0)

# Dogrulama
assert df["finalgrade"].isna().sum() == 0, "finalgrade NULL var!"
assert (df["gradepass"] > 0).all(), "gradepass=0 var!"
assert (df["grademax"] > 0).all(), "grademax=0 var!"

feature_cols = [
    # Temel log
    "n_log", "n_aktif_gun", "log_per_gun", "aktif_sure_gun",
    "n_view", "n_pure_log", "n_perf_log",
    # Teslim / quiz
    "n_teslim", "n_quiz_deneme", "performans_skoru",
    # MNAR bayraklari
    "log_var", "teslim_var",
    # Not (EDA only - ML leakage!)
    "norm_pct", "grade_margin", "grade_margin_pct",
    # Forum + Modul cesitliligi
    "forum_submit", "forum_view", "n_modul_cesit",
    "resource_view", "quiz_act",
    # Temporal / Session
    "night_ratio", "weekend_ratio",
    "n_sessions", "clicks_per_session", "max_hissizlik",
    # log1p donusumleri (Hamle A)
    "n_log_log1p", "n_aktif_gun_log1p", "n_view_log1p",
    "n_perf_log_log1p", "n_teslim_log1p", "n_quiz_deneme_log1p",
    # Kurs z-score (Hamle B)
    "n_log_course_z", "n_aktif_gun_course_z",
    "n_perf_log_course_z", "aktif_sure_gun_course_z",
    # Oranlar (Hamle C)
    "perf_ratio", "view_ratio", "resource_view_pct",
    "quiz_act_pct", "teslim_per_gun",
    # Kurs icinde percentile rank (Hamle D)
    "n_log_pctile", "n_aktif_gun_pctile", "n_sessions_pctile",
    "n_perf_log_pctile", "n_modul_cesit_pctile",
    # Kurs tipi
    "kurs_tier",
]
remaining_nan = df[feature_cols].isnull().sum()
if remaining_nan.sum() > 0:
    print("  Kalan NaN -> 0 ile dolduruluyor:")
    for c, n in remaining_nan[remaining_nan > 0].items():
        print(f"    {c}: {n}")
    df[feature_cols] = df[feature_cols].fillna(0)

assert df[feature_cols].isnull().sum().sum() == 0, "Hala NaN var!"

# --------------------------------------------------------------------------- #
# Kaydet + Rapor
# --------------------------------------------------------------------------- #
kaydet(CIKTI_DIR, "01_cohort_dataset.csv", df)

n_total = len(df)
n1 = (df["label"] == 1).sum()
n0 = (df["label"] == 0).sum()
n_kurs = df["courseid"].nunique()
n_user = df["userid"].nunique()

lines = [
    "=== GRADEPASS COHORT: HAZIRLIK RAPORU ===",
    "",
    "--- Kohort Kriteri ---",
    "  itemtype = 'course'",
    "  finalgrade IS NOT NULL",
    "  gradepass > 0   (ogretmen esigi)",
    "  grademax > 0",
    "  grademin NOT NULL",
    "  grade_grades.hidden = 0",
    "  grade_items.hidden = 0",
    "  gradetype = 1   (sayisal) [kolon varsa]",
    "  needsupdate = 0 (guncel)  [kolon varsa]",
    "",
    "--- Moodle Veri Butunlugu Kontrolleri ---",
    f"  gradetype / needsupdate : {'uygulanmadi (CSV kolonlari eksik)' if not _gi_quality_cols else 'uygulandi'}",
    f"  Kayit kontrolu (enrol)  : {'atlanmadi — ' + str(len(_enrol_ok_pairs) if _enrol_ok_pairs is not None else 0) + ' aktif kayit cifti' if _enrol_ok_pairs is not None else 'atlanmadi (tablo yok)'}",
    f"  Grade categories        : {str(len(_gc_ok_courses)) + ' kurs icin kok kategori mevcut' if _gc_tbl is not None else 'atlanmadi (tablo yok)'}",
    "",
    "--- Kohort Boyutu ---",
    f"  Toplam (userid,courseid) cifti : {n_total:,}",
    f"  Benzersiz kullanici            : {n_user:,}",
    f"  Benzersiz kurs                 : {n_kurs:,}",
    "",
    "--- Sinif Dagilimi ---",
    f"  label=1 (Gecti): {n1:,}  (%{yuzde(n1, n_total):.1f})",
    f"  label=0 (Kaldi): {n0:,}  (%{yuzde(n0, n_total):.1f})",
    "",
    "--- Not Istatistikleri ---",
    f"  finalgrade  ort={df['finalgrade'].mean():.2f}  std={df['finalgrade'].std():.2f}",
    f"  gradepass   ort={df['gradepass'].mean():.2f}  std={df['gradepass'].std():.2f}",
    f"  norm_pct    ort={df['norm_pct'].mean():.3f}  std={df['norm_pct'].std():.3f}",
    f"  grade_margin ort={df['grade_margin'].mean():.2f}  std={df['grade_margin'].std():.2f}",
    "",
    "--- Log Oznitelikleri ---",
    f"  log_var=1 (logu olan): {df['log_var'].sum():,}  (%{yuzde(df['log_var'].sum(), n_total):.1f})",
    f"  n_log       ort={df['n_log'].mean():.1f}  medyan={df['n_log'].median():.0f}",
    f"  n_aktif_gun ort={df['n_aktif_gun'].mean():.1f}",
    f"  n_perf_log  ort={df['n_perf_log'].mean():.1f}",
    "",
    "--- Teslim + Quiz ---",
    f"  teslim_var=1: {df['teslim_var'].sum():,}  (%{yuzde(df['teslim_var'].sum(), n_total):.1f})",
    f"  n_teslim      ort={df['n_teslim'].mean():.2f}",
    f"  n_quiz_deneme ort={df['n_quiz_deneme'].mean():.2f}",
    "",
    "--- Dogrulama ---",
    f"  finalgrade NULL sayisi : {df['finalgrade'].isna().sum()}  (beklenen: 0)",
    f"  gradepass <= 0 sayisi  : {(df['gradepass'] <= 0).sum()}  (beklenen: 0)",
    f"  grademax  <= 0 sayisi  : {(df['grademax'] <= 0).sum()}  (beklenen: 0)",
    f"  NaN feature sayisi     : {df[feature_cols].isnull().sum().sum()}  (beklenen: 0)",
    "",
    "--- Feature Listesi ---",
]
for c in feature_cols:
    lines.append(f"  {c:28s}: ort={df[c].mean():.4f}  std={df[c].std():.4f}")

rapor(CIKTI_DIR, "01_cohort_rapor.txt", lines)
print("\n=== TAMAMLANDI ===")
print(f"\n>>> HAZIR: {os.path.join(CIKTI_DIR, '01_cohort_dataset.csv')}")

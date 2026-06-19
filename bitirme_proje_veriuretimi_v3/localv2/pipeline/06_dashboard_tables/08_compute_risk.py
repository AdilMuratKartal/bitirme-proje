# -*- coding: utf-8 -*-
"""[08] compute_risk.py — Golden kullanicilar icin dash_risk + dash_features uretimi

Mimari: dash-only. Risk OFFLINE hesaplanir; canli API yalnizca dash_risk'i OKUR.

Akis:
  1. Golden (userid, courseid) ciftleri  -> dash_03_course_progress.csv
  2. Model girdisi feature'lari (saved_models/student_success_meta.json'daki liste)
     loglardan + assign/quiz tablolarindan hesaplanir.  (01_hazirla.py ile AYNI formuller)
  3. Egitilmis model (saved_models/student_success_model.pkl) -> (user,course) pass_probability
  4. Kullanici bazinda topla (kurslar uzerinden ortalama) -> dash_08_risk.csv
  5. Feature denetim tablosu -> dash_09_features.csv

NOT (domain-shift kaydi): model NOTU KESINLESMIS (bitmis) kurslarla egitildi; golden
kullanicilar cogunlukla devam eden ogrenciler. Bu yuzden tahmin "mevcut davranis surerse
gecer/kalir" seklinde bir ERKEN-UYARI'dir. course_z/pctile normalizasyonlari golden
populasyonu uzerinden hesaplanir (egitimdeki cohort populasyonundan farkli).
"""
import sys, os, json, pickle, datetime as _dt

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(THIS_DIR, "..", "..", "pipeline"))  # common
from common import load, num, kaydet, MONTHLY_LOG_FILES, DATA_DIR, TS_LO, NOW

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Yollar                                                                       #
# --------------------------------------------------------------------------- #
CIKTI_DIR  = os.path.join(THIS_DIR, "cikti")
DASH03_CSV = os.path.join(CIKTI_DIR, "dash_03_course_progress.csv")

SAVED_DIR  = os.path.join(THIS_DIR, "..", "..", "saved_models")
MODEL_PKL  = os.path.join(SAVED_DIR, "student_success_model.pkl")
META_JSON  = os.path.join(SAVED_DIR, "student_success_meta.json")

CHUNK_SIZE = 500_000
_EPS = 1e-5
# Ham mdl_log kolon sirasi (basliksiz dosyalar icin) — common.py docstring'i ile ayni
RAW_LOG_COLS = ["id", "time", "userid", "ip", "course", "module", "cmid", "action", "url", "info"]
USE_COLS     = ["time", "userid", "course", "module", "action"]


def _has_header(fpath) -> bool:
    """Ilk satirda 'userid'/'time' gibi metin kolon adi varsa basliklidir."""
    with open(fpath, "r", encoding="utf-8-sig", errors="replace") as f:
        first = f.readline().strip().lower()
    return ("userid" in first) or ("time" in first and "userid" in first)

# risk_level esikleri (frontend tonlamasiyla uyumlu: Dusuk=green, Orta=amber, Yuksek=red)
def _risk_level(risk_score: float) -> str:
    if risk_score < 40:  return "Düşük"
    if risk_score <= 70: return "Orta"
    return "Yüksek"


# --------------------------------------------------------------------------- #
# 1. Model + feature listesi                                                   #
# --------------------------------------------------------------------------- #
def _load_model():
    if not os.path.exists(MODEL_PKL):
        raise SystemExit(f"HATA: {MODEL_PKL} yok. Once student_success modelini egitin.")
    with open(MODEL_PKL, "rb") as f:
        saved = pickle.load(f)
    best = saved["best_name"]
    model = saved["trained"][best]
    feats = saved["features"]          # egitimdeki kesin sira
    return model, best, feats


# --------------------------------------------------------------------------- #
# 2. Log feature'lari (01_hazirla.py BLOK1 ile ayni)                          #
# --------------------------------------------------------------------------- #
def _load_logs(u_set, c_set):
    parts = []
    paths = list(MONTHLY_LOG_FILES)
    full_log = os.path.join(DATA_DIR, "anon_mdl_log.csv")
    if os.path.exists(full_log):
        paths.append(full_log)
    for fpath in paths:
        headered = _has_header(fpath)
        read_kw = dict(sep=",", low_memory=False, encoding="utf-8-sig",
                       encoding_errors="replace", on_bad_lines="skip",
                       chunksize=CHUNK_SIZE)
        if headered:
            read_kw["usecols"] = USE_COLS
        else:
            # Basliksiz ham dosya: tum kolon adlarini ver, gerekenleri sec
            read_kw["header"] = None
            read_kw["names"]  = RAW_LOG_COLS
            read_kw["usecols"] = USE_COLS
        for chunk in pd.read_csv(fpath, **read_kw):
            chunk.columns = [str(c).strip().lower() for c in chunk.columns]
            if "course" in chunk.columns and "courseid" not in chunk.columns:
                chunk = chunk.rename(columns={"course": "courseid"})
            chunk["userid"]   = num(chunk["userid"]).astype("Int64")
            chunk["courseid"] = num(chunk["courseid"]).astype("Int64")
            chunk["time"]     = num(chunk["time"])
            chunk = chunk[chunk["userid"].isin(u_set) & chunk["courseid"].isin(c_set)]
            if len(chunk):
                parts.append(chunk[["userid", "courseid", "time", "module", "action"]].copy())
    if not parts:
        return None
    log_df = pd.concat(parts, ignore_index=True)
    ts_mask = (log_df["time"] >= TS_LO) & (log_df["time"] <= NOW)
    log_df = log_df[ts_mask].drop_duplicates(subset=["userid", "courseid", "time", "action"])
    log_df["userid"]   = log_df["userid"].astype(int)
    log_df["courseid"] = log_df["courseid"].astype(int)
    log_df["time"]     = log_df["time"].astype("int64")
    return log_df


def _compute_log_features(log_df):
    grp = log_df.groupby(["userid", "courseid"])
    feat = pd.DataFrame({
        "n_log":       grp["time"].count(),
        "ilk_log":     grp["time"].min(),
        "son_log":     grp["time"].max(),
        "n_aktif_gun": grp["time"].apply(lambda x: x.map(lambda t: int(t) // 86400).nunique()),
        "n_perf_log":  grp.apply(
            lambda g: g["module"].isin(["assign", "quiz", "workshop", "lesson"]).sum(),
            include_groups=False),
        "resource_view": grp.apply(
            lambda g: ((g["module"] == "resource") &
                       g["action"].str.contains("view", case=False, na=False)).sum(),
            include_groups=False),
        "n_modul_cesit": grp["module"].nunique(),
    }).reset_index()

    feat["aktif_sure_gun"] = ((feat["son_log"] - feat["ilk_log"]) / 86400).round(2)
    feat["log_per_gun"] = (feat["n_log"] / feat["n_aktif_gun"].replace(0, np.nan)).round(4)

    # weekend_ratio  ((epoch//86400 + 4) % 7 -> weekday, 5/6 = haftasonu)
    _weekday = (log_df["time"] // 86400 + 4) % 7
    _den = log_df.groupby(["userid", "courseid"]).size()
    weekend = (log_df[_weekday.isin([5, 6])].groupby(["userid", "courseid"]).size() / _den).fillna(0).round(4)
    feat = feat.merge(weekend.rename("weekend_ratio").reset_index(), on=["userid", "courseid"], how="left")

    # n_sessions (30-dk = 1800 sn kesme) + max_hissizlik (gun)
    log_sorted = log_df.sort_values(["userid", "courseid", "time"])

    def _sessions(g):
        t = g["time"].values
        return int(1 + (np.diff(t) > 1800).sum()) if len(t) else 0

    def _max_hissizlik(g):
        days = sorted(set(int(t) // 86400 for t in g["time"].values))
        return int(max(np.diff(days))) if len(days) >= 2 else 0

    ses = log_sorted.groupby(["userid", "courseid"]).apply(_sessions, include_groups=False)
    hiss = log_sorted.groupby(["userid", "courseid"]).apply(_max_hissizlik, include_groups=False)
    feat = feat.merge(ses.rename("n_sessions").reset_index(), on=["userid", "courseid"], how="left")
    feat = feat.merge(hiss.rename("max_hissizlik").reset_index(), on=["userid", "courseid"], how="left")
    return feat


# --------------------------------------------------------------------------- #
# 3. Teslim + Quiz -> performans_skoru (01_hazirla.py ile ayni)               #
# --------------------------------------------------------------------------- #
def _perf_maps(u_set, c_set):
    n_teslim_map, n_quiz_map = {}, {}

    asub = load("assign_submission", usecols=["assignment", "userid", "status"])
    atbl = load("assign", usecols=["id", "course"])
    if asub is not None and atbl is not None:
        asub["userid"]     = num(asub["userid"]).astype("Int64")
        asub["assignment"] = num(asub["assignment"]).astype("Int64")
        atbl["id"]         = num(atbl["id"]).astype("Int64")
        atbl["course"]     = num(atbl["course"]).astype("Int64")
        if "status" in asub.columns:
            asub = asub[asub["status"].isin(["submitted", "new", "reopened"])].copy()
        asub = asub.merge(atbl.rename(columns={"id": "assignment", "course": "courseid"}),
                          on="assignment", how="left").dropna(subset=["userid", "courseid"])
        asub["userid"] = asub["userid"].astype(int); asub["courseid"] = asub["courseid"].astype(int)
        asub = asub[asub["userid"].isin(u_set) & asub["courseid"].isin(c_set)]
        n_teslim_map = asub.groupby(["userid", "courseid"]).size().to_dict()

    qatt = load("quiz_attempts", usecols=["quiz", "userid", "timefinish"])
    qtbl = load("quiz", usecols=["id", "course"])
    if qatt is not None and qtbl is not None:
        qatt["userid"]     = num(qatt["userid"]).astype("Int64")
        qatt["quiz"]       = num(qatt["quiz"]).astype("Int64")
        qatt["timefinish"] = num(qatt["timefinish"])
        qtbl["id"]         = num(qtbl["id"]).astype("Int64")
        qtbl["course"]     = num(qtbl["course"]).astype("Int64")
        qatt = qatt[qatt["timefinish"] > 0].merge(
            qtbl.rename(columns={"id": "quiz", "course": "courseid"}),
            on="quiz", how="left").dropna(subset=["userid", "courseid"])
        qatt["userid"] = qatt["userid"].astype(int); qatt["courseid"] = qatt["courseid"].astype(int)
        qatt = qatt[qatt["userid"].isin(u_set) & qatt["courseid"].isin(c_set)]
        n_quiz_map = qatt.groupby(["userid", "courseid"]).size().to_dict()

    return n_teslim_map, n_quiz_map


# --------------------------------------------------------------------------- #
# Ana akis                                                                     #
# --------------------------------------------------------------------------- #
def main():
    print("=== [08] compute_risk: dash_risk + dash_features ===\n")
    model, best_name, FEATURES = _load_model()
    print(f"Model: {best_name}  |  {len(FEATURES)} feature")

    if not os.path.exists(DASH03_CSV):
        raise SystemExit(f"HATA: {DASH03_CSV} yok. Once 03_compute_course_progress.py calistirin.")
    prog = pd.read_csv(DASH03_CSV)[["userid", "courseid"]].dropna()
    prog["userid"] = prog["userid"].astype(int); prog["courseid"] = prog["courseid"].astype(int)
    pairs = prog.drop_duplicates().reset_index(drop=True)
    u_set, c_set = set(pairs["userid"]), set(pairs["courseid"])
    print(f"Golden ciftleri: {len(pairs):,}  |  {len(u_set):,} kullanici  |  {len(c_set):,} kurs")

    # --- feature iskeleti (tum ciftler) ---
    df = pairs.copy()

    print("\n[1] Log feature'lari hesaplaniyor...")
    log_df = _load_logs(u_set, c_set)
    if log_df is not None:
        print(f"  Temiz log: {len(log_df):,} satir")
        logf = _compute_log_features(log_df)
        df = df.merge(logf, on=["userid", "courseid"], how="left")
    else:
        print("  UYARI: log yuklenemedi; log feature'lari 0.")

    print("[2] Teslim + Quiz (performans_skoru)...")
    n_teslim_map, n_quiz_map = _perf_maps(u_set, c_set)
    df["n_teslim"]      = [n_teslim_map.get((u, c), 0) for u, c in zip(df.userid, df.courseid)]
    df["n_quiz_deneme"] = [n_quiz_map.get((u, c), 0) for u, c in zip(df.userid, df.courseid)]

    # --- ham sayilari 0'la doldur ---
    base_cols = ["n_log", "n_aktif_gun", "aktif_sure_gun", "log_per_gun", "n_perf_log",
                 "resource_view", "n_modul_cesit", "weekend_ratio", "n_sessions", "max_hissizlik"]
    for c in base_cols:
        if c not in df.columns:
            df[c] = 0
        df[c] = df[c].fillna(0)

    print("[3] Turetilmis + normalize feature'lar...")
    # performans_skoru
    df["performans_skoru"] = (df["n_teslim"] * 2.0 + df["n_quiz_deneme"] * 1.5).round(4)
    # oranlar
    _denom = df["n_log"] + _EPS
    df["perf_ratio"]        = (df["n_perf_log"]   / _denom).round(4)
    df["resource_view_pct"] = (df["resource_view"] / _denom).round(4)
    # log1p
    df["n_aktif_gun_log1p"] = np.log1p(df["n_aktif_gun"])
    # kurs bazli z-score
    for col in ["n_log", "n_perf_log", "aktif_sure_gun"]:
        df[f"{col}_course_z"] = df.groupby("courseid")[col].transform(
            lambda x: (x - x.mean()) / (x.std() + _EPS)).round(4)
    # kurs ici percentile
    df["n_modul_cesit_pctile"] = df.groupby("courseid")["n_modul_cesit"].rank(pct=True).round(4)

    # z-score NaN (tek elemanli kurs) -> 0
    z_cols = [c for c in df.columns if c.endswith("_course_z")]
    df[z_cols] = df[z_cols].fillna(0.0)

    # eksik feature kolonu varsa 0
    for f in FEATURES:
        if f not in df.columns:
            print(f"  [UYARI] feature uretilemedi, 0 atandi: {f}")
            df[f] = 0.0
    df[FEATURES] = df[FEATURES].fillna(0.0)

    print("[4] Model tahmini (pass_probability)...")
    X = df[FEATURES].astype(float)
    df["pass_prob"] = model.predict_proba(X)[:, 1]

    print("[5] Kullanici bazinda toplama -> dash_risk...")
    agg = df.groupby("userid")["pass_prob"].mean().reset_index()
    agg["pass_probability"] = agg["pass_prob"].round(4)
    agg["risk_score"]       = ((1.0 - agg["pass_prob"]) * 100).round(1)
    agg["risk_level"]       = agg["risk_score"].map(_risk_level)
    agg["will_pass"]        = (agg["pass_prob"] >= 0.5).astype(int)
    agg["predicted_grade"]  = np.nan          # siniflandirici — not tahmini yok
    agg["computed_at"]      = _dt.datetime.now(_dt.timezone.utc).isoformat()
    risk_out = agg[["userid", "risk_score", "risk_level", "predicted_grade",
                    "pass_probability", "will_pass", "computed_at"]].rename(
                    columns={"userid": "user_id"})

    kaydet(CIKTI_DIR, "dash_08_risk.csv", risk_out)

    # feature denetim tablosu
    feat_out = df[["userid", "courseid"] + FEATURES + ["pass_prob"]].copy()
    kaydet(CIKTI_DIR, "dash_09_features.csv", feat_out)

    # --- ozet ---
    print("\n--- OZET ---")
    print(f"  dash_08_risk.csv     : {len(risk_out):,} kullanici")
    print(f"  dash_09_features.csv : {len(feat_out):,} (user,course)")
    print(f"  risk_level dagilimi  : {risk_out['risk_level'].value_counts().to_dict()}")
    print(f"  will_pass=1 orani    : %{100*risk_out['will_pass'].mean():.1f}")
    print(f"  risk_score ort/min/max: {risk_out['risk_score'].mean():.1f} / "
          f"{risk_out['risk_score'].min():.1f} / {risk_out['risk_score'].max():.1f}")
    print("\n=== TAMAMLANDI ===")


if __name__ == "__main__":
    main()

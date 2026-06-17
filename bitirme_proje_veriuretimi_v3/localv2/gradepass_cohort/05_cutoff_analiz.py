# -*- coding: utf-8 -*-
"""Cutoff Hafta Analizi — Erken uyari sistemi ne kadar guc?

Fikir: Tam kurs verisi yerine yalnizca ilk W haftalik logu kullanarak
tahmin yapabilir miyiz? W = 2, 4, 6, 8, 10, 12, 16 hafta.

Cutoff anchor: course.startdate + W * 604800
  Fallback: her kursta gordugun minimum log zamanstampi + W * 604800

Feature'lar W haftaya kadar olan logdan yeniden hesaplanir.
Zaman-bagimsiz: kurs_tier eklenir.

Degerlendirme: 5-fold stratified CV (train/test split her W icin tutarli)

Girdi : cikti/01_cohort_dataset.csv
        anon_mdl_course.csv  (startdate icin)
        log-olarak-aylar/anon_*.csv  (ham log)
Cikti : cikti/05_auc_vs_haftalar.png
        cikti/05_feature_onem_by_week.png
        cikti/05_sample_coverage.png
        cikti/05_cutoff_rapor.txt
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from common import load, num, rapor, MONTHLY_LOG_FILES, DATA_DIR, TS_LO, NOW

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import roc_auc_score
import xgboost as xgb

CIKTI_DIR  = os.path.join(os.path.dirname(__file__), "cikti")
DATASET    = os.path.join(CIKTI_DIR, "01_cohort_dataset.csv")
CHUNK_SIZE = 500_000
LOG_COLS   = ["time", "userid", "course", "module", "action"]

CUTOFF_WEEKS = [2, 4, 6, 8, 10, 12, 16]
W_SECS       = 7 * 24 * 3600  # 604800 saniye = 1 hafta

print("=== CUTOFF HAFTA ANALIZI ===\n")

XGB = dict(
    n_estimators=200, max_depth=4, learning_rate=0.08,
    subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
    random_state=42, verbosity=0,
)

# ---------------------------------------------------------------------------
# 1. Cohort yükle
# ---------------------------------------------------------------------------
df_cohort = pd.read_csv(DATASET)
df_cohort["userid"]   = df_cohort["userid"].astype(int)
df_cohort["courseid"] = df_cohort["courseid"].astype(int)

cohort_users   = set(df_cohort["userid"])
cohort_courses = set(df_cohort["courseid"])
print(f"Cohort: {len(df_cohort):,} satir  |  {len(cohort_users)} kullanici  |  {len(cohort_courses)} kurs")

# ---------------------------------------------------------------------------
# 2. Course startdate
# ---------------------------------------------------------------------------
print("\nCourse startdate yukleniyor...")
course_tbl = load("course", usecols=["id", "startdate"])
startdate_map = {}
if course_tbl is not None:
    course_tbl["id"]        = num(course_tbl["id"]).astype("Int64")
    course_tbl["startdate"] = num(course_tbl["startdate"]).fillna(0).astype("int64")
    for _, row in course_tbl.iterrows():
        cid = int(row["id"])
        sd  = int(row["startdate"])
        if cid in cohort_courses and sd > TS_LO:
            startdate_map[cid] = sd
    print(f"  startdate bulunan kurs: {len(startdate_map)}/{len(cohort_courses)}")
else:
    print("  UYARI: anon_mdl_course.csv bulunamadi. Fallback: min log zamanstampi kullanilacak.")

# ---------------------------------------------------------------------------
# 3. Log verisi (bir kere yükle)
# ---------------------------------------------------------------------------
print("\nLog verisi yukleniyor (bir kez)...")

def _load_logs(fpath, u_set, c_set):
    parts = []
    for chunk in pd.read_csv(
        fpath, sep=",", low_memory=False, encoding="utf-8-sig",
        encoding_errors="replace", on_bad_lines="skip",
        usecols=LOG_COLS, chunksize=CHUNK_SIZE
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

all_parts = []
for fpath in MONTHLY_LOG_FILES:
    month = os.path.basename(fpath).replace("anon_", "").replace(".csv", "")
    print(f"  {month:12s}...", end=" ", flush=True)
    parts = _load_logs(fpath, cohort_users, cohort_courses)
    n = sum(len(p) for p in parts)
    all_parts.extend(parts)
    print(f"{n:,}")

full_log = os.path.join(DATA_DIR, "anon_mdl_log.csv")
if os.path.exists(full_log):
    print(f"  anon_mdl_log.csv ...", end=" ", flush=True)
    parts = _load_logs(full_log, cohort_users, cohort_courses)
    n = sum(len(p) for p in parts)
    all_parts.extend(parts)
    print(f"{n:,}")

if not all_parts:
    raise SystemExit("HATA: Hic log yuklenemedi.")

log_df = pd.concat(all_parts, ignore_index=True)
ts_mask = (log_df["time"] >= TS_LO) & (log_df["time"] <= NOW)
log_df  = log_df[ts_mask].drop_duplicates(
    subset=["userid", "courseid", "time", "action"]
).copy()
log_df["userid"]   = log_df["userid"].astype(int)
log_df["courseid"] = log_df["courseid"].astype(int)
log_df["time"]     = log_df["time"].astype("int64")

print(f"\nTemiz log: {len(log_df):,} satir")

# Fallback startdate: kurs bazinda minimum log zamani
course_min_time = log_df.groupby("courseid")["time"].min().to_dict()
for cid in cohort_courses:
    if cid not in startdate_map:
        if cid in course_min_time:
            startdate_map[cid] = int(course_min_time[cid])
        else:
            startdate_map[cid] = int(TS_LO)

print(f"Cutoff anchor hazir: {len(startdate_map)} kurs\n")

# ---------------------------------------------------------------------------
# 4. Feature hesaplama fonksiyonu (kesilmis log'dan)
# ---------------------------------------------------------------------------
_eps = 1e-5


def compute_features_from_log(log_slice: pd.DataFrame,
                               cohort_df: pd.DataFrame) -> pd.DataFrame:
    """
    log_slice : cutoff'a kadar olan loglar (userid, courseid, time, module, action)
    cohort_df : tam cohort (userid, courseid, label, kurs_tier)
    Döndürür  : cohort_df ile merge edilmiş feature DataFrame
    """
    if log_slice.empty:
        # Tum ozellikler 0 donecek
        out = cohort_df[["userid", "courseid", "label", "kurs_tier"]].copy()
        for c in ["n_log", "n_aktif_gun", "aktif_sure_gun", "log_per_gun",
                  "n_view", "n_pure_log", "n_perf_log",
                  "log_var", "night_ratio", "weekend_ratio",
                  "n_sessions", "clicks_per_session", "max_hissizlik",
                  "n_modul_cesit", "forum_view", "resource_view", "quiz_act",
                  "n_aktif_gun_pctile", "n_log_pctile"]:
            out[c] = 0
        return out

    grp = log_slice.groupby(["userid", "courseid"])

    # Temel sayimlar
    summary = pd.DataFrame({
        "n_log"      : grp["time"].count(),
        "ilk_log"    : grp["time"].min(),
        "son_log"    : grp["time"].max(),
        "n_aktif_gun": grp["time"].apply(
            lambda x: x.map(lambda t: int(t) // 86400).nunique()),
        "n_view"     : grp["action"].apply(
            lambda x: x.str.contains("view", case=False, na=False).sum()),
        "n_pure_log" : grp.apply(
            lambda g: (~((g["module"] == "resource") &
                         g["action"].str.contains("view", case=False, na=False))).sum(),
            include_groups=False),
        "n_perf_log" : grp.apply(
            lambda g: g["module"].isin(
                ["assign", "quiz", "workshop", "lesson"]).sum(),
            include_groups=False),
    }).reset_index()

    summary["aktif_sure_gun"] = (
        (summary["son_log"] - summary["ilk_log"]) / 86400
    ).round(2)
    summary["log_per_gun"] = (
        summary["n_log"] / summary["n_aktif_gun"].replace(0, np.nan)
    ).round(4).fillna(0)
    summary["log_var"] = (summary["n_log"] > 0).astype(int)

    # Temporal oranlar
    _hour    = (log_slice["time"] % 86400 // 3600)
    _weekday = (log_slice["time"] // 86400 + 4) % 7
    night_m  = (_hour >= 22) | (_hour <= 5)
    wknd_m   = _weekday.isin([5, 6])

    _den = log_slice.groupby(["userid", "courseid"]).size()
    night_r = (log_slice[night_m].groupby(
        ["userid", "courseid"]).size() / _den).fillna(0).rename("night_ratio")
    wknd_r  = (log_slice[wknd_m].groupby(
        ["userid", "courseid"]).size() / _den).fillna(0).rename("weekend_ratio")

    # Oturum istatistikleri
    log_sorted = log_slice.sort_values(["userid", "courseid", "time"])

    def _sess(g):
        t = g["time"].values.astype("int64")
        if len(t) == 0:
            return pd.Series({"n_sessions": 0, "cps": 0.0})
        ns = int(1 + (np.diff(t) > 1800).sum())
        return pd.Series({"n_sessions": ns, "cps": round(len(t) / ns, 4)})

    sess_df = (log_sorted.groupby(["userid", "courseid"])
               .apply(_sess, include_groups=False).reset_index())

    # Max hissizlik
    def _maxhiz(g):
        days = sorted(set(int(t) // 86400 for t in g["time"].values.astype("int64")))
        return int(max(np.diff(days))) if len(days) >= 2 else 0

    hiz_s = (log_sorted.groupby(["userid", "courseid"])
             .apply(_maxhiz, include_groups=False).rename("max_hissizlik"))

    # Forum + modül
    forum_v = (log_slice[(log_slice["module"] == "forum") &
                          log_slice["action"].str.contains("view", case=False, na=False)]
               .groupby(["userid", "courseid"]).size().rename("forum_view"))
    modul_c = log_slice.groupby(["userid", "courseid"])["module"].nunique().rename("n_modul_cesit")
    res_v   = (log_slice[(log_slice["module"] == "resource") &
                          log_slice["action"].str.contains("view", case=False, na=False)]
               .groupby(["userid", "courseid"]).size().rename("resource_view"))
    quiz_a  = (log_slice[log_slice["module"] == "quiz"]
               .groupby(["userid", "courseid"]).size().rename("quiz_act"))

    # Birleştir
    feat = (summary
            .join(night_r,  on=["userid", "courseid"])
            .join(wknd_r,   on=["userid", "courseid"])
            .join(sess_df.set_index(["userid", "courseid"])["n_sessions"], on=["userid", "courseid"])
            .join(sess_df.set_index(["userid", "courseid"])["cps"].rename("clicks_per_session"), on=["userid", "courseid"])
            .join(hiz_s,    on=["userid", "courseid"])
            .join(forum_v,  on=["userid", "courseid"])
            .join(modul_c,  on=["userid", "courseid"])
            .join(res_v,    on=["userid", "courseid"])
            .join(quiz_a,   on=["userid", "courseid"])
            )

    # Percentile (kurs içi rank)
    feat["n_aktif_gun_pctile"] = feat.groupby("courseid")["n_aktif_gun"].rank(pct=True).round(4)
    feat["n_log_pctile"]       = feat.groupby("courseid")["n_log"].rank(pct=True).round(4)

    feat["userid"]   = feat["userid"].astype(int)
    feat["courseid"] = feat["courseid"].astype(int)

    # Cohort ile birleştir (label + kurs_tier)
    merged = cohort_df[["userid", "courseid", "label", "kurs_tier"]].merge(
        feat.drop(columns=["ilk_log", "son_log"], errors="ignore"),
        on=["userid", "courseid"], how="left"
    )
    # Log olmayanlar için 0
    fill_cols = [c for c in merged.columns
                 if c not in ["userid", "courseid", "label", "kurs_tier"]]
    merged[fill_cols] = merged[fill_cols].fillna(0)

    return merged


# ---------------------------------------------------------------------------
# 5. Her cutoff W için hesapla + değerlendir
# ---------------------------------------------------------------------------
print("Cutoff analizi basliyor...")
print(f"Haftalar: {CUTOFF_WEEKS}\n")

cv5 = StratifiedKFold(5, shuffle=True, random_state=42)

cutoff_results = []  # {W, auc_global, auc_tier1, n_with_logs, n_total, feat_imp}

LEAKAGE_CUT = {"userid", "courseid", "label"}

for W in CUTOFF_WEEKS:
    print(f"[W={W:2d}] Cutoff filtre uygulanıyor...")

    # Cutoff timestamp'leri hesapla (kurs bazlı)
    cutoff_ts = {cid: startdate_map.get(cid, 0) + W * W_SECS
                 for cid in cohort_courses}

    # Log'u filtrele
    log_slice = log_df.copy()
    # Her (userid, courseid) için cutoff farklı → vectorize et
    cutoff_series = log_df["courseid"].map(cutoff_ts)
    log_slice     = log_df[log_df["time"] <= cutoff_series].copy()

    n_with_logs = log_slice.groupby(["userid", "courseid"]).ngroups
    print(f"  {n_with_logs}/{len(df_cohort)} (userid,courseid) log mevcut")

    # Feature hesapla
    feat_df = compute_features_from_log(log_slice, df_cohort)

    feat_cols = sorted([c for c in feat_df.columns if c not in LEAKAGE_CUT and c != "kurs_tier"])
    feat_cols = feat_cols + ["kurs_tier"]  # kurs_tier en sona

    X_cut = feat_df[feat_cols].fillna(0).astype(float)
    y_cut = feat_df["label"].astype(int)

    # Global CV AUC
    auc_global = np.nan
    if y_cut.nunique() > 1 and len(y_cut) >= 10:
        scores = cross_val_score(
            xgb.XGBClassifier(**XGB), X_cut, y_cut,
            cv=cv5, scoring="roc_auc", n_jobs=-1
        )
        auc_global = scores.mean()

    # Tier 1 Only CV AUC
    t1_mask  = feat_df["kurs_tier"] == 1
    X_t1 = X_cut[t1_mask]
    y_t1 = y_cut[t1_mask]
    auc_t1 = np.nan
    if y_t1.nunique() > 1 and len(y_t1) >= 20:
        scores_t1 = cross_val_score(
            xgb.XGBClassifier(**XGB), X_t1, y_t1,
            cv=cv5, scoring="roc_auc", n_jobs=-1
        )
        auc_t1 = scores_t1.mean()

    # Feature importance (XGBoost gain) — full dataset eğitimi
    fi = {}
    if y_cut.nunique() > 1:
        m = xgb.XGBClassifier(**XGB)
        m.fit(X_cut, y_cut)
        fi = m.get_booster().get_score(importance_type="gain")

    cutoff_results.append({
        "W": W,
        "auc_global": auc_global,
        "auc_tier1": auc_t1,
        "n_with_logs": n_with_logs,
        "n_total": len(df_cohort),
        "feat_imp": fi,
    })

    g_s = f"{auc_global:.4f}" if not np.isnan(auc_global) else "N/A"
    t1_s = f"{auc_t1:.4f}" if not np.isnan(auc_t1) else "N/A"
    print(f"  Global 5-CV AUC={g_s}  Tier1 5-CV AUC={t1_s}")

print("\nTum cutoff'lar tamamlandi.\n")

# ---------------------------------------------------------------------------
# 6. Referans: tam veri AUC
# ---------------------------------------------------------------------------
LEAKAGE_FULL = {
    "norm_pct", "grade_margin", "grade_margin_pct",
    "finalgrade", "gradepass", "grademax", "grademin",
    "userid", "courseid", "label",
}
full_feats = sorted([c for c in df_cohort.columns if c not in LEAKAGE_FULL])
X_full = df_cohort[full_feats].fillna(0).astype(float)
y_full = df_cohort["label"].astype(int)
full_auc = cross_val_score(
    xgb.XGBClassifier(**XGB), X_full, y_full,
    cv=cv5, scoring="roc_auc", n_jobs=-1
).mean()
t1_full_mask = df_cohort["kurs_tier"] == 1
full_t1_auc  = cross_val_score(
    xgb.XGBClassifier(**XGB),
    X_full[t1_full_mask], y_full[t1_full_mask],
    cv=cv5, scoring="roc_auc", n_jobs=-1
).mean()
print(f"Referans tam veri 5-CV AUC: Global={full_auc:.4f}  Tier1={full_t1_auc:.4f}")

# ---------------------------------------------------------------------------
# 7. Grafik — AUC eğrisi
# ---------------------------------------------------------------------------
print("\n[Grafik] AUC vs haftalar...")

weeks_  = [r["W"] for r in cutoff_results]
aucs_g  = [r["auc_global"] for r in cutoff_results]
aucs_t1 = [r["auc_tier1"] for r in cutoff_results]
coverages = [r["n_with_logs"] / r["n_total"] * 100 for r in cutoff_results]

fig, ax1 = plt.subplots(figsize=(11, 6))

ax1.plot(weeks_, aucs_g,  "o-", color="#2196F3", lw=2.5, markersize=8,
         label="5-CV AUC (Global)")
ax1.plot(weeks_, aucs_t1, "s-", color="#27ae60", lw=2.5, markersize=8,
         label="5-CV AUC (Tier 1)")
ax1.axhline(full_auc,    color="#2196F3", linestyle="--", linewidth=1.2, alpha=0.6,
            label=f"Tam veri AUC Global={full_auc:.3f}")
ax1.axhline(full_t1_auc, color="#27ae60", linestyle="--", linewidth=1.2, alpha=0.6,
            label=f"Tam veri AUC Tier1={full_t1_auc:.3f}")
ax1.axhline(0.7, color="gray", linestyle=":", linewidth=1, alpha=0.5, label="AUC=0.70 esigi")
ax1.axhline(0.8, color="gray", linestyle=":",  linewidth=1, alpha=0.5)

ax1.set_xlabel("Cutoff Haftasi (kurs baslangicından itibaren)", fontsize=12)
ax1.set_ylabel("5-Fold CV AUC", fontsize=12)
ax1.set_xticks(weeks_)
ax1.set_ylim(0.45, 1.02)
ax1.legend(loc="lower right", fontsize=10)
ax1.set_title("Cutoff Hafta Analizi — Erken Uyarı Performansı\n"
              "(x=W haftanın logu, y=AUC, kesikli=tam veri referansı)", fontsize=12)

# Annotation: AUC değerleri
for w, ag, at in zip(weeks_, aucs_g, aucs_t1):
    if not np.isnan(ag):
        ax1.annotate(f"{ag:.3f}", xy=(w, ag), xytext=(w, ag + 0.025),
                     ha="center", fontsize=8, color="#2196F3")
    if not np.isnan(at):
        ax1.annotate(f"{at:.3f}", xy=(w, at), xytext=(w, at - 0.038),
                     ha="center", fontsize=8, color="#27ae60")

plt.tight_layout()
plt.savefig(os.path.join(CIKTI_DIR, "05_auc_vs_haftalar.png"), dpi=150)
plt.close()
print("  05_auc_vs_haftalar.png")

# ---------------------------------------------------------------------------
# 8. Grafik — Coverage
# ---------------------------------------------------------------------------
print("[Grafik] Sample coverage...")

fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(weeks_, coverages, color="#FF9800", alpha=0.85, width=1.5)
for w, c in zip(weeks_, coverages):
    ax.text(w, c + 0.5, f"%{c:.0f}", ha="center", fontsize=9)
ax.set_xlabel("Cutoff Haftası")
ax.set_ylabel("Log kaydı olan öğrenci oranı (%)")
ax.set_xticks(weeks_)
ax.set_ylim(0, 110)
ax.set_title("Coverage: Her Haftada Logu Olan (userid,courseid) Oranı")
plt.tight_layout()
plt.savefig(os.path.join(CIKTI_DIR, "05_sample_coverage.png"), dpi=150)
plt.close()
print("  05_sample_coverage.png")

# ---------------------------------------------------------------------------
# 9. Grafik — Feature importance by week (top 10 heatmap)
# ---------------------------------------------------------------------------
print("[Grafik] Feature importance by week...")

all_feats_union = set()
for r in cutoff_results:
    all_feats_union.update(r["feat_imp"].keys())
all_feats_list = sorted(all_feats_union)

fi_matrix = pd.DataFrame(index=CUTOFF_WEEKS, columns=all_feats_list, dtype=float)
for r in cutoff_results:
    for f, v in r["feat_imp"].items():
        fi_matrix.loc[r["W"], f] = v
fi_matrix = fi_matrix.fillna(0)

# Her hafta için normalize et (sum=1)
fi_norm = fi_matrix.div(fi_matrix.sum(axis=1) + 1e-9, axis=0)

# Top 12 feature (ortalama önem)
top12 = fi_norm.mean(axis=0).nlargest(12).index.tolist()
fi_plot = fi_norm[top12]

fig, ax = plt.subplots(figsize=(13, 6))
sns.heatmap(fi_plot, annot=True, fmt=".2f", cmap="YlOrRd",
            ax=ax, linewidths=0.5, cbar_kws={"label": "Normalize Gain (%)"},
            yticklabels=[f"W={w}" for w in CUTOFF_WEEKS])
ax.set_title("Feature Importance (Norm. Gain) — Haftaya Göre Değişim\n(Değer yükseldikçe o hafta için daha önemli)")
ax.set_xlabel("Feature")
plt.tight_layout()
plt.savefig(os.path.join(CIKTI_DIR, "05_feature_onem_by_week.png"), dpi=150)
plt.close()
print("  05_feature_onem_by_week.png")

# ---------------------------------------------------------------------------
# 10. Rapor
# ---------------------------------------------------------------------------
print("\n[Rapor] yaziliyor...")

# AUC eşik haftaları bul
def find_threshold_week(aucs, weeks, threshold):
    for w, a in zip(weeks, aucs):
        if not np.isnan(a) and a >= threshold:
            return w
    return None

t70_g  = find_threshold_week(aucs_g,  weeks_, 0.70)
t80_g  = find_threshold_week(aucs_g,  weeks_, 0.80)
t70_t1 = find_threshold_week(aucs_t1, weeks_, 0.70)
t80_t1 = find_threshold_week(aucs_t1, weeks_, 0.80)

lines = [
    "=== CUTOFF HAFTA ANALIZI RAPORU ===",
    "",
    "--- SORU ---",
    "  Model 'erken uyari sistemi' olarak kullanilabilir mi?",
    "  Yalnizca ilk W haftanin logu ile AUC ne kadar?",
    "",
    "--- YONTEM ---",
    "  Cutoff anchor : course.startdate + W * 604800 saniye",
    f"  Fallback      : kurs bazinda min log zamani + W hafta",
    f"  Cutoff haftalar: {CUTOFF_WEEKS}",
    "  Degerlendirme : Stratified 5-Fold CV (XGBoost)",
    "",
    "--- REFERANS (TAM VERİ) ---",
    f"  Global 5-CV AUC : {full_auc:.4f}",
    f"  Tier1  5-CV AUC : {full_t1_auc:.4f}",
    "",
    "--- CUTOFF HAFTA SONUCLARI ---",
    f"  {'Hafta':>5}  {'Global AUC':>10}  {'Tier1 AUC':>10}  {'Coverage':>9}  {'Global/Tam':>10}",
]

for r, cov in zip(cutoff_results, coverages):
    W  = r["W"]
    ag = r["auc_global"]
    at = r["auc_tier1"]
    ag_s  = f"{ag:.4f}" if not np.isnan(ag) else "  N/A  "
    at_s  = f"{at:.4f}" if not np.isnan(at) else "  N/A  "
    rat_s = f"{ag/full_auc:.2%}" if not np.isnan(ag) else "  N/A  "
    lines.append(f"  {W:>5}  {ag_s:>10}  {at_s:>10}  %{cov:>7.1f}  {rat_s:>10}")

lines += [
    "",
    "--- AUC ESIK HAFTALARI ---",
    f"  Global AUC >= 0.70 ilk hafta : W={t70_g}" if t70_g else "  Global AUC 0.70'e ulasmiyor",
    f"  Global AUC >= 0.80 ilk hafta : W={t80_g}" if t80_g else "  Global AUC 0.80'e ulasmiyor",
    f"  Tier1  AUC >= 0.70 ilk hafta : W={t70_t1}" if t70_t1 else "  Tier1 AUC 0.70'e ulasmiyor",
    f"  Tier1  AUC >= 0.80 ilk hafta : W={t80_t1}" if t80_t1 else "  Tier1 AUC 0.80'e ulasmiyor",
    "",
    "--- TOP FEATURE'LAR (Ortalama Normalize Gain, tum haftalar) ---",
]
top10_overall = fi_norm.mean(axis=0).nlargest(10)
for feat, val in top10_overall.items():
    lines.append(f"  {feat:30s}: {val:.3f}")

lines += [
    "",
    "--- W=2 HAFTASINDA FEATURE'LAR ---",
    "  (Cok erken donemde hangi ozellikler one cikiyor?)",
]
if any(r["W"] == 2 for r in cutoff_results):
    r2 = next(r for r in cutoff_results if r["W"] == 2)
    top5_w2 = sorted(r2["feat_imp"].items(), key=lambda x: x[1], reverse=True)[:5]
    for feat, val in top5_w2:
        lines.append(f"  {feat:30s}: gain={val:.1f}")
else:
    lines.append("  W=2 sonucu bulunamadi.")

lines += [
    "",
    "--- YORUM VE ONERILER ---",
]

valid_aucs = [(r["W"], r["auc_global"]) for r in cutoff_results if not np.isnan(r["auc_global"])]
if valid_aucs:
    early_auc = valid_aucs[0][1]   # W=2 veya en erken
    late_auc  = valid_aucs[-1][1]  # En gec
    auc_drop  = full_auc - late_auc

    lines.append(f"  En erken AUC (W={valid_aucs[0][0]}): {early_auc:.4f}")
    lines.append(f"  En gec AUC  (W={valid_aucs[-1][0]}): {late_auc:.4f}")
    lines.append(f"  Tam veri AUC                      : {full_auc:.4f}")
    lines.append(f"  En gec - Tam fark                 : {auc_drop:+.4f}")
    lines.append("")

    if early_auc >= 0.75:
        lines.append("  SONUC: Cok iyi erken uyari! W=2'de bile yuksek AUC.")
        lines.append("  Model zaten cok erkenden ogrencileri ayirt edebiliyor.")
    elif early_auc >= 0.65:
        lines.append("  SONUC: Orta erken uyari kapasitesi.")
        lines.append("  W=2-4 haftalarda kabul edilebilir AUC, W=8+ ile guclu.")
    else:
        lines.append("  SONUC: Zayif erken uyari. W=2'de yetersiz veri.")

    lines += [
        "",
        "  Performans iyilestirme onerileri (erken haftalarda):",
        "  1. VELOCITY features: n_log_son7gun, n_log_onceki7gun (degisim hizi)",
        "  2. BINARY bayraklar: ilk2hf_teslim_var, ilk2hf_quiz_var",
        "  3. RECENCY: son_log_uzerinden_gun (uzun sessizlik = erken dropout)",
        "  4. KURS-ICI NORM: W. haftaya kadar olan percentile rank",
        "     (aynı hafta sayısı, farklı kursların ortalamasına gore)",
        "  5. MOMENTUM: son3gun_aktiflik / ilk3gun_aktiflik orani",
]

lines += [
    "",
    "--- CIKTI DOSYALARI ---",
    "  05_auc_vs_haftalar.png     — AUC egri grafigi (ana gorsel)",
    "  05_feature_onem_by_week.png — Feature importance heatmap (hafta x feature)",
    "  05_sample_coverage.png      — Coverage: kac ogrencinin logu var",
    "  05_cutoff_rapor.txt         — Bu rapor",
]

rapor(CIKTI_DIR, "05_cutoff_rapor.txt", lines)
print(f"\n=== TAMAMLANDI ===")
print(f">>> Rapor: {os.path.join(CIKTI_DIR, '05_cutoff_rapor.txt')}")

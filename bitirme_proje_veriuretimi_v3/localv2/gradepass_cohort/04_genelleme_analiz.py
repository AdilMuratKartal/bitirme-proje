# -*- coding: utf-8 -*-
"""Genelleme Analizi — AUC=0.923 gercekten guvenilir mi?

A. Tier bazli performans   : Global model test setinde tier'a gore nasil?
B. Tier 1 Only Model       : Sadece anlamli buyuk kurslarda AUC ne?
C. Leave-One-Course-Out CV : Cross-course gercek genelleme
D. Within-Course vs LOCO   : Model kurs-spesifik mi, yoksa evrensel mi?

Girdi : cikti/01_cohort_dataset.csv
Cikti : cikti/04_tier_performans.png
        cikti/04_loco_cv.png
        cikti/04_within_vs_loco.png
        cikti/04_genelleme_rapor.txt
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from common import rapor

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score
import xgboost as xgb

CIKTI_DIR = os.path.join(os.path.dirname(__file__), "cikti")
DATASET   = os.path.join(CIKTI_DIR, "01_cohort_dataset.csv")

print("=== GENELLEME ANALIZI ===\n")

# ---------------------------------------------------------------------------
# Veri + Feature
# ---------------------------------------------------------------------------
if not os.path.exists(DATASET):
    raise SystemExit(f"HATA: {DATASET} bulunamadi.")

df = pd.read_csv(DATASET)
df["userid"]   = df["userid"].astype(int)
df["courseid"] = df["courseid"].astype(int)

LEAKAGE = {
    "norm_pct", "grade_margin", "grade_margin_pct",
    "finalgrade", "gradepass", "grademax", "grademin",
    "userid", "courseid", "label",
}
ML_FEATURES = sorted([c for c in df.columns if c not in LEAKAGE])

X = df[ML_FEATURES].fillna(0).astype(float)
y = df["label"].astype(int)

print(f"Dataset : {len(df):,} satir  |  {len(ML_FEATURES)} feature")
print(f"Label   : Gecti={int(y.sum())}  Kaldi={int((y==0).sum())}  denge=%{y.mean()*100:.1f}")

tier_dist = df["kurs_tier"].value_counts().sort_index()
for t, n in tier_dist.items():
    print(f"  Tier {t}: {n} ogrenci  {df[df['kurs_tier']==t]['courseid'].nunique()} kurs")

# XGBoost parametreleri
XGB = dict(
    n_estimators=300, max_depth=5, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
    random_state=42, verbosity=0,
)


def fit_xgb(X_tr, y_tr, X_te, y_te):
    m = xgb.XGBClassifier(**XGB)
    m.fit(X_tr, y_tr)
    prob = m.predict_proba(X_te)[:, 1]
    pred = m.predict(X_te)
    auc  = roc_auc_score(y_te, prob) if y_te.nunique() > 1 else np.nan
    return {
        "auc": auc,
        "acc": accuracy_score(y_te, pred),
        "f1":  f1_score(y_te, pred, zero_division=0),
        "model": m,
    }


# ---------------------------------------------------------------------------
# A. Global Model + Tier Bazlı Değerlendirme
# ---------------------------------------------------------------------------
print("\n[A] Global model egitiliyor (80/20 split)...")

X_tr, X_te, y_tr, y_te = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
gres  = fit_xgb(X_tr, y_tr, X_te, y_te)
gm    = gres["model"]
print(f"  Global AUC={gres['auc']:.4f}  ACC={gres['acc']:.4f}  F1={gres['f1']:.4f}")

tier_col = df.loc[X_te.index, "kurs_tier"]
tier_res  = {}
for t in sorted(tier_col.unique()):
    mask = tier_col == t
    if mask.sum() < 3:
        continue
    yt   = y_te[mask]
    prob = gm.predict_proba(X_te[mask])[:, 1]
    auc  = roc_auc_score(yt, prob) if yt.nunique() > 1 else np.nan
    tier_res[t] = {"auc": auc, "n": int(mask.sum()), "pr": float(yt.mean())}
    auc_s = f"{auc:.4f}" if not np.isnan(auc) else "N/A (tek sinif)"
    print(f"  Tier {t}: n={mask.sum():<4}  pass={yt.mean():.2f}  AUC={auc_s}")

# Grafik A
valid_tiers = [t for t in sorted(tier_res) if not np.isnan(tier_res[t]["auc"])]
fig, ax = plt.subplots(figsize=(9, 5))
pal = {0: "#e74c3c", 1: "#27ae60", 2: "#3498db", 3: "#95a5a6"}
bars = ax.bar(
    [f"Tier {t}\n(n={tier_res[t]['n']})" for t in valid_tiers],
    [tier_res[t]["auc"] for t in valid_tiers],
    color=[pal.get(t, "#7f8c8d") for t in valid_tiers],
    alpha=0.85, width=0.5,
)
for bar, t in zip(bars, valid_tiers):
    v = tier_res[t]["auc"]
    ax.text(bar.get_x() + bar.get_width()/2, v + 0.008,
            f"{v:.3f}", ha="center", fontsize=11, fontweight="bold")
ax.axhline(gres["auc"], color="black", linestyle="--", linewidth=1.5,
           label=f"Global AUC = {gres['auc']:.3f}")
ax.axhline(0.5, color="gray", linestyle=":", linewidth=1, alpha=0.6, label="Rasgele (0.5)")
ax.set_ylim(0.35, 1.08)
ax.set_ylabel("AUC (test seti)")
ax.set_title("A. Global Model — Tier Bazlı AUC\n"
             "Tier 0: Trivial (0%/100% geçme)  |  Tier 1: Büyük+Dengeli  |  Tier 2: Küçük+Dengeli")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(CIKTI_DIR, "04_tier_performans.png"), dpi=150)
plt.close()
print("  04_tier_performans.png kaydedildi")

# ---------------------------------------------------------------------------
# B. Tier 1 Only Model
# ---------------------------------------------------------------------------
print("\n[B] Tier 1 only model...")

df1 = df[df["kurs_tier"] == 1].copy()
X1  = df1[ML_FEATURES].fillna(0).astype(float)
y1  = df1["label"].astype(int)
print(f"  Tier 1: {len(df1)} satir  |  kurs={df1['courseid'].nunique()}  pass={y1.mean():.2f}")

t1_res    = {"auc": np.nan, "acc": np.nan, "f1": np.nan}
t1_cv_auc = np.nan

if y1.nunique() > 1 and len(df1) >= 30:
    X1_tr, X1_te, y1_tr, y1_te = train_test_split(
        X1, y1, test_size=0.2, random_state=42, stratify=y1
    )
    t1_res = fit_xgb(X1_tr, y1_tr, X1_te, y1_te)
    print(f"  Tier 1 test AUC={t1_res['auc']:.4f}  ACC={t1_res['acc']:.4f}")

    cv5 = StratifiedKFold(5, shuffle=True, random_state=42)
    t1_cv_auc = cross_val_score(
        xgb.XGBClassifier(**XGB), X1, y1, cv=cv5, scoring="roc_auc", n_jobs=-1
    ).mean()
    print(f"  Tier 1 5-CV AUC={t1_cv_auc:.4f}")
    print(f"  Global vs Tier1 fark: {gres['auc'] - t1_res['auc']:+.4f}")

# ---------------------------------------------------------------------------
# C. Leave-One-Course-Out (LOCO-CV)
# ---------------------------------------------------------------------------
print("\n[C] LOCO-CV (Tier 1 + Tier 2)...")

loco_df = df[df["kurs_tier"].isin([1, 2])].copy()
loco_courses = sorted(loco_df["courseid"].unique())
print(f"  Kurslar: {loco_courses}  (toplam: {len(loco_df)} satir)")

loco_rows = []
for cid in loco_courses:
    te_mask = loco_df["courseid"] == cid
    tr_mask = ~te_mask

    X_te_l = loco_df[te_mask][ML_FEATURES].fillna(0).astype(float)
    y_te_l = loco_df[te_mask]["label"].astype(int)
    X_tr_l = loco_df[tr_mask][ML_FEATURES].fillna(0).astype(float)
    y_tr_l = loco_df[tr_mask]["label"].astype(int)

    n_te  = len(y_te_l)
    pr_te = float(y_te_l.mean())
    tier  = int(df[df["courseid"] == cid]["kurs_tier"].iloc[0])

    if y_te_l.nunique() < 2 or n_te < 5:
        note = "tek_sinif"
        loco_rows.append({"courseid": cid, "n": n_te, "tier": tier,
                          "pr": pr_te, "auc": np.nan, "note": note})
        print(f"  Kurs {cid:5d} (n={n_te:3d}) ATLANDI: {note}")
        continue

    if y_tr_l.nunique() < 2:
        note = "train_tek_sinif"
        loco_rows.append({"courseid": cid, "n": n_te, "tier": tier,
                          "pr": pr_te, "auc": np.nan, "note": note})
        print(f"  Kurs {cid:5d} (n={n_te:3d}) ATLANDI: {note}")
        continue

    res = fit_xgb(X_tr_l, y_tr_l, X_te_l, y_te_l)
    loco_rows.append({"courseid": cid, "n": n_te, "tier": tier,
                      "pr": pr_te, "auc": res["auc"], "note": "ok"})
    print(f"  Kurs {cid:5d} (n={n_te:3d}, tier={tier}): AUC={res['auc']:.4f}  pass={pr_te:.2f}")

loco_df_res = pd.DataFrame(loco_rows)
loco_valid  = loco_df_res[loco_df_res["auc"].notna()]
loco_mean   = loco_valid["auc"].mean() if len(loco_valid) else np.nan
print(f"\n  LOCO ort.AUC={loco_mean:.4f}  ({len(loco_valid)}/{len(loco_courses)} kurs gecerli)")

# Grafik C
if len(loco_valid) >= 2:
    fig, ax = plt.subplots(figsize=(max(10, len(loco_valid)*1.2), 6))
    lv = loco_valid.sort_values("auc", ascending=False)
    bar_colors = ["#27ae60" if t == 1 else "#3498db" for t in lv["tier"]]
    bars = ax.bar(
        range(len(lv)), lv["auc"],
        color=bar_colors, alpha=0.85, width=0.6,
    )
    for i, (bar, row) in enumerate(zip(bars, lv.itertuples())):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.008,
                f"{row.auc:.2f}", ha="center", fontsize=8, fontweight="bold")
    ax.set_xticks(range(len(lv)))
    ax.set_xticklabels(
        [f"K{int(r.courseid)}\n(n={int(r.n)})" for r in lv.itertuples()],
        fontsize=9
    )
    ax.axhline(loco_mean, color="black", linestyle="--", linewidth=1.5,
               label=f"LOCO ort. AUC = {loco_mean:.3f}")
    ax.axhline(gres["auc"], color="red", linestyle=":", linewidth=1.5,
               label=f"Global AUC = {gres['auc']:.3f}")
    ax.axhline(0.5, color="gray", linestyle=":", linewidth=1, alpha=0.5)
    ax.set_ylim(0.2, 1.1)
    ax.set_ylabel("AUC (test kursu)")
    ax.set_title("C. Leave-One-Course-Out (LOCO-CV)\n"
                 "Her çubuk = 1 kurs dışarıda, geride kalanlarla eğitilmiş model | Yeşil=Tier1, Mavi=Tier2")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(CIKTI_DIR, "04_loco_cv.png"), dpi=150)
    plt.close()
    print("  04_loco_cv.png kaydedildi")

# ---------------------------------------------------------------------------
# D. Within-Course CV vs LOCO Karşılaştırma
# ---------------------------------------------------------------------------
print("\n[D] Within-course CV vs LOCO...")

within_rows = []
for cid in loco_courses:
    sub = loco_df[loco_df["courseid"] == cid].copy()
    Xw  = sub[ML_FEATURES].fillna(0).astype(float)
    yw  = sub["label"].astype(int)
    n   = len(sub)
    tier = int(sub["kurs_tier"].iloc[0])

    if n < 20 or yw.nunique() < 2:
        continue
    if min(yw.sum(), (yw == 0).sum()) < 4:
        continue

    n_folds = min(5, int(yw.sum()), int((yw == 0).sum()))
    if n_folds < 2:
        continue

    cv_w = StratifiedKFold(n_folds, shuffle=True, random_state=42)
    try:
        w_auc = cross_val_score(
            xgb.XGBClassifier(**XGB), Xw, yw, cv=cv_w, scoring="roc_auc", n_jobs=-1
        ).mean()
    except Exception:
        continue

    loco_row = loco_df_res[loco_df_res["courseid"] == cid]
    if loco_row.empty or np.isnan(loco_row["auc"].iloc[0]):
        continue

    loco_auc = float(loco_row["auc"].iloc[0])
    gap = w_auc - loco_auc
    within_rows.append({
        "courseid": cid, "n": n, "tier": tier,
        "within_auc": w_auc, "loco_auc": loco_auc, "gap": gap,
    })
    print(f"  Kurs {cid:5d}: within={w_auc:.4f}  loco={loco_auc:.4f}  gap={gap:+.4f}")

within_df = pd.DataFrame(within_rows)

if not within_df.empty:
    mean_gap = float(within_df["gap"].mean())
    fig, ax  = plt.subplots(figsize=(max(9, len(within_df)*1.4), 6))
    wd = within_df.sort_values("courseid")
    xp = np.arange(len(wd))
    w  = 0.35
    ax.bar(xp - w/2, wd["within_auc"], w,
           label="Within-course CV AUC", color="#27ae60", alpha=0.85)
    ax.bar(xp + w/2, wd["loco_auc"],   w,
           label="LOCO-CV AUC",          color="#e74c3c", alpha=0.85)
    ax.set_xticks(xp)
    ax.set_xticklabels(
        [f"K{int(r.courseid)}\n(n={int(r.n)})" for r in wd.itertuples()],
        fontsize=9
    )
    ax.set_ylim(0.2, 1.1)
    ax.set_ylabel("AUC")
    ax.set_title(f"D. Within-Course CV vs LOCO-CV — Ortalama Gap = {mean_gap:+.3f}\n"
                 "Gap büyükse model kurs-spesifik özellik öğreniyor (gerçek genelleme zayıf)")
    ax.legend()
    ax.axhline(0.5, color="gray", linestyle=":", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(CIKTI_DIR, "04_within_vs_loco.png"), dpi=150)
    plt.close()
    print("  04_within_vs_loco.png kaydedildi")

# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------
print("\n[Rapor] yaziliyor...")

tier0_auc = tier_res.get(0, {}).get("auc", np.nan)
tier1_auc = tier_res.get(1, {}).get("auc", np.nan)

lines = [
    "=== GENELLEME ANALIZI RAPORU ===",
    "",
    "--- SORU ---",
    "  1. Global AUC=0.923 gercekten guvenilir mi, yoksa Tier 0 sisiriyor mu?",
    "  2. Model cross-course (yeni, gorulmemis kurslar icin) genelliyor mu?",
    "",
    "--- A. GLOBAL MODEL + TIER BAZLI PERFORMANS ---",
    f"  Global AUC  : {gres['auc']:.4f}",
    f"  Global ACC  : {gres['acc']:.4f}",
    f"  Global F1   : {gres['f1']:.4f}",
    "",
    "  Tier bazli AUC (global modelin test setinde tier performansi):",
]
for t in sorted(tier_res):
    r = tier_res[t]
    s = f"{r['auc']:.4f}" if not np.isnan(r["auc"]) else "N/A (tek sinif — trivial)"
    lines.append(f"    Tier {t}: n={r['n']:<4}  pass_rate={r['pr']:.2f}  AUC={s}")

if not np.isnan(tier0_auc) and not np.isnan(tier1_auc):
    diff = tier0_auc - tier1_auc
    lines += [
        "",
        f"  Tier 0 - Tier 1 AUC farki: {diff:+.4f}",
    ]
    if diff > 0.08:
        lines.append("  YORUM: Tier 0 AUC cok yuksek -> global AUC kismi olarak sismis!")
        lines.append("         Tier 1 AUC gercek zorlugun gostergesi.")
    elif diff > 0.03:
        lines.append("  YORUM: Tier 0 AUC biraz daha yuksek ama buyuk fark degil.")
    else:
        lines.append("  YORUM: Tier 0 ve Tier 1 AUC birbirine yakin — model her ikisinde de iyi.")

lines += [
    "",
    "--- B. TIER 1 ONLY MODEL ---",
    f"  Tier 1 ogrenci sayisi : {len(df1)}",
    f"  Tier 1 kurs sayisi    : {df1['courseid'].nunique()}",
    f"  Tier 1 test AUC       : {t1_res['auc']:.4f}" if not np.isnan(t1_res['auc']) else "  Tier 1 test AUC: N/A",
    f"  Tier 1 5-CV AUC       : {t1_cv_auc:.4f}" if not np.isnan(t1_cv_auc) else "  Tier 1 5-CV AUC: N/A",
]
if not np.isnan(t1_res['auc']):
    fark = gres['auc'] - t1_res['auc']
    lines.append(f"  Global - Tier1 fark    : {fark:+.4f}")
    if fark > 0.05:
        lines.append("  YORUM: Global AUC Tier 1'e gore sisirmis. Gercekci beklenti Tier 1 AUC.")
    else:
        lines.append("  YORUM: Tier 1 modeli global ile rekabetci — behavioral features evrensel.")

lines += [
    "",
    "--- C. LOCO-CV (LEAVE-ONE-COURSE-OUT) SONUCLARI ---",
    f"  Toplam LOCO kurs  : {len(loco_courses)}",
    f"  Gecerli kurs (AUC): {len(loco_valid)}",
    f"  LOCO ort. AUC     : {loco_mean:.4f}" if not np.isnan(loco_mean) else "  LOCO ort. AUC: N/A",
]

if len(loco_valid) >= 2:
    min_row = loco_valid.loc[loco_valid["auc"].idxmin()]
    max_row = loco_valid.loc[loco_valid["auc"].idxmax()]
    lines += [
        f"  LOCO min AUC      : {min_row['auc']:.4f}  (Kurs {int(min_row['courseid'])}, n={int(min_row['n'])})",
        f"  LOCO max AUC      : {max_row['auc']:.4f}  (Kurs {int(max_row['courseid'])}, n={int(max_row['n'])})",
        "",
        "  Kurs bazli LOCO detay (AUC'ye gore siralandi):",
    ]
    for _, row in loco_df_res.sort_values("auc", ascending=False, na_position="last").iterrows():
        s = f"{row['auc']:.4f}" if not np.isnan(row["auc"]) else f"N/A ({row['note']})"
        lines.append(f"    Kurs {int(row['courseid']):5d} | n={int(row['n']):3d} | "
                     f"tier={int(row['tier'])} | pass={row['pr']:.2f} | AUC={s}")

if not np.isnan(loco_mean) and not np.isnan(gres["auc"]):
    fark = gres["auc"] - loco_mean
    lines += [
        "",
        f"  Global vs LOCO fark: {fark:+.4f}",
    ]
    if fark > 0.12:
        lines.append("  YORUM: BUYUK fark — model buyuk olcude kurs-spesifik sinyal ogrenmiş.")
        lines.append("         Yeni bir kursa uygulandiginda performans belirgin duser.")
    elif fark > 0.06:
        lines.append("  YORUM: ORTA fark — model kismen genelliyor ama kurs ozellikleri etkili.")
    else:
        lines.append("  YORUM: KUCUK fark — model gercekten genelliyor. Behavioral features evrensel.")

if not within_df.empty:
    mean_gap = float(within_df["gap"].mean())
    lines += [
        "",
        "--- D. WITHIN-COURSE VS LOCO KARSILASTIRMA ---",
        f"  Karsilastirilan kurs sayisi : {len(within_df)}",
        f"  Ort. within-course CV AUC   : {within_df['within_auc'].mean():.4f}",
        f"  Ort. LOCO-CV AUC            : {within_df['loco_auc'].mean():.4f}",
        f"  Ort. gap (within - LOCO)    : {mean_gap:+.4f}",
        "",
        "  Kurs bazli:",
    ]
    for _, row in within_df.sort_values("gap", ascending=False).iterrows():
        lines.append(f"    Kurs {int(row['courseid']):5d}: within={row['within_auc']:.4f}  "
                     f"loco={row['loco_auc']:.4f}  gap={row['gap']:+.4f}")
    lines += [
        "",
        "  YORUM:",
    ]
    if mean_gap > 0.12:
        lines.append(f"  Gap={mean_gap:.3f} BUYUK: Model kurs-spesifik ozellikler ogrenmiş.")
        lines.append("  Kurs biaslama var. ONERI:")
        lines.append("  1. Daha guclu kurs-ici normalizasyon (percentile rank artir)")
        lines.append("  2. Courseid'yi kategorik embedding olarak ekle")
        lines.append("  3. Kurs-agnostik velocity features ekle")
    elif mean_gap > 0.06:
        lines.append(f"  Gap={mean_gap:.3f} ORTA: Model kismen kurs-ozgun ama bir olcude genelliyor.")
        lines.append("  ONERI: Percentile features agirligini artir, momentum features ekle.")
    else:
        lines.append(f"  Gap={mean_gap:.3f} KUCUK: Model iyi genelliyor! Behavioral features evrensel.")

lines += [
    "",
    "--- GENEL DEGERLENDIRME VE ONERILER ---",
    "",
    f"  Global AUC (tum kurslar) : {gres['auc']:.4f}",
    f"  Tier 1 AUC (gercekci)    : {t1_res['auc']:.4f}" if not np.isnan(t1_res['auc']) else "  Tier 1 AUC: N/A",
    f"  LOCO-CV AUC (gercek gen.): {loco_mean:.4f}" if not np.isnan(loco_mean) else "  LOCO-CV AUC: N/A",
    "",
    "  Cikti Dosyalari:",
    "    04_tier_performans.png  — Tier bazli AUC bar grafigi",
    "    04_loco_cv.png          — LOCO-CV kurs bazli AUC",
    "    04_within_vs_loco.png   — Within-Course vs LOCO karsilastirma",
    "    04_genelleme_rapor.txt  — Bu rapor",
]

rapor(CIKTI_DIR, "04_genelleme_rapor.txt", lines)
print(f"\n=== TAMAMLANDI ===")
print(f">>> Rapor: {os.path.join(CIKTI_DIR, '04_genelleme_rapor.txt')}")

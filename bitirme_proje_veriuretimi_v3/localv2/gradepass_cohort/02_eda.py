# -*- coding: utf-8 -*-
"""Kesin Esikli Kohort — Kesifsel Veri Analizi (EDA)

Girdi: cikti/01_cohort_dataset.csv  (01_hazirla.py ciktisi)

Analizler:
  1. Sinif dengesi
  2. grade_margin dagilimi (gecenler vs kalanlar)
  3. Log-etiket korelasyonu
  4. Feature dagilim histogramlari (label=0 vs label=1)
  5. Box plot: temel ozellikler vs label
  6. Korelasyon heatmap
  7. Kurs bazinda ogrenci sayisi + gecme orani
  8. gradepass deger dagilimi

Cikti: cikti/ altinda rapor + grafikler
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from common import kaydet, rapor, yuzde

import pandas as pd
import numpy as np

CIKTI_DIR = os.path.join(os.path.dirname(__file__), "cikti")
DATASET   = os.path.join(CIKTI_DIR, "01_cohort_dataset.csv")

print("=== GRADEPASS COHORT: 02_eda.py ===\n")

if not os.path.exists(DATASET):
    raise SystemExit(
        f"HATA: {DATASET} bulunamadi.\n"
        f"  Once 01_hazirla.py calistirin."
    )

df = pd.read_csv(DATASET)
df["userid"]   = df["userid"].astype(int)
df["courseid"] = df["courseid"].astype(int)
print(f"Dataset: {len(df):,} satir  x  {len(df.columns)} kolon")
print(f"Kolonlar: {list(df.columns)}\n")

n_total = len(df)
n1 = (df["label"] == 1).sum()
n0 = (df["label"] == 0).sum()

NUMERIC_FEATURES = [
    # Temel log
    "n_log", "n_aktif_gun", "log_per_gun", "aktif_sure_gun",
    "n_view", "n_pure_log", "n_perf_log",
    # Teslim / quiz
    "n_teslim", "n_quiz_deneme", "performans_skoru",
    # MNAR bayraklari
    "log_var", "teslim_var",
    # Not (EDA only — leakage riski)
    "norm_pct", "grade_margin", "grade_margin_pct",
    # Forum + Modul
    "forum_submit", "forum_view", "n_modul_cesit",
    "resource_view", "quiz_act",
    # Temporal / Session
    "night_ratio", "weekend_ratio",
    "n_sessions", "clicks_per_session", "max_hissizlik",
    # log1p (Hamle A)
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
NUMERIC_FEATURES = [c for c in NUMERIC_FEATURES if c in df.columns]

# --------------------------------------------------------------------------- #
# 1. Sinif Dengesi
# --------------------------------------------------------------------------- #
print("[1] Sinif Dengesi")
print(f"  Toplam  : {n_total:,}")
print(f"  Gecti=1 : {n1:,}  (%{yuzde(n1, n_total):.1f})")
print(f"  Kaldi=0 : {n0:,}  (%{yuzde(n0, n_total):.1f})")

# --------------------------------------------------------------------------- #
# 2. grade_margin Dagilimi
# --------------------------------------------------------------------------- #
print("\n[2] grade_margin Dagilimi")
if "grade_margin" in df.columns:
    gm1 = df[df["label"] == 1]["grade_margin"]
    gm0 = df[df["label"] == 0]["grade_margin"]
    print(f"  Gecti (label=1)  ort={gm1.mean():.2f}  medyan={gm1.median():.2f}  "
          f"std={gm1.std():.2f}")
    print(f"  Kaldi (label=0)  ort={gm0.mean():.2f}  medyan={gm0.median():.2f}  "
          f"std={gm0.std():.2f}")
    pos_margin = (df["grade_margin"] > 0).sum()
    neg_margin = (df["grade_margin"] < 0).sum()
    zero_margin = (df["grade_margin"] == 0).sum()
    print(f"  grade_margin > 0 (gecti):  {pos_margin:,}")
    print(f"  grade_margin < 0 (kaldi):  {neg_margin:,}")
    print(f"  grade_margin = 0 (sinir):  {zero_margin:,}")

# --------------------------------------------------------------------------- #
# 3. Log-Etiket Korelasyonu
# --------------------------------------------------------------------------- #
print("\n[3] Log-Etiket Korelasyonu (Pearson r)")
corr_results = {}
for feat in NUMERIC_FEATURES:
    r = df[feat].corr(df["label"])
    corr_results[feat] = r

for feat, r in sorted(corr_results.items(), key=lambda x: abs(x[1]), reverse=True):
    if abs(r) < 0.05:
        flag = " <- ZAYIF"
    elif abs(r) < 0.2:
        flag = " <- ORTA"
    else:
        flag = " <- GUCLU"
    print(f"  {feat:28s}: r = {r:+.4f}{flag}")

# --------------------------------------------------------------------------- #
# 4. Feature Ozet Istatistikleri (label bazinda)
# --------------------------------------------------------------------------- #
print("\n[4] Feature Ozet (label=0 vs label=1)")
for feat in NUMERIC_FEATURES[:8]:  # terminale sadece ilk 8'i yaz
    v0 = df[df["label"] == 0][feat]
    v1 = df[df["label"] == 1][feat]
    print(f"  {feat:28s}:  label=0 ort={v0.mean():.2f}  | label=1 ort={v1.mean():.2f}")

# --------------------------------------------------------------------------- #
# 5. Kurs bazinda dagilim
# --------------------------------------------------------------------------- #
print("\n[5] Kurs Bazinda Dagilim")
course_stats = df.groupby("courseid").agg(
    n_ogrenci=("userid", "count"),
    gecme_pct=("label", lambda x: 100 * x.mean()),
    gradepass_val=("gradepass", "first"),
).reset_index()
print(f"  Toplam kurs          : {len(course_stats):,}")
print(f"  Medyan ogrenci/kurs  : {course_stats['n_ogrenci'].median():.0f}")
print(f"  Ortalama gecme orani : %{course_stats['gecme_pct'].mean():.1f}")
kucuk = (course_stats["n_ogrenci"] < 5).sum()
print(f"  Kurs (<5 ogrenci)    : {kucuk:,}")

# --------------------------------------------------------------------------- #
# 6. gradepass Deger Dagilimi
# --------------------------------------------------------------------------- #
print("\n[6] gradepass Deger Dagilimi (ilk 10)")
gp_dist = df["gradepass"].value_counts().head(10)
for val, cnt in gp_dist.items():
    print(f"  gradepass={val:6.1f}  ->  {cnt:,} kayit  (%{yuzde(cnt, n_total):.1f})")

# --------------------------------------------------------------------------- #
# 7. Korelasyon Matrisi (kaydet)
# --------------------------------------------------------------------------- #
corr_cols = NUMERIC_FEATURES + ["label"]
corr_df = df[corr_cols].corr().round(4)
kaydet(CIKTI_DIR, "02_korelasyon.csv", corr_df.reset_index())
print(f"\n>>> 02_korelasyon.csv kaydedildi")

# --------------------------------------------------------------------------- #
# 8. Grafikler (matplotlib / seaborn)
# --------------------------------------------------------------------------- #
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    palette = {0: "#e74c3c", 1: "#2ecc71"}

    # 8a. Sinif dagilimi bar chart
    fig, ax = plt.subplots(figsize=(6, 4))
    label_counts = df["label"].value_counts().sort_index()
    bars = ax.bar(["Kaldi (0)", "Gecti (1)"], label_counts.values,
                  color=[palette[0], palette[1]])
    for bar, val in zip(bars, label_counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(label_counts.values) * 0.01,
                f"{val:,}\n(%{val / n_total * 100:.1f})",
                ha="center", fontsize=10)
    ax.set_title("Kesin Esikli Kohort — Sinif Dagilimi")
    ax.set_ylabel("Kayit Sayisi")
    plt.tight_layout()
    plt.savefig(os.path.join(CIKTI_DIR, "02_label_dist.png"), dpi=150)
    plt.close()
    print("  [Grafik] 02_label_dist.png")

    # 8b. grade_margin histogrami
    if "grade_margin" in df.columns:
        fig, ax = plt.subplots(figsize=(8, 4))
        for lbl in [0, 1]:
            data = df[df["label"] == lbl]["grade_margin"].dropna()
            ax.hist(data, bins=60, alpha=0.6,
                    label=f"label={lbl} ({'Gecti' if lbl else 'Kaldi'})",
                    color=palette[lbl])
        ax.axvline(0, color="black", linestyle="--", linewidth=1.2, label="Sinir (margin=0)")
        ax.set_title("grade_margin Dagilimi (finalgrade - gradepass)")
        ax.set_xlabel("grade_margin")
        ax.set_ylabel("Kayit Sayisi")
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(CIKTI_DIR, "02_grade_margin_dist.png"), dpi=150)
        plt.close()
        print("  [Grafik] 02_grade_margin_dist.png")

    # 8c. Feature histogramlari (label=0 vs label=1)
    plot_feats = [c for c in ["n_log", "n_aktif_gun", "log_per_gun",
                               "n_perf_log", "n_teslim", "norm_pct"]
                  if c in df.columns]
    if plot_feats:
        ncols = 3
        nrows = (len(plot_feats) + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols,
                                 figsize=(5 * ncols, 4 * nrows))
        axes = np.array(axes).flatten()
        for i, feat in enumerate(plot_feats):
            ax = axes[i]
            for lbl in [0, 1]:
                data = df[df["label"] == lbl][feat].dropna()
                ax.hist(data, bins=40, alpha=0.6,
                        label=f"{'Gecti' if lbl else 'Kaldi'}",
                        color=palette[lbl])
            ax.set_title(feat)
            ax.set_xlabel("Deger")
            ax.legend(fontsize=8)
        for j in range(len(plot_feats), len(axes)):
            axes[j].set_visible(False)
        plt.suptitle("Feature Dagilimi — Gecti vs Kaldi (Kesin Esikli Kohort)",
                     y=1.02, fontsize=13)
        plt.tight_layout()
        plt.savefig(os.path.join(CIKTI_DIR, "02_feature_dists.png"),
                    dpi=150, bbox_inches="tight")
        plt.close()
        print("  [Grafik] 02_feature_dists.png")

    # 8d. Box plot
    box_feats = [c for c in ["n_log", "n_teslim", "n_quiz_deneme", "norm_pct"]
                 if c in df.columns]
    if box_feats:
        fig, axes = plt.subplots(1, len(box_feats),
                                 figsize=(4 * len(box_feats), 5))
        if len(box_feats) == 1:
            axes = [axes]
        for ax, feat in zip(axes, box_feats):
            data_dict = {
                "Kaldi (0)": df[df["label"] == 0][feat].dropna().values,
                "Gecti (1)": df[df["label"] == 1][feat].dropna().values,
            }
            ax.boxplot(data_dict.values(), labels=data_dict.keys(),
                       patch_artist=True,
                       boxprops=dict(facecolor="#b3d9ff"),
                       medianprops=dict(color="red", linewidth=2))
            ax.set_title(feat)
            ax.set_ylabel("Deger")
        plt.suptitle("Box Plot — Kaldi vs Gecti", fontsize=13)
        plt.tight_layout()
        plt.savefig(os.path.join(CIKTI_DIR, "02_boxplot.png"),
                    dpi=150, bbox_inches="tight")
        plt.close()
        print("  [Grafik] 02_boxplot.png")

    # 8e. Korelasyon heatmap
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(df[corr_cols].corr(), annot=True, fmt=".2f",
                cmap="coolwarm", center=0, ax=ax, square=True,
                linewidths=0.3, cbar_kws={"shrink": 0.8})
    ax.set_title("Feature Korelasyon Matrisi (Kesin Esikli Kohort — label dahil)",
                 fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(CIKTI_DIR, "02_correlation_heatmap.png"),
                dpi=150, bbox_inches="tight")
    plt.close()
    print("  [Grafik] 02_correlation_heatmap.png")

    # 8f. Kurs bazinda gecme orani dagilimi
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(course_stats["gecme_pct"], bins=30, color="#3498db", edgecolor="white")
    ax.axvline(course_stats["gecme_pct"].mean(), color="red",
               linestyle="--", label=f"Ort. %{course_stats['gecme_pct'].mean():.1f}")
    ax.set_title("Kurs Bazinda Gecme Orani Dagilimi")
    ax.set_xlabel("Gecme Orani (%)")
    ax.set_ylabel("Kurs Sayisi")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(CIKTI_DIR, "02_kurs_gecme_orani.png"), dpi=150)
    plt.close()
    print("  [Grafik] 02_kurs_gecme_orani.png")

    grafik_notu = "Grafikler basariyla olusturuldu (matplotlib/seaborn)."

except ImportError as e:
    grafik_notu = f"matplotlib/seaborn yuklu degil: {e}. Grafikler atlanıyor."
    print(f"\n  UYARI: {grafik_notu}")

# --------------------------------------------------------------------------- #
# Rapor
# --------------------------------------------------------------------------- #
lines = [
    "=== GRADEPASS COHORT: EDA RAPORU ===",
    "",
    "--- Dataset ---",
    f"  Toplam kayit: {n_total:,}  |  Kurs: {df['courseid'].nunique():,}  |  Kullanici: {df['userid'].nunique():,}",
    "",
    "--- Sinif Dengesi ---",
    f"  label=1 (Gecti): {n1:,}  (%{yuzde(n1, n_total):.1f})",
    f"  label=0 (Kaldi): {n0:,}  (%{yuzde(n0, n_total):.1f})",
]

if n1 / n_total < 0.30 or n1 / n_total > 0.70:
    lines.append("  UYARI: Belirgin sinif dengesizligi! "
                 "class_weight veya SMOTE degerlendirilmeli.")
else:
    lines.append("  Sinif dengesi ML icin makul.")

if "grade_margin" in df.columns:
    lines += [
        "",
        "--- grade_margin (finalgrade - gradepass) ---",
        f"  Gecti label=1: ort={df[df['label']==1]['grade_margin'].mean():.2f}  "
        f"medyan={df[df['label']==1]['grade_margin'].median():.2f}",
        f"  Kaldi label=0: ort={df[df['label']==0]['grade_margin'].mean():.2f}  "
        f"medyan={df[df['label']==0]['grade_margin'].median():.2f}",
        f"  margin=0 (sinirda): {(df['grade_margin']==0).sum()}",
    ]

lines += [
    "",
    "--- Log-Etiket Korelasyonu (Pearson r) ---",
]
for feat, r in sorted(corr_results.items(), key=lambda x: abs(x[1]), reverse=True):
    lines.append(f"  {feat:28s}: r = {r:+.4f}")

lines += [
    "",
    "--- Kurs Bazinda Dagilim ---",
    f"  Toplam kurs              : {len(course_stats):,}",
    f"  Medyan ogrenci/kurs      : {course_stats['n_ogrenci'].median():.0f}",
    f"  Ortalama gecme orani     : %{course_stats['gecme_pct'].mean():.1f}",
    f"  Gecme >%80 olan kurs     : {(course_stats['gecme_pct'] > 80).sum()}",
    f"  Gecme <%20 olan kurs     : {(course_stats['gecme_pct'] < 20).sum()}",
    f"  Kurs (<5 ogrenci)        : {kucuk:,}",
    "",
    "--- gradepass En Yaygin Degerler ---",
]
for val, cnt in gp_dist.items():
    lines.append(f"  {val:6.1f}  ->  {cnt:,}  (%{yuzde(cnt, n_total):.1f})")

lines += [
    "",
    "--- Not Istatistikleri (label bazinda) ---",
]
for feat in ["norm_pct", "n_log", "n_teslim", "performans_skoru"]:
    if feat in df.columns:
        v0 = df[df["label"] == 0][feat]
        v1 = df[df["label"] == 1][feat]
        lines.append(f"  {feat:20s}  label=0 ort={v0.mean():.3f}  "
                     f"label=1 ort={v1.mean():.3f}")

lines += [
    "",
    "--- Grafikler ---",
    f"  {grafik_notu}",
    "",
    "--- Oneri ---",
]
weak_corr = [f for f, r in corr_results.items() if abs(r) < 0.05]
if weak_corr:
    lines.append(f"  Dusuk korelasyonlu (<0.05): {', '.join(weak_corr)}")
    lines.append("  -> Ham sayi yerine log_var / teslim_var gibi varlik bayraklari daha bilgilendirici olabilir.")
strong_corr = [(f, r) for f, r in corr_results.items() if abs(r) >= 0.2]
if strong_corr:
    lines.append(f"  Guclu korelasyonlar (>=0.2): "
                 f"{', '.join(f'{f}={r:+.3f}' for f, r in strong_corr)}")

rapor(CIKTI_DIR, "02_eda_rapor.txt", lines)
print("\n=== TAMAMLANDI ===")
print(f"\n>>> Tum ciktilar: {CIKTI_DIR}")

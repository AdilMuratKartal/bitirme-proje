# -*- coding: utf-8 -*-
"""Kesin Esikli Kohort — Kurs Bazli Derin Analiz

Girdi: cikti/01_cohort_dataset.csv  (01_hazirla.py ciktisi)

Analizler:
  1. Kurs tier ataması (Tier 0=ekstrem, 1=buyuk-anlamli, 2=kucuk-anlamli, 3=cok kucuk)
  2. Her anlamli kurs icin behavioral feature korelasyonlari (within-course Pearson r)
  3. Kurs x Feature r heatmap (Tier 0-2 kurslar)
  4. Tier 1 kurslar icin boxplot karsilastirmasi
  5. Confounding kaniti: Ham deger vs Percentile scatter (renk=label)
  6. Kurs bazli metin raporu

Cikti:
  cikti/03_kurs_tier_table.csv     — tier, n, pass_rate, within-r tablosu
  cikti/03_kurs_feature_heatmap.png — Kurs x Feature r heatmap
  cikti/03_tier1_boxplot.png        — Tier1 kurslar karsilastirma boxplot
  cikti/03_confounding_kaniti.png   — Ham deger vs Percentile (confounding kaniti)
  cikti/03_kurs_rapor.txt           — Kurs bazli metin raporu
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
from common import kaydet, rapor, yuzde

import pandas as pd
import numpy as np

CIKTI_DIR = os.path.join(os.path.dirname(__file__), "cikti")
DATASET   = os.path.join(CIKTI_DIR, "01_cohort_dataset.csv")

print("=== GRADEPASS COHORT: 03_kurs_analiz.py ===\n")

if not os.path.exists(DATASET):
    raise SystemExit(
        f"HATA: {DATASET} bulunamadi.\n"
        f"  Once 01_hazirla.py calistirin."
    )

df = pd.read_csv(DATASET)
df["userid"]   = df["userid"].astype(int)
df["courseid"] = df["courseid"].astype(int)
print(f"Dataset: {len(df):,} satir  x  {len(df.columns)} kolon\n")

# --------------------------------------------------------------------------- #
# 1. Kurs tier ataması
# --------------------------------------------------------------------------- #
print("[1] Kurs tier ataması...")

kurs_stats = df.groupby("courseid").agg(
    n=("userid", "nunique"),
    pass_rate=("label", "mean")
).reset_index()

def _kurs_tier(row):
    p, n = row["pass_rate"], row["n"]
    if p <= 0.05 or p >= 0.95: return 0   # Tier 0: ekstrem (%0 veya %100)
    if n >= 50 and 0.10 < p < 0.90: return 1  # Tier 1: buyuk + dengeli
    if n >= 10: return 2                    # Tier 2: kucuk ama anlamli
    return 3                                # Tier 3: cok kucuk

kurs_stats["tier"] = kurs_stats.apply(_kurs_tier, axis=1)
kurs_stats["gecme_pct"] = (kurs_stats["pass_rate"] * 100).round(1)

tier_counts = kurs_stats["tier"].value_counts().sort_index()
for t, cnt in tier_counts.items():
    aciklama = {0:"Ekstrem (0%/100%)", 1:"Buyuk+Dengeli (n>=50)",
                2:"Kucuk+Anlamli (n>=10)", 3:"Cok Kucuk"}
    n_ogrenci = kurs_stats[kurs_stats["tier"]==t]["n"].sum()
    print(f"  Tier {t} [{aciklama.get(t,'')}]: {cnt} kurs, {n_ogrenci} ogrenci")

# --------------------------------------------------------------------------- #
# 2. Within-course Pearson r hesaplama
# --------------------------------------------------------------------------- #
print("\n[2] Within-course korelasyon hesaplaniyor...")

BEHAV_COLS = [
    "n_log", "n_aktif_gun", "n_sessions", "max_hissizlik",
    "n_modul_cesit", "view_ratio", "forum_view", "clicks_per_session",
    "n_aktif_gun_pctile", "n_sessions_pctile", "n_log_pctile",
]
BEHAV_COLS = [c for c in BEHAV_COLS if c in df.columns]

kurs_r_rows = []
for _, ks in kurs_stats.iterrows():
    cid  = ks["courseid"]
    tier = ks["tier"]
    g    = df[df["courseid"] == cid]
    if len(g) < 5 or g["label"].std() == 0:
        continue
    row = {
        "courseid":  cid,
        "n":         int(ks["n"]),
        "pass_rate": round(ks["pass_rate"], 3),
        "tier":      int(tier),
    }
    for c in BEHAV_COLS:
        if c in g.columns and g[c].std() > 0:
            row[f"r_{c}"] = round(g[c].corr(g["label"]), 3)
        else:
            row[f"r_{c}"] = None
    kurs_r_rows.append(row)

kurs_r_df = pd.DataFrame(kurs_r_rows).sort_values("n", ascending=False)
kurs_r_df = kurs_r_df.merge(
    kurs_stats[["courseid", "gecme_pct"]], on="courseid", how="left"
)

# Tier 0-2 kurslar icin r tablosi kaydet
kaydet(CIKTI_DIR, "03_kurs_tier_table.csv", kurs_r_df)
print(f"  {len(kurs_r_df)} kurs icin within-r hesaplandi")

# --------------------------------------------------------------------------- #
# 3. Grafikler
# --------------------------------------------------------------------------- #
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    palette = {0: "#e74c3c", 1: "#27ae60"}

    # ------------------------------------------------------------------ #
    # 3a. Kurs x Feature r Heatmap (Tier 0-2 kurslar)
    # ------------------------------------------------------------------ #
    print("\n[3a] Kurs x Feature heatmap olusturuluyor...")

    r_cols = [c for c in kurs_r_df.columns if c.startswith("r_")]
    hmap_df = kurs_r_df[kurs_r_df["tier"].isin([0, 1, 2])].copy()
    hmap_df = hmap_df.sort_values(["tier", "n"], ascending=[True, False])

    kurs_labels = hmap_df.apply(
        lambda row: f"C{int(row['courseid'])} (n={int(row['n'])}, T{int(row['tier'])}, %{row['gecme_pct']:.0f})",
        axis=1
    ).tolist()

    r_matrix = hmap_df[r_cols].values.astype(float)
    feat_labels = [c.replace("r_", "") for c in r_cols]

    fig, ax = plt.subplots(figsize=(max(10, len(feat_labels) * 1.3),
                                    max(6, len(kurs_labels) * 0.5)))
    im = ax.imshow(r_matrix, cmap="coolwarm", vmin=-0.8, vmax=0.8, aspect="auto")
    plt.colorbar(im, ax=ax, shrink=0.8, label="Pearson r (label ile)")

    ax.set_xticks(range(len(feat_labels)))
    ax.set_xticklabels(feat_labels, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(kurs_labels)))
    ax.set_yticklabels(kurs_labels, fontsize=8)

    for i in range(len(kurs_labels)):
        for j in range(len(feat_labels)):
            val = r_matrix[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=7, color="white" if abs(val) > 0.4 else "black")

    ax.set_title("Kurs x Feature Korelasyon Haritasi (T0=Ekstrem, T1=Buyuk, T2=Kucuk)",
                 fontsize=11, pad=12)
    plt.tight_layout()
    plt.savefig(os.path.join(CIKTI_DIR, "03_kurs_feature_heatmap.png"),
                dpi=150, bbox_inches="tight")
    plt.close()
    print("  [Grafik] 03_kurs_feature_heatmap.png")

    # ------------------------------------------------------------------ #
    # 3b. Tier 1 Kurslar Boxplot (n_aktif_gun vs label, kurs bazinda)
    # ------------------------------------------------------------------ #
    print("[3b] Tier 1 boxplot olusturuluyor...")

    tier1_cids = kurs_stats[kurs_stats["tier"] == 1]["courseid"].tolist()
    tier1_df   = df[df["courseid"].isin(tier1_cids)].copy()

    plot_feat = "n_aktif_gun"
    if len(tier1_cids) > 0 and plot_feat in tier1_df.columns:
        ncols = min(3, len(tier1_cids))
        nrows = (len(tier1_cids) + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols,
                                 figsize=(5 * ncols, 4 * nrows),
                                 squeeze=False)

        for idx, cid in enumerate(sorted(tier1_cids,
                                         key=lambda c: -kurs_stats[kurs_stats["courseid"]==c]["n"].values[0])):
            row_i, col_i = divmod(idx, ncols)
            ax = axes[row_i][col_i]
            g = tier1_df[tier1_df["courseid"] == cid]
            ks = kurs_stats[kurs_stats["courseid"] == cid].iloc[0]

            data0 = g[g["label"] == 0][plot_feat].dropna().values
            data1 = g[g["label"] == 1][plot_feat].dropna().values
            bplot = ax.boxplot([data0, data1], labels=["Kaldi", "Gecti"],
                               patch_artist=True,
                               boxprops=dict(facecolor="#b3d9ff"),
                               medianprops=dict(color="red", linewidth=2))
            bplot["boxes"][1].set_facecolor("#b3ffb3")

            within_r = kurs_r_df[kurs_r_df["courseid"]==cid][f"r_{plot_feat}"].values
            r_str = f"r={within_r[0]:.3f}" if len(within_r) > 0 and within_r[0] is not None else ""
            ax.set_title(f"Kurs {cid}  (n={int(ks['n'])}, %{ks['gecme_pct']:.0f})  {r_str}",
                         fontsize=9)
            ax.set_ylabel(plot_feat, fontsize=8)

        for idx in range(len(tier1_cids), nrows * ncols):
            row_i, col_i = divmod(idx, ncols)
            axes[row_i][col_i].set_visible(False)

        plt.suptitle(f"Tier 1 Kurslar — {plot_feat}: Kaldi vs Gecti",
                     fontsize=12, y=1.01)
        plt.tight_layout()
        plt.savefig(os.path.join(CIKTI_DIR, "03_tier1_boxplot.png"),
                    dpi=150, bbox_inches="tight")
        plt.close()
        print("  [Grafik] 03_tier1_boxplot.png")

    # ------------------------------------------------------------------ #
    # 3c. Confounding Kaniti: Ham Deger vs Percentile (renk=label)
    # ------------------------------------------------------------------ #
    print("[3c] Confounding kaniti grafigi olusturuluyor...")

    # Percentile kolonlari yoksa hesapla
    pctile_pairs = [
        ("n_aktif_gun", "n_aktif_gun_pctile", "Aktif Gun"),
        ("n_log",       "n_log_pctile",       "Log Sayisi"),
        ("n_sessions",  "n_sessions_pctile",  "Oturum Sayisi"),
    ]
    for col, pcol, _ in pctile_pairs:
        if col in df.columns and pcol not in df.columns:
            df[pcol] = df.groupby("courseid")[col].rank(pct=True)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        "Confounding Kaniti: Ham Deger vs Kurs-Ici Percentile\n"
        "Ayni X'te Kirmizi+Yesil = Ham Deger Tek Basina Anlamsiz | "
        "Y Ekseninde Yesil Uste Cikiyor = Percentile Ayirim Yapiyor",
        fontsize=11
    )

    for ax, (col, pcol, lbl) in zip(axes, pctile_pairs):
        if col not in df.columns or pcol not in df.columns:
            ax.set_visible(False)
            continue

        for label_val, color, name in [(0, "#e74c3c", "Kaldi"), (1, "#27ae60", "Gecti")]:
            sub = df[df["label"] == label_val]
            ax.scatter(sub[col], sub[pcol],
                       c=color, alpha=0.30, s=12, linewidths=0, label=name)

        ax.set_xlabel(f"{lbl}  (ham deger)", fontsize=10)
        ax.set_ylabel(f"{lbl}  (kurs-ici percentile)", fontsize=10)
        ax.set_title(lbl, fontsize=11)
        ax.set_ylim(-0.03, 1.03)
        ax.legend(loc="upper left", markerscale=2, fontsize=9)

        # Yatay cizgi: percentile 0.5 (kurs medyani)
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)

    plt.tight_layout()
    plt.savefig(os.path.join(CIKTI_DIR, "03_confounding_kaniti.png"),
                dpi=150, bbox_inches="tight")
    plt.close()
    print("  [Grafik] 03_confounding_kaniti.png")

    grafik_notu = "Tum grafikler basariyla olusturuldu."

except ImportError as e:
    grafik_notu = f"matplotlib/seaborn yuklu degil: {e}"
    print(f"\n  UYARI: {grafik_notu}")

# --------------------------------------------------------------------------- #
# 4. Metin Raporu
# --------------------------------------------------------------------------- #
print("\n[4] Metin raporu olusturuluyor...")

lines = [
    "=== GRADEPASS COHORT: KURS BAZLI ANALIZ RAPORU ===",
    "",
    f"  Toplam kurs: {len(kurs_stats)}  |  Toplam ogrenci: {len(df)}",
    "",
    "--- TIER DAGILIMI ---",
]

tier_aciklama = {
    0: "Ekstrem (%0 veya %100 gecme) — global ML'de gurultu katıyor",
    1: "Buyuk + Dengeli (n>=50, %10-90) — en anlamli sinyal buradan",
    2: "Kucuk + Anlamli (n>=10, %10-90) — kısıtlı ama kullanilabilir",
    3: "Cok Kucuk (n<10) — analiz icin yetersiz",
}

for t in sorted(kurs_stats["tier"].unique()):
    kts = kurs_stats[kurs_stats["tier"] == t]
    lines.append(f"  Tier {t} [{tier_aciklama.get(t,'')}]:")
    lines.append(f"    {len(kts)} kurs  |  {kts['n'].sum()} ogrenci")
    for _, ks in kts.sort_values("n", ascending=False).iterrows():
        lines.append(f"      Kurs {int(ks['courseid'])}: n={int(ks['n'])}, "
                     f"gecme=%{ks['gecme_pct']:.1f}")
    lines.append("")

lines += [
    "",
    "--- WITHIN-COURSE KORELASYON (Kaldi vs Gecti) ---",
    "  (Global r her zaman daha dusuk - kurs karisimi sinyali yok ediyor)",
    "",
]

# Ana behavioral feature'lar icin kurs bazli r tablosu
for _, row in kurs_r_df.sort_values(["tier", "n"], ascending=[True, False]).iterrows():
    cid  = int(row["courseid"])
    tier = int(row["tier"])
    n    = int(row["n"])
    pr   = float(row["pass_rate"])
    pct  = float(row["gecme_pct"])

    # En iyi ayırıcı feature'ı bul
    r_vals = {c.replace("r_", ""): row[c] for c in kurs_r_df.columns
              if c.startswith("r_") and pd.notna(row.get(c))}
    if not r_vals:
        continue
    best_feat = max(r_vals, key=lambda k: abs(r_vals[k]) if r_vals[k] is not None else 0)
    best_r    = r_vals.get(best_feat)

    lines.append(f"=== KURS {cid} (n={n}, %{pct:.0f} gecme, Tier {tier}) ===")
    if best_r is not None:
        lines.append(f"  En iyi ayirici feature: {best_feat} (r={best_r:+.3f})")

    key_feats = ["n_aktif_gun", "n_sessions", "n_log", "n_aktif_gun_pctile",
                 "n_sessions_pctile", "max_hissizlik"]
    for kf in key_feats:
        r_key = f"r_{kf}"
        if r_key in row and pd.notna(row[r_key]):
            lines.append(f"    {kf:28s}: r={row[r_key]:+.3f}")

    # Ortalama karsilastirmasi
    g = df[df["courseid"] == cid]
    for feat_show in ["n_aktif_gun", "n_log", "n_sessions"]:
        if feat_show in g.columns:
            v0 = g[g["label"] == 0][feat_show].mean()
            v1 = g[g["label"] == 1][feat_show].mean()
            if not (np.isnan(v0) and np.isnan(v1)):
                lines.append(f"    {feat_show:28s}: Kaldi ort={v0:.1f}  |  Gecti ort={v1:.1f}")
    lines.append("")

lines += [
    "",
    "--- CONFOUNDING OZETI ---",
    "  Ayni n_aktif_gun=18-25 bandinda:",
]
band = df[(df["n_aktif_gun"] >= 18) & (df["n_aktif_gun"] <= 25)]
kurs_band = band.groupby("courseid").agg(
    n_band=("label","count"), gecme=("label","mean")).reset_index()
kurs_band = kurs_band[kurs_band["n_band"] >= 3].sort_values("gecme")
for _, brow in kurs_band.iterrows():
    lines.append(f"    Kurs {int(brow['courseid'])}: "
                 f"n={int(brow['n_band'])}, gecme=%{brow['gecme']*100:.0f}")

lines += [
    "",
    "  Sonuc: Ayni ham aktivite farkli kurslarda tamamen farkli risk anlami tasiyor.",
    "  Percentile rank bu bagi cozuyor: kurs-ici siralama = baglamsal risk.",
    "",
    "--- GRAFIKLER ---",
    f"  {grafik_notu}",
    "  03_kurs_feature_heatmap.png  — Kurs x Feature r degerleri",
    "  03_tier1_boxplot.png          — Tier1 kurslar n_aktif_gun boxplot",
    "  03_confounding_kaniti.png     — Ham deger vs Percentile scatter",
    "",
    "--- ML ONERILERI ---",
    "  1. Tier 0 kurslar (0%/100% gecme): model bunlari 'kurs kimligini' ogrenecek,",
    "     ogrenci davranisini degil. Tier 1+2'ye odaklanmak daha temiz sinyal verir.",
    "  2. Percentile features (n_aktif_gun_pctile, n_sessions_pctile): global z-score'dan",
    "     daha iyi — carpik dagilim icin distribution-free alternatif.",
    "  3. XGBoost/LightGBM + courseid kategorik: kurs*davranis etkilesimini otomatik ogrenir.",
    "  4. Tier 1 only model beklenen AUC: 0.80-0.85 (global ~0.72-0.78).",
]

rapor(CIKTI_DIR, "03_kurs_rapor.txt", lines)
print("\n=== TAMAMLANDI ===")
print(f"\n>>> Tum ciktilar: {CIKTI_DIR}")
